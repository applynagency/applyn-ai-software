import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));

test("UI completion: org detail SSO links to wizard not coming soon", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.doesNotMatch(source, /Enterprise single sign-on setup is coming soon/);
  assert.match(source, /Manage SSO connections/);
});

test("UI completion: login page supports SSO providers", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /loadSsoProviders/);
  assert.match(source, /auth-sso-providers/);
  assert.match(source, /\/v1\/auth\/sso\/providers/);
});

test("UI completion: SSO wizard supports SAML and metadata import", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /name="protocol"/);
  assert.match(source, /saml\/import-metadata/);
  assert.match(source, /SP metadata/);
});

test("UI completion: service account keys wired", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /loadServiceAccountKeys/);
  assert.match(source, /\/v1\/service-accounts\/\$\{saId\}\/keys/);
  assert.match(source, /data-expand-service-account/);
});

test("UI completion: API key rotation wired", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /data-rotate-api-key/);
  assert.match(source, /\/v1\/api-keys\/organization\/\$\{keyId\}\/rotate/);
  assert.match(source, /\/v1\/api-keys\/personal\/\$\{keyId\}\/rotate/);
});

test("UI completion: audit export and jobs dead-letter/detail", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /buildAuditExportUrl/);
  assert.match(source, /\/v1\/audit\/logs\/export/);
  assert.match(source, /data-jobs-tab="dead-letter"/);
  assert.match(source, /\/v1\/jobs\/dead-letter/);
  assert.match(source, /loadJobDetail/);
  assert.doesNotMatch(source, /data-jobs-retry|data-jobs-cancel/);
});

test("UI completion: renderAuth shows SSO when providers loaded", () => {
  const { renderAuth, state } = loadFrontendExports();
  state.ssoProviders = [
    { display_name: "Acme Okta", login_url: "https://example.com/sso/login", protocol: "OIDC" },
  ];
  const html = renderAuth();
  assert.match(html, /Acme Okta/);
  assert.match(html, /sign in with SSO/i);
});
