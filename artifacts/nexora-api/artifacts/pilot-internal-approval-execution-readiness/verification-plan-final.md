# APPROVED FOR INTERNAL PILOT — NOT EXECUTED — TYPED CONFIRMATION REQUIRED

# Verification Checklist

**PROPOSED ONLY — NOT APPROVED — NOT EXECUTED**

- [ ] deployment desired replicas = 2
- [ ] available replicas = 2
- [ ] both pods Ready
- [ ] no warning events attributable to the operation
- [ ] restart count does not increase unexpectedly
- [ ] Prometheus deployment available replicas query returns 2
- [ ] Failure watch: rollout does not reach 2 available replicas within configured timeout
- [ ] Failure watch: warning events show scheduling/image/probe failure
- [ ] Failure watch: Prometheus or Kubernetes evidence is unavailable