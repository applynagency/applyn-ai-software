"""SCIM error envelope (RFC 7644 §3.12)."""

from __future__ import annotations

ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


class ScimError(Exception):
    """A SCIM protocol error carrying an HTTP status and optional scimType."""

    def __init__(self, status_code: int, detail: str, scim_type: str | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.scim_type = scim_type

    def to_body(self) -> dict:
        return scim_error_body(self.status_code, self.detail, self.scim_type)


def scim_error_body(status_code: int, detail: str, scim_type: str | None = None) -> dict:
    body: dict = {
        "schemas": [ERROR_SCHEMA],
        "detail": detail,
        "status": str(status_code),
    }
    if scim_type:
        body["scimType"] = scim_type
    return body
