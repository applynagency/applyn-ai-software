"""Sprint 35A — Enterprise Credential & Secret Management security tests.

Validates:
- secrets encrypted at rest (AES-256-GCM envelope)
- no plaintext DB storage
- no secret leakage in API responses
- no secret leakage in audit events
- credential revocation works
- secret rotation works
- multi-tenant isolation works
- master key required
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.auth.org_context import OrgContext
from app.models.credential import DeploymentCredential, SecretAccessAudit
from app.models.organization import OrganizationRole
from app.models.user import User
from app.schemas.deployment import DeploymentOutput
from app.security.secrets import SecretManagerService
from app.security.secrets.crypto import (
    MasterKeyMissingError,
    SecretCipher,
    ensure_master_key,
)
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    setup_deployment_pipeline,
    switch_organization,
)

AZURE_SECRET = {
    "subscription_id": "sub-123",
    "tenant_id": "tenant-123",
    "client_id": "client-123",
    "client_secret": "SUPER-SECRET-AZURE-VALUE",
}
VM_SECRET = {
    "host": "10.0.0.5",
    "port": 22,
    "username": "ubuntu",
    "private_key": "-----BEGIN PRIVATE KEY-----VERYSECRETKEY-----END PRIVATE KEY-----",
}
K8S_SECRET = {"kubeconfig": "apiVersion: v1\nclusters:\n- cluster: {server: https://x}\n"}


async def _org_user(client, *, email, username, slug):
    safe_username = slug.replace("-", "_")
    _, tokens = await create_authenticated_user(client, email=email, username=safe_username)
    org = await create_organization(client, tokens["access_token"], name=slug, slug=slug)
    tokens = await switch_organization(client, tokens["access_token"], org["id"])
    return tokens, org["id"]


async def _create(client, token, provider="AZURE", name="prod", secret=None):
    return await client.post(
        "/v1/credentials",
        headers=auth_headers(token),
        json={"provider": provider, "name": name, "secret": secret or AZURE_SECRET},
    )


# --------------------------------------------------------------------------- #
# Crypto + startup
# --------------------------------------------------------------------------- #
def test_cipher_roundtrip_and_envelope():
    cipher = SecretCipher()
    token = cipher.encrypt("SUPER-SECRET-AZURE-VALUE")
    assert token.startswith("v1:")
    assert "SUPER-SECRET-AZURE-VALUE" not in token
    assert cipher.decrypt(token) == "SUPER-SECRET-AZURE-VALUE"


def test_cipher_tamper_detection():
    cipher = SecretCipher()
    token = cipher.encrypt("data")
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(Exception):
        cipher.decrypt(tampered)


def test_master_key_required():
    with patch.dict("os.environ", {}, clear=False) as _env:
        import os

        os.environ.pop("MASTER_ENCRYPTION_KEY", None)
        with patch("app.security.secrets.crypto.settings") as s:
            s.MASTER_ENCRYPTION_KEY = None
            with pytest.raises(MasterKeyMissingError):
                ensure_master_key()
    # restore for the rest of the suite
    import os

    os.environ["MASTER_ENCRYPTION_KEY"] = "test-master-encryption-key-for-pytest-only"


# --------------------------------------------------------------------------- #
# API: no secret leakage
# --------------------------------------------------------------------------- #
async def test_create_credential_never_returns_secret(client):
    tokens, _ = await _org_user(client, email="c1@x.com", username="c1", slug="cred-1")
    resp = await _create(client, tokens["access_token"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["provider"] == "AZURE"
    assert body["name"] == "prod"
    assert "last_used_at" in body
    # No secret material anywhere in the response.
    for leak in ("client_secret", "SUPER-SECRET-AZURE-VALUE", "secret", "encrypted_payload"):
        assert leak not in resp.text


async def test_get_and_list_never_return_secret(client):
    tokens, _ = await _org_user(client, email="c2@x.com", username="c2", slug="cred-2")
    cred_id = (await _create(client, tokens["access_token"])).json()["id"]

    got = await client.get(f"/v1/credentials/{cred_id}", headers=auth_headers(tokens["access_token"]))
    listed = await client.get("/v1/credentials", headers=auth_headers(tokens["access_token"]))
    assert got.status_code == 200 and listed.status_code == 200
    for text in (got.text, listed.text):
        assert "SUPER-SECRET-AZURE-VALUE" not in text
        assert "client_secret" not in text
        assert "encrypted_payload" not in text
    assert listed.json()["total"] == 1


async def test_validation_rejects_missing_fields(client):
    tokens, _ = await _org_user(client, email="c3@x.com", username="c3", slug="cred-3")
    resp = await client.post(
        "/v1/credentials",
        headers=auth_headers(tokens["access_token"]),
        json={"provider": "AZURE", "name": "bad", "secret": {"subscription_id": "x"}},
    )
    assert resp.status_code == 422
    assert "missing required fields" in resp.text


# --------------------------------------------------------------------------- #
# Encryption at rest / no plaintext
# --------------------------------------------------------------------------- #
async def test_secret_encrypted_at_rest(client):
    from app.database.session import AsyncSessionLocal

    tokens, _ = await _org_user(client, email="c4@x.com", username="c4", slug="cred-4")
    cred_id = (await _create(client, tokens["access_token"], secret=VM_SECRET, provider="VM")).json()["id"]

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(DeploymentCredential).where(DeploymentCredential.id == cred_id)
            )
        ).scalar_one()
        # Ciphertext envelope only — never the raw private key or any field name/value.
        assert row.encrypted_payload.startswith("v1:")
        assert "BEGIN PRIVATE KEY" not in row.encrypted_payload
        assert "VERYSECRETKEY" not in row.encrypted_payload
        assert "ubuntu" not in row.encrypted_payload
        # And the column set has no plaintext secret columns.
        col_names = {c.name for c in DeploymentCredential.__table__.columns}
        for forbidden in ("private_key", "client_secret", "kubeconfig", "secret_key", "password"):
            assert forbidden not in col_names


# --------------------------------------------------------------------------- #
# Rotation + revocation
# --------------------------------------------------------------------------- #
async def test_secret_rotation(client):
    from app.database.session import AsyncSessionLocal

    tokens, _ = await _org_user(client, email="c5@x.com", username="c5", slug="cred-5")
    cred_id = (await _create(client, tokens["access_token"])).json()["id"]

    async with AsyncSessionLocal() as session:
        before = (
            await session.execute(
                select(DeploymentCredential.encrypted_payload).where(
                    DeploymentCredential.id == cred_id
                )
            )
        ).scalar_one()

    new_secret = {**AZURE_SECRET, "client_secret": "ROTATED-SECRET-VALUE"}
    upd = await client.put(
        f"/v1/credentials/{cred_id}",
        headers=auth_headers(tokens["access_token"]),
        json={"secret": new_secret},
    )
    assert upd.status_code == 200
    assert "ROTATED-SECRET-VALUE" not in upd.text

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(DeploymentCredential).where(DeploymentCredential.id == cred_id)
            )
        ).scalar_one()
        assert row.encrypted_payload != before  # ciphertext changed
        cipher = SecretCipher()
        import json

        assert json.loads(cipher.decrypt(row.encrypted_payload))["client_secret"] == "ROTATED-SECRET-VALUE"

        events = {
            a.event
            for a in (
                await session.execute(
                    select(SecretAccessAudit).where(SecretAccessAudit.credential_id == cred_id)
                )
            ).scalars().all()
        }
        assert "SECRET_CREATED" in events
        assert "SECRET_UPDATED" in events


async def test_revocation_blocks_use(client):
    from app.database.session import AsyncSessionLocal

    tokens, org_id = await _org_user(client, email="c6@x.com", username="c6", slug="cred-6")
    me = await client.get("/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    user_id = me.json()["id"]
    cred_id = (await _create(client, tokens["access_token"])).json()["id"]

    revoke = await client.put(
        f"/v1/credentials/{cred_id}",
        headers=auth_headers(tokens["access_token"]),
        json={"is_active": False},
    )
    assert revoke.status_code == 200
    assert revoke.json()["is_active"] is False

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        ctx = OrgContext(user=user, organization_id=org_id, role=OrganizationRole.OWNER)
        service = SecretManagerService(session)
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            await service.resolve_secret(cred_id, user=user, org_context=ctx)

        events = {
            a.event
            for a in (
                await session.execute(
                    select(SecretAccessAudit).where(SecretAccessAudit.credential_id == cred_id)
                )
            ).scalars().all()
        }
        assert "SECRET_REVOKED" in events


async def test_delete_credential_audits_revoked(client):
    from app.database.session import AsyncSessionLocal

    tokens, _ = await _org_user(client, email="c7@x.com", username="c7", slug="cred-7")
    cred_id = (await _create(client, tokens["access_token"])).json()["id"]

    deleted = await client.delete(
        f"/v1/credentials/{cred_id}", headers=auth_headers(tokens["access_token"])
    )
    assert deleted.status_code == 204

    gone = await client.get(
        f"/v1/credentials/{cred_id}", headers=auth_headers(tokens["access_token"])
    )
    assert gone.status_code == 404

    async with AsyncSessionLocal() as session:
        events = (
            await session.execute(
                select(SecretAccessAudit).where(SecretAccessAudit.credential_id.is_(None))
            )
        ).scalars().all()
        # delete sets credential_id NULL via FK; ensure a REVOKED event exists overall
        all_events = (
            await session.execute(select(SecretAccessAudit))
        ).scalars().all()
        assert any(e.event == "SECRET_REVOKED" for e in all_events)


# --------------------------------------------------------------------------- #
# Audit events carry no secret material
# --------------------------------------------------------------------------- #
async def test_audit_events_contain_no_secret(client):
    from app.database.session import AsyncSessionLocal

    tokens, _ = await _org_user(client, email="c8@x.com", username="c8", slug="cred-8")
    await _create(client, tokens["access_token"], secret=VM_SECRET, provider="VM")

    async with AsyncSessionLocal() as session:
        audits = (await session.execute(select(SecretAccessAudit))).scalars().all()
        assert audits
        for a in audits:
            blob = f"{a.event}|{a.reason}|{a.deployment_id}"
            assert "BEGIN PRIVATE KEY" not in blob
            assert "VERYSECRETKEY" not in blob


# --------------------------------------------------------------------------- #
# Multi-tenant isolation
# --------------------------------------------------------------------------- #
async def test_multi_tenant_isolation(client):
    a_tokens, _ = await _org_user(client, email="ta@x.com", username="ta", slug="tenant-a")
    b_tokens, _ = await _org_user(client, email="tb@x.com", username="tb", slug="tenant-b")

    cred_id = (await _create(client, a_tokens["access_token"])).json()["id"]

    # Org B cannot read, update, or delete org A's credential.
    assert (await client.get(f"/v1/credentials/{cred_id}", headers=auth_headers(b_tokens["access_token"]))).status_code == 404
    assert (await client.put(f"/v1/credentials/{cred_id}", headers=auth_headers(b_tokens["access_token"]), json={"name": "x"})).status_code == 404
    assert (await client.delete(f"/v1/credentials/{cred_id}", headers=auth_headers(b_tokens["access_token"]))).status_code == 404

    # Org B's list is empty.
    b_list = await client.get("/v1/credentials", headers=auth_headers(b_tokens["access_token"]))
    assert b_list.json()["total"] == 0


# --------------------------------------------------------------------------- #
# Deployment integration: credential_id injects secret + audits SECRET_USED
# --------------------------------------------------------------------------- #
async def test_resolve_secret_decrypts_and_audits_used(client):
    from app.database.session import AsyncSessionLocal

    tokens, org_id = await _org_user(client, email="c9@x.com", username="c9", slug="cred-9")
    me = await client.get("/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    user_id = me.json()["id"]
    cred_id = (await _create(client, tokens["access_token"], secret=VM_SECRET, provider="VM")).json()["id"]

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        ctx = OrgContext(user=user, organization_id=org_id, role=OrganizationRole.OWNER)
        service = SecretManagerService(session)
        credential, payload = await service.resolve_secret(
            cred_id, user=user, org_context=ctx, deployment_id="dep-xyz"
        )
        await session.commit()
        assert payload["private_key"].startswith("-----BEGIN PRIVATE KEY")
        assert payload["host"] == "10.0.0.5"
        assert credential.last_used_at is not None

        used = (
            await session.execute(
                select(SecretAccessAudit).where(
                    SecretAccessAudit.credential_id == cred_id,
                    SecretAccessAudit.event == "SECRET_USED",
                )
            )
        ).scalars().all()
        assert used and used[0].deployment_id == "dep-xyz"


async def test_deploy_with_credential_id_injects_secret(client):
    from app.database.session import AsyncSessionLocal

    tokens, _ = await _org_user(client, email="c10@x.com", username="c10", slug="cred-10")
    token = tokens["access_token"]
    cred_id = (await _create(client, token, secret=VM_SECRET, provider="VM")).json()["id"]

    workspace = await create_workspace(client, token, slug="cred-ws")
    project = await create_project(client, token, workspace_id=workspace["id"], slug="cred-proj")
    requirement = await create_requirement(client, token, project_id=project["id"])
    await setup_deployment_pipeline(client, token, requirement["id"])

    captured: dict = {}
    vm_output = DeploymentOutput(
        deployment_provider="VM",
        deployment_status="DEPLOYED",
        live_url="http://10.0.0.5:8000",
        deployment_logs=["deployed"],
        rollback_available=True,
        deployment_metadata={"provider": "VM", "server_ip": "10.0.0.5"},
    )

    async def fake_run(**kwargs):
        captured.update(kwargs)
        return vm_output

    with patch(
        "app.services.deployment.DeploymentAgent.run",
        new=AsyncMock(side_effect=fake_run),
    ):
        resp = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(token),
            json={
                "requirement_id": requirement["id"],
                "deployment_provider": "VM",
                "credential_id": cred_id,
            },
        )
    assert resp.status_code == 201, resp.text
    deployment_id = resp.json()["id"]

    # The decrypted secret was injected into the provider's deployment_target,
    # and never appears in the API response.
    assert captured["deployment_target"]["private_key"].startswith("-----BEGIN PRIVATE KEY")
    assert captured["deployment_target"]["host"] == "10.0.0.5"
    assert "BEGIN PRIVATE KEY" not in resp.text

    async with AsyncSessionLocal() as session:
        used = (
            await session.execute(
                select(SecretAccessAudit).where(
                    SecretAccessAudit.credential_id == cred_id,
                    SecretAccessAudit.event == "SECRET_USED",
                )
            )
        ).scalars().all()
        assert any(u.deployment_id == deployment_id for u in used)
