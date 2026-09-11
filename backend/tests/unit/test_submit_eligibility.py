"""Unit tests for the submit_eligibility Lambda (SQS-triggered eligibility
check and the overall onboarding STATUS it resolves)."""
import json
from unittest.mock import patch

import boto3
from moto import mock_aws

from tests.helpers import load_handler

TABLE = "PatientRecords-test"


def _create_table():
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "INTAKE_ID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "INTAKE_ID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return boto3.resource("dynamodb", region_name="us-east-1").Table(TABLE)


def _sqs_event(intake_id, member_id):
    return {
        "Records": [
            {"body": json.dumps({"intake_id": intake_id, "member_id": member_id})}
        ]
    }


@mock_aws
def test_approved_when_all_three_checks_pass(lambda_context):
    table = _create_table()
    table.put_item(Item={
        "INTAKE_ID": "abc", "IDENTITY_VERIFIED": True, "DETAILS_MATCH": True,
    })

    handler = load_handler("submit_eligibility")
    with patch.object(handler, "_call_eligibility_api", return_value={"eligible": True}):
        handler.lambda_handler(_sqs_event("abc", "M1"), lambda_context)

    item = table.get_item(Key={"INTAKE_ID": "abc"})["Item"]
    assert item["ELIGIBILITY_VERIFIED"] is True
    assert item["STATUS"] == "APPROVED"


@mock_aws
def test_needs_review_when_details_already_failed(lambda_context):
    """Eligibility can still come back true on its own, but the overall
    STATUS must not read as approved if an earlier check already failed -
    that's the exact confusing state this rollup exists to prevent."""
    table = _create_table()
    table.put_item(Item={
        "INTAKE_ID": "abc", "IDENTITY_VERIFIED": True, "DETAILS_MATCH": False,
    })

    handler = load_handler("submit_eligibility")
    with patch.object(handler, "_call_eligibility_api", return_value={"eligible": True}):
        handler.lambda_handler(_sqs_event("abc", "M1"), lambda_context)

    item = table.get_item(Key={"INTAKE_ID": "abc"})["Item"]
    assert item["ELIGIBILITY_VERIFIED"] is True
    assert item["STATUS"] == "NEEDS_REVIEW"


@mock_aws
def test_needs_review_and_notifies_when_not_eligible(lambda_context):
    table = _create_table()
    table.put_item(Item={
        "INTAKE_ID": "abc", "IDENTITY_VERIFIED": True, "DETAILS_MATCH": True,
    })

    handler = load_handler("submit_eligibility")
    with patch.object(handler, "_call_eligibility_api",
                       return_value={"eligible": False, "message": "no coverage"}), \
         patch.object(handler.sns, "publish") as mock_publish:
        handler.lambda_handler(_sqs_event("abc", "M1"), lambda_context)

    item = table.get_item(Key={"INTAKE_ID": "abc"})["Item"]
    assert item["ELIGIBILITY_VERIFIED"] is False
    assert item["STATUS"] == "NEEDS_REVIEW"
    mock_publish.assert_called_once()
