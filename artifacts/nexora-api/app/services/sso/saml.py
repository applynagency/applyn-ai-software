"""SAML 2.0 Service Provider engine.

Implements the SP side of SAML Web Browser SSO:

* SP metadata generation (for IdP onboarding)
* AuthnRequest via HTTP-Redirect binding (deflate + base64)
* Assertion Consumer Service (ACS): decode + XML-DSIG signature verification
  (``signxml``, against the configured IdP certificate) + condition validation
  (audience, time window) + identity/attribute extraction.

XML is parsed with a hardened lxml parser (no DTD, no network, no entity
expansion) to prevent XXE/billion-laughs, and only signature-verified content is
trusted for identity.
"""

from __future__ import annotations

import base64
import secrets
import zlib
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import structlog

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.models.sso import SSOConnection
from app.services.sso.claims import SSOClaims

logger = structlog.get_logger(__name__)

NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "md": "urn:oasis:names:tc:SAML:2.0:metadata",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}

_CLOCK_SKEW = timedelta(minutes=5)

# Common SAML attribute Names that carry an email, used as fallbacks when the
# connection's configured email attribute is absent.
_EMAIL_FALLBACKS = (
    "email",
    "mail",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    "urn:oid:0.9.2342.19200300.100.1.3",
)


class SAMLError(UnauthorizedError):
    pass


def _etree():
    """Lazy lxml import so OIDC-only deployments don't require the SAML libs."""
    try:
        from lxml import etree
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise SAMLError("SAML support requires the 'lxml' package") from exc
    return etree


def _hardened_parser():
    etree = _etree()
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )


def _parse_xml(data: bytes):
    etree = _etree()
    try:
        return etree.fromstring(data, parser=_hardened_parser())
    except etree.XMLSyntaxError as exc:
        raise SAMLError("Malformed SAML XML") from exc


def _normalize_cert(cert: str) -> str:
    cert = (cert or "").strip()
    if not cert:
        raise SAMLError("SAML connection is missing the IdP signing certificate")
    if "BEGIN CERTIFICATE" in cert:
        return cert
    body = "".join(cert.split())
    lines = "\n".join(body[i : i + 64] for i in range(0, len(body), 64))
    return f"-----BEGIN CERTIFICATE-----\n{lines}\n-----END CERTIFICATE-----\n"


def _parse_instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_idp_metadata(metadata_xml: str) -> dict:
    """Parse an IdP SAML metadata document into connection fields.

    Returns a dict with ``idp_entity_id``, ``idp_sso_url``, ``logout_url`` and
    ``idp_x509_cert`` (first signing certificate). Used by metadata import so an
    admin can paste/upload IdP metadata instead of typing each field.
    """
    if not metadata_xml or not metadata_xml.strip():
        raise SAMLError("Empty SAML metadata document")
    root = _parse_xml(metadata_xml.encode("utf-8"))

    entity_id = root.get("entityID")
    idp = root.find("./md:IDPSSODescriptor", NS)
    if idp is None:
        raise SAMLError("Metadata does not contain an IDPSSODescriptor")

    sso_url = None
    for sso in idp.findall("./md:SingleSignOnService", NS):
        binding = sso.get("Binding", "")
        location = sso.get("Location")
        if location and binding.endswith("HTTP-Redirect"):
            sso_url = location
            break
        if location and sso_url is None:
            sso_url = location

    logout_url = None
    for slo in idp.findall("./md:SingleLogoutService", NS):
        location = slo.get("Location")
        if location:
            logout_url = location
            if slo.get("Binding", "").endswith("HTTP-Redirect"):
                break

    cert = None
    for kd in idp.findall("./md:KeyDescriptor", NS):
        use = kd.get("use")
        if use not in (None, "signing"):
            continue
        x509 = kd.find("./ds:KeyInfo/ds:X509Data/ds:X509Certificate", NS)
        if x509 is not None and x509.text:
            cert = "".join(x509.text.split())
            break

    return {
        "idp_entity_id": entity_id,
        "idp_sso_url": sso_url,
        "logout_url": logout_url,
        "idp_x509_cert": cert,
    }


