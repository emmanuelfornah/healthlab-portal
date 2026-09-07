"""Property-based tests for the eligibility mock using Hypothesis.

Verifies invariants that must hold for every input, not just chosen examples.
"""
import json
import os

os.environ.setdefault("POWERTOOLS_TRACE_DISABLED", "true")

from hypothesis import given, settings, strategies as st

from tests.helpers import load_handler


class _Ctx:
    function_name = "test"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    aws_request_id = "test-request-id"


# Load the handler once; re-importing per Hypothesis example is slow and
# unnecessary (the handler is stateless).
_HANDLER = load_handler("validate_eligibility")
_CTX = _Ctx()


def _eligible(member_id):
    response = _HANDLER.lambda_handler(
        {"body": json.dumps({"member_id": member_id})}, _CTX
    )
    assert response["statusCode"] == 200
    return json.loads(response["body"])["eligible"]


@settings(deadline=None)
@given(member_id=st.text(min_size=6, max_size=40).filter(lambda s: len(s.strip()) >= 6))
def test_wellformed_ids_are_eligible(member_id):
    # Invariant: any member_id whose trimmed length is >= 6 is eligible.
    assert _eligible(member_id) is True


@settings(deadline=None)
@given(member_id=st.text(max_size=5))
def test_short_ids_are_never_eligible(member_id):
    # Invariant: a member_id with trimmed length < 6 is never eligible.
    assert _eligible(member_id) is False


@settings(deadline=None)
@given(member_id=st.text())
def test_response_is_always_boolean(member_id):
    # Invariant: eligibility is always a strict boolean, never None/other.
    assert isinstance(_eligible(member_id), bool)
