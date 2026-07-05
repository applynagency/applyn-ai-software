# SERVING ARCHITECTURE

## Runtime Trace (localhost:8000)

Request  
↓  
Docker port `8000` listener (`com.docker`)  
↓  
FastAPI app `app.main:app` inside `api` container  
↓  
Static routing from `_setup_dashboard()` in `app/main.py`  
↓  
`STATIC_DIR = artifacts/nexora-api/static` (inside container image filesystem)  
↓  
Entry files:
- `/` -> `index.html`
- `/styles.css` -> `styles.css`
- `/app.js` -> `app.js`
↓  
Client-side router in `static/app.js` (`parseRoute`, `navigate`, `renderPage`)  
↓  
Page render functions (dashboard, applications, builds, deployments, releases, etc.)

## Key Server Handlers

- `app/main.py` mounts:
  - `/static` via `StaticFiles(directory=STATIC_DIR)`
  - direct routes for `/`, `/styles.css`, `/app.js`
  - fallback `/{full_path:path}` to `index.html` for SPA paths

## Why Audit Saw Old UI

- Hash comparison showed served assets differ from workspace files:
  - local `static/app.js` != served `/app.js`
  - local `static/index.html` != served `/`
- This indicates container serves a previously built image layer (not latest local static edits) until image/container refresh is performed.

## Active Frontend Components

- Active entry: `static/index.html`
- Active router: `parseRoute()` in `static/app.js`
- Active nav component: `renderHeader()` in `static/app.js`
- Active page switcher: `renderPage()` in `static/app.js`

## File Load Chain (Current Platform)

Browser request  
→ FastAPI route (`/`, `/styles.css`, `/app.js`)  
→ FileResponse from `STATIC_DIR`  
→ JS boot (`bootstrap`)  
→ API calls (`/nexora-api/v1/...`)  
→ route render via `renderPage()`

