# 🏥 HealthLab Portal — Serverless Patient Onboarding

[![CI](https://github.com/emmanuelfornah/healthlab-portal/actions/workflows/ci.yml/badge.svg)](https://github.com/emmanuelfornah/healthlab-portal/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![AWS SAM](https://img.shields.io/badge/AWS-SAM-orange.svg)](https://aws.amazon.com/serverless/sam/)
[![FHIR R4](https://img.shields.io/badge/FHIR-R4-red.svg)](https://hl7.org/fhir/R4/)

Serverless patient onboarding on AWS that verifies patient identity, reconciles
intake details, and checks patient eligibility for lab test orders. A patient
signs in, uploads an intake bundle (intake form, ID document, selfie), and an
event-driven workflow runs those checks in parallel — establishing whether the
patient is eligible (insurance/coverage) before lab test orders proceed, then
records the outcome for the care team.

> **Scope & honesty note.** This is a portfolio/demonstration project. It
> follows HIPAA-aligned patterns (encryption at rest, least-privilege IAM,
> private storage, audit-friendly workflow) but is **not** a HIPAA-certified
> system and should not process real PHI. The insurance eligibility service is a
> **mock** stand-in for a real payer/clearinghouse API. Everything described
> below is implemented and tested locally; see [Testing](#testing).

---

## Architecture

```
Patient ─► Cognito Hosted UI (sign in) ─► JWT
        ─► React SPA (Vite)
        ─► Patient API (API Gateway HTTP API, Cognito JWT authorizer)
             ├─ POST /intake/upload-url        presigned S3 upload URL
             └─ GET  /intake/{id}/status       onboarding status
        ─► PUT intake bundle ─► S3 (encrypted, EventBridge enabled)
              └─ EventBridge (intake/ prefix) ─► Step Functions
                   ├─ UnzipIntake
                   ├─ WritePatientRecord ─► DynamoDB
                   ├─ Parallel:
                   │     ├─ VerifyIdentity   (Amazon Rekognition)
                   │     └─ ExtractDetails   (Amazon Textract AnalyzeID)
                   └─ SubmitEligibilityCheck ─► SQS ─► ValidateEligibility (mock API)
                         └─ SNS notification on any failed check
```

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite (single-page patient portal) |
| Auth | Amazon Cognito User Pool + Hosted UI (Authorization Code flow) |
| API | Amazon API Gateway (HTTP API) with a Cognito JWT authorizer |
| Compute | AWS Lambda (Python 3.13), 7 functions |
| Orchestration | AWS Step Functions (parallel validation branches) |
| Identity / OCR | Amazon Rekognition (face match), Amazon Textract (AnalyzeID) |
| Eventing | Amazon EventBridge (S3 → Step Functions) |
| Messaging | Amazon SQS (+ dead-letter queue), Amazon SNS |
| Storage | Amazon S3 (encrypted, private), Amazon DynamoDB |
| IaC | AWS SAM |
| Observability | AWS X-Ray active tracing, structured logs (Lambda Powertools) |
| Testing | pytest, moto, Hypothesis (property-based) |

## Repository layout

```
healthlab-portal/
├── backend/
│   ├── template.yaml                 # SAM stack (all AWS resources)
│   ├── statemachine/
│   │   └── onboarding_workflow.asl.json
│   ├── src/
│   │   ├── unzip/                    # extract intake bundle
│   │   ├── write_patient_record/     # parse intake CSV → DynamoDB
│   │   ├── verify_identity/          # Rekognition: selfie vs ID
│   │   ├── extract_details/          # Textract: ID vs intake form
│   │   ├── submit_eligibility/       # SQS-triggered eligibility check
│   │   ├── validate_eligibility/     # mock eligibility API (HTTP)
│   │   └── patient_portal/           # Cognito-protected patient API
│   └── tests/                        # unit + property tests
└── frontend/
    ├── src/
    │   ├── auth.js                   # Cognito Hosted UI code flow
    │   ├── api.js                    # Patient API client (JWT)
    │   └── App.jsx                   # sign in → upload → status
    └── ...
```

## Onboarding workflow

1. A patient signs in through the Cognito Hosted UI; the SPA exchanges the
   authorization code for a JWT.
2. The SPA calls `POST /intake/upload-url` (JWT-authorized) and receives a
   short-lived presigned S3 URL and an `intake_id`.
3. The patient's browser uploads the intake ZIP directly to S3 under `intake/`.
4. The S3 upload emits an EventBridge event that starts the Step Functions
   execution.
5. The workflow unzips the bundle, writes the patient record, then runs two
   checks in parallel — Rekognition identity match and Textract detail
   reconciliation — before submitting an eligibility check via SQS.
6. Each check updates the DynamoDB record; failures publish an SNS notification
   for manual review. The patient can poll `GET /intake/{id}/status`.

The intake bundle contains exactly three files:
`<intake_id>_intake.csv`, `<intake_id>_id.png`, `<intake_id>_selfie.png`.

## Local development

### Backend

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r tests/requirements.txt
sam validate --lint          # validate the template
pytest                       # run unit + property tests
```

### Frontend

```bash
cd frontend
cp .env.example .env         # fill in after deploying the backend
npm install
npm run dev                  # http://localhost:5173
npm run lint
npm run test
```

Frontend environment variables (`.env`):

```
VITE_PATIENT_API_URL=      # PatientApiEndpoint output
VITE_COGNITO_DOMAIN=       # CognitoHostedUiDomain output
VITE_COGNITO_CLIENT_ID=    # CognitoUserPoolClientId output
VITE_REDIRECT_URI=http://localhost:5173/
```

## Testing

Backend tests run without any AWS account — AWS calls are mocked with `moto`,
and the eligibility mock is covered with property-based tests (Hypothesis) that
assert invariants across generated inputs.

| Suite | What it covers |
|---|---|
| `tests/unit/test_unzip.py` | intake extraction + file-count validation |
| `tests/unit/test_write_patient_record.py` | CSV → DynamoDB record |
| `tests/unit/test_validate_eligibility.py` | eligibility mock responses |
| `tests/unit/test_patient_portal.py` | auth gate, presigned URL, status lookup |
| `tests/property/test_eligibility_properties.py` | eligibility invariants (Hypothesis) |

All 14 tests pass locally; `sam validate --lint` passes; the frontend builds,
lints clean, and its auth tests pass.

## Security notes

- Cognito JWT authorizer protects the patient API; the patient identity is read
  from verified token claims.
- S3 intake bucket is private (all public access blocked) and encrypted at rest;
  uploads use short-lived presigned URLs.
- Each Lambda uses a scoped IAM role (S3, DynamoDB, Rekognition, Textract, SNS,
  SQS) — no wildcard admin access, no long-lived credentials in code.
- No secrets or AWS account identifiers are committed to the repository.

## Deployment (planned)

The stack deploys with `sam build && sam deploy`. The frontend is intended to be
hosted on S3 + CloudFront behind the custom domain **healthlabportal.com**
(Route 53 + ACM). Deployment and live hosting are the next step and are not yet
completed.

## Roadmap

Planned extensions (not yet implemented):

- **Duplicate & redundant lab-order detection.** Flag lab test orders that
  overlap in their component analytes so physicians avoid redundant draws and
  billing. Examples:
  - A glucose ordered separately when a **BMP** or **CMP** (which already
    include glucose) is also ordered.
  - A **BMP** later "upgraded" to a **CMP** — the CMP superset already contains
    the BMP analytes, making the earlier BMP redundant.
  - Overlapping panels ordered together (e.g. BMP + CMP, where CMP is a superset
    of BMP + LFT components).
  - **Time-based redundancy** — tests reordered within a clinically meaningless
    interval. For example, **HbA1c ordered again within 3 months**: A1c reflects
    roughly 90 days of average glycemia (red-cell lifespan), so a repeat inside
    that window adds cost without new clinical information.

  The intent is a rules service combining an **analyte-mapping** layer (resolve
  each panel to its component analytes to catch overlaps) with a **frequency**
  layer (flag reorders inside evidence-based minimum intervals) — reducing cost
  and duplicate specimen collection. (Design informed by clinical laboratory
  experience.)
- **AWS HealthLake** as the production FHIR datastore (this build ships a
  FHIR R4 mapping layer; HealthLake would provide managed FHIR persistence and
  query APIs).
- **WAF on CloudFront** (managed rules + rate limiting) and account-level threat
  detection — see [SECURITY.md](SECURITY.md).

## Author

**Emmanuel Fornah** — AWS Cloud Application Developer (healthcare & serverless)

AWS Certified: Developer – Associate · Solutions Architect – Associate · AI Practitioner · Cloud Practitioner
· HashiCorp Terraform Associate

[Credly](https://www.credly.com/users/emmanuel-fornah) · [GitHub](https://github.com/emmanuelfornah)

## License

MIT
