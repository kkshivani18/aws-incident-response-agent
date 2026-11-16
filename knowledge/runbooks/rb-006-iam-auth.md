# Runbook: IAM Authentication & STS Token Expiration

## Symptoms
- Applications reporting `ExpiredTokenException` or `AccessDeniedException`.
- AWS STS AssumeRole calls failing with timestamp signature expiration.
- Intermittent 401/403 authorization failures across cloud services.

## Triage & Root Cause
1. Verify if instance profile / ECS task role credentials expired before renewal.
2. Check system clock drift (NTP synchronization issue on host).
3. Check IAM role session duration limits vs application refresh interval.

## Allow-Listed Remediation
1. Force task credential refresh or restart task to obtain fresh STS temporary credentials.
2. Synchronize NTP chrony daemon on EC2/container hosts.
