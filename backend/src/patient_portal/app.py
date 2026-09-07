"""Patient-facing API behind the Cognito JWT authorizer.

Two routes:
  POST /intake/upload-url        -> presigned S3 URL for the patient to upload
                                    their intake bundle (intake/<intake_id>.zip)
  GET  /intake/{intake_id}/status -> current onboarding status for that intake

The authenticated patient's identity (Cognito sub) is read from the JWT claims
that API Gateway injects into the request context.
"""
import json
import os
import uuid

import sys

import boto3
from aws_lambda_powertools import Logger, Tracer

# Ensure the sibling fhir module is importable both in Lambda and in tests.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fhir import to_bundle

logger = Logger()
tracer = Tracer()

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = os.environ.get("BUCKET_NAME", "healthlab-intake-dev")
TABLE_NAME = os.environ.get("TABLE_NAME", "PatientRecords-dev")
UPLOAD_URL_EXPIRY = 300  # seconds

table = dynamodb.Table(TABLE_NAME)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _patient_sub(event):
    """Extract the authenticated Cognito subject from the JWT claims."""
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    except (KeyError, TypeError):
        return None


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, context):
    route_key = event.get("routeKey", "")
    patient_sub = _patient_sub(event)

    if not patient_sub:
        return _response(401, {"message": "Unauthorized"})

    if route_key == "POST /intake/upload-url":
        return _create_upload_url(patient_sub)
    if route_key == "GET /intake/{intake_id}/status":
        intake_id = event.get("pathParameters", {}).get("intake_id", "")
        return _get_status(intake_id)
    if route_key == "GET /intake/{intake_id}/fhir":
        intake_id = event.get("pathParameters", {}).get("intake_id", "")
        return _get_fhir(intake_id)

    return _response(404, {"message": "Not found"})


def _create_upload_url(patient_sub):
    intake_id = str(uuid.uuid4())
    key = f"intake/{intake_id}.zip"

    upload_url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET_NAME, "Key": key, "ContentType": "application/zip"},
        ExpiresIn=UPLOAD_URL_EXPIRY,
    )
    logger.info(f"Issued upload URL for intake {intake_id} (patient {patient_sub})")

    return _response(200, {
        "intake_id": intake_id,
        "upload_url": upload_url,
        "expires_in": UPLOAD_URL_EXPIRY,
    })


def _get_status(intake_id):
    if not intake_id:
        return _response(400, {"message": "intake_id is required"})

    item = table.get_item(Key={"INTAKE_ID": intake_id}).get("Item")
    if not item:
        return _response(404, {"message": "Intake not found", "intake_id": intake_id})

    return _response(200, {
        "intake_id": intake_id,
        "status": item.get("STATUS"),
        "identity_verified": item.get("IDENTITY_VERIFIED"),
        "details_match": item.get("DETAILS_MATCH"),
        "eligibility_verified": item.get("ELIGIBILITY_VERIFIED"),
    })


def _get_fhir(intake_id):
    """Return the patient record as a FHIR R4 Bundle (Patient + Coverage)."""
    if not intake_id:
        return _response(400, {"message": "intake_id is required"})

    item = table.get_item(Key={"INTAKE_ID": intake_id}).get("Item")
    if not item:
        return _response(404, {"message": "Intake not found", "intake_id": intake_id})

    bundle = to_bundle(item)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/fhir+json"},
        "body": json.dumps(bundle),
    }
