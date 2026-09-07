"""Parse the patient intake form (CSV) and store the patient record in DynamoDB."""
import csv
import io
import os
from datetime import datetime, timezone

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ.get("TABLE_NAME", "PatientRecords-dev")
table = dynamodb.Table(TABLE_NAME)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, context):
    try:
        intake_id = event["intake_id"]
        bucket = event["bucket"]
        intake_form_path = event["intake_form_path"]

        logger.info(f"Processing intake form for {intake_id}: s3://{bucket}/{intake_form_path}")

        csv_obj = s3_client.get_object(Bucket=bucket, Key=intake_form_path)
        csv_content = csv_obj["Body"].read().decode("utf-8")

        reader = csv.DictReader(io.StringIO(csv_content))
        patient_data = next(reader)

        item = {
            "INTAKE_ID": intake_id,
            "MEMBER_ID": patient_data.get("MEMBER_ID", ""),
            "FIRST_NAME": patient_data.get("FIRST_NAME", ""),
            "LAST_NAME": patient_data.get("LAST_NAME", ""),
            "DATE_OF_BIRTH": patient_data.get("DATE_OF_BIRTH", ""),
            "ADDRESS": patient_data.get("ADDRESS", ""),
            "STATE_IN_ADDRESS": patient_data.get("STATE_IN_ADDRESS", ""),
            "CITY_IN_ADDRESS": patient_data.get("CITY_IN_ADDRESS", ""),
            "ZIP_CODE_IN_ADDRESS": patient_data.get("ZIP_CODE_IN_ADDRESS", ""),
            "INSURANCE_PROVIDER": patient_data.get("INSURANCE_PROVIDER", ""),
            "IDENTITY_VERIFIED": None,
            "DETAILS_MATCH": None,
            "ELIGIBILITY_VERIFIED": None,
            "STATUS": "PENDING",
            "CREATED_AT": datetime.now(timezone.utc).isoformat(),
        }

        table.put_item(Item=item)
        logger.info(f"Stored patient record for {intake_id}")

        return {
            "intake_id": intake_id,
            "member_id": item["MEMBER_ID"],
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Error writing patient record: {str(e)}")
        raise
