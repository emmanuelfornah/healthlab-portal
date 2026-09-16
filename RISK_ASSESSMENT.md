# Risk Assessment — HealthLab Portal

This document applies a formal risk-assessment methodology to the actual
architecture in this repository — not a hypothetical enterprise deployment.
Risks are drawn from the real threat model in `SECURITY.md` and the
`Known limitations` table there; this document adds likelihood/impact
scoring, prioritization, and a business continuity plan that those didn't
have yet.

## Methodology

**Framework:** NIST Cybersecurity Framework (Identify → Protect → Detect →
Respond → Recover), scored with a simple 1-5 likelihood × impact matrix.

**Why NIST CSF over alternatives:** CSA CAIQ is built around auditing a
cloud *service provider's* controls — not applicable here, since AWS's
side of the shared-responsibility model isn't what this document is
assessing. ISO 27017 assumes a formal ISMS with a security team; this is
a solo-maintained serverless project. NIST CSF's five functions map
cleanly onto what already exists here (Identify = the architecture
inventory, Protect = the IAM/encryption/auth controls in `SECURITY.md`,
Detect = CloudWatch alarms, Respond = the incident response section,
Recover = the business continuity plan below) without requiring
enterprise-scale process this project doesn't have.

**Scope note:** this assesses the *application's* real risk posture at
its actual current scale (demo/portfolio traffic, no production PHI).
It does not assess AWS's infrastructure risk (out of scope, shared
responsibility model) or fabricate an enterprise SLA/budget this project
doesn't have.

## Risk Register

| # | Risk | Threat source | Likelihood (1-5) | Impact (1-5) | Score |
|---|---|---|---|---|---|
| 1 | Stolen/leaked JWT or intercepted OAuth code used to access another patient's record | External attacker, credential theft | 2 | 4 | 8 |
| 2 | Compromised Lambda (vulnerable dependency) used to pivot into other AWS resources | Supply-chain / dependency CVE | 2 | 3 | 6 |
| 3 | IAM console user compromise — no MFA enforced yet | Credential stuffing, phishing | 3 | 4 | 12 |
| 4 | Regional AWS outage (us-east-1) — no cross-region failover | AWS infrastructure event | 1 | 5 | 5 |
| 5 | Undetected regression reaches production — no automated E2E test in CI | Human error, untested edge case | 3 | 3 | 9 |
| 6 | Cost-based denial of service (upload/API flood driving up Lambda/Textract/Rekognition spend) | External actor or misconfigured client | 2 | 3 | 6 |
| 7 | S3/DynamoDB misconfiguration exposing intake data | Human error during a future change | 1 | 5 | 5 |
| 8 | Mock eligibility service replaced with a real payer API without re-reviewing the trust boundary | Future integration work | 1 | 3 | 3 |

**Scoring:** Likelihood × Impact, 1 (rare/negligible) to 5 (near-certain/
severe). This is a small system with a small, known attack surface — the
scores reflect that; they are not inflated to make the exercise look more
serious than the actual system is.

## Prioritization

```
Impact
  5 │  [7]              [4]
  4 │  [1]
  3 │  [2] [6]     [5]
  2 │
  1 │              [8]
    └───────────────────────
      1    2    3    4    5
              Likelihood
```

**Top priority — #3, IAM console MFA not enforced (score 12).** Highest
score here specifically because it's the one risk on this list that's
both plausible *and* already flagged as an open gap (`SECURITY.md`'s
Known Limitations), not a hypothetical.

**Second — #5, no automated E2E test in CI (score 9).** Not a security
control gap in the traditional sense, but a real risk to data integrity
and availability — the exact kind of thing NIST CSF's "Detect" function
is meant to cover, and it's already honestly tracked as unclosed.

**Third — #1 and #2 (score 8 and 6).** Already substantially mitigated
(PKCE, per-function least-privilege IAM, patient-scoped authorization) —
scored above the "low" items because the *consequence* if either control
failed is still meaningful, even though the controls are real.

