"""Unit tests for the FHIR R4 mapping layer."""
import importlib.util
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FHIR_PATH = os.path.join(BACKEND_DIR, "src", "patient_portal", "fhir.py")

_spec = importlib.util.spec_from_file_location("fhir_module", FHIR_PATH)
fhir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fhir)


SAMPLE = {
    "INTAKE_ID": "int-123",
    "MEMBER_ID": "M123456",
    "FIRST_NAME": "Jane",
    "LAST_NAME": "Doe",
    "DATE_OF_BIRTH": "1990-01-01",
    "ADDRESS": "1 Main St",
    "CITY_IN_ADDRESS": "Dallas",
    "STATE_IN_ADDRESS": "TX",
    "ZIP_CODE_IN_ADDRESS": "75001",
    "INSURANCE_PROVIDER": "BlueCross",
    "ELIGIBILITY_VERIFIED": True,
}


def test_patient_resource_structure():
    p = fhir.to_patient_resource(SAMPLE)
    assert p["resourceType"] == "Patient"
    assert p["id"] == "int-123"
    assert p["name"][0]["family"] == "Doe"
    assert p["name"][0]["given"] == ["Jane"]
    assert p["birthDate"] == "1990-01-01"
    assert p["address"][0]["state"] == "TX"
    assert p["address"][0]["postalCode"] == "75001"
    # member id and intake id both present as identifiers
    values = [i["value"] for i in p["identifier"]]
    assert "M123456" in values
    assert "int-123" in values


def test_coverage_status_maps_from_eligibility():
    assert fhir.to_coverage_resource({**SAMPLE, "ELIGIBILITY_VERIFIED": True})["status"] == "active"
    assert fhir.to_coverage_resource({**SAMPLE, "ELIGIBILITY_VERIFIED": False})["status"] == "cancelled"
    assert fhir.to_coverage_resource({**SAMPLE, "ELIGIBILITY_VERIFIED": None})["status"] == "draft"


def test_coverage_references_patient():
    c = fhir.to_coverage_resource(SAMPLE)
    assert c["resourceType"] == "Coverage"
    assert c["beneficiary"]["reference"] == "Patient/int-123"
    assert c["subscriberId"] == "M123456"
    assert c["payor"][0]["display"] == "BlueCross"


def test_bundle_contains_patient_and_coverage():
    bundle = fhir.to_bundle(SAMPLE)
    assert bundle["resourceType"] == "Bundle"
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Patient" in types
    assert "Coverage" in types


def test_handles_minimal_record():
    minimal = {"INTAKE_ID": "int-min"}
    p = fhir.to_patient_resource(minimal)
    assert p["resourceType"] == "Patient"
    assert p["id"] == "int-min"
    # no address block when no address fields present
    assert "address" not in p
    c = fhir.to_coverage_resource(minimal)
    assert c["status"] == "draft"
