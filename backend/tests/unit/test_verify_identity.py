"""Unit tests for the verify_identity Lambda (Rekognition CompareFaces)."""
from unittest.mock import patch

import boto3
import pytest
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


def _event(intake_id="abc"):
    return {
        "intake_id": intake_id,
        "bucket": BUCKET,
        "id_document_path": f"extracted/{intake_id}/{intake_id}_id.png",
        "selfie_path": f"extracted/{intake_id}/{intake_id}_selfie.png",
    }


@mock_aws
def test_verified_true_above_threshold(lambda_context):
    table = _create_table()
    table.put_item(Item={"INTAKE_ID": "abc"})

    handler = load_handler("verify_identity")
    with patch.object(handler.rekognition, "compare_faces",
                       return_value={"FaceMatches": [{"Similarity": 97.5}]}):
        result = handler.lambda_handler(_event(), lambda_context)

    assert result["verified"] is True
    assert result["similarity"] == 97.5
    assert table.get_item(Key={"INTAKE_ID": "abc"})["Item"]["IDENTITY_VERIFIED"] is True


@mock_aws
def test_not_verified_and_notifies_when_no_face_matches(lambda_context):
    table = _create_table()
    table.put_item(Item={"INTAKE_ID": "abc"})

    handler = load_handler("verify_identity")
    with patch.object(handler.rekognition, "compare_faces", return_value={"FaceMatches": []}), \
         patch.object(handler.sns, "publish") as mock_publish:
        result = handler.lambda_handler(_event(), lambda_context)

    assert result["verified"] is False
    assert result["similarity"] == 0
    mock_publish.assert_called_once()
    assert table.get_item(Key={"INTAKE_ID": "abc"})["Item"]["IDENTITY_VERIFIED"] is False


@mock_aws
def test_not_verified_when_similarity_below_threshold(lambda_context):
    table = _create_table()
    table.put_item(Item={"INTAKE_ID": "abc"})

    handler = load_handler("verify_identity")
    with patch.object(handler.rekognition, "compare_faces",
                       return_value={"FaceMatches": [{"Similarity": 42.0}]}), \
         patch.object(handler.sns, "publish") as mock_publish:
        result = handler.lambda_handler(_event(), lambda_context)

    assert result["verified"] is False
    mock_publish.assert_called_once()


@mock_aws
def test_exception_marks_unverified_and_reraises(lambda_context):
    table = _create_table()
    table.put_item(Item={"INTAKE_ID": "abc", "IDENTITY_VERIFIED": None})

    handler = load_handler("verify_identity")
    with patch.object(handler.rekognition, "compare_faces", side_effect=RuntimeError("Rekognition unavailable")):
        with pytest.raises(RuntimeError):
            handler.lambda_handler(_event(), lambda_context)

    assert table.get_item(Key={"INTAKE_ID": "abc"})["Item"]["IDENTITY_VERIFIED"] is False
