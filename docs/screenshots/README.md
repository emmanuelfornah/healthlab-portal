# Screenshots — Evidence Checklist

Capture these and save them **in this folder** using the exact filenames below,
then reference them from the main README. Number prefixes keep them ordered.

Save format: **PNG**. Keep them readable (full window, not cropped tiny), and
make sure resource names / green states are visible.

## Available now (code + CI)

| Filename | What to capture |
|---|---|
| `01_ci_pipeline_green.png` | GitHub repo → **Actions** tab → the CI run with both jobs (Backend, Frontend) green |
| `02_repo_homepage.png` | Repo homepage showing the README, badges, and topics |
| `03_pytest_31_passed.png` | Terminal: `pytest -q` showing **31 passed** |
| `04_sam_validate.png` | Terminal: `sam validate --lint` → "valid SAM Template" |
| `05_frontend_build.png` | Terminal: `npm run build` succeeding |

## Live and deployed

| Filename | What to capture |
|---|---|
| `06_cloudformation_complete.png` | CloudFormation stack → UPDATE_COMPLETE with resources |
| `07_stepfunctions_execution.png` | Step Functions → a successful execution graph (parallel branches green) |
| `08_cognito_signin.png` | Cognito sign-in page at `auth.healthlabportal.com` (after the Managed Login branding pass) |
| `09_live_app.png` | The running app at `https://healthlabportal.com` — capture the welcome screen, the upload screen, and a status result as three separate shots if possible |
| `10_waf_webacl.png` | WAFv2 Web ACL rules + metrics, showing it's attached to the CloudFront distribution |
| `11_xray_trace.png` | X-Ray service map / trace of a real onboarding run |
| `12_dynamodb_patient_record.png` | DynamoDB `PatientRecords-dev` item after a run |
| `13_cloudwatch_dashboard.png` | CloudWatch dashboard `HealthLab-Operations-dev` — workflow, API, Lambda, queue widgets in one view |
| `14_route53_and_acm.png` | Route 53 hosted zone showing the `healthlabportal.com` / `auth.healthlabportal.com` records, and the ACM certificate showing **Issued** |
| `15_security_hub_guardduty.png` | (Optional) Security Hub findings dashboard or GuardDuty summary — shows account-level monitoring is real, not just claimed in docs |
| `16_iam_policy_simulator.png` | IAM Policy Simulator — `HealthLab-ValidateEligibilityRole-dev` denied on S3/DynamoDB/Rekognition (proves it holds zero resource access), and/or `HealthLab-VerifyIdentityRole-dev` allowed on Rekognition but denied on Textract (proves per-function scoping, not just an empty role) |

## How to reference in the main README

```markdown
## Screenshots

![CI pipeline](docs/screenshots/01_ci_pipeline_green.png)
![Step Functions execution](docs/screenshots/07_stepfunctions_execution.png)
```
