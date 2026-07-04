#!/usr/bin/env python3
"""Extract settings-org-ui.js from static/app.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
DEV_UI = ROOT / "static" / "development-ui.js"
OUT = ROOT / "static" / "settings-org-ui.js"

LOADER_FNS = [
    "loadOrganizationDetail",
    "loadInvitationPreview",
    "probeIdentityCapabilities",
    "loadMfaStatus",
    "loadUserSessions",
    "loadPersonalApiKeys",
    "loadOrgApiKeys",
    "loadServiceAccounts",
    "loadServiceAccountKeys",
    "loadSsoProviders",
    "loadSsoConnections",
    "loadOrganizationSso",
    "buildAuditQuery",
    "loadAuditLogs",
    "buildJobsQuery",
    "filterJobsByDateRange",
    "loadJobsList",
    "loadJobDetail",
    "buildAuditExportUrl",
    "loadSettingsTabData",
]

UI_FNS = [
    "settingsTabHref",
    "settingsTabsForCapabilities",
    "renderSettingsTabs",
    "renderIdentityUnavailableCard",
    "renderSettingsNotificationsTab",
    "renderSettingsProfileTab",
    "renderSettingsSecurityTab",
    "renderSettingsSessionsTab",
    "renderSettingsApiKeysTab",
    "renderServiceAccountKeysPanel",
    "renderSettingsServiceAccountsTab",
    "renderAuditFiltersForm",
    "renderAuditPagination",
    "renderSettingsAuditTab",
    "renderOrganizationAuditPage",
    "renderSsoConnectionForm",
    "renderOrganizationSsoPage",
    "renderJobsFiltersForm",
    "renderJobsPagination",
    "renderJobDetailPanel",
    "renderOperationsJobsPage",
    "slugifyOrganizationName",
    "renderOrganizationDemoNextStep",
    "canAssignOwner",
    "assignableMemberRoles",
    "invitationAcceptLink",
    "renderCustomerOrganization",
    "renderOrganizations",
    "renderOrganizationCreate",
    "renderOrganizationDetail",
]

CONST_BLOCKS: list[tuple[int, int]] = []

RENDER_SETTINGS = """
function renderSettings() {
  const tab = state.settingsTab || state.route.settingsTab || "profile";
  let body = "";
  if (tab === "profile") body = renderSettingsProfileTab();
  else if (tab === "security") body = renderSettingsSecurityTab();
  else if (tab === "sessions") body = renderSettingsSessionsTab();
  else if (tab === "api-keys") body = renderSettingsApiKeysTab();
  else if (tab === "service-accounts") body = renderSettingsServiceAccountsTab();
  else if (tab === "audit") body = renderSettingsAuditTab();
  else if (tab === "notifications") body = renderSettingsNotificationsTab();
  else body = renderSettingsProfileTab();
  return `
    <div class="container">
      ${renderHeader("Settings", "Manage your account and organization security")}
      ${renderAlerts()}
      ${renderSettingsTabs()}
      ${body}
    </div>
  `;
}
"""

LAZY_LOADER = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Settings / Organization admin UI
 * ---------------------------------------------------------------------- */
let __settingsOrgUiChunkPromise = null;
function settingsOrgUiChunkReady() {
  return typeof renderSettings === "function";
}
function settingsOrgUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["settings-org-ui.js"]) return assets["settings-org-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/settings-org-ui.js";
}
function loadSettingsOrgUiChunk() {
  if (settingsOrgUiChunkReady()) return Promise.resolve();
  if (__settingsOrgUiChunkPromise) return __settingsOrgUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __settingsOrgUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = settingsOrgUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __settingsOrgUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __settingsOrgUiChunkPromise = null;
      resolve();
    }
  });
  return __settingsOrgUiChunkPromise;
}
function lazySettingsOrgView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadSettingsOrgUiChunk().then(() => {
    if (settingsOrgUiChunkReady()) render();
  });
  return renderSkeleton("page");
}

"""


