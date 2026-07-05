"""OIDC / OAuth2 authorization-code engine.

One standards-compliant engine drives Microsoft Entra ID, Okta, Google
Workspace, Ping and any generic OIDC provider. It performs discovery, builds the
authorization redirect (with PKCE + nonce), exchanges the code for tokens,
verifies the ID token signature against the provider JWKS, and normalizes the
result into :class:`SSOClaims`.

All outbound calls go through the SSRF-safe HTTP client.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
import structlog
from jose import jwt

from app.core.exceptions import UnauthorizedError
from app.models.sso import SSOConnection
from app.redis import cache
from app.security.secrets import get_cipher
from app.security.ssrf import safe_http_client
from app.services.sso import presets
from app.services.sso.claims import SSOClaims

logger = structlog.get_logger(__name__)

_HTTP_TIMEOUT = 10.0
_DISCOVERY_TTL = 3600
_JWKS_TTL = 3600


class OIDCError(UnauthorizedError):
    pass


def generate_pkce() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for PKCE S256."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class OIDCService:
    def __init__(self, connection: SSOConnection):
        self.connection = connection

    # --- discovery ----------------------------------------------------------

    async def discover(self) -> dict:
        """Resolve OIDC endpoints, preferring explicit connection config.

        If the connection already specifies the authorization/token/JWKS
        endpoints we use them directly; otherwise we fetch (and cache) the
        provider's ``.well-known/openid-configuration`` document.
        """
        c = self.connection
        if c.authorization_endpoint and c.token_endpoint and c.jwks_uri:
            return {
                "issuer": c.issuer,
                "authorization_endpoint": c.authorization_endpoint,
                "token_endpoint": c.token_endpoint,
                "jwks_uri": c.jwks_uri,
                "userinfo_endpoint": c.userinfo_endpoint,
            }

        disco_url = presets.discovery_url_for(c.issuer, c.discovery_url)
        if not disco_url:
            raise OIDCError("OIDC connection is missing issuer/discovery configuration")

        cache_key = f"sso:oidc:disco:{c.id}"
        cached = await cache.get(cache_key)
        if cached:
            return cached
        doc = await self._fetch_json(disco_url)
        await cache.set(cache_key, doc, ttl=_DISCOVERY_TTL)
        return doc

    async def _get_jwks(self) -> dict:
        disco = await self.discover()
        jwks_uri = disco.get("jwks_uri")
        if not jwks_uri:
            raise OIDCError("OIDC provider did not advertise a JWKS endpoint")
        cache_key = f"sso:oidc:jwks:{self.connection.id}"
        cached = await cache.get(cache_key)
        if cached:
            return cached
        jwks = await self._fetch_json(jwks_uri)
        await cache.set(cache_key, jwks, ttl=_JWKS_TTL)
        return jwks

    async def _fetch_json(self, url: str) -> dict:
        async with safe_http_client(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            return resp.json()

    # --- authorization request ---------------------------------------------

    async def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_challenge: str | None = None,
    ) -> str:
        disco = await self.discover()
        endpoint = disco.get("authorization_endpoint")
        if not endpoint:
            raise OIDCError("OIDC provider did not advertise an authorization endpoint")
        scopes = self.connection.scopes or presets.default_scopes(self.connection.provider)
        params = {
            "response_type": "code",
            "client_id": self.connection.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "nonce": nonce,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        sep = "&" if "?" in endpoint else "?"
        return f"{endpoint}{sep}{urlencode(params)}"

    # --- token exchange + verification --------------------------------------

    async def exchange_code(
        self, *, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> dict:
        disco = await self.discover()
        token_endpoint = disco.get("token_endpoint")
        if not token_endpoint:
            raise OIDCError("OIDC provider did not advertise a token endpoint")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.connection.client_id,
        }
        secret = self._client_secret()
        if secret:
            data["client_secret"] = secret
        if code_verifier:
            data["code_verifier"] = code_verifier
        async with safe_http_client(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(
                token_endpoint,
                data=data,
                headers={"Accept": "application/json"},
            )
        if resp.status_code >= 400:
            logger.warning("oidc_token_exchange_failed", status=resp.status_code)
            raise OIDCError("Token exchange with the identity provider failed")
        return resp.json()

    def verify_id_token(self, id_token: str, *, nonce: str | None, jwks: dict) -> dict:
        try:
            header = jwt.get_unverified_header(id_token)
        except Exception as exc:  # noqa: BLE001
            raise OIDCError("Malformed ID token") from exc

        kid = header.get("kid")
        alg = header.get("alg", "RS256")
        keys = jwks.get("keys", [])
        key = next((k for k in keys if k.get("kid") == kid), None)
        if key is None and keys:
            key = keys[0]
        if key is None:
            raise OIDCError("No signing key available to verify the ID token")

        options = {"verify_at_hash": False}
        issuer = self.connection.issuer
        try:
            claims = jwt.decode(
                id_token,
                key,
                algorithms=[alg],
                audience=self.connection.client_id,
                issuer=issuer if issuer else None,
                options={**options, "verify_iss": bool(issuer), "verify_aud": bool(self.connection.client_id)},
            )
        except Exception as exc:  # noqa: BLE001
            raise OIDCError("ID token signature or claims are invalid") from exc

        if nonce is not None and claims.get("nonce") != nonce:
            raise OIDCError("ID token nonce mismatch")
        return claims

    async def fetch_userinfo(self, access_token: str) -> dict:
        disco = await self.discover()
        endpoint = disco.get("userinfo_endpoint")
        if not endpoint:
            return {}
        try:
            async with safe_http_client(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.get(
                    endpoint, headers={"Authorization": f"Bearer {access_token}"}
                )
                if resp.status_code >= 400:
                    return {}
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("oidc_userinfo_failed", error=str(exc))
            return {}

    async def fetch_claims(
        self,
        *,
        code: str,
        redirect_uri: str,
        expected_nonce: str | None,
        code_verifier: str | None = None,
    ) -> SSOClaims:
        """Full callback path: exchange code, verify ID token, normalize claims."""
        tokens = await self.exchange_code(
            code=code, redirect_uri=redirect_uri, code_verifier=code_verifier
        )
        id_token = tokens.get("id_token")
        if not id_token:
            raise OIDCError("Identity provider did not return an ID token")
        jwks = await self._get_jwks()
        id_claims = self.verify_id_token(id_token, nonce=expected_nonce, jwks=jwks)

        userinfo: dict = {}
        access_token = tokens.get("access_token")
        if access_token and not id_claims.get(self.connection.email_claim):
            userinfo = await self.fetch_userinfo(access_token)
        return self.extract_claims(id_claims, userinfo)

    def extract_claims(self, id_claims: dict, userinfo: dict | None = None) -> SSOClaims:
        merged = {**(userinfo or {}), **id_claims}
        c = self.connection
        subject = str(merged.get(c.subject_claim) or merged.get("sub") or "")
        email = str(merged.get(c.email_claim) or merged.get("email") or "").lower()
        name = merged.get(c.name_claim) or merged.get("name")
        groups = _as_list(merged.get(c.groups_claim))
        if not subject:
            raise OIDCError("Identity provider response is missing a subject")
        return SSOClaims(
            subject=subject,
            email=email,
            full_name=name,
            groups=groups,
            raw=merged,
        )

    def _client_secret(self) -> str | None:
        if not self.connection.encrypted_client_secret:
            return None
        return get_cipher().decrypt(self.connection.encrypted_client_secret)


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return [str(value)]
