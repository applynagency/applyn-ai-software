# Enterprise UI Shell

The customer web app (`static/app.js` + `static/styles.css`) ships an
enterprise-grade application shell on top of the existing vanilla-JS SPA. It
adds toast notifications, a command palette with global search, a notification
center, light/dark/system theming, keyboard shortcuts, skeleton loading and
WCAG 2.1 AA accessibility affordances.

All UI logic is plain ES2020 — no build step, no framework. The pure helpers
are exported through `static/frontend.harness.mjs` and covered by
`static/frontend.test.mjs` (run with `node --test static/frontend.test.mjs`).

## Capabilities

### Toast notifications
- `pushToast(message, type, { title, duration })` enqueues a toast.
  `type ∈ {success, error, warning, info}`; default auto-dismiss is 5s.
- Toasts live in a persistent `#toast-stack` region on `document.body`
  (`role="region" aria-live="polite"`) so they survive full re-renders.
- The list is capped at `TOAST_MAX` (5) — oldest are dropped first
  (`nextToastList`).
- Transient `state.message` / `state.error` are mirrored into toasts exactly
  once per change via `syncAlertsToToasts()`. Errors also remain inline so the
  **Retry** action is always reachable, and are recorded in the notification
  center.

### Skeleton loading
- `renderSkeleton("page" | "list")` returns shimmering placeholders
  (`aria-busy="true"`). While `state.loading` is set during bootstrap /
  refresh / reload, the main content area renders a skeleton instead of a bare
  spinner.

### Command palette + global search
- Open with `⌘K` / `Ctrl+K` (or `/`), the topbar command / search buttons.
- `buildCommandRegistry(navGroups, opts)` builds commands from the navigation
  groups plus global actions (toggle theme, open notifications, show shortcuts,
  refresh, sign out). `filterCommands` ranks them with `scoreMatch`
  (substring first, subsequence fallback).
- `buildSearchIndex(state)` indexes loaded entities (organizations, AI teams,
  workflows, applications, incidents, war rooms, services, runbooks);
  `searchIndex` returns ranked matches that appear alongside commands when a
  query is typed.
- Keyboard: `↑/↓` move, `Enter` activates, `Esc` closes. The result list uses
  `role="listbox"`/`role="option"` with `aria-selected`.

### Notification center
- Bell button in the topbar with an unread badge (`unreadNotificationCount`).
- Persisted to `localStorage` (`appyln_notifications`, capped at 50). Pure
  helpers: `addNotificationToList`, `markNotificationReadInList`,
  `markAllReadInList`. Items with a `path` navigate on click.

### Theme (light / dark / system)
- `state.theme ∈ {light, dark, system}`, persisted to `localStorage`
  (`appyln_theme`). `resolveTheme(stored, prefersDark)` resolves `system`
  against `prefers-color-scheme`; `applyTheme()` sets
  `<html data-theme="…">` and `color-scheme`.
- The theme toggle cycles with `cycleTheme`. Dark values are defined as CSS
  custom properties under `:root[data-theme="dark"]`; most surfaces use
  `var(--card)` / `var(--text)` so they invert automatically.

### Keyboard shortcuts
A single idempotent global handler (`ensureGlobalShortcuts`) maps events via
the pure `parseShortcut(event, prevKey, inInput)`:

| Keys | Action |
| --- | --- |
| `⌘K` / `Ctrl+K` | Open command palette (works even in inputs) |
| `/` | Search everything |
| `N` | Toggle notification center |
| `?` | Toggle shortcuts help |
| `G` then `D/I/A/T/W/S/R/H` | Go to Dashboard / Incidents / Applications / AI Teams / Workflows / Services / War Rooms / Help |
| `Esc` | Close any open overlay |

Single-key shortcuts are suppressed while typing in inputs/textareas/selects.

### Accessibility (WCAG 2.1 AA)
- Skip-to-content link, `<main id="main-content" tabindex="-1">` landmark.
- Visible `:focus-visible` outlines; focus is trapped inside open overlays
  (`installFocusTrap`) and overlays are `role="dialog" aria-modal="true"`.
- `aria-live` regions for toasts; `aria-label`s on icon-only controls;
  `.sr-only` helper for screen-reader-only text.
- `prefers-reduced-motion` disables shimmer/slide animations.

### Responsive
- Topbar tools collapse, the org-switcher label hides, toasts span the full
  width, and the notification panel becomes full-screen below 720px. The
  sidebar continues to use the existing off-canvas drawer.

## Testing

`static/frontend.test.mjs` exercises the pure helpers in a DOM-less VM sandbox
(`static/frontend.harness.mjs`): theme resolution/cycling, toast queue capping,
notification store, command registry + fuzzy filter, global search index,
shortcut parsing and skeleton output. DOM-touching functions are no-ops under
the harness so `render()` stays test-safe.

```bash
node --check static/app.js
node scripts/validate-frontend.js
node --test static/frontend.test.mjs
```