class SAMLService:
    def __init__(self, connection: SSOConnection):
        self.connection = connection

    # --- metadata / request -------------------------------------------------

    def sp_metadata(self, *, sp_entity_id: str, acs_url: str) -> str:
        etree = _etree()
        md = NS["md"]
        root = etree.Element(f"{{{md}}}EntityDescriptor", nsmap={"md": md})
        root.set("entityID", sp_entity_id)
        spsso = etree.SubElement(root, f"{{{md}}}SPSSODescriptor")
        spsso.set("protocolSupportEnumeration", "urn:oasis:names:tc:SAML:2.0:protocol")
        spsso.set("AuthnRequestsSigned", "false")
        spsso.set("WantAssertionsSigned", "true" if self.connection.want_assertions_signed else "false")
        acs = etree.SubElement(spsso, f"{{{md}}}AssertionConsumerService")
        acs.set("Binding", "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST")
        acs.set("Location", acs_url)
        acs.set("index", "0")
        acs.set("isDefault", "true")
        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode()

    def build_authn_request_redirect(self, *, acs_url: str, relay_state: str | None = None) -> str:
        if not self.connection.idp_sso_url:
            raise SAMLError("SAML connection is missing the IdP SSO URL")
        etree = _etree()
        samlp, saml = NS["samlp"], NS["saml"]
        req_id = "_" + secrets.token_hex(16)
        issue_instant = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        root = etree.Element(
            f"{{{samlp}}}AuthnRequest", nsmap={"samlp": samlp, "saml": saml}
        )
        root.set("ID", req_id)
        root.set("Version", "2.0")
        root.set("IssueInstant", issue_instant)
        root.set("Destination", self.connection.idp_sso_url)
        root.set("ProtocolBinding", "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST")
        root.set("AssertionConsumerServiceURL", acs_url)
        issuer = etree.SubElement(root, f"{{{saml}}}Issuer")
        issuer.text = self.connection.sp_entity_id or acs_url

        xml = etree.tostring(root, xml_declaration=False, encoding="UTF-8")
        # HTTP-Redirect binding: raw DEFLATE + base64 + urlencode.
        deflated = zlib.compress(xml)[2:-4]
        encoded = base64.b64encode(deflated).decode("ascii")
        params = {"SAMLRequest": encoded}
        if relay_state:
            params["RelayState"] = relay_state
        sep = "&" if "?" in self.connection.idp_sso_url else "?"
        return f"{self.connection.idp_sso_url}{sep}{urlencode(params)}"

    # --- ACS ----------------------------------------------------------------

    def parse_and_validate_response(
        self,
        saml_response_b64: str,
        *,
        acs_url: str | None = None,
        allow_idp_initiated: bool | None = None,
    ) -> SSOClaims:
        try:
            xml_bytes = base64.b64decode(saml_response_b64)
        except (ValueError, TypeError) as exc:
            raise SAMLError("SAMLResponse is not valid base64") from exc

        response = _parse_xml(xml_bytes)

        # IdP-initiated SSO sends an unsolicited response (no InResponseTo).
        if allow_idp_initiated is None:
            allow_idp_initiated = getattr(
                self.connection, "allow_idp_initiated", True
            )
        if not allow_idp_initiated and not response.get("InResponseTo"):
            raise SAMLError("Unsolicited (IdP-initiated) SAML responses are not allowed")

        self._check_status(response)

        assertion = self._verified_assertion(response, xml_bytes)
        self._validate_conditions(assertion, acs_url)
        return self._extract_claims(assertion)

    def _check_status(self, response) -> None:
        code = response.find("./samlp:Status/samlp:StatusCode", NS)
        if code is not None:
            value = code.get("Value", "")
            if value and not value.endswith(":Success"):
                raise SAMLError(f"SAML response status was not Success: {value}")

    def _verified_assertion(self, response, xml_bytes: bytes):
        """Return the assertion element, enforcing signature verification."""
        require_sig = self.connection.want_assertions_signed and not settings.SSO_ALLOW_UNSIGNED_SAML
        if not require_sig:
            assertion = response.find("./saml:Assertion", NS)
            if assertion is None:
                raise SAMLError("SAML response contained no assertion")
            return assertion

        from signxml import XMLVerifier

        # Certificate rotation: accept a signature from either the primary cert
        # or the staged "next" cert so IdP cert rollovers cause no downtime.
        candidates = [
            c for c in (self.connection.idp_x509_cert, self.connection.idp_x509_cert_next)
            if c and c.strip()
        ]
        if not candidates:
            raise SAMLError("SAML connection is missing the IdP signing certificate")
        result = None
        last_exc: Exception | None = None
        for raw_cert in candidates:
            try:
                result = XMLVerifier().verify(
                    xml_bytes, x509_cert=_normalize_cert(raw_cert)
                )
                break
            except Exception as exc:  # noqa: BLE001 - signxml raises many types
                last_exc = exc
        if result is None:
            logger.warning("saml_signature_invalid", error=str(last_exc))
            raise SAMLError(
                "SAML assertion signature verification failed"
            ) from last_exc

        signed = result.signed_xml
        if signed is None:
            raise SAMLError("SAML signature did not cover any element")
        tag = _etree().QName(signed).localname
        if tag == "Assertion":
            return signed
        # Signature covered the Response: locate the assertion within it.
        assertion = signed.find("./saml:Assertion", NS)
        if assertion is None:
            raise SAMLError("Signed SAML response contained no assertion")
        return assertion

    def _validate_conditions(self, assertion, acs_url: str | None) -> None:
        now = datetime.now(UTC)
        conditions = assertion.find("./saml:Conditions", NS)
        if conditions is not None:
            not_before = _parse_instant(conditions.get("NotBefore"))
            not_after = _parse_instant(conditions.get("NotOnOrAfter"))
            if not_before and now + _CLOCK_SKEW < not_before:
                raise SAMLError("SAML assertion is not yet valid")
            if not_after and now - _CLOCK_SKEW >= not_after:
                raise SAMLError("SAML assertion has expired")
            audiences = [
                a.text
                for a in conditions.findall(
                    "./saml:AudienceRestriction/saml:Audience", NS
                )
                if a.text
            ]
            expected = self.connection.sp_entity_id
            if expected and audiences and expected not in audiences:
                raise SAMLError("SAML assertion audience does not match the SP entity ID")

        confirm = assertion.find(
            "./saml:Subject/saml:SubjectConfirmation/saml:SubjectConfirmationData", NS
        )
        if confirm is not None:
            scd_not_after = _parse_instant(confirm.get("NotOnOrAfter"))
            if scd_not_after and now - _CLOCK_SKEW >= scd_not_after:
                raise SAMLError("SAML subject confirmation has expired")

    def _extract_claims(self, assertion) -> SSOClaims:
        c = self.connection
        name_id_el = assertion.find("./saml:Subject/saml:NameID", NS)
        name_id = name_id_el.text.strip() if name_id_el is not None and name_id_el.text else None

        attrs: dict[str, list[str]] = {}
        for attr in assertion.findall("./saml:AttributeStatement/saml:Attribute", NS):
            key = attr.get("Name") or attr.get("FriendlyName")
            if not key:
                continue
            values = [
                v.text.strip()
                for v in attr.findall("./saml:AttributeValue", NS)
                if v.text and v.text.strip()
            ]
            attrs[key] = values
            friendly = attr.get("FriendlyName")
            if friendly and friendly not in attrs:
                attrs[friendly] = values

        def first(name: str) -> str | None:
            vals = attrs.get(name)
            return vals[0] if vals else None

        email = first(c.email_claim)
        if not email:
            for fb in _EMAIL_FALLBACKS:
                email = first(fb)
                if email:
                    break
        if not email and name_id and "@" in name_id:
            email = name_id

        subject = first(c.subject_claim) or name_id
        if not subject:
            raise SAMLError("SAML assertion is missing a subject (NameID)")
        if not email:
            raise SAMLError("SAML assertion did not provide an email address")

        full_name = first(c.name_claim)
        groups = attrs.get(c.groups_claim, [])

        return SSOClaims(
            subject=str(subject),
            email=email.lower(),
            full_name=full_name,
            groups=list(groups),
            raw={"name_id": name_id, "attributes": attrs},
        )
