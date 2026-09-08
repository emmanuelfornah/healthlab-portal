# Security

This document describes the security controls for HealthLab Portal and how each
one is applied. Controls are split into **enforced in code (IaC)** and
**applied at the account/edge level (console)** so it is clear what deploys
automatically versus what an operator enables.

> This is a demonstration project. It uses HIPAA-aligned patterns but is not a
> HIPAA-certified system and must not process real PHI.

## Enforced in code (SAM template)

These deploy automatically with `sam deploy` — no manual steps.

| Control | How |
|---|---|
| Encryption at rest — S3 intake bucket | `BucketEncryption` (AES256) |
| Private storage | S3 `PublicAccessBlockConfiguration` blocks all public access |
| Private frontend hosting | S3 bucket has no public access; served only via CloudFront through Origin Access Control, bucket policy scoped to that one distribution's ARN |
| Encryption at rest — DynamoDB | `SSESpecification` (AWS-managed key) |
| Point-in-time recovery — DynamoDB | `PointInTimeRecoverySpecification` |
| Encryption at rest — SQS + DLQ | `SqsManagedSseEnabled` |
| Encryption at rest — SNS | `KmsMasterKeyId: alias/aws/sns` |
| Least-privilege IAM | Each of the 7 Lambdas has its **own** IAM role scoped to only the actions its own code calls (e.g. `ValidateEligibilityRole` has no AWS resource permissions at all — that handler never touches S3/DynamoDB/etc.), rather than one broad role shared across every function — no wildcard admin anywhere |
| Authentication | Amazon Cognito User Pool; patient API protected by a Cognito JWT authorizer |
| PKCE (OAuth) | Frontend's Authorization Code flow uses PKCE (S256) — a leaked authorization code alone isn't redeemable for tokens |
| Per-patient authorization | `/intake/{id}/status` and `/fhir` are scoped to the requesting patient's Cognito `sub`, recorded when the upload URL is issued — a mismatched owner gets a 404, not another patient's record |
| Short-lived upload access | Presigned S3 URLs (300s), not public writes |
| Deploy credentials | GitHub Actions authenticates via OIDC (`sts:AssumeRoleWithWebIdentity`) — no long-lived AWS access keys stored in CI |
| Tracing / audit | AWS X-Ray active tracing; structured logs via Lambda Powertools |
| Operational monitoring | CloudWatch alarms on Step Functions failures, the eligibility DLQ, Patient API 5xx errors, and critical-path Lambda errors, notifying a dedicated `OperationalAlarms` SNS topic; a CloudWatch dashboard aggregates workflow, API, Lambda, and queue metrics |
| WAF on the frontend | `AWS::WAFv2::WebACL` (Core rule set + Known Bad Inputs managed rule groups, plus a 1,000 req/5min per-IP rate limit) attached directly to the CloudFront distribution's `WebACLId` |
| TLS-only S3 access | Both S3 bucket policies (intake bucket, frontend bucket) explicitly `Deny` any request where `aws:SecureTransport` is `false` — belt-and-suspenders on top of everything already being HTTPS in practice |
| No secrets in VCS | No credentials or account IDs committed; `.env` gitignored |

## Applied in the console (edge / account level)

These are intentionally **not** in the app's SAM template — they are account- or
edge-scoped and are easier to manage from the console without coupling them to
application deploys.

> **A note on WAF's placement.** This was originally planned as a
> console-managed, out-of-template step — the reasoning being that
> edge/account-level controls are easier to manage without coupling them to
> app deploys. That reasoning didn't hold up for WAF specifically: its
> attachment point (`WebACLId`) is a property of the CloudFront
> distribution this template already owns, so managing it out-of-band risked
> a future `sam deploy` silently reverting the association when
> CloudFormation resent the distribution's full config. It's now in the SAM
> template instead (see the table above) — the account-level controls below
> (GuardDuty, CloudTrail, Config, Security Hub) don't have this problem,
> since nothing in this stack owns them.

> The API layer uses an HTTP API, which does not support direct WAF association
> (WAF integrates with REST APIs). The API is protected by the Cognito JWT
> authorizer and API Gateway throttling; unauthenticated requests are rejected
> before reaching any Lambda.

### Network segmentation — not applicable here

This backend is Lambda + managed AWS services only (API Gateway, S3,
DynamoDB, SQS, SNS, Rekognition, Textract) — no Lambda runs inside a VPC,
and there's no EC2 or RDS to segment with security groups. The classic
3-tier VPC/security-group model (frontend-sg → backend-sg → db-sg, with
SSH/RDP locked to an admin IP) doesn't map onto an architecture with no
VPC-bound compute. The equivalent perimeter controls here are the Cognito
JWT authorizer at the API layer and per-function least-privilege IAM roles
at the compute layer (see the table above) — noted explicitly so the
absence of VPC controls reads as a deliberate architectural fit, not a gap.

### Customer-managed KMS keys — considered, not adopted

Everything is encrypted at rest (see table above) using AWS-managed keys
(SSE-S3 / `alias/aws/*`) rather than a customer-managed key (CMK). A CMK
would add a key policy scoping exactly which roles can use it, rotation
control, and the ability to revoke access at the key level independent of
IAM. Deliberately not adopted: it's a small recurring cost (~$1/month) for
a capability — independent key-level access revocation — this project
doesn't currently need, since per-function IAM roles already scope access
tightly. Worth revisiting if this needs to satisfy a real audit rather than
demonstrate the pattern.

