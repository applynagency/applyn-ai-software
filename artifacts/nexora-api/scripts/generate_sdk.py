"""Generate Nexora SDKs from the live FastAPI OpenAPI schema (Sprint 62A).

Produces, under ``sdk/``:

* ``sdk/openapi.json``                       — the canonical OpenAPI 3.1 document
* ``sdk/python/nexora_client/__init__.py``   — a typed-ish Python client (httpx)
* ``sdk/typescript/src/client.ts``           — a TypeScript client (fetch)
* ``sdk/README.md``                          — usage notes

The clients are generated automatically from the API: one method per operation
(``operationId``), so they always track the real surface. Run::

    python -m scripts.generate_sdk
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK_DIR = ROOT / "sdk"


def _load_openapi() -> dict:
    from app.main import app

    return app.openapi()


def _snake(name: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_")
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return name.lower()


def _operations(schema: dict) -> list[dict]:
    ops: list[dict] = []
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            op_id = op.get("operationId") or _snake(f"{method}_{path}")
            params = op.get("parameters", [])
            path_params = [p["name"] for p in params if p.get("in") == "path"]
            query_params = [p["name"] for p in params if p.get("in") == "query"]
            has_body = "requestBody" in op
            ops.append({
                "name": _snake(op_id),
                "method": method.upper(),
                "path": path,
                "path_params": path_params,
                "query_params": query_params,
                "has_body": has_body,
                "summary": op.get("summary", ""),
                "tags": op.get("tags", []),
            })
    ops.sort(key=lambda o: o["name"])
    return ops


# --------------------------------------------------------------------------- #
# Python client
# --------------------------------------------------------------------------- #
_PY_HEADER = '''"""Auto-generated Nexora Python SDK. Do not edit by hand.

Regenerate with ``python -m scripts.generate_sdk``.
"""

from __future__ import annotations

from typing import Any

import httpx


class NexoraClient:
    def __init__(self, base_url: str, token: str | None = None,
                 *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(base_url=self.base_url, headers=headers,
                                    timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "NexoraClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(self, method: str, path: str, *, params: dict | None = None,
                json: Any = None) -> Any:
        resp = self._client.request(method, path, params=params, json=json)
        resp.raise_for_status()
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.text
'''


def _py_method(op: dict) -> str:
    args = ["self"]
    for p in op["path_params"]:
        args.append(f"{_snake(p)}: str")
    extra = []
    if op["query_params"]:
        extra.append("params: dict | None = None")
    if op["has_body"]:
        extra.append("json: Any = None")
    if extra:
        args.append("*")
        args.extend(extra)
    sig = ", ".join(args)

    path_expr = '"' + op["path"] + '"'
    if op["path_params"]:
        fmt_args = ", ".join(f"{p}={_snake(p)}" for p in op["path_params"])
        path_expr = '"' + op["path"] + f'".format({fmt_args})'

    call = [f'"{op["method"]}"', path_expr]
    if op["query_params"]:
        call.append("params=params")
    if op["has_body"]:
        call.append("json=json")
    body = f"        return self.request({', '.join(call)})"
    doc = f'        """{op["summary"] or op["name"]}"""' if op["summary"] else ""
    lines = [f"    def {op['name']}({sig}) -> Any:"]
    if doc:
        lines.append(doc)
    lines.append(body)
    return "\n".join(lines)


def _generate_python(ops: list[dict]) -> str:
    methods = "\n\n".join(_py_method(op) for op in ops)
    return _PY_HEADER + "\n" + methods + "\n"


# --------------------------------------------------------------------------- #
# TypeScript client
# --------------------------------------------------------------------------- #
_TS_HEADER = """// Auto-generated Nexora TypeScript SDK. Do not edit by hand.
// Regenerate with `python -m scripts.generate_sdk`.

export interface NexoraClientOptions {
  baseUrl: string;
  token?: string;
}

export class NexoraClient {
  private baseUrl: string;
  private token?: string;

  constructor(opts: NexoraClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\\/$/, "");
    this.token = opts.token;
  }

  async request<T = unknown>(
    method: string,
    path: string,
    opts: { params?: Record<string, unknown>; body?: unknown } = {}
  ): Promise<T> {
    const url = new URL(this.baseUrl + path);
    if (opts.params) {
      for (const [k, v] of Object.entries(opts.params)) {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
      }
    }
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const res = await fetch(url.toString(), {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
    if (!res.ok) throw new Error(`Nexora API ${res.status}: ${await res.text()}`);
    const ct = res.headers.get("content-type") || "";
    return (ct.includes("application/json") ? await res.json() : await res.text()) as T;
  }
"""


def _ts_method(op: dict) -> str:
    params: list[str] = []
    for p in op["path_params"]:
        params.append(f"{_snake(p)}: string")
    opt_fields = []
    if op["query_params"]:
        opt_fields.append("params?: Record<string, unknown>")
    if op["has_body"]:
        opt_fields.append("body?: unknown")
    if opt_fields:
        params.append("opts: { " + "; ".join(opt_fields) + " } = {}")
    sig = ", ".join(params)

    path_template = op["path"]
    for p in op["path_params"]:
        path_template = path_template.replace("{" + p + "}", "${" + _snake(p) + "}")
    path_expr = "`" + path_template + "`"

    opts_obj = []
    if op["query_params"]:
        opts_obj.append("params: opts.params")
    if op["has_body"]:
        opts_obj.append("body: opts.body")
    opts_expr = ", { " + ", ".join(opts_obj) + " }" if opts_obj else ""

    name = _camel(op["name"])
    return (f"  {name}({sig}) {{\n"
            f'    return this.request("{op["method"]}", {path_expr}{opts_expr});\n'
            f"  }}")


def _camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _generate_typescript(ops: list[dict]) -> str:
    methods = "\n\n".join(_ts_method(op) for op in ops)
    return _TS_HEADER + "\n" + methods + "\n}\n"


_README = """# Nexora SDKs

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
"""


def generate(write: bool = True) -> dict[str, str]:
    """Return a mapping of ``relative_path -> file_content`` for every SDK artifact.

    When ``write`` is true the files are also written to disk under ``sdk/``.
    The returned dict additionally contains an ``operations`` key with the count
    of API operations the SDKs were generated from.
    """
    schema = _load_openapi()
    ops = _operations(schema)
    artifacts = {
        "operations": str(len(ops)),
        "sdk/openapi.json": json.dumps(schema, indent=2, sort_keys=True),
        "sdk/python/nexora_client/__init__.py": _generate_python(ops),
        "sdk/typescript/src/client.ts": _generate_typescript(ops),
        "sdk/README.md": _README,
    }
    if write:
        for rel, content in artifacts.items():
            if rel == "operations":
                continue
            target = ROOT / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
    return artifacts


if __name__ == "__main__":
    out = generate(write=True)
    print(f"Generated SDKs from {out['operations']} operations:")
    for key in ("sdk/openapi.json", "sdk/python/nexora_client/__init__.py",
                "sdk/typescript/src/client.ts", "sdk/README.md"):
        print(f"  - {key} ({len(out[key])} bytes)")
