# Route Inventory

## Primary Customer Routes

- `/`
- `/applications`
- `/applications/create`
- `/builds`
- `/deployments`
- `/releases`
- `/change-requests`
- `/teams`
- `/organization`
- `/settings`

## Internal / Engineering Routes (retained)

- `/organizations`
- `/organizations/create`
- `/product-owner`
- `/business-analyst`
- `/backend-architect`
- `/backend-v1`
- `/backend-v2`
- `/backend-v3`
- `/backend-code-review`
- `/backend-execution`
- `/uiux`
- `/frontend-architect`
- `/frontend-v1`
- `/frontend-v2`
- `/frontend-v3`
- `/frontend-code-review`
- `/frontend-execution`
- `/fullstack-assembly`
- `/workflows`
- `/workflows/create`
- `/workflow-executions`
- `/workflow-templates`
- `/agents`
- `/agents/create`
- `/agent-templates`
- `/team-templates`
- `/approvals`

## Dynamic Detail Routes

- `/product-owner/:id`
- `/organizations/:id`
- `/teams/:id`
- `/workflows/:id`
- `/workflow-executions/:id`
- `/business-analyst/:id`
- `/backend-architect/:id`
- `/backend-v1/:id`
- `/backend-v2/:id`
- `/backend-v3/:id`
- `/backend-code-review/:id`
- `/backend-execution/:id`
- `/uiux/:id`
- `/frontend-architect/:id`
- `/frontend-v1/:id`
- `/frontend-v2/:id`
- `/frontend-v3/:id`
- `/frontend-code-review/:id`
- `/frontend-execution/:id`
- `/fullstack-assembly/:id`
- `/applications/:id`
- `/change-requests/:id`
- `/approvals/:id`
- `/deployments/:id`
- `/agents/:id`
- `/invitations/accept/:token` and `/invitations/accept?token=...`

## Notes

- Internal routes are intentionally preserved and not deleted.
- Customer IA is intended to be route-discoverable through primary nav, while internal routes are role-gated in navigation.

