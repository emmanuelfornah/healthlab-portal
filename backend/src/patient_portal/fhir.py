"""Map internal patient records to FHIR R4 resources.

We model the patient onboarding data using the HL7 FHIR R4 standard so the API
speaks the same language as real EHRs and payer systems:

  - Patient   (http://hl7.org/fhir/R4/patient.html)
  - Coverage  (http://hl7.org/fhir/R4/coverage.html)

This is a lightweight, dependency-free mapping of the fields this project
captures; it is not a full FHIR server implementation.
"""

FHIR_R4 = "4.0.1"


def to_patient_resource(record):
    """Build a FHIR R4 Patient resource from an internal patient record dict."""
    intake_id = record.get("INTAKE_ID", "")

    identifiers = []
    if record.get("MEMBER_ID"):
        identifiers.append({
            "system": "https://healthlabportal.com/fhir/member-id",
            "value": record["MEMBER_ID"],
        })
    identifiers.append({
        "system": "https://healthlabportal.com/fhir/intake-id",
        "value": intake_id,
    })

    resource = {
        "resourceType": "Patient",
        "id": intake_id,
        "meta": {"profile": ["http://hl7.org/fhir/StructureDefinition/Patient"]},
        "identifier": identifiers,
        "active": True,
        "name": [{
            "use": "official",
            "family": record.get("LAST_NAME", ""),
            "given": [record.get("FIRST_NAME", "")] if record.get("FIRST_NAME") else [],
        }],
    }

    if record.get("DATE_OF_BIRTH"):
        resource["birthDate"] = record["DATE_OF_BIRTH"]

    address = {}
    if record.get("ADDRESS"):
        address["line"] = [record["ADDRESS"]]
    if record.get("CITY_IN_ADDRESS"):
        address["city"] = record["CITY_IN_ADDRESS"]
    if record.get("STATE_IN_ADDRESS"):
        address["state"] = record["STATE_IN_ADDRESS"]
    if record.get("ZIP_CODE_IN_ADDRESS"):
        address["postalCode"] = record["ZIP_CODE_IN_ADDRESS"]
    if address:
        address["use"] = "home"
        resource["address"] = [address]

    return resource


def to_coverage_resource(record):
    """Build a FHIR R4 Coverage resource representing the patient's insurance."""
    intake_id = record.get("INTAKE_ID", "")
    eligibility = record.get("ELIGIBILITY_VERIFIED")

    # FHIR Coverage.status is a required code; map our verification result.
    if eligibility is True:
        status = "active"
    elif eligibility is False:
        status = "cancelled"
    else:
        status = "draft"  # not yet verified

    resource = {
        "resourceType": "Coverage",
        "id": f"{intake_id}-coverage",
        "meta": {"profile": ["http://hl7.org/fhir/StructureDefinition/Coverage"]},
        "status": status,
        "beneficiary": {"reference": f"Patient/{intake_id}"},
    }

    if record.get("MEMBER_ID"):
        resource["subscriberId"] = record["MEMBER_ID"]
    if record.get("INSURANCE_PROVIDER"):
        resource["payor"] = [{"display": record["INSURANCE_PROVIDER"]}]

    return resource


def to_bundle(record):
    """Wrap the Patient and Coverage resources in a FHIR searchset Bundle."""
    resources = [to_patient_resource(record), to_coverage_resource(record)]
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }
