# Runbook: Security Group Misconfiguration & Egress Blocking

## Symptoms
- Connection refused on port 443 / fatal connect: connection refused to api.stripe.com:443.
- Traffic dropped or TCP connection timeouts after SecurityGroup (e.g. sg-019) updated.
- VPC Flow Logs showing `REJECT` on outbound HTTPS packets to third-party APIs.

## Triage & Root Cause
1. Review CloudTrail audit logs for recent `AuthorizeSecurityGroupEgress` or `RevokeSecurityGroupEgress` events.
2. Check security group rules attached to the ECS ENI / EC2 instance.
3. Verify VPC Route Table and NAT Gateway connectivity.

## Allow-Listed Remediation
1. Re-add missing outbound HTTPS (port 443) rule to the service security group.
2. Revert unauthorized security group changes to previous known-good state.
