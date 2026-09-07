"""Unzip a patient intake bundle uploaded to S3 and organize its contents.

The intake bundle is a ZIP containing exactly three files:
  - <intake_id>_intake.csv   patient-provided intake form data
  - <intake_id>_id.png       photo of a government ID document
  - <intake_id>_selfie.png   patient selfie for identity verification
"""
import io
import zipfile

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

s3_client = boto3.client("s3")


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, context):
    try:
        # Support both EventBridge S3 events and direct invocation
        bucket = event.get("detail", {}).get("bucket", {}).get("name") or event.get("bucket")
        key = event.get("detail", {}).get("object", {}).get("key") or event.get("key")

        logger.info(f"Processing intake bundle: s3://{bucket}/{key}")

        # Derive intake_id from the object key (intake/<intake_id>.zip)
        filename = key.split("/")[-1]
        intake_id = filename.replace(".zip", "")

        zip_obj = s3_client.get_object(Bucket=bucket, Key=key)
        zip_content = zip_obj["Body"].read()

        extracted_files = {}
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_ref:
            file_list = zip_ref.namelist()

            if len(file_list) != 3:
                raise ValueError(f"Expected 3 files in intake bundle, found {len(file_list)}")

            for file_name in file_list:
                file_data = zip_ref.read(file_name)

                if file_name.endswith("_intake.csv"):
                    file_type = "intake_form"
                elif file_name.endswith("_id.png"):
                    file_type = "id_document"
                elif file_name.endswith("_selfie.png"):
                    file_type = "selfie"
                else:
                    raise ValueError(f"Unexpected file in intake bundle: {file_name}")

                extracted_key = f"extracted/{intake_id}/{file_name}"
                s3_client.put_object(Bucket=bucket, Key=extracted_key, Body=file_data)
                extracted_files[file_type] = extracted_key
                logger.info(f"Extracted {file_type}: {extracted_key}")

        result = {
            "intake_id": intake_id,
            "bucket": bucket,
            "intake_form_path": extracted_files["intake_form"],
            "id_document_path": extracted_files["id_document"],
            "selfie_path": extracted_files["selfie"],
        }
        logger.info(f"Successfully extracted intake bundle for {intake_id}")
        return result

    except Exception as e:
        logger.error(f"Error processing intake bundle: {str(e)}")
        raise
