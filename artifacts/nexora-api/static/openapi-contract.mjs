import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const nexoraApiRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const openapiPath = join(nexoraApiRoot, "sdk", "openapi.json");

/** Paths the SPA calls that may lag behind sdk/openapi.json until the spec is regenerated. */
const FRONTEND_API_PREFIX_ALLOWLIST = [
  "/v1/delivery/dashboard",
  "/v1/delivery/operations",
  "/v1/pilot/readiness",
  "/v1/org-config/variables",
  "/v1/platform-engineering/secrets",
  "/v1/integrations/connections/{id}/credentials",
  "/v1/onboarding/integrations/sessions/{id}/environment",
  "/v1/onboarding/integrations/sessions/{id}/credentials",
  "/v1/onboarding/integrations/sessions/{id}/validate",
];

export function normalizeOpenApiPath(path) {
  return path.replace(/^\/nexora-api/, "").replace(/\{[^}]+\}/g, "{id}");
}

export function loadOpenApiPaths() {
  const spec = JSON.parse(readFileSync(openapiPath, "utf8"));
  const paths = new Set();
  for (const p of Object.keys(spec.paths || {})) {
    paths.add(normalizeOpenApiPath(p));
  }
  for (const extra of FRONTEND_API_PREFIX_ALLOWLIST) {
    paths.add(normalizeOpenApiPath(extra));
  }
  return paths;
}

export function openApiPrefixes(openApiPaths) {
  const prefixes = new Set();
  for (const p of openApiPaths) {
    const parts = p.split("/").filter(Boolean);
    for (let i = 2; i <= Math.min(parts.length, 6); i++) {
      prefixes.add("/" + parts.slice(0, i).join("/"));
    }
  }
  return prefixes;
}

export function pathMatchesOpenApi(fePath, openApiPaths) {
  const normalized = fePath.replace(/\{id\}/g, "{id}");
  if (openApiPaths.has(normalized)) return true;
  const prefixes = openApiPrefixes(openApiPaths);
  const parts = normalized.split("/").filter(Boolean);
  for (let i = parts.length; i >= 2; i--) {
    const candidate = "/" + parts.slice(0, i).join("/");
    if (prefixes.has(candidate)) return true;
  }
  return false;
}
