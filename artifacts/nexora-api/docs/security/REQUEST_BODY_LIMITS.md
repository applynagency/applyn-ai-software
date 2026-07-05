# Request Body Size Limits

Nexora enforces a **global maximum request body size** so a single oversized
payload cannot exhaust API memory. Limits are applied in middleware before a
request reaches any route handler, and oversized requests are rejected with
**HTTP 413 Request Entity Too Large**.

This addresses a denial-of-service hardening finding (unbounded request bodies).

## Limits

The limit is selected by `Content-Type`:

| Content-Type   | Default limit | Setting                    |
| -------------- | ------------- | -------------------------- |
| `multipart/*`  | 100 MB        | `MAX_MULTIPART_BODY_BYTES` |
| everything else (JSON, form, text) | 5 MB | `MAX_JSON_BODY_BYTES` |

Multipart gets a larger budget because it carries file uploads; JSON and other
payloads use the smaller default.

## Per-route override

Any route can raise or lower its limit. Register an override by **path suffix**
(longest matching suffix wins):

```python
from app.middleware.body_limit import set_route_body_limit

# Allow a 50 MB JSON import on one endpoint only.
set_route_body_limit("/v1/imports/bulk", 50 * 1024 * 1024)

# Tighten a sensitive endpoint to 64 KB.
set_route_body_limit("/v1/auth/login", 64 * 1024)
```

Overrides can also be passed directly to the middleware as
`route_overrides={"/suffix": max_bytes}` (used in tests). A route override
applies regardless of `Content-Type`.

## How it is enforced

Two complementary layers:

1. **`Content-Length` fast path.** Well-behaved clients (browsers, `httpx`,
   `curl`, `fetch`) send `Content-Length`. When it exceeds the limit the request
   is rejected immediately with **413** — no body bytes are read. This is the
   primary, reliable mechanism.
2. **Streaming guard.** For chunked transfers, a missing, or an understated
   `Content-Length`, body bytes are counted as the route pulls them and the read
   is aborted the instant the limit is crossed. This bounds memory even for
   adversarial clients: at most one extra chunk beyond the limit is ever read.

   Note: when a route binds a Pydantic body model, FastAPI's own body parser
   wraps the aborted read and returns **400** ("error parsing the body") rather
   than 413 for this uncommon chunked-without-length case. The request is still
   rejected and memory is still bounded; only the status code differs. Routes
   that read the body directly (`await request.body()/json()`) return **413**.

## Response when rejected

```http
HTTP/1.1 413 Request Entity Too Large
Content-Type: application/json

{
  "detail": "Request payload too large.",
  "max_bytes": 5242880
}
```

## Configuration

Settings live in `app/core/config.py` (env-overridable):

| Setting                    | Default          | Purpose                                  |
| -------------------------- | ---------------- | ---------------------------------------- |
| `BODY_LIMIT_ENABLED`       | `true`           | Master switch for the middleware.        |
| `MAX_JSON_BODY_BYTES`      | `5242880` (5 MB) | Limit for JSON / form / other bodies.    |
| `MAX_MULTIPART_BODY_BYTES` | `104857600` (100 MB) | Limit for `multipart/*` uploads.     |

## Files

| File                                | Change                                                |
| ----------------------------------- | ----------------------------------------------------- |
| `app/middleware/body_limit.py`      | New — `BodyLimitMiddleware`, `set_route_body_limit`.  |
| `app/core/config.py`                | New `BODY_LIMIT_*` settings.                           |
| `app/main.py`                       | Registers `BodyLimitMiddleware` as the outermost middleware. |
| `app/tests/test_body_limit.py`      | Tests — fast path, streaming guard, content-type limits, overrides, 413, disabled. |

## Registration & ordering

`BodyLimitMiddleware` is registered **last** so it runs **outermost** and can
reject an oversized request with 413 before any other middleware buffers it.
Because it short-circuits at the edge, its 413 response does not carry the CSP /
HSTS security headers (those are added by an inner middleware); this is an
intentional trade-off for rejecting abusive payloads as early as possible.

## Migration notes

- **Backward compatible.** Default limits (5 MB JSON, 100 MB multipart) are well
  above normal request sizes; legitimate traffic is unaffected.
- To relax or tighten globally, set `MAX_JSON_BODY_BYTES` /
  `MAX_MULTIPART_BODY_BYTES`; for a single endpoint use `set_route_body_limit`.

## Testing

```bash
pytest app/tests/test_body_limit.py
```
