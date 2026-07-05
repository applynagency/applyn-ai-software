# Customer-Facing Change Summary

**PROPOSED ONLY — NOT APPROVED — NOT EXECUTED**

Nexora proposes a controlled, reversible scale of deployment `pilot-demo` in namespace `nexora-pilot` (non-production).

Controlled internal pilot validation: scale deployment pilot-demo from 1 to 2 replicas in namespace nexora-pilot (non-production) using namespace-scoped Kubernetes RBAC.

Rollback: Scale replicas from 2 back to 1 in namespace nexora-pilot