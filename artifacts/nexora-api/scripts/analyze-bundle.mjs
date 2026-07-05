#!/usr/bin/env node
/*
 * Bundle analyzer for the APPYLN SPA. Reads static/dist/analysis.json (written
 * by build-frontend.mjs) and prints a per-asset size table plus the budget
 * status. Exits non-zero if the budget is exceeded so it can gate CI.
 *
 * Usage: node scripts/analyze-bundle.mjs [--json]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { evaluateBudget, toKB } from "./build-lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const analysisPath = path.join(root, "static", "dist", "analysis.json");

if (!fs.existsSync(analysisPath)) {
  console.error("No analysis.json found. Run `npm run build` first.");
  process.exit(1);
}

const report = JSON.parse(fs.readFileSync(analysisPath, "utf8"));
const { assets, budget } = report;

if (process.argv.includes("--json")) {
  const result = evaluateBudget(assets, budget);
  console.log(JSON.stringify({ assets, ...result }, null, 2));
  process.exit(result.ok ? 0 : 1);
}

const pad = (s, n) => (String(s).length >= n ? String(s) : String(s) + " ".repeat(n - String(s).length));

console.log(`Bundle report — generated ${report.generatedAt}`);
console.log("═".repeat(66));
console.log(pad("Asset", 14) + pad("Raw", 12) + pad("Minified", 12) + pad("Gzip", 11) + "Brotli");
console.log("─".repeat(66));
let totalBrotli = 0;
for (const [name, a] of Object.entries(assets)) {
  const lazy = budget.assets?.[name]?.lazy ? "  (lazy)" : "";
  console.log(
    pad(name + lazy, 14) +
      pad(`${toKB(a.raw)}KB`, 12) +
      pad(`${toKB(a.min)}KB`, 12) +
      pad(`${toKB(a.gzip)}KB`, 11) +
      `${toKB(a.brotli)}KB`
  );
  totalBrotli += a.brotli;
}
console.log("─".repeat(66));
console.log(pad("TOTAL", 14) + pad("", 12) + pad("", 12) + pad("", 11) + `${toKB(totalBrotli)}KB`);

const result = evaluateBudget(assets, budget);
console.log("");
console.log(
  `Initial bundle (brotli): ${toKB(result.initialBrotli)}KB / ${budget.initialBundleKB}KB — ${
    result.ok ? "WITHIN BUDGET ✓" : "OVER BUDGET ✗"
  }`
);
for (const v of result.violations) console.log(`  ✗ ${v.message}`);
process.exit(result.ok ? 0 : 1);
