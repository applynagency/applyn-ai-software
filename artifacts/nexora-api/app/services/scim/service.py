"""SCIM 2.0 provisioning service.

Implements the org-scoped resource lifecycle for Users and Groups: create / read
/ list (with equality filter + pagination) / replace (PUT) / partial update
(PATCH) / delete, plus Bulk. Deactivate/reactivate is the standard SCIM
``active`` attribute and is mirrored to the global ``users.is_active`` flag so a
deprovisioned user can no longer sign in.

SCIM Group membership drives the member's organization role: a group's role is
resolved from the organization's SSO role mappings (by group display name), and
each member's ``OrganizationMember.role`` is set to the strongest role among the
groups they belong to.
"""

from __future__ import annotations

import re

import structlog
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database.base import utcnow
from app.models.organization import OrganizationRole
from app.repositories.organization import OrganizationMemberRepository
from app.repositories.scim import (
    ScimGroupMemberRepository,
    ScimGroupRepository,
    ScimUserRepository,
)
from app.repositories.sso import SSOConnectionRepository
from app.repositories.user import UserRepository
from app.services.scim.auth import ScimContext
from app.services.scim.errors import ScimError

logger = structlog.get_logger(__name__)

_ROLE_PRIORITY = [
    OrganizationRole.VIEWER,
    OrganizationRole.DEVELOPER,
    OrganizationRole.PROJECT_MANAGER,
    OrganizationRole.ADMIN,
    OrganizationRole.OWNER,
]


def _as_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _coerce_role(value: str | None) -> OrganizationRole | None:
    if not value:
        return None
    try:
        return OrganizationRole(str(value).upper())
    except ValueError:
        return None