### Account-level threat detection & monitoring

Enable once per account (console), shared across all projects. Status as of
the last review:

| Control | Status |
|---|---|
| **Amazon GuardDuty** — threat detection | ✅ Enabled |
| **AWS CloudTrail** — multi-region trail, S3-delivered, log file validation on (beyond the account's default 90-day event history) | ✅ Enabled |
| **AWS Security Hub** — aggregates GuardDuty/Inspector/Macie/Config findings into one dashboard, default standards on | ✅ Enabled |
| **AWS Config** — scoped to `AWS::S3::Bucket` only (not `allSupported`, to avoid recording every resource type account-wide), with `s3-bucket-server-side-encryption-enabled` and `s3-bucket-public-read-prohibited` rules (`restricted-ssh` doesn't apply — no EC2/SSH anywhere in this stack) | ✅ Enabled |
| **MFA** on all console/IAM users | ⚠️ Partial — verify every IAM user with console access has MFA before treating this as done |
| **IAM Policy Simulator** validation of the per-function roles | ⬜ Not yet run |

(AWS WAF moved to the "Enforced in code" table above — see the note further up.)

These are intentionally generic here — see the private project log for the
exact commands and account-specific values used to enable them (not
committed to this repo, consistent with the "no secrets/account identifiers
in VCS" rule above).

## HIPAA Security Rule — technical safeguards mapping

> This section maps implemented controls to the Security Rule's **technical
> safeguards** (§164.312) for reference. It is **not** a compliance claim.
> HIPAA compliance also requires administrative safeguards (§164.308 —
> workforce training, formal risk analysis, sanction policy, business
> associate agreements) and physical safeguards (§164.310) that are
> organizational, not code — a solo demo repo cannot satisfy those, and none
> are claimed here. Using AWS for real PHI additionally requires an active
> **Business Associate Agreement (BAA)** with AWS, which this project does
> not have; several services used here (notably **Rekognition** and
> **Textract**) should be checked against AWS's current HIPAA-eligible
> services list before any real PHI would be allowed near this pipeline —
> which is exactly why this repo only ever processes synthetic test data.

| Technical safeguard (§164.312) | Implementation here |
|---|---|
| Access control — unique user identification | Cognito `sub` per patient; every API-authenticated action traces to one identity |
| Access control — automatic logoff | Cognito-issued JWTs are short-lived; `isAuthenticated()` checks expiry client-side |
| Access control — encryption/decryption | S3, DynamoDB, SQS, SNS all encrypted at rest (see table above) |
| Audit controls | CloudWatch Logs (structured, via Lambda Powertools) + AWS X-Ray tracing on every Lambda and the state machine; CloudWatch alarms surface failures instead of relying on someone reading logs |
| Integrity | DynamoDB SSE + point-in-time recovery; S3 SSE; workflow only ever merges records via `update_item`, never blind-overwrites |
| Person or entity authentication | Amazon Cognito User Pool (password policy: 8+ chars, upper/lower/number/symbol), JWT authorizer on every protected route |
| Transmission security | HTTPS enforced end-to-end — API Gateway, CloudFront, S3 presigned URLs; PKCE on the OAuth flow protects the auth handshake itself |

## Threat model (STRIDE)

| Threat | Example, specific to this app | Mitigating control |
|---|---|---|
| **S**poofing | Forged/expired JWT presented to the Patient API; authorization code stolen mid-sign-in | Cognito JWT authorizer validates signature/issuer/audience before any Lambda runs; PKCE (S256) prevents a stolen authorization code from being redeemed by anyone but the browser that requested it |
| **T**ampering | A patient's `intake_id` leaks (screenshot, log, referrer) and is used to view or alter another patient's record | `PATIENT_SUB` ownership check on `/status` and `/fhir`; `write_patient_record` merges via `update_item`, never a blind overwrite that could erase ownership |
| **R**epudiation | Dispute over whether an identity/eligibility check ran, or what it returned | Structured Powertools logs + X-Ray tracing on every Lambda and the state machine; an SNS notification fires on every failed check, creating a record independent of the DynamoDB row |
| **I**nformation disclosure | Intake ZIP (ID photo, selfie, PII) intercepted in transit, or read from storage by an unauthorized principal | TLS end-to-end (API Gateway, CloudFront, presigned URLs); S3/DynamoDB/SQS/SNS encrypted at rest; per-function IAM roles limit what a compromised Lambda could actually read |
| **D**enial of service | A flood of upload or API requests drives up cost or exhausts downstream capacity | API Gateway default throttling; 300s presigned-URL expiry; SQS + DLQ (`maxReceiveCount: 5`) absorbs eligibility-check bursts without cascading Lambda retries; WAF rate-based rule (console, see above) |
| **E**levation of privilege | A compromised Lambda (e.g. a vulnerable dependency) is used to pivot into other AWS resources | Per-function least-privilege IAM roles — e.g. a compromised `ValidateEligibilityFunction` has zero AWS resource permissions to pivot with, by design |

## Incident response (summary)

If credentials are suspected compromised: rotate immediately, review CloudTrail
for unauthorized activity, and audit IAM permissions. Report vulnerabilities
privately to the repository owner rather than via a public issue.
