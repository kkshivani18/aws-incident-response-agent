# Runbook: Security Group Misconfiguration & Egress Blocking

## Symptoms
- TCP connection timeouts or connection refused on port 443 / external API calls.
- Traffic suddenly dropped following recent Terraform or CloudFormation infrastructure updates.
- VPC Flow Logs showing `REJECT` on outbound packets to third-party endpoints.

## Triage & Root Cause
1. Review CloudTrail audit logs for recent `AuthorizeSecurityGroupEgress` or `RevokeSecurityGroupEgress` events.
2. Check security group rules attached to the ECS ENI / EC2 instance.
3. Verify VPC Route Table and NAT Gateway connectivity.

## Allow-Listed Remediation
1. Re-add missing outbound HTTPS (port 443) rule to the service security group.
2. Revert unauthorized security group changes to previous known-good state.
