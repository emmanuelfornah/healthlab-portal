"""Extract fields from the patient's ID document and reconcile them against the
intake form data already stored in DynamoDB.

Uses Amazon Textract AnalyzeID. Mismatches are recorded and trigger an SNS
notification for manual review.
"""
import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

textract = boto3.client("textract")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

TABLE_NAME = os.environ.get("TABLE_NAME", "PatientRecords-dev")
TOPIC_ARN = os.environ.get("TOPIC_ARN")

table = dynamodb.Table(TABLE_NAME)


def normalize_text(text):
    if not text:
        return ""
    return text.lower().strip().replace("  ", " ")


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, context):
    try:
        intake_id = event["intake_id"]
        bucket = event["bucket"]
        id_document_path = event["id_document_path"]

        logger.info(f"Extracting ID document details for {intake_id}")

        record = table.get_item(Key={"INTAKE_ID": intake_id}).get("Item", {})

        textract_response = textract.analyze_id(
            DocumentPages=[{"S3Object": {"Bucket": bucket, "Name": id_document_path}}]
        )

        extracted_data = {}
        for document in textract_response.get("IdentityDocuments", []):
            for field in document.get("IdentityDocumentFields", []):
                field_type = field.get("Type", {}).get("Text", "")
                field_value = field.get("ValueDetection", {}).get("Text", "")
                extracted_data[field_type] = field_value

        logger.info(f"Extracted ID fields: {list(extracted_data.keys())}")

        fields_to_compare = {
            "FIRST_NAME": ["FIRST_NAME", "GIVEN_NAME"],
            "LAST_NAME": ["LAST_NAME", "SURNAME"],
            "DATE_OF_BIRTH": ["DATE_OF_BIRTH", "BIRTH_DATE"],
            "ADDRESS": ["ADDRESS"],
            "STATE_IN_ADDRESS": ["STATE_IN_ADDRESS", "STATE"],
            "CITY_IN_ADDRESS": ["CITY_IN_ADDRESS", "CITY"],
            "ZIP_CODE_IN_ADDRESS": ["ZIP_CODE_IN_ADDRESS", "ZIP_CODE", "POSTAL_CODE"],
        }

        if not extracted_data:
            # Textract found no identity document fields at all - the image
            # isn't a readable ID, so there's nothing to reconcile against.
            # Treating this as a match would let an unreadable/non-ID upload
            # pass the check vacuously (nothing to disagree with).
            logger.warning(f"No ID document fields extracted for {intake_id}")
            mismatched_fields = list(fields_to_compare.keys())
        else:
            mismatched_fields = []
            for record_field, id_fields in fields_to_compare.items():
                record_value = normalize_text(record.get(record_field, ""))

                id_value = ""
                for f in id_fields:
                    if f in extracted_data:
                        id_value = normalize_text(extracted_data[f])
                        break

                if record_value and id_value and record_value != id_value:
                    mismatched_fields.append(record_field)
                    logger.warning(
                        f"Mismatch in {record_field}: form='{record_value}' vs ID='{id_value}'"
                    )

        match = len(mismatched_fields) == 0

        table.update_item(
            Key={"INTAKE_ID": intake_id},
            UpdateExpression="SET DETAILS_MATCH = :m",
            ExpressionAttributeValues={":m": match},
        )

        if not match:
            sns.publish(
                TopicArn=TOPIC_ARN,
                Subject="Onboarding Review: Intake Details Mismatch",
                Message=json.dumps({
                    "intake_id": intake_id,
                    "validation_type": "DETAILS_MATCH",
                    "status": "FAILED",
                    "mismatched_fields": mismatched_fields,
                }),
            )
            logger.info(f"Sent details review notification for {intake_id}")

        return {"intake_id": intake_id, "match": match, "mismatched_fields": mismatched_fields}

    except Exception as e:
        logger.error(f"Error extracting details: {str(e)}")
        try:
            table.update_item(
                Key={"INTAKE_ID": event["intake_id"]},
                UpdateExpression="SET DETAILS_MATCH = :m",
                ExpressionAttributeValues={":m": False},
            )
        except Exception:
            pass
        raise
