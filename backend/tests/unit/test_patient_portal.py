"""Unit tests for the patient_portal Lambda (Cognito-protected API)."""
import json

import boto3
from moto import mock_aws

from tests.helpers import load_handler

BUCKET = "healthlab-intake-test"
TABLE = "PatientRecords-test"


def _auth_event(route_key, path_params=None):
    return {
        "routeKey": route_key,
        "pathParameters": path_params or {},
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": "patient-abc-123"}}}
        },
    }


def test_rejects_unauthenticated_request(lambda_context):
    handler = load_handler("patient_portal")
    event = {"routeKey": "POST /intake/upload-url", "requestContext": {}}
    response = handler.lambda_handler(event, lambda_context)
    assert response["statusCode"] == 401


@mock_aws
def test_create_upload_url_returns_presigned_url(lambda_context):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)

    handler = load_handler("patient_portal")
    response = handler.lambda_handler(_auth_event("POST /intake/upload-url"), lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "intake_id" in body
    assert body["upload_url"].startswith("https://")
    assert body["expires_in"] == 300


@mock_aws
def test_get_status_returns_record(lambda_context):
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "INTAKE_ID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "INTAKE_ID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    resource = boto3.resource("dynamodb", region_name="us-east-1")
    resource.Table(TABLE).put_item(Item={
        "INTAKE_ID": "int-1",
        "STATUS": "PENDING",
        "IDENTITY_VERIFIED": True,
        "DETAILS_MATCH": True,
        "ELIGIBILITY_VERIFIED": None,
    })

    handler = load_handler("patient_portal")
    event = _auth_event("GET /intake/{intake_id}/status", {"intake_id": "int-1"})
    response = handler.lambda_handler(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "PENDING"
    assert body["identity_verified"] is True


@mock_aws
def test_get_fhir_returns_bundle(lambda_context):
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "INTAKE_ID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "INTAKE_ID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    resource = boto3.resource("dynamodb", region_name="us-east-1")
    resource.Table(TABLE).put_item(Item={
        "INTAKE_ID": "int-1",
        "MEMBER_ID": "M999999",
        "FIRST_NAME": "Ada",
        "LAST_NAME": "Lovelace",
        "ELIGIBILITY_VERIFIED": True,
    })

    handler = load_handler("patient_portal")
    event = _auth_event("GET /intake/{intake_id}/fhir", {"intake_id": "int-1"})
    response = handler.lambda_handler(event, lambda_context)

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/fhir+json"
    bundle = json.loads(response["body"])
    assert bundle["resourceType"] == "Bundle"
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Patient" in types and "Coverage" in types


@mock_aws
def test_get_status_404_when_missing(lambda_context):
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "INTAKE_ID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "INTAKE_ID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    handler = load_handler("patient_portal")
    event = _auth_event("GET /intake/{intake_id}/status", {"intake_id": "missing"})
    response = handler.lambda_handler(event, lambda_context)
    assert response["statusCode"] == 404
