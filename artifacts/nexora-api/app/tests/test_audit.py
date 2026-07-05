"""Tests for tamper-evident audit logging.

Covers: per-organization hash chain (sequence + linkage), organization scoping,
filtering, CSV/JSON export, integrity verification (valid + tamper detection),
retention purge, ORM-level immutability, and access control.
"""

import csv
import io
import json

import pytest
from sqlalchemy import update

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditImmutableError, AuditLog
from app.repositories.audit import AuditLogRepository
from app.services.audit.hashing import row_hash

from .conftest import auth_headers, create_authenticated_user, create_organization

pytestmark = pytest.mark.asyncio


async def _owner_org(client, slug: str):
    _, tokens = await create_authenticated_user(
        client, email=f"{slug}@example.com", username=slug.replace("-", "_")
    )
    org = await create_organization(client, tokens["access_token"], name=slug, slug=slug)
    return org["context"]["access_token"], org["id"], tokens


async def _seed(org_id: str | None, items: list[dict]) -> list[str]:
    async with AsyncSessionLocal() as session:
        repo = AuditLogRepository(session)
        ids = []
        for item in items:
            row = await repo.log(organization_id=org_id, **item)
            ids.append(row.id)
        await session.commit()
        return ids


# --------------------------------------------------------------------------- #
# Hash chain
# --------------------------------------------------------------------------- #
async def test_chain_sequence_and_linkage(client):
    _, org_id, _ = await _owner_org(client, "audit-chain")
    await _seed(
        org_id,
        [
            {"action": "a.one", "resource_type": "thing"},
            {"action": "a.two", "resource_type": "thing"},
            {"action": "a.three", "resource_type": "thing"},
        ],
    )
    async with AsyncSessionLocal() as session:
        chain = await AuditLogRepository(session).list_chain(org_id)

    assert [r.sequence for r in chain] == [0, 1, 2]
    assert chain[0].prev_hash is None
    assert chain[1].prev_hash == chain[0].entry_hash
    assert chain[2].prev_hash == chain[1].entry_hash
    for r in chain:
        assert r.entry_hash == row_hash(r)


async def test_chains_are_per_organization(client):
    _, org_a, _ = await _owner_org(client, "audit-orga")
    _, org_b, _ = await _owner_org(client, "audit-orgb")
    await _seed(org_a, [{"action": "x", "resource_type": "t"}])
    await _seed(org_b, [{"action": "y", "resource_type": "t"}])

    async with AsyncSessionLocal() as session:
        repo = AuditLogRepository(session)
        chain_a = await repo.list_chain(org_a)
        chain_b = await repo.list_chain(org_b)

    assert len(chain_a) == 1 and chain_a[0].sequence == 0
    assert len(chain_b) == 1 and chain_b[0].sequence == 0
    # Independent genesis chains.
    assert chain_a[0].prev_hash is None and chain_b[0].prev_hash is None


# --------------------------------------------------------------------------- #
# API: listing, filtering, scoping
# --------------------------------------------------------------------------- #
async def test_list_is_org_scoped_and_filterable(client):
    token_a, org_a, _ = await _owner_org(client, "audit-scope-a")
    _, org_b, _ = await _owner_org(client, "audit-scope-b")
    await _seed(
        org_a,
        [
            {"action": "user.login", "resource_type": "user"},
            {"action": "incident.create", "resource_type": "incident"},
        ],
    )
    await _seed(org_b, [{"action": "user.login", "resource_type": "user"}])

    resp = await client.get("/v1/audit/logs", headers=auth_headers(token_a))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Only org A's rows (org creation itself may also have logged events for A).
    assert all(it["organization_id"] == org_a for it in body["items"])
    actions = {it["action"] for it in body["items"]}
    assert {"user.login", "incident.create"} <= actions

    filtered = await client.get(
        "/v1/audit/logs",
        headers=auth_headers(token_a),
        params={"resource_type": "incident"},
    )
    assert filtered.status_code == 200
    fitems = filtered.json()["items"]
    assert fitems and all(it["resource_type"] == "incident" for it in fitems)


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
async def test_export_json(client):
    token, org_id, _ = await _owner_org(client, "audit-exp-json")
    await _seed(org_id, [{"action": "e.json", "resource_type": "t"}])

    resp = await client.get(
        "/v1/audit/logs/export",
        headers=auth_headers(token),
        params={"format": "json", "action": "e.json"},
    )
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["action"] == "e.json"
    assert rows[0]["entry_hash"]


