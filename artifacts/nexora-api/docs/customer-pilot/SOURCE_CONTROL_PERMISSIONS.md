# Source Control Permissions

## Scope

- **Exactly one repository** per onboarding session (`owner/name`)
- Wildcard or organization-wide access is rejected

## Supported platforms

| Platform | API |
|----------|-----|
| GitHub | `https://api.github.com` |
| GitHub Enterprise | Your enterprise API base URL |
| Gitea | Gitea API base URL (GitHub-compatible) |

## Minimum read capabilities

| Capability | Purpose |
|------------|---------|
| Repository metadata | Confirm repository exists and is accessible |
| Branches | Baseline and assessment context |
| Commits | Read-only change context |

## Optional capabilities

| Capability | If unavailable |
|------------|----------------|
| Workflow / Actions history | **INSUFFICIENT_EVIDENCE** — not a connection failure if repository read works |

## Not requested during onboarding

- Repository write, admin, or delete
- Webhook creation
- Deploy keys with write access
- Pull request creation or merge
- Workflow dispatch or run triggering

Store credentials via the onboarding wizard only; tokens are encrypted and never displayed after submission.
