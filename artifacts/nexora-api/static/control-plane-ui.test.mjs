import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

const staticDir = fileURLToPath(new URL(".", import.meta.url));

test("control plane loads federation summary API", () => {
  const source = readFileSync(`${staticDir}/control-plane.js`, "utf8");
  assert.match(source, /\/v1\/control-plane\/federation/);
  assert.match(source, /renderCpFederationCard/);
  assert.match(source, /Cross-cluster federation/);
});

test("platform engineering exposes live apply and destroy actions", () => {
  const source = readFileSync(`${staticDir}/platform-ops-ui.js`, "utf8");
  assert.match(source, /data-pe-apply/);
  assert.match(source, /data-pe-destroy/);
  assert.match(source, /plan\/apply\/destroy/);
  assert.match(source, /peSubmitRun/);
});
