"""Unit tests for the unzip Lambda."""
import io
import zipfile

import boto3
import pytest
from moto import mock_aws

from tests.helpers import load_handler

BUCKET = "healthlab-intake-test"


def _make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    buffer.seek(0)
    return buffer.read()


@mock_aws
def test_unzip_extracts_three_files(lambda_context):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)

    zip_bytes = _make_zip({
        "abc123_intake.csv": "MEMBER_ID,FIRST_NAME\nM123456,Jane\n",
        "abc123_id.png": b"\x89PNG-fake-id",
        "abc123_selfie.png": b"\x89PNG-fake-selfie",
    })
    s3.put_object(Bucket=BUCKET, Key="intake/abc123.zip", Body=zip_bytes)

    unzip = load_handler("unzip")
    result = unzip.lambda_handler({"bucket": BUCKET, "key": "intake/abc123.zip"}, lambda_context)

    assert result["intake_id"] == "abc123"
    assert result["intake_form_path"] == "extracted/abc123/abc123_intake.csv"
    assert result["id_document_path"] == "extracted/abc123/abc123_id.png"
    assert result["selfie_path"] == "extracted/abc123/abc123_selfie.png"

    listing = s3.list_objects_v2(Bucket=BUCKET, Prefix="extracted/abc123/")
    assert listing["KeyCount"] == 3


@mock_aws
def test_unzip_rejects_wrong_file_count(lambda_context):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)

    zip_bytes = _make_zip({"only_intake.csv": "x"})
    s3.put_object(Bucket=BUCKET, Key="intake/bad.zip", Body=zip_bytes)

    unzip = load_handler("unzip")
    with pytest.raises(ValueError):
        unzip.lambda_handler({"bucket": BUCKET, "key": "intake/bad.zip"}, lambda_context)
