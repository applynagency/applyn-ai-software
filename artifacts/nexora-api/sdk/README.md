# Nexora SDKs

These SDKs are generated automatically from the Nexora OpenAPI schema. Do not
edit the generated files by hand — run `python -m scripts.generate_sdk` after any
API change.

## Contents
- `openapi.json` — canonical OpenAPI document (use with any OpenAPI generator).
- `python/nexora_client/__init__.py` — Python client (requires `httpx`).
- `typescript/src/client.ts` — TypeScript client (uses `fetch`).

Every API operation is exposed as a method named after its `operationId`. The
generic `request(method, path, ...)` escape hatch is always available too.

## Python
```python
from nexora_client import NexoraClient

with NexoraClient("https://api.nexora.example/nexora-api", token="...") as nx:
    # generic call (always works):
    nx.request("GET", "/v1/platform/search", params={"q": "database"})
    # or the generated per-operation method:
    nx.global_search_nexora_api_v1_platform_search_get(params={"q": "database"})
```

## TypeScript
```ts
import { NexoraClient } from "./client";

const nx = new NexoraClient({ baseUrl: "https://api.nexora.example/nexora-api", token: "..." });
await nx.request("GET", "/v1/platform/search", { params: { q: "database" } });
```
