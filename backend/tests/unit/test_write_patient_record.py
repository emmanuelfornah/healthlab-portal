"""Unit tests for the write_patient_record Lambda."""
import boto3
from moto import mock_aws

from tests.helpers import load_handler

BUCKET = "healthlab-intake-test"
TABLE = "PatientRecords-test"


def _setup(s3, dynamodb):
    s3.create_bucket(Bucket=BUCKET)
    dynamodb.create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "INTAKE_ID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "INTAKE_ID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


@mock_aws
def test_write_patient_record_persists_item(lambda_context):
    s3 = boto3.client("s3", region_name="us-east-1")
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    _setup(s3, dynamodb)

    csv_data = (
        "MEMBER_ID,FIRST_NAME,LAST_NAME,DATE_OF_BIRTH,INSURANCE_PROVIDER\n"
        "M123456,Jane,Doe,1990-01-01,BlueCross\n"
    )
    s3.put_object(Bucket=BUCKET, Key="extracted/abc123/abc123_intake.csv", Body=csv_data)

    handler = load_handler("write_patient_record")
    event = {
        "intake_id": "abc123",
        "bucket": BUCKET,
        "intake_form_path": "extracted/abc123/abc123_intake.csv",
    }
    result = handler.lambda_handler(event, lambda_context)

    assert result["intake_id"] == "abc123"
    assert result["member_id"] == "M123456"

    resource = boto3.resource("dynamodb", region_name="us-east-1")
    item = resource.Table(TABLE).get_item(Key={"INTAKE_ID": "abc123"})["Item"]
    assert item["FIRST_NAME"] == "Jane"
    assert item["STATUS"] == "PENDING"
    assert item["IDENTITY_VERIFIED"] is None
