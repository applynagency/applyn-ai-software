import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  analyzeAssets,
  buildManifest,
  contentHash,
  evaluateBudget,
  hashedName,
  rewriteIndexHtml,
  toKB,
} from "../scripts/build-lib.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
const distDir = fileURLToPath(new URL("./dist/", import.meta.url));

test("contentHash is deterministic and fixed-length", () => {
  const a = contentHash("hello world");
  const b = contentHash("hello world");
  const c = contentHash("hello worlds");
  assert.equal(a, b);
  assert.notEqual(a, c);
  assert.equal(a.length, 10);
  assert.match(a, /^[0-9a-f]+$/);
});

test("hashedName inserts the hash before the extension", () => {
  assert.equal(hashedName("app.js", "abc123"), "app.abc123.js");
  assert.equal(hashedName("styles.css", "deadbeef"), "styles.deadbeef.css");
  assert.equal(hashedName("noext", "x"), "noext.x");
});

test("buildManifest maps logical names to /assets URLs", () => {
  const manifest = buildManifest([
    { name: "app.js", file: "app.abc.js" },
    { name: "styles.css", file: "styles.def.css" },
  ]);
  assert.equal(manifest["app.js"], "/assets/app.abc.js");
  assert.equal(manifest["styles.css"], "/assets/styles.def.css");
});

test("rewriteIndexHtml fingerprints assets and inlines the manifest", () => {
  const html = [
    "<head>",
    '<link rel="stylesheet" href="/styles.css?v=86" />',
    "</head><body>",
    '<script src="/app.js?v=86"></script>',
    "</body>",
  ].join("\n");
  const manifest = {
    "app.js": "/assets/app.AAA.js",
    "help.js": "/assets/help.BBB.js",
    "styles.css": "/assets/styles.CCC.css",
  };
  const out = rewriteIndexHtml(html, manifest);
  assert.match(out, /window\.__NEXORA_API_BASE__="\/nexora-api"/);
  assert.match(out, /window\.__ASSETS__/);
  assert.match(out, /href="\/assets\/styles\.CCC\.css"/);
  assert.match(out, /src="\/assets\/app\.AAA\.js" defer/);
  assert.match(out, /window\.__ASSETS__ = /);
  assert.match(out, /help\.BBB\.js/); // lazy chunk URL available to the loader
  assert.doesNotMatch(out, /\/app\.js\?v=/);
  assert.doesNotMatch(out, /\/styles\.css\?v=/);
});

test("analyzeAssets reports compressed sizes smaller than minified", () => {
  const big = "a".repeat(20000) + "function x(){return 1;}".repeat(500);
  const analysis = analyzeAssets({ "app.js": { raw: big, min: big } });
  const a = analysis["app.js"];
  assert.equal(a.raw, Buffer.byteLength(big));
  assert.ok(a.brotli < a.min, "brotli should be smaller than minified");
  assert.ok(a.brotli <= a.gzip, "brotli should be <= gzip for repetitive input");
});

test("evaluateBudget passes within budget and flags violations", () => {
  const analysis = {
    "app.js": { raw: 800 * 1024, min: 600 * 1024, gzip: 110 * 1024, brotli: 80 * 1024 },
    "styles.css": { raw: 60 * 1024, min: 50 * 1024, gzip: 10 * 1024, brotli: 9 * 1024 },
    "help.js": { raw: 30 * 1024, min: 25 * 1024, gzip: 7 * 1024, brotli: 6 * 1024 },
  };
  const budget = {
    initialBundleKB: 200,
    initial: ["app.js", "styles.css"],
    assets: { "app.js": { maxBrotliKB: 180 } },
  };
  const ok = evaluateBudget(analysis, budget);
  assert.equal(ok.ok, true);
  assert.equal(ok.violations.length, 0);
  // help.js is lazy and excluded from the initial sum (89KB, not 95KB).
  assert.equal(toKB(ok.initialBrotli), 89);

  const tight = { initialBundleKB: 50, initial: ["app.js", "styles.css"], assets: {} };
  const over = evaluateBudget(analysis, tight);
  assert.equal(over.ok, false);
  assert.equal(over.violations[0].type, "initial");

  const assetCap = {
    initialBundleKB: 200,
    initial: ["app.js"],
    assets: { "app.js": { maxBrotliKB: 50 } },
  };
  const capped = evaluateBudget(analysis, assetCap);
  assert.equal(capped.ok, false);
  assert.ok(capped.violations.some((v) => v.type === "asset-brotli"));
});

test("end-to-end build emits hashed, compressed assets within budget", () => {
  execSync("node scripts/build-frontend.mjs --silent", { cwd: root, stdio: "pipe" });

  const manifest = JSON.parse(readFileSync(`${distDir}manifest.json`, "utf8"));
  for (const logical of ["app.js", "help.js", "pilot-operator.js", "styles.css"]) {
    const url = manifest[logical];
    assert.ok(url, `${logical} missing from manifest`);
    assert.match(url, /^\/assets\/.+\.[0-9a-f]{10}\.(js|css)$/);
    const file = url.replace("/assets/", "");
    assert.ok(existsSync(`${distDir}${file}`), `${file} not emitted`);
    assert.ok(existsSync(`${distDir}${file}.br`), `${file}.br not emitted`);
    assert.ok(existsSync(`${distDir}${file}.gz`), `${file}.gz not emitted`);
    // precompressed variants must be smaller than the raw asset
    assert.ok(statSync(`${distDir}${file}.br`).size < statSync(`${distDir}${file}`).size);
  }

  const report = JSON.parse(readFileSync(`${distDir}analysis.json`, "utf8"));
  const result = evaluateBudget(report.assets, report.budget);
  assert.equal(result.ok, true, "built bundle should be within budget");
  assert.ok(result.initialBrotli < 200 * 1024, "initial bundle must be < 200KB brotli");
  // Lazy chunks must be real, separate bundles (code splitting), not in the initial set.
  assert.ok(report.assets["help.js"].brotli > 0);
  assert.ok(report.assets["pilot-operator.js"].brotli > 0);
});
