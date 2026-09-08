"""Unit tests for the extract_details Lambda (Textract AnalyzeID reconciliation)."""
from unittest.mock import patch

import boto3
from moto import mock_aws

from tests.helpers import load_handler

BUCKET = "healthlab-intake-test"
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


def _textract_response(**fields):
    return {
        "IdentityDocuments": [
            {
                "IdentityDocumentFields": [
                    {"Type": {"Text": k}, "ValueDetection": {"Text": v}}
                    for k, v in fields.items()
                ]
            }
        ]
    }


def _event(intake_id):
    return {
        "intake_id": intake_id,
        "bucket": BUCKET,
        "id_document_path": f"extracted/{intake_id}/{intake_id}_id.png",
    }


@mock_aws
def test_match_when_id_fields_agree_with_intake_form(lambda_context):
    table = _create_table()
    table.put_item(Item={"INTAKE_ID": "abc", "FIRST_NAME": "Jane", "LAST_NAME": "Doe"})

    handler = load_handler("extract_details")
    with patch.object(handler.textract, "analyze_id",
                       return_value=_textract_response(FIRST_NAME="Jane", LAST_NAME="Doe")):
        result = handler.lambda_handler(_event("abc"), lambda_context)

    assert result["match"] is True
    assert result["mismatched_fields"] == []
    assert table.get_item(Key={"INTAKE_ID": "abc"})["Item"]["DETAILS_MATCH"] is True


@mock_aws
def test_flags_mismatch_and_notifies(lambda_context):
    table = _create_table()
    table.put_item(Item={"INTAKE_ID": "abc", "FIRST_NAME": "Jane", "LAST_NAME": "Doe"})

    handler = load_handler("extract_details")
    with patch.object(handler.textract, "analyze_id",
                       return_value=_textract_response(FIRST_NAME="John", LAST_NAME="Doe")), \
         patch.object(handler.sns, "publish") as mock_publish:
        result = handler.lambda_handler(_event("abc"), lambda_context)

    assert result["match"] is False
    assert result["mismatched_fields"] == ["FIRST_NAME"]
    mock_publish.assert_called_once()
    assert table.get_item(Key={"INTAKE_ID": "abc"})["Item"]["DETAILS_MATCH"] is False


@mock_aws
def test_no_match_when_textract_extracts_nothing(lambda_context):
    """Regression test: an unreadable/non-ID image must not pass vacuously.

    Previously, if Textract found zero fields (blank image, wrong document
    type, adversarial upload), every comparison was skipped for lack of an
    id_value to compare - so mismatched_fields stayed empty and the check
    reported a match by default instead of failing safely.
    """
    table = _create_table()
    table.put_item(Item={"INTAKE_ID": "abc", "FIRST_NAME": "Jane", "LAST_NAME": "Doe"})

    handler = load_handler("extract_details")
    with patch.object(handler.textract, "analyze_id",
                       return_value={"IdentityDocuments": [{"IdentityDocumentFields": []}]}), \
         patch.object(handler.sns, "publish") as mock_publish:
        result = handler.lambda_handler(_event("abc"), lambda_context)

    assert result["match"] is False
    mock_publish.assert_called_once()
    assert table.get_item(Key={"INTAKE_ID": "abc"})["Item"]["DETAILS_MATCH"] is False


@mock_aws
def test_missing_id_field_is_not_treated_as_mismatch(lambda_context):
    """A field Textract couldn't read (but others were extracted) shouldn't
    fail the check on its own - only fields present on both sides that
    actually disagree count as a mismatch."""
    table = _create_table()
    table.put_item(Item={"INTAKE_ID": "abc", "FIRST_NAME": "Jane", "LAST_NAME": "Doe"})

    handler = load_handler("extract_details")
    with patch.object(handler.textract, "analyze_id",
                       return_value=_textract_response(FIRST_NAME="Jane")):
        result = handler.lambda_handler(_event("abc"), lambda_context)

    assert result["match"] is True
