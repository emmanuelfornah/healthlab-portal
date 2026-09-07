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
| `03_pytest_20_passed.png` | Terminal: `pytest -q` showing **20 passed** |
| `04_sam_validate.png` | Terminal: `sam validate --lint` → "valid SAM Template" |
| `05_frontend_build.png` | Terminal: `npm run build` succeeding |

## After deployment (activations)

| Filename | What to capture |
|---|---|
| `06_cloudformation_complete.png` | CloudFormation stack → CREATE_COMPLETE with resources |
| `07_stepfunctions_execution.png` | Step Functions → a successful execution graph (parallel branches green) |
| `08_cognito_hosted_ui.png` | Cognito Hosted UI sign-in page |
| `09_live_app.png` | The running app (CloudFront URL / healthlabportal.com) |
| `10_waf_cloudfront.png` | WAF Web ACL associated with the CloudFront distribution |
| `11_xray_trace.png` | X-Ray service map / trace of an onboarding run |
| `12_dynamodb_patient_record.png` | DynamoDB PatientRecords item after a run |

## How to reference in the main README

```markdown
## Screenshots

![CI pipeline](docs/screenshots/01_ci_pipeline_green.png)
![Step Functions execution](docs/screenshots/07_stepfunctions_execution.png)
```
