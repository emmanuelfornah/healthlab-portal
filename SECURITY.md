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
| Least-privilege IAM | Scoped role: S3, DynamoDB, Rekognition, Textract, SNS, SQS only — no wildcard admin |
| Authentication | Amazon Cognito User Pool; patient API protected by a Cognito JWT authorizer |
| PKCE (OAuth) | Frontend's Authorization Code flow uses PKCE (S256) — a leaked authorization code alone isn't redeemable for tokens |
| Per-patient authorization | `/intake/{id}/status` and `/fhir` are scoped to the requesting patient's Cognito `sub`, recorded when the upload URL is issued — a mismatched owner gets a 404, not another patient's record |
| Short-lived upload access | Presigned S3 URLs (300s), not public writes |
| Deploy credentials | GitHub Actions authenticates via OIDC (`sts:AssumeRoleWithWebIdentity`) — no long-lived AWS access keys stored in CI |
| Tracing / audit | AWS X-Ray active tracing; structured logs via Lambda Powertools |
| Operational monitoring | CloudWatch alarms on Step Functions failures, the eligibility DLQ, Patient API 5xx errors, and critical-path Lambda errors, notifying a dedicated `OperationalAlarms` SNS topic; a CloudWatch dashboard aggregates workflow, API, Lambda, and queue metrics |
| No secrets in VCS | No credentials or account IDs committed; `.env` gitignored |

## Applied in the console (edge / account level)

These are intentionally **not** in the app's SAM template — they are account- or
edge-scoped and are easier to manage from the console without coupling them to
application deploys.

### AWS WAF on CloudFront (frontend)

WAF cannot attach to S3 directly; it attaches to the CloudFront distribution
that fronts the private S3 bucket, so it protects all traffic to the site.

Steps (console):
1. AWS WAF → **Create web ACL** → Region **Global (CloudFront)** (created in `us-east-1`).
2. Add rules:
   - **AWS Managed Rules — Core rule set (AWSManagedRulesCommonRuleSet)**
   - **Known Bad Inputs (AWSManagedRulesKnownBadInputsRuleSet)**
   - A **rate-based rule** (e.g. 1,000 requests / 5 min per IP).
3. Associate the web ACL with the HealthLab CloudFront distribution.

> The API layer uses an HTTP API, which does not support direct WAF association
> (WAF integrates with REST APIs). The API is protected by the Cognito JWT
> authorizer and API Gateway throttling; unauthenticated requests are rejected
> before reaching any Lambda.

### Account-level threat detection & monitoring

Enable once per account (console), shared across all projects:
- **Amazon GuardDuty** — threat detection
- **AWS CloudTrail** — API activity audit trail
- **AWS Config** — configuration compliance
- **AWS Security Hub** — centralized findings
- **MFA** on all console/IAM users

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

## Incident response (summary)

If credentials are suspected compromised: rotate immediately, review CloudTrail
for unauthorized activity, and audit IAM permissions. Report vulnerabilities
privately to the repository owner rather than via a public issue.
