"""Consume eligibility-check requests from SQS and call the eligibility API.

Triggered by the EligibilityQueue. Calls the (mock) eligibility service and
records the result on the patient record. Uses urllib from the standard library
so no third-party dependency needs to be bundled.
"""
import json
import os
import urllib.request

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

TABLE_NAME = os.environ.get("TABLE_NAME", "PatientRecords-dev")
TOPIC_ARN = os.environ.get("TOPIC_ARN")
API_ENDPOINT = os.environ.get("API_ENDPOINT")

table = dynamodb.Table(TABLE_NAME)


def _call_eligibility_api(member_id):
    url = f"{API_ENDPOINT}/eligibility"
    payload = json.dumps({"member_id": member_id}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, context):
    try:
        for record in event["Records"]:
            message = json.loads(record["body"])
            intake_id = message["intake_id"]
            member_id = message["member_id"]

            logger.info(f"Checking eligibility for {intake_id}: member {member_id}")

            api_result = _call_eligibility_api(member_id)
            eligible = api_result.get("eligible", False)
            logger.info(f"Eligibility result for {intake_id}: {eligible}")

            table.update_item(
                Key={"INTAKE_ID": intake_id},
                UpdateExpression="SET ELIGIBILITY_VERIFIED = :e",
                ExpressionAttributeValues={":e": eligible},
            )

            if not eligible:
                sns.publish(
                    TopicArn=TOPIC_ARN,
                    Subject="Onboarding Review: Insurance Eligibility Failed",
                    Message=json.dumps({
                        "intake_id": intake_id,
                        "validation_type": "ELIGIBILITY_VERIFIED",
                        "status": "FAILED",
                        "member_id": member_id,
                        "api_message": api_result.get("message", ""),
                    }),
                )
                logger.info(f"Sent eligibility review notification for {intake_id}")

        return {"statusCode": 200, "body": json.dumps({"message": "Eligibility check completed"})}

    except Exception as e:
        logger.error(f"Error checking eligibility: {str(e)}")
        raise