**Deliberately low — #4 and #7 (score 5).** Not because they don't
matter, but because the actual likelihood at this project's scale is
genuinely low, and treating them as top priority would misallocate
effort a solo maintainer doesn't have to spare. This is the same
reasoning `DR_SCENARIO.md`/`DR_RUNBOOK.md` uses for the sibling
`deployment-evolution` project: proportionate response, not maximal
paranoia.

## Mitigation — top 3

**#3 — MFA enforcement**
- Control type: preventive
- Action: enroll a virtual MFA device per IAM console user, attach a
  deny-without-MFA policy (`"Condition": {"BoolIfExists":
  {"aws:MultiFactorAuthPresent": "false"}}`)
- Effort: ~15 minutes, no cost
- Residual risk: low — the remaining exposure is device loss/theft,
  mitigated by AWS's standard MFA-device-recovery process

**#5 — Automated E2E test in CI**
- Control type: detective
- Action: a scripted pytest step creating a disposable Cognito test
  user, uploading a synthetic intake ZIP, polling `/status` to a
  terminal state, then tearing the test user down — on every push to
  `main`, not just verified manually
- Effort: real — new IAM permissions on the deploy role, test-data
  lifecycle management; `SECURITY.md` already scopes this honestly as
  bigger than a config change
- Residual risk: medium until built — this is the one open item on this
  list without a control in place yet

**#1 — Stolen JWT / intercepted OAuth code**
- Control type: preventive (already implemented) + detective (partial)
- Existing control: PKCE (S256) on the Authorization Code flow, short
  JWT expiry, per-patient `sub`-scoped authorization on every record
  lookup
- Gap: no anomaly detection on token use patterns (e.g., same JWT from
  geographically implausible locations in a short window) — reasonable
  to leave unaddressed at this scale; noted here rather than silently
  assumed complete

## Business Continuity

**RTO/RPO by failure mode:**

| Scenario | RTO | RPO | Why |
|---|---|---|---|
| Single Lambda function failure | Seconds | 0 | Lambda's own automatic retry/redeploy; stateless |
| Step Functions execution failure | Minutes | 0 | Every state has a `Catch`; SNS notifies on failure; DynamoDB record persists partial progress |
| DynamoDB table issue | N/A | ≤ 5 min | Point-in-time recovery enabled |
| CI/CD pipeline failure | N/A | 0 | Deploy only runs after CI passes; a broken deploy simply doesn't ship |
| Regional AWS outage (us-east-1) | Not defined | Not defined | **Accepted risk, not mitigated** — see below |

**On the regional-outage gap, stated honestly:** this project has no
cross-region failover, unlike `deployment-evolution`'s documented (if
also unbuilt) DR design. That's a deliberate scope decision, not an
oversight: this is a serverless, single-purpose demo app with no real
PHI and no uptime SLA to meet. A cross-region DR build here would be
solving a problem this project doesn't actually have — the same
proportionality principle used to keep risk scores honest above, applied
to the mitigation budget itself. If this were a real production
healthcare system with a real SLA, this would be the single biggest gap
on this entire document; at this project's actual scope, it's an
accepted risk, written down rather than silently ignored.

**Communication plan during a disruption:** SNS notification to the
`OnboardingNotifications` topic on any workflow failure; CloudWatch
alarms on Step Functions failures, the eligibility DLQ, API 5xx errors,
and critical-path Lambda errors, aggregated on the
`HealthLab-Operations-dev` dashboard. For a solo-maintained project,
"the maintainer gets paged" is the entire communication plan — stated
plainly rather than describing an incident-response team this project
doesn't have.

## What this document deliberately does not claim

No 99.99% uptime commitment, no fictional budget figures, no compliance
certification (see `SECURITY.md`'s own HIPAA scope note — this is
HIPAA-*aligned*, not certified, and must not process real PHI). This
document assesses the system that actually exists, at the scale it
actually runs at.
