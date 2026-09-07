"""Verify patient identity by comparing the selfie against the ID document photo.

Uses Amazon Rekognition CompareFaces. On failure, records the result and
publishes an SNS notification for the care team to review.
"""
import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

rekognition = boto3.client("rekognition")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

TABLE_NAME = os.environ.get("TABLE_NAME", "PatientRecords-dev")
TOPIC_ARN = os.environ.get("TOPIC_ARN")
SIMILARITY_THRESHOLD = 80

table = dynamodb.Table(TABLE_NAME)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, context):
    try:
        intake_id = event["intake_id"]
        bucket = event["bucket"]
        id_document_path = event["id_document_path"]
        selfie_path = event["selfie_path"]

        logger.info(f"Verifying identity for {intake_id}")

        response = rekognition.compare_faces(
            SourceImage={"S3Object": {"Bucket": bucket, "Name": id_document_path}},
            TargetImage={"S3Object": {"Bucket": bucket, "Name": selfie_path}},
            SimilarityThreshold=SIMILARITY_THRESHOLD,
        )

        verified = False
        similarity = 0

        if response.get("FaceMatches"):
            similarity = response["FaceMatches"][0]["Similarity"]
            verified = similarity >= SIMILARITY_THRESHOLD
            logger.info(f"Identity verified: {verified}, similarity: {similarity}")
        else:
            logger.warning(f"No face matches found for {intake_id}")

        table.update_item(
            Key={"INTAKE_ID": intake_id},
            UpdateExpression="SET IDENTITY_VERIFIED = :v",
            ExpressionAttributeValues={":v": verified},
        )

        if not verified:
            sns.publish(
                TopicArn=TOPIC_ARN,
                Subject="Onboarding Review: Identity Verification Failed",
                Message=json.dumps({
                    "intake_id": intake_id,
                    "validation_type": "IDENTITY_VERIFIED",
                    "status": "FAILED",
                    "similarity": similarity,
                    "threshold": SIMILARITY_THRESHOLD,
                }),
            )
            logger.info(f"Sent identity review notification for {intake_id}")

        return {"intake_id": intake_id, "similarity": similarity, "verified": verified}

    except Exception as e:
        logger.error(f"Error verifying identity: {str(e)}")
        try:
            table.update_item(
                Key={"INTAKE_ID": event["intake_id"]},
                UpdateExpression="SET IDENTITY_VERIFIED = :v",
                ExpressionAttributeValues={":v": False},
            )
        except Exception:
            pass
        raise
