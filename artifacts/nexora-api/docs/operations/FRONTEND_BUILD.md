# Frontend Build & Performance

The customer SPA (`static/`) is a dependency-free, classic-script app. For
production it is run through an optimization pipeline that minifies, code-splits,
fingerprints and precompresses the assets, and enforces a performance budget.

## Quick start

```bash
cd artifacts/nexora-api
npm install            # one-time: installs esbuild (the only devDependency)
npm run build          # -> static/dist/ (minified, hashed, gz + br, manifest)
npm run analyze        # bundle size table + budget status (exits non-zero if over)
npm run validate       # parse + structural gate for app.js / help.js
npm test               # node --test for static/*.test.mjs
```

`static/dist/` is a build artifact (gitignored) and is produced in CI / release
images. When it is absent the server transparently serves the raw dev files.

## What the pipeline does

| Requirement | Implementation |
| --- | --- |
| **Code splitting** | The Help Center is extracted into `static/help.js`, a separate chunk that is **not** part of the initial bundle. |
| **Lazy loading** | `loadHelpChunk()` injects `help.js` on demand the first time a `/help…` route is opened; `renderPage()` shows a skeleton until it resolves. |
| **Tree shaking** | esbuild minification performs dead-code elimination / constant folding on each asset. |
| **Content hashing** | Each asset is emitted as `name.<sha256-10>.ext`; the URL changes only when the bytes change. |
| **Compression** | gzip (`.gz`, level 9) and brotli (`.br`, quality 11) are precomputed for every asset and the HTML shell. |
| **Cache headers** | Hashed assets under `/assets/…` are served `Cache-Control: public, max-age=31536000, immutable`; the HTML shell is `no-cache`. |
| **Bundle analysis** | `scripts/analyze-bundle.mjs` reads `dist/analysis.json` and prints raw/min/gzip/brotli per asset. |
| **Performance budget** | `frontend.budget.json` defines limits; the build **fails** if the initial bundle exceeds them. |

## Performance budget

`frontend.budget.json`:

- `initialBundleKB: 200` — the render-blocking JS+CSS (brotli) must stay under
  200KB. Lazy chunks (`help.js`) are excluded.
- Per-asset caps (`maxBrotliKB`, `maxRawKB`).

Current build (representative):

| Asset | Raw | Minified | Gzip | Brotli |
| --- | --- | --- | --- | --- |
| app.js | ~804KB | ~669KB | ~111KB | **~87KB** |
| styles.css | ~66KB | ~53KB | ~10KB | **~9KB** |
| help.js (lazy) | ~34KB | ~26KB | ~7KB | ~6KB |

**Initial bundle ≈ 96KB brotli — well under the 200KB budget.**

## Serving (FastAPI)

`app/web/static_assets.py` provides pure, tested helpers used by
`app/main.py`:

- `/assets/{filename}` — validates the name (no traversal), negotiates the best
  precompressed variant via `Accept-Encoding` (brotli preferred, then gzip,
  else identity), sets the correct `Content-Type`, `Content-Encoding`,
  `Vary: Accept-Encoding` and the immutable cache header.
- `/` and the SPA fallback serve `dist/index.html` (no-cache) when a build is
  present, else the raw dev `index.html`.

## Lighthouse (target > 95)

The pipeline targets the Lighthouse performance levers directly: small initial
JS (code splitting + minification), brotli transfer, immutable caching of
fingerprinted assets, `defer`-ed script, and an accessible shell (skip link,
landmarks, focus-visible, reduced-motion — see `UI_SHELL.md`). Run Lighthouse
against a server started on a `npm run build` output:

```bash
npm run build
uvicorn app.main:app --port 8000
npx lighthouse http://localhost:8000 --only-categories=performance,accessibility
```

## Tests

- `static/build.test.mjs` — content hashing, manifest, `index.html` rewrite,
  compression sizing, budget evaluation, and a full end-to-end build assertion
  (hashed + `.gz`/`.br` emitted, initial bundle < 200KB).
- `app/tests/test_static_assets.py` — encoding negotiation, safe-name guard,
  cache headers, and integration tests that fetch built assets and assert
  brotli + immutable caching (skipped automatically when `dist/` is absent).
