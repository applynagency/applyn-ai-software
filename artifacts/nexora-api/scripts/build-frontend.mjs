#!/usr/bin/env node
/*
 * Frontend production build for the APPYLN customer SPA.
 *
 * Pipeline:
 *   1. Minify   — esbuild minifies JS (with dead-code elimination / tree
 *                 shaking of unreachable code) and CSS.
 *   2. Hash     — content-hash each asset for immutable, far-future caching.
 *   3. Compress — precompute gzip (.gz) and brotli (.br) so the server can
 *                 serve precompressed bytes without per-request CPU cost.
 *   4. Manifest — logical-name -> hashed-URL map, inlined into index.html so
 *                 the runtime lazy-loader can resolve the code-split chunk.
 *   5. Analyze  — write analysis.json and print a size table.
 *   6. Budget   — fail the build if the initial bundle blows the budget.
 *
 * Output: static/dist/  (gitignored; produced in CI / release images).
 *
 * Usage: node scripts/build-frontend.mjs [--no-fail] [--silent]
 */
import esbuild from "esbuild";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  analyzeAssets,
  brotliBuffer,
  buildManifest,
  contentHash,
  evaluateBudget,
  gzipBuffer,
  hashedName,
  rewriteIndexHtml,
  toKB,
} from "./build-lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const staticDir = path.join(root, "static");
const distDir = path.join(staticDir, "dist");
const budget = JSON.parse(fs.readFileSync(path.join(root, "frontend.budget.json"), "utf8"));

const args = new Set(process.argv.slice(2));
const noFail = args.has("--no-fail");
const silent = args.has("--silent");
const log = (...a) => !silent && console.log(...a);

const SOURCES = [
  { name: "app.js", loader: "js" },
  { name: "help.js", loader: "js" },
  { name: "pilot-operator.js", loader: "js" },
  { name: "billing.js", loader: "js" },
  { name: "product-catalog.js", loader: "js" },
  { name: "operations-overview.js", loader: "js" },
  { name: "integration-onboarding.js", loader: "js" },
  { name: "secrets-hub.js", loader: "js" },
  { name: "incidents.js", loader: "js" },
  { name: "delivery.js", loader: "js" },
  { name: "war-rooms.js", loader: "js" },
  { name: "observability-ui.js", loader: "js" },
  { name: "development-ui.js", loader: "js" },
  { name: "security-platform.js", loader: "js" },
  { name: "platform-ops-ui.js", loader: "js" },
  { name: "control-plane.js", loader: "js" },
  { name: "incident-response-ui.js", loader: "js" },
  { name: "discovery-ui.js", loader: "js" },
  { name: "reliability-ops-ui.js", loader: "js" },
  { name: "customer-journey-ui.js", loader: "js" },
  { name: "copilot-runbooks-ui.js", loader: "js" },
  { name: "ops-command-center-ui.js", loader: "js" },
  { name: "settings-org-ui.js", loader: "js" },
  { name: "styles.css", loader: "css" },
];

async function minify(name, loader, code) {
  const result = await esbuild.transform(code, {
    loader,
    minify: true,
    legalComments: "none",
    target: loader === "css" ? "chrome90" : "es2020",
  });
  return result.code;
}

async function run() {
  fs.rmSync(distDir, { recursive: true, force: true });
  fs.mkdirSync(distDir, { recursive: true });

  const manifestEntries = [];
  const analysisInput = {};

  for (const { name, loader } of SOURCES) {
    const srcPath = path.join(staticDir, name);
    const raw = fs.readFileSync(srcPath);
    const min = await minify(name, loader, raw.toString("utf8"));
    const minBuf = Buffer.from(min);
    const hash = contentHash(minBuf);
    const file = hashedName(name, hash);

    fs.writeFileSync(path.join(distDir, file), minBuf);
    fs.writeFileSync(path.join(distDir, `${file}.gz`), gzipBuffer(minBuf));
    fs.writeFileSync(path.join(distDir, `${file}.br`), brotliBuffer(minBuf));

    manifestEntries.push({ name, file });
    analysisInput[name] = { raw, min: minBuf };
  }

  const manifest = buildManifest(manifestEntries);
  fs.writeFileSync(path.join(distDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);

  // Hashed, manifest-aware index.html (served with no-cache so deploys are
  // picked up immediately while the hashed assets stay immutable forever).
  const indexHtml = fs.readFileSync(path.join(staticDir, "index.html"), "utf8");
  const builtIndex = rewriteIndexHtml(indexHtml, manifest);
  fs.writeFileSync(path.join(distDir, "index.html"), builtIndex);
  fs.writeFileSync(path.join(distDir, "index.html.gz"), gzipBuffer(Buffer.from(builtIndex)));
  fs.writeFileSync(path.join(distDir, "index.html.br"), brotliBuffer(Buffer.from(builtIndex)));

  const analysis = analyzeAssets(analysisInput);
  const report = { generatedAt: new Date().toISOString(), manifest, assets: analysis, budget };
  fs.writeFileSync(path.join(distDir, "analysis.json"), `${JSON.stringify(report, null, 2)}\n`);

  printTable(analysis);

  const result = evaluateBudget(analysis, budget);
  log("");
  log(
    `Initial bundle (brotli): ${toKB(result.initialBrotli)}KB / ${budget.initialBundleKB}KB budget` +
      ` — ${result.ok ? "OK" : "OVER"}`
  );
  if (!result.ok) {
    for (const v of result.violations) log(`  ✗ ${v.message}`);
    if (!noFail) {
      console.error("\nPerformance budget exceeded. Failing build.");
      process.exit(1);
    }
  } else {
    log("Performance budget: PASS");
  }
}

function printTable(analysis) {
  const rows = Object.entries(analysis).map(([name, a]) => ({
    Asset: name,
    Raw: `${toKB(a.raw)}KB`,
    Min: `${toKB(a.min)}KB`,
    Gzip: `${toKB(a.gzip)}KB`,
    Brotli: `${toKB(a.brotli)}KB`,
  }));
  log("\nBundle analysis");
  log("─".repeat(58));
  log(pad("Asset", 14) + pad("Raw", 11) + pad("Min", 11) + pad("Gzip", 11) + "Brotli");
  log("─".repeat(58));
  for (const r of rows) {
    log(pad(r.Asset, 14) + pad(r.Raw, 11) + pad(r.Min, 11) + pad(r.Gzip, 11) + r.Brotli);
  }
  log("─".repeat(58));
}

function pad(s, n) {
  s = String(s);
  return s.length >= n ? s : s + " ".repeat(n - s.length);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
