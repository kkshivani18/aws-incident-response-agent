# Runbook: Database Connection Pool Exhaustion

## Symptoms
- Application logs contain: `Connection is not available, request timed out after Xms`.
- DB connection count at max capacity (e.g., HikariCP / RDS max_connections reached).

## Triage & Root Cause
1. Slow SQL queries holding connections open without releasing.
2. Missing connection release in application error handlers (connection leak).
3. RDS CPU or memory pressure preventing fast query completion.

## Allow-Listed Remediation
1. Inspect RDS `DatabaseConnections` CloudWatch metric.
2. Identify slow transactions via Performance Insights.
3. Restart offending application tasks to forcibly release hung connections.