"""Versioned prompt registry (Sprint 61D).

Prompts are stored with versions and optional per-organization overrides. The
active version for an org resolves as: org override (active) > global (active).
Supports register (new version), render (variable substitution), list versions,
rollback (re-activate a prior version) and test (dry-run render).
"""

from __future__ import annotations

import re
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_platform import PromptTemplate
from app.repositories.audit import AuditLogRepository

_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def extract_variables(template: str) -> list[str]:
    return sorted(set(_VAR_RE.findall(template or "")))


class PromptRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def _max_version(self, key: str, organization_id: str | None) -> int:
        rows = (await self.session.execute(
            select(PromptTemplate.version).where(
                PromptTemplate.key == key,
                PromptTemplate.organization_id.is_(organization_id)
                if organization_id is None
                else PromptTemplate.organization_id == organization_id,
            )
        )).scalars().all()
        return max(rows) if rows else 0

    async def register(
        self, *, key: str, template: str, organization_id: str | None = None,
        variables: list[str] | None = None, description: str | None = None,
        actor_user_id: str | None = None,
    ) -> PromptTemplate:
        version = await self._max_version(key, organization_id) + 1
        # Deactivate prior versions in the same scope so there is one active.
        await self._deactivate_scope(key, organization_id)
        tmpl = PromptTemplate(
            organization_id=organization_id, key=key, version=version,
            template=template, variables=variables or extract_variables(template),
            description=description, is_active=True, created_by=actor_user_id,
        )
        self.session.add(tmpl)
        await self.session.flush()
        await self.audit.log(
            action="prompt.registered", resource_type="prompt_template",
            resource_id=tmpl.id, organization_id=organization_id, user_id=actor_user_id,
            details={"key": key, "version": version},
        )
        return tmpl

    async def _deactivate_scope(self, key: str, organization_id: str | None) -> None:
        rows = (await self.session.execute(
            select(PromptTemplate).where(
                PromptTemplate.key == key,
                PromptTemplate.organization_id.is_(None)
                if organization_id is None
                else PromptTemplate.organization_id == organization_id,
            )
        )).scalars().all()
        for row in rows:
            row.is_active = False
            self.session.add(row)

    async def get_active(self, key: str, organization_id: str | None = None) -> PromptTemplate | None:
        if organization_id is not None:
            override = await self.session.scalar(
                select(PromptTemplate).where(
                    PromptTemplate.key == key,
                    PromptTemplate.organization_id == organization_id,
                    PromptTemplate.is_active.is_(True),
                ).order_by(PromptTemplate.version.desc())
            )
            if override is not None:
                return override
        return await self.session.scalar(
            select(PromptTemplate).where(
                PromptTemplate.key == key,
                PromptTemplate.organization_id.is_(None),
                PromptTemplate.is_active.is_(True),
            ).order_by(PromptTemplate.version.desc())
        )

    async def list_versions(self, key: str, organization_id: str | None = None) -> list[PromptTemplate]:
        return list((await self.session.execute(
            select(PromptTemplate).where(
                PromptTemplate.key == key,
                PromptTemplate.organization_id.is_(None)
                if organization_id is None
                else PromptTemplate.organization_id == organization_id,
            ).order_by(PromptTemplate.version.asc())
        )).scalars().all())

    async def render(
        self, key: str, variables: dict, *, organization_id: str | None = None,
    ) -> str:
        tmpl = await self.get_active(key, organization_id)
        if tmpl is None:
            raise PromptError(f"Prompt '{key}' not found", status_code=404)
        return self.render_template(tmpl.template, variables)

    @staticmethod
    def render_template(template: str, variables: dict) -> str:
        required = extract_variables(template)
        missing = [v for v in required if v not in variables]
        if missing:
            raise PromptError(f"Missing variables: {', '.join(missing)}")
        # Safe substitution: only {name} placeholders are replaced.
        return string.Template(
            _VAR_RE.sub(r"${\1}", template)
        ).safe_substitute(**{k: str(v) for k, v in variables.items()})

    async def rollback(
        self, key: str, version: int, *, organization_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> PromptTemplate:
        target = await self.session.scalar(
            select(PromptTemplate).where(
                PromptTemplate.key == key, PromptTemplate.version == version,
                PromptTemplate.organization_id.is_(None)
                if organization_id is None
                else PromptTemplate.organization_id == organization_id,
            )
        )
        if target is None:
            raise PromptError("Version not found", status_code=404)
        await self._deactivate_scope(key, organization_id)
        target.is_active = True
        self.session.add(target)
        await self.session.flush()
        await self.audit.log(
            action="prompt.rolled_back", resource_type="prompt_template",
            resource_id=target.id, organization_id=organization_id, user_id=actor_user_id,
            details={"key": key, "version": version},
        )
        return target
