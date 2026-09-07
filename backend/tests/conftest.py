"""Shared pytest fixtures for the HealthLab backend tests."""
import pytest


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Set fake AWS credentials and env vars so boto3/moto don't touch real AWS."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("TABLE_NAME", "PatientRecords-test")
    monkeypatch.setenv("TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
    monkeypatch.setenv("BUCKET_NAME", "healthlab-intake-test")
    monkeypatch.setenv("API_ENDPOINT", "https://example.execute-api.us-east-1.amazonaws.com")
    # Disable powertools tracing in tests so it doesn't require the X-Ray SDK/daemon.
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "true")


class LambdaContext:
    function_name = "test"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    aws_request_id = "test-request-id"


@pytest.fixture
def lambda_context():
    return LambdaContext()
