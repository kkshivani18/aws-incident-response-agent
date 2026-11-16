# Runbook: Disk Space Exhaustion (>95% Capacity)

## Symptoms
- CloudWatch disk utilization alarm breached (>95% on root or data volume /dev/xvda1).
- Disk space critical, unable to write application logs (e.g. /var/log/app.log consumed disk).
- `No space left on device` errors in system syslog.

## Triage & Root Cause
1. Identify high-growth directories using disk usage inspection (e.g. `/var/log`).
2. Verify if log rotation (logrotate) failed or stdout redirection created oversized log files.
3. Check for orphan docker containers or unpruned container layers.

## Allow-Listed Remediation
1. Rotate, truncate, and compress old application log files immediately.
2. Expand EBS volume size or attach secondary logging volume.
