# Runbook: HTTP 5xx Error Spike Post-Deployment

## Symptoms
- ALB 5xx metric spikes immediately following an ECS service deployment.
- Application logs show unhandled exceptions, NullPointerException, or initialization errors.
- HTTP 500 status returned on high percentage of traffic post deploy.

## Triage & Root Cause
1. Check the timestamp of the latest deploy revision against the alarm trigger time.
2. If errors began within 5 minutes of deploy, treat deployment as suspect.
3. Review application stack traces for null pointer exceptions or broken dependencies.

## Allow-Listed Remediation
1. Trigger immediate rollback to previous stable task definition revision:
   `aws ecs update-service --service <name> --task-definition <previous-stable-family:rev>`
2. Notify the release author on Slack with offending stack traces.