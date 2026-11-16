# Runbook: ECS Task Out of Memory (OOMKilled - Exit Code 137)

## Symptoms
- Container terminates unexpectedly with exit code 137.
- CloudWatch metric `MemoryUtilization` reaches 100%.
- EventBridge emits `TaskStoppedReason: Out of Memory: Container killed`.

## Triage & Root Cause
1. Verify if traffic (RequestsPerTarget) spiked concurrently.
2. If traffic is normal, suspect a memory leak or undersized container limit.
3. Check container memory reservation vs hard limit in task definition.

## Allow-Listed Remediation
1. Immediate relief: Temporarily scale task definition memory by 2x via `aws ecs update-service`.
2. Permanent fix: Review application heap dump and profile memory allocation.