async def test_export_csv(client):
    token, org_id, _ = await _owner_org(client, "audit-exp-csv")
    await _seed(
        org_id,
        [
            {"action": "e.csv", "resource_type": "t", "details": {"k": "v"}},
        ],
    )

    resp = await client.get(
        "/v1/audit/logs/export",
        headers=auth_headers(token),
        params={"format": "csv", "action": "e.csv"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    reader = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(reader) == 1
    assert reader[0]["action"] == "e.csv"
    assert json.loads(reader[0]["details"]) == {"k": "v"}
    assert reader[0]["entry_hash"]


# --------------------------------------------------------------------------- #
# Integrity verification
# --------------------------------------------------------------------------- #
async def test_verify_valid_chain(client):
    token, org_id, _ = await _owner_org(client, "audit-verify-ok")
    await _seed(
        org_id,
        [{"action": f"v.{i}", "resource_type": "t"} for i in range(4)],
    )
    resp = await client.get("/v1/audit/verify", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True
    assert body["errors"] == []
    assert body["verified"] >= 4


async def test_verify_detects_content_tamper(client):
    token, org_id, ids_tokens = await _owner_org(client, "audit-tamper")
    ids = await _seed(
        org_id,
        [
            {"action": "t.one", "resource_type": "t"},
            {"action": "t.two", "resource_type": "t"},
            {"action": "t.three", "resource_type": "t"},
        ],
    )
    # Out-of-band modification via core UPDATE (bypasses ORM immutability guard,
    # simulating direct DB tampering) -> recomputed hash no longer matches.
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AuditLog)
            .where(AuditLog.id == ids[1])
            .values(details={"tampered": True})
        )
        await session.commit()

    resp = await client.get("/v1/audit/verify", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    error_ids = {e["id"] for e in body["errors"]}
    assert ids[1] in error_ids
    assert any(e["error"] == "hash_mismatch" for e in body["errors"])


async def test_verify_detects_deletion_breaks_link(client):
    token, org_id, _ = await _owner_org(client, "audit-del-link")
    ids = await _seed(
        org_id,
        [
            {"action": "d.one", "resource_type": "t"},
            {"action": "d.two", "resource_type": "t"},
            {"action": "d.three", "resource_type": "t"},
        ],
    )
    # Remove a middle entry via core DELETE -> link from the next entry breaks.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete

        await session.execute(delete(AuditLog).where(AuditLog.id == ids[1]))
        await session.commit()

    resp = await client.get("/v1/audit/verify", headers=auth_headers(token))
    body = resp.json()
    assert body["valid"] is False
    assert any(e["error"] == "broken_link" for e in body["errors"])


# --------------------------------------------------------------------------- #
# Retention
# --------------------------------------------------------------------------- #
async def test_retention_purge_removes_old_entries(client):
    from datetime import timedelta

    from app.database.base import utcnow

    su_token, org_id, _ = await _owner_org(client, "audit-retain")
    ids = await _seed(
        org_id,
        [
            {"action": "old", "resource_type": "t"},
            {"action": "new", "resource_type": "t"},
        ],
    )
    # Age the first entry beyond the retention window.
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AuditLog)
            .where(AuditLog.id == ids[0])
            .values(created_at=utcnow() - timedelta(days=400))
        )
        await session.commit()

    # Retention purge is superuser-only.
    async with AsyncSessionLocal() as session:
        from app.repositories.user import UserRepository

        user = await UserRepository(session).get_by_email("audit-retain@example.com")
        user.is_superuser = True
        session.add(user)
        await session.commit()

    resp = await client.post(
        "/v1/audit/retention/purge",
        headers=auth_headers(su_token),
        params={"days": 365, "organization_id": org_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted"] == 1

    async with AsyncSessionLocal() as session:
        remaining = await AuditLogRepository(session).list_chain(org_id)
    remaining_ids = {r.id for r in remaining}
    assert ids[0] not in remaining_ids
    assert ids[1] in remaining_ids


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #
async def test_orm_update_is_blocked(client):
    _, org_id, _ = await _owner_org(client, "audit-immut-upd")
    ids = await _seed(org_id, [{"action": "i.u", "resource_type": "t"}])

    with pytest.raises(AuditImmutableError):
        async with AsyncSessionLocal() as session:
            row = await session.get(AuditLog, ids[0])
            row.status = "mutated"
            await session.flush()


async def test_orm_delete_is_blocked(client):
    _, org_id, _ = await _owner_org(client, "audit-immut-del")
    ids = await _seed(org_id, [{"action": "i.d", "resource_type": "t"}])

    with pytest.raises(AuditImmutableError):
        async with AsyncSessionLocal() as session:
            row = await session.get(AuditLog, ids[0])
            await session.delete(row)
            await session.flush()


# --------------------------------------------------------------------------- #
# Access control
# --------------------------------------------------------------------------- #
async def test_owner_of_default_org_can_read(client):
    # Login auto-provisions a default organization with the user as OWNER, so the
    # default login token is org-scoped and authorized to read audit logs.
    _, tokens = await create_authenticated_user(
        client, email="audit-owner@example.com", username="auditowner"
    )
    resp = await client.get("/v1/audit/logs", headers=auth_headers(tokens["access_token"]))
    assert resp.status_code == 200, resp.text


async def test_non_admin_role_forbidden(client):
    owner_token, org_id, _ = await _owner_org(client, "audit-roles")
    dev_user, dev_tokens = await create_authenticated_user(
        client, email="audit-dev@example.com", username="auditdev"
    )
    add = await client.post(
        f"/v1/organizations/{org_id}/members",
        headers=auth_headers(owner_token),
        json={"user_id": dev_user["id"], "role": "DEVELOPER"},
    )
    assert add.status_code == 201, add.text

    switched = await client.post(
        f"/v1/organizations/{org_id}/switch",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    dev_org_token = switched.json()["access_token"]

    resp = await client.get("/v1/audit/logs", headers=auth_headers(dev_org_token))
    assert resp.status_code == 403