class ScimService:
    def __init__(self, context: ScimContext):
        self.ctx = context
        self.session = context.session
        self.org_id = context.organization_id
        self.users = ScimUserRepository(self.session)
        self.groups = ScimGroupRepository(self.session)
        self.members = ScimGroupMemberRepository(self.session)
        self.org_members = OrganizationMemberRepository(self.session)
        self.user_repo = UserRepository(self.session)
        self.sso_repo = SSOConnectionRepository(self.session)

    # --- Users --------------------------------------------------------------

    async def create_user(self, payload: dict):
        user_name = (payload.get("userName") or "").strip().lower()
        if not user_name:
            raise ScimError(400, "userName is required", "invalidValue")
        if await self.users.get_by_username(self.org_id, user_name):
            raise ScimError(409, "User already exists", "uniqueness")

        name = payload.get("name") or {}
        active = _as_bool(payload.get("active"), True)
        given = name.get("givenName")
        family = name.get("familyName")
        display = payload.get("displayName") or name.get("formatted")

        user = await self._get_or_create_global_user(
            user_name, display or " ".join(p for p in [given, family] if p) or user_name
        )
        await self._set_user_active(user, active)
        await self._ensure_org_membership(user.id)

        scim_user = await self.users.create(
            organization_id=self.org_id,
            user_id=user.id,
            user_name=user_name,
            external_id=payload.get("externalId"),
            active=active,
            given_name=given,
            family_name=family,
            display_name=display,
            raw=payload,
        )
        logger.info("scim_user_created", org=self.org_id, user_name=user_name)
        return scim_user

    async def get_user(self, scim_id: str):
        scim_user = await self.users.get_scoped(self.org_id, scim_id)
        if scim_user is None:
            raise ScimError(404, "User not found")
        return scim_user

    async def list_users(self, *, filter_str, start_index, count):
        from app.services.scim.filters import parse_eq_filter

        user_name = external_id = None
        parsed = parse_eq_filter(filter_str)
        if parsed:
            attr, value = parsed
            attr_l = attr.lower()
            if attr_l == "username":
                user_name = value.lower()
            elif attr_l == "externalid":
                external_id = value
        offset = max(start_index - 1, 0)
        return await self.users.list_filtered(
            self.org_id,
            user_name=user_name,
            external_id=external_id,
            offset=offset,
            limit=count,
        )

    async def replace_user(self, scim_id: str, payload: dict):
        scim_user = await self.get_user(scim_id)
        name = payload.get("name") or {}
        active = _as_bool(payload.get("active"), scim_user.active)
        new_username = (payload.get("userName") or scim_user.user_name).strip().lower()
        if new_username != scim_user.user_name and await self.users.get_by_username(
            self.org_id, new_username
        ):
            raise ScimError(409, "User already exists", "uniqueness")

        await self.users.update(
            scim_user,
            user_name=new_username,
            external_id=payload.get("externalId"),
            active=active,
            given_name=name.get("givenName"),
            family_name=name.get("familyName"),
            display_name=payload.get("displayName") or name.get("formatted"),
            raw=payload,
        )
        await self._apply_user_side_effects(scim_user, new_username, active)
        return scim_user

    async def patch_user(self, scim_id: str, operations: list[dict]):
        scim_user = await self.get_user(scim_id)
        for op in operations:
            self._apply_user_patch_op(scim_user, op)
        scim_user.updated_at = utcnow()
        self.session.add(scim_user)
        await self.session.flush()
        await self._apply_user_side_effects(
            scim_user, scim_user.user_name, scim_user.active
        )
        return scim_user

    def _apply_user_patch_op(self, scim_user, op: dict) -> None:
        operation = (op.get("op") or "").lower()
        path = (op.get("path") or "").strip()
        value = op.get("value")

        if operation not in ("add", "replace", "remove"):
            raise ScimError(400, f"Unsupported PATCH op '{operation}'", "invalidSyntax")

        # No path: value is an attribute bag (Microsoft Entra style).
        if not path and isinstance(value, dict):
            for key, val in value.items():
                self._set_user_attr(scim_user, key, val, removing=False)
            return

        removing = operation == "remove"
        self._set_user_attr(scim_user, path, value, removing=removing)

    def _set_user_attr(self, scim_user, path: str, value, *, removing: bool) -> None:
        key = path.lower()
        if key == "active":
            scim_user.active = False if removing else _as_bool(value, True)
        elif key in ("username", "username.value"):
            if not removing and value:
                scim_user.user_name = str(value).strip().lower()
        elif key == "externalid":
            scim_user.external_id = None if removing else value
        elif key in ("name.givenname",):
            scim_user.given_name = None if removing else value
        elif key in ("name.familyname",):
            scim_user.family_name = None if removing else value
        elif key in ("displayname",):
            scim_user.display_name = None if removing else value
        # Unknown attributes are ignored (SCIM allows partial support).

    async def delete_user(self, scim_id: str) -> None:
        scim_user = await self.get_user(scim_id)
        user_id = scim_user.user_id
        await self.users.hard_delete(scim_user)

        membership = await self.org_members.get_membership(self.org_id, user_id)
        if membership:
            await self.org_members.hard_delete(membership)

        # Deactivate the global account if it is no longer SCIM-managed anywhere.
        others = await self._count_scim_users_for(user_id)
        if others == 0:
            user = await self.user_repo.get_by_id(user_id)
            if user:
                await self._set_user_active(user, False)

    # --- Groups -------------------------------------------------------------

    async def create_group(self, payload: dict):
        display_name = (payload.get("displayName") or "").strip()
        if not display_name:
            raise ScimError(400, "displayName is required", "invalidValue")
        if await self.groups.get_by_display_name(self.org_id, display_name):
            raise ScimError(409, "Group already exists", "uniqueness")

        role = await self._resolve_group_role(display_name)
        group = await self.groups.create(
            organization_id=self.org_id,
            display_name=display_name,
            external_id=payload.get("externalId"),
            mapped_role=role,
            raw=payload,
        )
        member_ids = self._member_ids(payload.get("members"))
        await self._add_members(group, member_ids)
        return group

    async def get_group(self, scim_id: str):
        group = await self.groups.get_scoped(self.org_id, scim_id)
        if group is None:
            raise ScimError(404, "Group not found")
        return group

    async def list_groups(self, *, filter_str, start_index, count):
        from app.services.scim.filters import parse_eq_filter

        display_name = external_id = None
        parsed = parse_eq_filter(filter_str)
        if parsed:
            attr, value = parsed
            attr_l = attr.lower()
            if attr_l == "displayname":
                display_name = value
            elif attr_l == "externalid":
                external_id = value
        offset = max(start_index - 1, 0)
        return await self.groups.list_filtered(
            self.org_id,
            display_name=display_name,
            external_id=external_id,
            offset=offset,
            limit=count,
        )

    async def replace_group(self, scim_id: str, payload: dict):
        group = await self.get_group(scim_id)
        new_name = (payload.get("displayName") or group.display_name).strip()
        affected = {m.scim_user_id for m in await self.members.list_for_group(group.id)}

        await self.groups.update(
            group,
            display_name=new_name,
            external_id=payload.get("externalId"),
            mapped_role=await self._resolve_group_role(new_name),
            raw=payload,
        )
        # Replace membership entirely.
        for m in await self.members.list_for_group(group.id):
            await self.members.hard_delete(m)
        new_ids = self._member_ids(payload.get("members"))
        await self._add_members(group, new_ids, recompute=False)

        affected |= set(new_ids)
        await self._recompute_roles(affected)
        return group

    async def patch_group(self, scim_id: str, operations: list[dict]):
        group = await self.get_group(scim_id)
        affected: set[str] = set()
        for op in operations:
            affected |= await self._apply_group_patch_op(group, op)
        group.updated_at = utcnow()
        self.session.add(group)
        await self.session.flush()
        await self._recompute_roles(affected)
        return group

    async def _apply_group_patch_op(self, group, op: dict) -> set[str]:
        operation = (op.get("op") or "").lower()
        path = (op.get("path") or "").strip()
        value = op.get("value")
        if operation not in ("add", "replace", "remove"):
            raise ScimError(400, f"Unsupported PATCH op '{operation}'", "invalidSyntax")

        path_l = path.lower()
        if path_l in ("displayname", "") and isinstance(value, dict):
            new_name = value.get("displayName")
            if new_name:
                group.display_name = new_name.strip()
                group.mapped_role = await self._resolve_group_role(group.display_name)
            return set()
        if path_l == "displayname":
            group.display_name = str(value).strip()
            group.mapped_role = await self._resolve_group_role(group.display_name)
            return set()

        # members operations
        if path_l == "members" or path_l.startswith("members["):
            return await self._patch_group_members(group, operation, path, value)
        return set()

    async def _patch_group_members(self, group, operation, path, value) -> set[str]:
        affected: set[str] = set()
        # Okta-style filtered remove: members[value eq "<id>"]
        match = re.search(r'members\[\s*value\s+eq\s+"([^"]+)"\s*\]', path, re.IGNORECASE)
        if operation == "remove" and match:
            uid = match.group(1)
            await self._remove_members(group, [uid])
            return {uid}

        ids = self._member_ids(value)
        if operation == "add":
            await self._add_members(group, ids, recompute=False)
            affected |= set(ids)
        elif operation == "replace":
            existing = {m.scim_user_id for m in await self.members.list_for_group(group.id)}
            for m in await self.members.list_for_group(group.id):
                await self.members.hard_delete(m)
            await self._add_members(group, ids, recompute=False)
            affected |= existing | set(ids)
        elif operation == "remove":
            if ids:
                await self._remove_members(group, ids)
                affected |= set(ids)
            else:
                existing = {m.scim_user_id for m in await self.members.list_for_group(group.id)}
                for m in await self.members.list_for_group(group.id):
                    await self.members.hard_delete(m)
                affected |= existing
        return affected

    async def delete_group(self, scim_id: str) -> None:
        group = await self.get_group(scim_id)
        affected = {m.scim_user_id for m in await self.members.list_for_group(group.id)}
        await self.groups.hard_delete(group)
        await self._recompute_roles(affected)

    async def members_of(self, group) -> list[tuple[str, str]]:
        """Return ``(scim_user_id, user_name)`` for each group member."""
        out: list[tuple[str, str]] = []
        for m in await self.members.list_for_group(group.id):
            scim_user = await self.users.get_by_id(m.scim_user_id)
            if scim_user:
                out.append((scim_user.id, scim_user.user_name))
        return out

    # --- Bulk ---------------------------------------------------------------

    async def process_bulk(
        self, operations: list[dict], *, fail_on_errors: int | None = None
    ) -> list[dict]:
        results: list[dict] = []
        error_count = 0
        for op in operations:
            method = (op.get("method") or "").upper()
            path = op.get("path") or ""
            result: dict = {"method": method, "bulkId": op.get("bulkId")}
            try:
                rtype, rid, status = await self._dispatch_bulk(
                    method, path, op.get("data") or {}
                )
                result["status"] = str(status)
                if rtype:
                    result["_resource_type"] = rtype
                if rid:
                    result["_resource_id"] = rid
            except ScimError as exc:
                result["status"] = str(exc.status_code)
                result["response"] = exc.to_body()
                error_count += 1
            results.append(result)
            if fail_on_errors is not None and error_count >= fail_on_errors:
                break
        return results

    async def _dispatch_bulk(self, method: str, path: str, data: dict):
        parts = [p for p in path.strip("/").split("/") if p]
        if not parts or parts[0] not in ("Users", "Groups"):
            raise ScimError(400, f"Unsupported bulk path '{path}'", "invalidPath")
        resource = parts[0]
        resource_id = parts[1] if len(parts) > 1 else None
        is_user = resource == "Users"

        if method == "POST" and resource_id is None:
            created = await (self.create_user(data) if is_user else self.create_group(data))
            return resource[:-1], created.id, 201
        if resource_id is None:
            raise ScimError(400, f"{method} requires a resource id", "invalidPath")

        if method == "PUT":
            updated = await (
                self.replace_user(resource_id, data)
                if is_user
                else self.replace_group(resource_id, data)
            )
            return resource[:-1], updated.id, 200
        if method == "PATCH":
            ops = data.get("Operations") or data.get("operations") or []
            updated = await (
                self.patch_user(resource_id, ops)
                if is_user
                else self.patch_group(resource_id, ops)
            )
            return resource[:-1], updated.id, 200
        if method == "DELETE":
            if is_user:
                await self.delete_user(resource_id)
            else:
                await self.delete_group(resource_id)
            return None, None, 204
        raise ScimError(400, f"Unsupported bulk method '{method}'", "invalidSyntax")

    # --- helpers ------------------------------------------------------------

    def _member_ids(self, members) -> list[str]:
        if not members:
            return []
        ids = []
        for m in members:
            if isinstance(m, dict) and m.get("value"):
                ids.append(str(m["value"]))
            elif isinstance(m, str):
                ids.append(m)
        return ids

    async def _add_members(self, group, scim_user_ids, *, recompute: bool = True) -> None:
        added = []
        for uid in scim_user_ids:
            scim_user = await self.users.get_scoped(self.org_id, uid)
            if scim_user is None:
                raise ScimError(400, f"Member '{uid}' is not a known user", "invalidValue")
            if await self.members.get(group.id, uid) is None:
                await self.members.create(group_id=group.id, scim_user_id=uid)
                added.append(uid)
        if recompute and added:
            await self._recompute_roles(set(added))

    async def _remove_members(self, group, scim_user_ids) -> None:
        for uid in scim_user_ids:
            existing = await self.members.get(group.id, uid)
            if existing:
                await self.members.hard_delete(existing)

    async def _resolve_group_role(self, display_name: str) -> str | None:
        """Resolve a group's org role from the org's SSO role mappings."""
        connections = await self.sso_repo.list_for_organization(self.org_id)
        wanted = display_name.lower()
        for conn in connections:
            for group_name, role in (conn.role_mappings or {}).items():
                if group_name.lower() == wanted:
                    coerced = _coerce_role(role)
                    if coerced:
                        return coerced.value
        return None

    async def _recompute_roles(self, scim_user_ids: set[str]) -> None:
        for uid in scim_user_ids:
            scim_user = await self.users.get_by_id(uid)
            if scim_user is None or scim_user.organization_id != self.org_id:
                continue
            await self._apply_member_role(scim_user)

    async def _apply_member_role(self, scim_user) -> None:
        memberships = await self.members.list_for_user(scim_user.id)
        roles: list[OrganizationRole] = []
        for m in memberships:
            group = await self.groups.get_by_id(m.group_id)
            if group and group.mapped_role:
                role = _coerce_role(group.mapped_role)
                if role:
                    roles.append(role)
        if not roles:
            return
        target = max(roles, key=_ROLE_PRIORITY.index)
        membership = await self.org_members.get_membership(self.org_id, scim_user.user_id)
        if membership and membership.role != target:
            await self.org_members.update(membership, role=target)

    async def _get_or_create_global_user(self, email: str, full_name: str):
        existing = await self.user_repo.get_by_email(email)
        if existing:
            return existing
        username = await self._unique_username(email)
        # Race-safe: concurrent SCIM provisioning of the same user can pass the
        # get_by_email check simultaneously. The unique email/username constraints
        # reject the loser; recover by returning the winning row instead of 500.
        try:
            async with self.session.begin_nested():
                return await self.user_repo.create(
                    email=email,
                    username=username,
                    full_name=full_name or email.split("@", 1)[0],
                    hashed_password=None,
                )
        except IntegrityError:
            winner = await self.user_repo.get_by_email(email)
            if winner is not None:
                return winner
            # Username collided (rare); retry once with a freshly unique handle.
            username = await self._unique_username(email)
            async with self.session.begin_nested():
                return await self.user_repo.create(
                    email=email,
                    username=username,
                    full_name=full_name or email.split("@", 1)[0],
                    hashed_password=None,
                )

    async def _unique_username(self, email: str) -> str:
        base = re.sub(r"[^a-z0-9_-]+", "-", email.split("@", 1)[0].lower()).strip("-")
        base = base[:40] or "scimuser"
        candidate = base
        suffix = 1
        while await self.user_repo.get_by_username(candidate):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    async def _ensure_org_membership(self, user_id: str) -> None:
        membership = await self.org_members.get_membership(self.org_id, user_id)
        if membership is None:
            default = _coerce_role(settings.SCIM_DEFAULT_ROLE) or OrganizationRole.VIEWER
            await self.org_members.create(
                organization_id=self.org_id, user_id=user_id, role=default
            )

    async def _set_user_active(self, user, active: bool) -> None:
        if user.is_active != active:
            user.is_active = active
            self.session.add(user)
            await self.session.flush()

    async def _apply_user_side_effects(self, scim_user, user_name: str, active: bool) -> None:
        user = await self.user_repo.get_by_id(scim_user.user_id)
        if user is None:
            return
        await self._set_user_active(user, active)

    async def _count_scim_users_for(self, user_id: str) -> int:
        from sqlalchemy import func, select

        from app.models.scim import ScimUser

        result = await self.session.execute(
            select(func.count()).select_from(ScimUser).where(ScimUser.user_id == user_id)
        )
        return int(result.scalar_one())
