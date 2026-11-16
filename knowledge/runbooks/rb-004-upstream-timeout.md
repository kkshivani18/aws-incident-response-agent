# Runbook: Downstream Dependency Timeout & Retry Storm

## Symptoms
- Upstream service returns 504 Gateway Timeout.
- Client requests timing out after fixed timeout limit (e.g. 5000ms).
- Retries multiplying traffic to downstream dependency.

## Triage & Root Cause
1. Identify which downstream dependency service is failing or unresponsive.
2. Check if downstream service is suffering CPU saturation or high latency.
3. Verify if exponential backoff and circuit breaker are active on client calls.

## Allow-Listed Remediation
1. Enable circuit breaker to fail fast and stop retry storm.
2. Scale downstream dependency service tasks.
