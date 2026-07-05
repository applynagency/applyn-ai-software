# AI Platform Operator (Sprint 64B)

Autonomous DevOps reasoning layer that **orchestrates** existing Nexora services — it does not duplicate engines.

## Architecture

`AIOperatorService` composes:

| Capability | Delegated To |
|------------|--------------|
| Platform signals | `DevOpsSREWorkspaceService`, `PlatformEngineeringService` |
| Recommendations | `ExplainabilityService` (SRE AI recommendations) |
| Learning | `MemoryService` (organization scope) |
| Execution | Existing delivery / PE / control-plane workflows via proposals |
| Events | `emit_event()` on the domain event bus |

## API

Prefix: `/v1/operator`

| Endpoint | Description |
|----------|-------------|
| `GET /dashboard` | Operator overview, findings, predictions, goal progress |
| `POST /analyze` | Run continuous platform analysis |
| `GET /recommendations` | List recommendations with evidence |
| `POST /recommendations/{id}/simulate` | Blast-radius simulation |
| `POST /recommendations/{id}/propose` | Create approval-gated action proposal |
| `POST /proposals/{id}/decide` | Approve or reject proposal |
| `GET /policies` | AI operational policies |
| `GET /goals` | Operational goals |
| `GET /history` | Operator timeline |
| `GET /learning` | Learning records |
| `GET /simulations` | Simulation history |
| `GET /savings` | Cost savings opportunities |
| `POST /executive/briefing` | Generate weekly executive summary |
| `GET /ai-context` | Copilot / agent context |

## Modes

- **OBSERVATION** — analyze only
- **RECOMMEND** — generate recommendations
- **APPROVAL_REQUIRED** — proposals need human approval (default)
- **FULLY_AUTOMATIC** — auto-execute when policy allows

## Events Published

- `OperatorRecommendationCreated`
- `OperatorApproved`
- `OperatorExecuted`
- `OperatorLearningUpdated`
- `OperatorGoalAchieved`
- `OperatorSimulationCompleted`

## Event Subscriptions (no polling)

Reacts to: `IncidentCreated`, `DeploymentFailed`, `TerraformDriftDetected`, `ProvisionCompleted`, `OpsDailyBriefing`, and related domain events.

## Configuration

- `AI_OPERATOR_ENABLED=true` (default)

## Database Tables (`op_*`)

- `op_policies`, `op_goals`, `op_recommendations`, `op_simulations`
- `op_action_proposals`, `op_timeline_entries`, `op_learning_records`
- `op_executive_briefings`

Migration: `0026_operator`

## AI Tools

- `operator.analyze`
- `operator.recommend`
- `operator.simulate`
- `operator.execute_proposal`