def find_ranges(lines: list[str], names: list[str]) -> list[tuple[int, int]]:
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^(async )?function (\w+)\s*\(", line)
        if m:
            starts.append((i, m.group(2)))
    fn_map: dict[str, tuple[int, int]] = {}
    for idx, (start_i, name) in enumerate(starts):
        end_i = (starts[idx + 1][0] - 1) if idx + 1 < len(starts) else len(lines) - 1
        while end_i > start_i and lines[end_i].strip() == "":
            end_i -= 1
        fn_map[name] = (start_i + 1, end_i + 1)
    missing = [n for n in names if n not in fn_map]
    if missing:
        raise SystemExit(f"Missing functions: {missing}")
    return [fn_map[n] for n in names]


def extract_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> str:
    parts: list[str] = []
    for start, end in sorted(ranges):
        parts.extend(lines[start - 1 : end])
    return "".join(parts)


def delete_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    drop = set()
    for start, end in ranges:
        for i in range(start - 1, end):
            drop.add(i)
    return [line for i, line in enumerate(lines) if i not in drop]


def extract_function_block(text: str, name: str) -> str:
    idx = text.find(f"function {name}(")
    if idx < 0:
        raise SystemExit(f"function not found: {name}")
    pos = text.find("{", idx)
    depth = 0
    end_pos = pos
    for i in range(pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break
    return text[idx : end_pos + 1] + "\n"


def remove_function_block(text: str, name: str) -> str:
    block = extract_function_block(text, name)
    return text.replace(block, "", 1)


def insert_after_function(text: str, anchor_name: str, payload: str) -> str:
    idx = text.find(f"function {anchor_name}(")
    if idx < 0:
        raise SystemExit(f"anchor not found: {anchor_name}")
    pos = text.find("{", idx)
    depth = 0
    end_pos = pos
    for i in range(pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break
    return text[:end_pos] + payload + text[end_pos:]


def extract_function_body(text: str, name: str) -> str:
    block = extract_function_block(text, name)
    lines = block.splitlines()
    if len(lines) < 2:
        raise SystemExit(f"empty function body: {name}")
    return "\n".join(lines[1:-1]) + "\n"


def main() -> None:
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    loader_ranges = find_ranges(lines, LOADER_FNS)
    ui_ranges = find_ranges(lines, UI_FNS)
    all_ranges = loader_ranges + ui_ranges + CONST_BLOCKS

    full_text = "".join(lines)
    bind_sprint2_body = extract_function_body(full_text, "bindSprint2Events")
    bind_security_body = extract_function_body(full_text, "bindSettingsSecurityEvents")

    header = """/*
 * Nexora Settings / Organization UI chunk — lazy-loaded on settings & org routes.
 * Globals: state, api, apiUrl, escapeHtml, formatDate, render, renderHeader, renderAlerts,
 * renderSkeleton, isOrgAdminRole, canManageMembers, canCreateOrganization, organizationRoleFor,
 * canManageOrgRecord, ssoConnectionStatusBadge, renderAccessDeniedPage, renderFeatureUnavailablePage,
 * sanitizeAuditEntry, sanitizeJobError, probeOperationsCapabilities, loadOrganizations, loadCredentials.
 */

"""
    chunk_body = extract_ranges(lines, loader_ranges)
    chunk_body += extract_ranges(lines, ui_ranges)
    chunk_body += RENDER_SETTINGS
    chunk_body += "\nfunction bindSettingsOrgEvents() {\n"
    chunk_body += bind_sprint2_body
    chunk_body += bind_security_body
    chunk_body += "}\n"
    OUT.write_text(header + chunk_body, encoding="utf-8")

    new_lines = delete_ranges(lines, all_ranges)
    text = "".join(new_lines)
    text = remove_function_block(text, "bindSprint2Events")
    text = remove_function_block(text, "bindSettingsSecurityEvents")

    if "function loadSettingsOrgUiChunk(" in text:
        raise SystemExit("lazy loader already present")

    text = insert_after_function(text, "lazyOpsCommandCenterView", LAZY_LOADER)

    route_replacements = [
        (
            '  } else if (state.route.page === "organization-sso") {\n    await loadOrganizationSso();',
            '  } else if (state.route.page === "organization-sso") {\n'
            "    await loadSettingsOrgUiChunk();\n"
            '    if (typeof loadOrganizationSso === "function") await loadOrganizationSso();',
        ),
        (
            '  } else if (state.route.page === "organization-audit") {\n    await loadAuditLogs();',
            '  } else if (state.route.page === "organization-audit") {\n'
            "    await loadSettingsOrgUiChunk();\n"
            '    if (typeof loadAuditLogs === "function") await loadAuditLogs();',
        ),
        (
            '  } else if (state.route.page === "operations-jobs") {\n    await loadJobsList();',
            '  } else if (state.route.page === "operations-jobs") {\n'
            "    await loadSettingsOrgUiChunk();\n"
            '    if (typeof loadJobsList === "function") await loadJobsList();',
        ),
        (
            '  } else if (state.route.page === "settings") {\n    state.settingsTab = state.route.settingsTab || "profile";\n    await loadSettingsTabData(state.settingsTab);',
            '  } else if (state.route.page === "settings") {\n    state.settingsTab = state.route.settingsTab || "profile";\n'
            "    await loadSettingsOrgUiChunk();\n"
            '    if (typeof loadSettingsTabData === "function") await loadSettingsTabData(state.settingsTab);',
        ),
        (
            '  } else if (state.route.page === "organization-detail") {\n    await loadOrganizationDetail(state.route.id);',
            '  } else if (state.route.page === "organization-detail") {\n'
            "    await loadSettingsOrgUiChunk();\n"
            '    if (typeof loadOrganizationDetail === "function") await loadOrganizationDetail(state.route.id);',
        ),
        (
            '  } else if (state.route.page === "invitation-accept") {\n    await loadInvitationPreview(state.route.token);',
            '  } else if (state.route.page === "invitation-accept") {\n'
            "    await loadSettingsOrgUiChunk();\n"
            '    if (typeof loadInvitationPreview === "function") await loadInvitationPreview(state.route.token);',
        ),
    ]
    for old, new in route_replacements:
        if old not in text:
            raise SystemExit(f"route anchor missing: {old[:70]!r}")
        text = text.replace(old, new, 1)

    render_cases = [
        ("organization", "renderCustomerOrganization"),
        ("organizations", "renderOrganizations"),
        ("organizations-create", "renderOrganizationCreate"),
        ("organization-detail", "renderOrganizationDetail"),
        ("settings", "renderSettings"),
        ("organization-sso", "renderOrganizationSsoPage"),
        ("organization-audit", "renderOrganizationAuditPage"),
        ("operations-jobs", "renderOperationsJobsPage"),
    ]
    for page, renderer in render_cases:
        old = f'case "{page}":\n      return {renderer}();'
        new = f'case "{page}":\n      return lazySettingsOrgView("{renderer}");'
        if old not in text:
            raise SystemExit(f"render case missing: {page}")
        text = text.replace(old, new, 1)

    bind_stub = '  if (typeof bindSettingsOrgEvents === "function") bindSettingsOrgEvents();\n'
    ops_marker = '  if (typeof bindOpsCommandCenterEvents === "function") bindOpsCommandCenterEvents();'
    if bind_stub.strip() not in text:
        text = text.replace(ops_marker, bind_stub + ops_marker, 1)

    old_bind = """  bindSettingsSecurityEvents();
  bindSprint2Events();"""
    if old_bind in text:
        text = text.replace(old_bind, "", 1)

    APP_JS.write_text(text, encoding="utf-8")

    dev_text = DEV_UI.read_text(encoding="utf-8")
    if "function renderSettings()" in dev_text:
        dev_text = remove_function_block(dev_text, "renderSettings")
        DEV_UI.write_text(dev_text, encoding="utf-8")
        print("Removed renderSettings() from development-ui.js")

    removed = len(lines) - len(text.splitlines())
    print("settings-org-ui.js written")
    print(f"Removed {removed} lines from app.js ({len(lines)} -> {len(text.splitlines())})")


if __name__ == "__main__":
    main()
