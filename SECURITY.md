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
| Encryption at rest — DynamoDB | `SSESpecification` (AWS-managed key) |
| Point-in-time recovery — DynamoDB | `PointInTimeRecoverySpecification` |
| Encryption at rest — SQS + DLQ | `SqsManagedSseEnabled` |
| Encryption at rest — SNS | `KmsMasterKeyId: alias/aws/sns` |
| Least-privilege IAM | Scoped role: S3, DynamoDB, Rekognition, Textract, SNS, SQS only — no wildcard admin |
| Authentication | Amazon Cognito User Pool; patient API protected by a Cognito JWT authorizer |
| Short-lived upload access | Presigned S3 URLs (300s), not public writes |
| Least-privilege uploads | Patient identity read from verified JWT claims |
| Tracing / audit | AWS X-Ray active tracing; structured logs via Lambda Powertools |
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

## Incident response (summary)

If credentials are suspected compromised: rotate immediately, review CloudTrail
for unauthorized activity, and audit IAM permissions. Report vulnerabilities
privately to the repository owner rather than via a public issue.
