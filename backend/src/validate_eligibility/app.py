"""Mock insurance eligibility API.

Stands in for a real payer eligibility service (e.g. an X12 270/271 clearinghouse
or a provider API). Returns eligible for any member_id that is present and
well-formed; this is a deterministic mock for demonstration purposes only.
"""
import json

from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()


def _cors_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, context):
    try:
        raw_body = event.get("body", {})
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body

        member_id = (body or {}).get("member_id", "")
        logger.info(f"Validating eligibility for member: {member_id}")

        # Mock rule: a member_id is eligible when present and at least 6 chars.
        # In production this would call a real payer eligibility service.
        eligible = bool(member_id) and len(str(member_id).strip()) >= 6

        return _cors_response(200, {
            "eligible": eligible,
            "member_id": member_id,
            "message": "Eligible" if eligible else "Member not eligible or ID invalid",
        })

    except Exception as e:
        logger.error(f"Error validating eligibility: {str(e)}")
        return _cors_response(500, {"eligible": False, "message": f"Validation error: {str(e)}"})
