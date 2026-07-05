# Rollback Runbook

**PROPOSED ONLY — NOT APPROVED — NOT EXECUTED**

Trigger: any verification failure or insufficient evidence

Action: Scale replicas from 2 back to 1 in namespace nexora-pilot

Re-verify deployment available replicas and pod readiness after rollback.