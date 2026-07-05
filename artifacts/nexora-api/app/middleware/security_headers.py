"""Enterprise HTTP security-headers middleware.

Adds the standard hardening response headers to every response:

  * ``Strict-Transport-Security`` (HSTS)      — production only
  * ``Content-Security-Policy`` (CSP)         — strict app policy; relaxed on docs
  * ``X-Frame-Options``                       — clickjacking protection
  * ``X-Content-Type-Options``                — MIME-sniffing protection
  * ``Referrer-Policy``
  * ``Permissions-Policy``
  * ``Cache-Control``                         — ``no-store`` for API/docs responses

Design goals
------------
* **Production vs development modes.** In production we emit HSTS and add
  ``upgrade-insecure-requests`` to the CSP. In development we omit HSTS (so plain
  ``http://localhost`` keeps working) and allow ``ws:``/``wss:`` in ``connect-src``
  for local tooling/hot-reload.
* **Do not break Swagger UI / ReDoc.** The default CSP is strict
  (``default-src 'self'``), which would block the CDN-hosted Swagger/ReDoc assets
  and their inline init scripts. Requests under the docs prefixes therefore
  receive a relaxed CSP that whitelists ``cdn.jsdelivr.net`` (+ Google Fonts for
  ReDoc) and the inline bootstrap scripts.
* **Do not fight the SPA.** The served dashboard uses inline ``style="…"``
  attributes, so ``style-src`` includes ``'unsafe-inline'``; its scripts are
  same-origin (``/app.js``), so ``script-src 'self'`` is sufficient.

The middleware never overwrites a ``Cache-Control`` header a route already set
(e.g. the dashboard's ``no-cache, must-revalidate``).
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def generate_nonce() -> str:
    """A fresh base64 CSP nonce (128 bits of entropy)."""
    return base64.b64encode(secrets.token_bytes(16)).decode("ascii")

_PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
    "encrypted-media=(), fullscreen=(self), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), midi=(), payment=(), usb=()"
)

_REFERRER_POLICY = "strict-origin-when-cross-origin"


def _csp(directives: dict[str, str]) -> str:
    """Serialize a CSP directive map to a header value (stable ordering)."""
    return "; ".join(f"{name} {value}".strip() for name, value in directives.items())


def _build_app_csp(
    *, production: bool, nonce: str | None = None, trusted_types: bool = False,
) -> str:
    """Strict CSP for the API + served dashboard (same-origin app).

    When ``nonce`` is provided the ``script-src`` carries a per-request nonce so
    inline bootstrap scripts can be allowed without ``'unsafe-inline'``. When
    ``trusted_types`` is set, DOM-XSS sinks are locked down via Trusted Types.
    """
    connect = "'self'" if production else "'self' ws: wss:"
    script_src = "'self'"
    if nonce:
        script_src = f"'self' 'nonce-{nonce}'"
    directives: dict[str, str] = {
        "default-src": "'self'",
        "base-uri": "'self'",
        "object-src": "'none'",
        "frame-ancestors": "'none'",
        "form-action": "'self'",
        # SPA serves inline style="" attributes; scripts are same-origin only.
        "script-src": script_src,
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: blob:",
        "font-src": "'self' data:",
        "connect-src": connect,
    }
    csp = _csp(directives)
    if trusted_types:
        csp += "; require-trusted-types-for 'script'; trusted-types default dompurify"
    if production:
        csp += "; upgrade-insecure-requests"
    return csp


def _build_docs_csp() -> str:
    """Relaxed CSP so Swagger UI and ReDoc (CDN + inline init) keep working."""
    directives: dict[str, str] = {
        "default-src": "'self'",
        "base-uri": "'self'",
        "object-src": "'none'",
        "frame-ancestors": "'none'",
        "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
        "img-src": "'self' data: https://cdn.jsdelivr.net https://fastapi.tiangolo.com",
        "font-src": "'self' data: https://fonts.gstatic.com",
        "worker-src": "'self' blob:",
        "connect-src": "'self'",
    }
    return _csp(directives)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach hardening headers to every response.

    Parameters
    ----------
    production:
        When True, emit HSTS and ``upgrade-insecure-requests``.
    base_path:
        API mount prefix (e.g. ``/nexora-api``). Used to (a) scope the
        ``no-store`` Cache-Control to API/docs responses and (b) detect the docs
        routes for the relaxed CSP.
    docs_paths:
        Explicit docs route prefixes. Defaults to ``<base_path>/docs`` and
        ``<base_path>/redoc``.
    enabled:
        Master switch; when False the middleware is a pass-through.
    hsts_max_age:
        ``Strict-Transport-Security`` max-age in seconds (production only).
    """

    def __init__(
        self,
        app,
        *,
        production: bool = False,
        base_path: str = "",
        docs_paths: Iterable[str] | None = None,
        enabled: bool = True,
        hsts_max_age: int = 63072000,
        csp_nonce: bool = False,
        trusted_types: bool = False,
    ):
        super().__init__(app)
        self._production = production
        self._enabled = enabled
        self._hsts_max_age = hsts_max_age
        self._csp_nonce = csp_nonce
        self._trusted_types = trusted_types
        self._base_path = (base_path or "").rstrip("/")
        if docs_paths is not None:
            self._docs_prefixes = tuple(docs_paths)
        else:
            self._docs_prefixes = (f"{self._base_path}/docs", f"{self._base_path}/redoc")
        # Precompute the static CSP for the common (no-nonce) path.
        self._app_csp = _build_app_csp(production=production, trusted_types=trusted_types)
        self._docs_csp = _build_docs_csp()

    def _is_docs(self, path: str) -> bool:
        return any(path == p or path.startswith(p + "/") or path.startswith(p) for p in self._docs_prefixes)

    async def dispatch(self, request: Request, call_next) -> Response:
        # CSP nonce: generate before the route runs so the response (e.g. the SPA
        # shell) can embed it via ``request.state.csp_nonce``.
        nonce = generate_nonce() if (self._csp_nonce and self._enabled) else None
        if nonce is not None:
            request.state.csp_nonce = nonce

        response = await call_next(request)
        if not self._enabled:
            return response

        path = request.url.path
        headers = response.headers

        # Content-Security-Policy — relaxed only on the API docs routes.
        if self._is_docs(path):
            headers["Content-Security-Policy"] = self._docs_csp
        elif nonce is not None:
            headers["Content-Security-Policy"] = _build_app_csp(
                production=self._production, nonce=nonce,
                trusted_types=self._trusted_types)
        else:
            headers["Content-Security-Policy"] = self._app_csp

        headers["X-Frame-Options"] = "DENY"
        headers["X-Content-Type-Options"] = "nosniff"
        headers["Referrer-Policy"] = _REFERRER_POLICY
        headers["Permissions-Policy"] = _PERMISSIONS_POLICY
        headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # HSTS only in production (ignored by browsers over plain HTTP anyway).
        if self._production:
            headers["Strict-Transport-Security"] = (
                f"max-age={self._hsts_max_age}; includeSubDomains; preload"
            )

        # Cache-Control: default API/docs responses to no-store so sensitive JSON
        # is never cached. Never override a header a route already set (e.g. the
        # dashboard's revalidation policy on static assets).
        if "cache-control" not in headers:
            if not self._base_path or path.startswith(self._base_path):
                headers["Cache-Control"] = "no-store"

        return response
