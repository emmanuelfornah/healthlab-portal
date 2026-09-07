"""Unit tests for the validate_eligibility mock API Lambda."""
import json

from tests.helpers import load_handler


def _invoke(body, ctx):
    handler = load_handler("validate_eligibility")
    return handler.lambda_handler({"body": json.dumps(body)}, ctx)


def test_eligible_for_valid_member_id(lambda_context):
    response = _invoke({"member_id": "M123456"}, lambda_context)
    assert response["statusCode"] == 200
    payload = json.loads(response["body"])
    assert payload["eligible"] is True


def test_not_eligible_for_short_member_id(lambda_context):
    response = _invoke({"member_id": "123"}, lambda_context)
    payload = json.loads(response["body"])
    assert payload["eligible"] is False


def test_not_eligible_for_missing_member_id(lambda_context):
    response = _invoke({}, lambda_context)
    payload = json.loads(response["body"])
    assert payload["eligible"] is False


def test_handles_dict_body_directly(lambda_context):
    handler = load_handler("validate_eligibility")
    response = handler.lambda_handler({"body": {"member_id": "MEMBER99"}}, lambda_context)
    assert json.loads(response["body"])["eligible"] is True
