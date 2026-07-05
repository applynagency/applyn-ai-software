# HTTP Security Headers

Enterprise hardening headers added to **every** response by
`app/middleware/security_headers.py` (`SecurityHeadersMiddleware`). Closes audit
finding **F-SEC3** (no security headers).

## Headers emitted

| Header | Value | Notes |
|---|---|---|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` | **Production only** (configurable max-age). |
| `Content-Security-Policy` | strict app policy / relaxed docs policy | See below. |
| `X-Frame-Options` | `DENY` | Clickjacking protection. |
| `X-Content-Type-Options` | `nosniff` | MIME-sniffing protection. |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | |
| `Permissions-Policy` | camera/mic/geo/usb/payment/… all `()` ; `fullscreen=(self)` | Disables powerful features. |
| `Cross-Origin-Opener-Policy` | `same-origin` | Cross-origin isolation. |
| `Cache-Control` | `no-store` | Only on API/docs responses; never overwrites a route's own value. |

## Content-Security-Policy

**App policy (API + served dashboard)** — strict:
```
default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none';
form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'
```
- `style-src 'unsafe-inline'` is required because the dashboard SPA uses inline
  `style="…"` attributes; **scripts are same-origin only** (no `'unsafe-inline'`).
- Production adds `upgrade-insecure-requests`.

**Docs policy (`<base_path>/docs`, `/redoc`)** — relaxed so Swagger UI / ReDoc
(CDN assets + inline bootstrap + ReDoc web worker) keep working:
```
script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
style-src  'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com;
img-src    'self' data: https://cdn.jsdelivr.net https://fastapi.tiangolo.com;
font-src   'self' data: https://fonts.gstatic.com;
worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; ...
```

## Production vs development

| | Production (`ENVIRONMENT=production`) | Development |
|---|---|---|
| HSTS | emitted | omitted (so `http://localhost` works) |
| `upgrade-insecure-requests` | on | off |
| `connect-src` | `'self'` | `'self' ws: wss:` (hot-reload/tooling) |

## Configuration (`app/core/config.py`)

| Setting | Default | Meaning |
|---|---|---|
| `SECURITY_HEADERS_ENABLED` | `True` | Master switch; `False` = pass-through. |
| `HSTS_MAX_AGE` | `63072000` | HSTS `max-age` seconds (production only). |

## Registration

Registered automatically in `app/main.py` after CORS, so it runs outermost and
stamps every response (API, docs, dashboard):
```python
app.add_middleware(
    SecurityHeadersMiddleware,
    production=settings.ENVIRONMENT.lower() == "production",
    base_path=BASE_PATH,
    enabled=settings.SECURITY_HEADERS_ENABLED,
    hsts_max_age=settings.HSTS_MAX_AGE,
)
```

## Files changed
- `app/middleware/security_headers.py` — **new** middleware.
- `app/main.py` — registration.
- `app/core/config.py` — `SECURITY_HEADERS_ENABLED`, `HSTS_MAX_AGE`.
- `app/tests/test_security_headers.py` — **new** tests.

## Tests & verification
`python -m pytest app/tests/test_security_headers.py -q` → 10 passed.

End-to-end against the real app (production mode) confirmed:
- `/nexora-api/health` → strict CSP, HSTS, `Cache-Control: no-store`.
- `/nexora-api/docs` → **Swagger UI renders** (relaxed CSP allows `cdn.jsdelivr.net`).
- `/` dashboard → security headers applied; the SPA's own
  `Cache-Control: no-cache, must-revalidate` is preserved (not overwritten).
