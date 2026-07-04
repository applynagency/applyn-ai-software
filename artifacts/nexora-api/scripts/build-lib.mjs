/*
 * Pure, dependency-free helpers shared by the frontend build, the bundle
 * analyzer and their unit tests. Everything here is deterministic and uses
 * only Node built-ins (crypto, zlib) so it can be unit-tested without esbuild.
 */
import crypto from "node:crypto";
import zlib from "node:zlib";

export const ASSET_URL_PREFIX = "/assets/";

/** Short, stable content hash for cache-busting (hex, default 10 chars). */
export function contentHash(content, length = 10) {
  return crypto.createHash("sha256").update(content).digest("hex").slice(0, length);
}

/** "app.js" + hash -> "app.<hash>.js" (handles multi-dot names safely). */
export function hashedName(name, hash) {
  const dot = name.lastIndexOf(".");
  if (dot === -1) return `${name}.${hash}`;
  return `${name.slice(0, dot)}.${hash}${name.slice(dot)}`;
}

export function gzipSize(content) {
  return zlib.gzipSync(content, { level: 9 }).length;
}

export function gzipBuffer(content) {
  return zlib.gzipSync(content, { level: 9 });
}

export function brotliSize(content) {
  return brotliBuffer(content).length;
}

export function brotliBuffer(content) {
  return zlib.brotliCompressSync(content, {
    params: {
      [zlib.constants.BROTLI_PARAM_QUALITY]: 11,
      [zlib.constants.BROTLI_PARAM_SIZE_HINT]: content.length,
    },
  });
}

/** Build the logical-name -> served-URL manifest. */
export function buildManifest(entries) {
  const manifest = {};
  for (const { name, file } of entries) {
    manifest[name] = `${ASSET_URL_PREFIX}${file}`;
  }
  return manifest;
}

/**
 * Rewrite the dev index.html to reference hashed, fingerprinted assets and
 * inline the manifest so the runtime lazy-loader can resolve chunk URLs.
 */
export function rewriteIndexHtml(html, manifest, options = {}) {
  const apiBase = options.apiBase ?? process.env.NEXORA_API_BASE ?? process.env.BASE_PATH ?? "/nexora-api";
  let out = html;
  if (manifest["styles.css"]) {
    out = out.replace(/href="\/styles\.css(?:\?[^"]*)?"/, `href="${manifest["styles.css"]}"`);
  }
  const apiConfig = `<script>window.__NEXORA_API_BASE__=${JSON.stringify(apiBase)};</script>`;
  const inject = `${apiConfig}\n    <script>window.__ASSETS__ = ${JSON.stringify(manifest)};</script>`;
  if (manifest["app.js"]) {
    out = out.replace(
      /<script>window\.__NEXORA_API_BASE__=[^<]*<\/script>\s*/,
      "",
    );
    out = out.replace(
      /<script src="\/app\.js(?:\?[^"]*)?"><\/script>/,
      `${inject}\n    <script src="${manifest["app.js"]}" defer></script>`
    );
  }
  return out;
}

const KB = 1024;
export function toKB(bytes) {
  return Math.round((bytes / KB) * 10) / 10;
}

/**
 * Compute compressed sizes for each asset.
 * `assets` is { name: { raw: Buffer|string, min: Buffer|string } }.
 * Returns { name: { raw, min, gzip, brotli } } in bytes.
 */
export function analyzeAssets(assets) {
  const out = {};
  for (const [name, { raw, min }] of Object.entries(assets)) {
    const rawBuf = Buffer.isBuffer(raw) ? raw : Buffer.from(raw);
    const minBuf = Buffer.isBuffer(min) ? min : Buffer.from(min);
    out[name] = {
      raw: rawBuf.length,
      min: minBuf.length,
      gzip: gzipSize(minBuf),
      brotli: brotliSize(minBuf),
    };
  }
  return out;
}

/**
 * Evaluate a performance budget against an analysis map. Pure: returns
 * { ok, initialBrotli, initialBudget, violations: [{type,name,actual,max,message}] }.
 */
export function evaluateBudget(analysis, budget) {
  const violations = [];
  const initialNames = budget.initial || [];
  let initialBrotli = 0;
  for (const name of initialNames) {
    const a = analysis[name];
    if (a) initialBrotli += a.brotli;
  }
  const initialBudget = (budget.initialBundleKB || 200) * KB;
  if (initialBrotli > initialBudget) {
    violations.push({
      type: "initial",
      name: "initial",
      actual: initialBrotli,
      max: initialBudget,
      message: `initial bundle ${toKB(initialBrotli)}KB exceeds ${budget.initialBundleKB}KB budget`,
    });
  }
  for (const [name, rule] of Object.entries(budget.assets || {})) {
    const a = analysis[name];
    if (!a) continue;
    if (rule.maxBrotliKB != null && a.brotli > rule.maxBrotliKB * KB) {
      violations.push({
        type: "asset-brotli",
        name,
        actual: a.brotli,
        max: rule.maxBrotliKB * KB,
        message: `${name} brotli ${toKB(a.brotli)}KB exceeds ${rule.maxBrotliKB}KB budget`,
      });
    }
    if (rule.maxRawKB != null && a.raw > rule.maxRawKB * KB) {
      violations.push({
        type: "asset-raw",
        name,
        actual: a.raw,
        max: rule.maxRawKB * KB,
        message: `${name} raw ${toKB(a.raw)}KB exceeds ${rule.maxRawKB}KB budget`,
      });
    }
  }
  return { ok: violations.length === 0, initialBrotli, initialBudget, violations };
}
