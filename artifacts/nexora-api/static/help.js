/*
 * Nexora Help Center chunk — lazy-loaded by app.js on /help routes.
 * Extracted from app.js for code-splitting. Classic script: its top-level
 * functions register on the global scope and reuse core helpers
 * (state, api, navigate, render, escapeHtml, navIcon, renderSkeleton, ...).
 */

/* ============================================================
 * Sprint 51F — Customer Documentation Portal (Help Center) UI.
 * Read-only consumer of the Sprint 51A–51E APIs:
 *   - 51A Documentation Center (/v1/docs/articles, /navigation, /portal, exports)
 *   - 51C Demo Asset Manager   (/v1/demo-assets/gallery)
 *   - 51D Product Tours        (/v1/product-tours)
 *   - 51E Documentation generator (/v1/docs/generate, /manual)
 * No backend/schema/migration changes.
 * ============================================================ */

function docDarkOn() {
  if (typeof state.docDark === "boolean") return state.docDark;
  try { return localStorage.getItem("docDark") === "1"; } catch { return false; }
}

function helpThemeClass() {
  return docDarkOn() ? "help-center doc-dark" : "help-center";
}

function helpAllCats() {
  const out = [];
  const walk = (arr) => (arr || []).forEach((c) => { out.push(c); if (c.children) walk(c.children); });
  walk(state.helpNav?.categories || []);
  return out;
}

function helpCatByKey(key) { return helpAllCats().find((c) => c.key === key) || null; }
function helpCatById(id) { return helpAllCats().find((c) => c.id === id) || null; }

function helpFmtDate(value) {
  if (!value) return "";
  try { return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }); }
  catch { return String(value); }
}

// Minimal, safe Markdown -> HTML for article rendering.
function mdToHtml(md) {
  if (!md) return "";
  const esc = (s) => escapeHtml(s);
  const inline = (s) => {
    let t = esc(s);
    t = t.replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`);
    t = t.replace(/\*\*([^*]+)\*\*/g, (_m, c) => `<strong>${c}</strong>`);
    t = t.replace(/(^|[^*])\*([^*]+)\*/g, (_m, p, c) => `${p}<em>${c}</em>`);
    t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, a, u) => {
      const s = helpImgSrc(u);
      return `<img class="help-inline-shot" alt="${a}" src="${s}" loading="lazy" data-zoom="${s}" title="Click to enlarge" />`;
    });
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, txt, u) => `<a href="${u}" target="_blank" rel="noopener">${txt}</a>`);
    return t;
  };
  const lines = String(md).split(/\r?\n/);
  const out = [];
  let inCode = false, codeBuf = [], listType = null, paraBuf = [];
  const flushPara = () => { if (paraBuf.length) { out.push(`<p>${inline(paraBuf.join(" "))}</p>`); paraBuf = []; } };
  const closeList = () => { if (listType) { out.push(listType === "ul" ? "</ul>" : "</ol>"); listType = null; } };
  const fence = "```";
  for (const raw of lines) {
    const line = raw;
    if (line.trim().startsWith(fence)) {
      if (inCode) { out.push(`<pre><code>${esc(codeBuf.join("\n"))}</code></pre>`); codeBuf = []; inCode = false; }
      else { flushPara(); closeList(); inCode = true; }
      continue;
    }
    if (inCode) { codeBuf.push(line); continue; }
    if (!line.trim()) { flushPara(); closeList(); continue; }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { flushPara(); closeList(); const lvl = h[1].length; out.push(`<h${lvl}>${inline(h[2])}</h${lvl}>`); continue; }
    if (/^\s*>\s?/.test(line)) { flushPara(); closeList(); out.push(`<blockquote>${inline(line.replace(/^\s*>\s?/, ""))}</blockquote>`); continue; }
    const ol = line.match(/^\s*\d+\.\s+(.*)$/);
    if (ol) { flushPara(); if (listType !== "ol") { closeList(); out.push("<ol>"); listType = "ol"; } out.push(`<li>${inline(ol[1])}</li>`); continue; }
    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    if (ul) { flushPara(); if (listType !== "ul") { closeList(); out.push("<ul>"); listType = "ul"; } out.push(`<li>${inline(ul[1])}</li>`); continue; }
    paraBuf.push(line.trim());
  }
  if (inCode) out.push(`<pre><code>${esc(codeBuf.join("\n"))}</code></pre>`);
  flushPara(); closeList();
  return out.join("\n");
}

async function loadHelpData() {
  const p = state.route.page;
  state.helpNav = await api("/v1/docs/navigation").catch(() => ({ categories: [], total_articles: 0 }));
  // First-visit bootstrap: if the portal is empty and the user can write, generate
  // the customer documentation automatically so categories are populated. Generation
  // is deterministic + idempotent (51E), so this is safe to run once per session.
  if ((state.helpNav.total_articles || 0) === 0 && canWriteResources() && !state.helpAutoGenTried) {
    state.helpAutoGenTried = true;
    try {
      await api("/v1/docs/generate", { method: "POST" });
      state.helpNav = await api("/v1/docs/navigation").catch(() => state.helpNav);
    } catch { /* leave the manual "Generate Docs" button as a fallback */ }
  }
  if (p === "help-home") {
    const all = await api("/v1/docs/articles?limit=200").catch(() => ({ items: [], total: 0 }));
    state.helpAllArticles = all.items || [];
  } else if (p === "help-search") {
    const params = new URLSearchParams();
    if (state.route.q) params.set("search", state.route.q);
    if (state.route.category) params.set("category_key", state.route.category);
    params.set("limit", "200");
    const res = await api(`/v1/docs/articles?${params.toString()}`).catch(() => ({ items: [], total: 0 }));
    state.helpSearchResults = res.items || [];
    state.helpSearchTotal = res.total || 0;
  } else if (p === "help-category") {
    const res = await api(`/v1/docs/articles?category_key=${encodeURIComponent(state.route.key)}&limit=200`).catch(() => ({ items: [] }));
    state.helpCategoryArticles = res.items || [];
  } else if (p === "help-article") {
    state.helpArticle = await api(`/v1/docs/articles/${state.route.id}`).catch(() => null);
    state.helpRelated = [];
    if (state.helpArticle) {
      const res = await api(`/v1/docs/articles?category_id=${encodeURIComponent(state.helpArticle.category_id)}&limit=12`).catch(() => ({ items: [] }));
      state.helpRelated = (res.items || []).filter((a) => a.id !== state.helpArticle.id).slice(0, 6);
    }
  } else if (p === "help-api") {
    const res = await api("/v1/docs/articles?category_key=api-reference&limit=50").catch(() => ({ items: [] }));
    const stub = (res.items || []).find((a) => a.slug === "api-guide") || (res.items || [])[0];
    state.helpApiArticle = stub ? await api(`/v1/docs/articles/${stub.id}?track_view=false`).catch(() => null) : null;
    state.helpApiList = res.items || [];
  } else if (p === "help-troubleshooting") {
    const res = await api("/v1/docs/articles?category_key=troubleshooting&limit=100").catch(() => ({ items: [] }));
    state.helpTroubleshootArticles = res.items || [];
    const stub = (res.items || []).find((a) => a.slug === "troubleshooting-guide");
    state.helpTroubleshootMain = stub ? await api(`/v1/docs/articles/${stub.id}?track_view=false`).catch(() => null) : null;
  } else if (p === "help-getting-started") {
    const res = await api("/v1/docs/articles?category_key=getting-started&limit=100").catch(() => ({ items: [] }));
    state.helpGSArticles = res.items || [];
  } else if (p === "help-onboarding") {
    const res = await api("/v1/docs/articles?category_key=onboarding&limit=100").catch(() => ({ items: [] }));
    state.helpOnbArticles = res.items || [];
  } else if (p === "help-demos") {
    const [gallery, arts] = await Promise.all([
      api("/v1/demo-assets/gallery").catch(() => ({ sections: [], total_assets: 0 })),
      api("/v1/docs/articles?search=demo&limit=50").catch(() => ({ items: [] })),
    ]);
    state.helpGallery = gallery;
    state.helpDemoArticles = arts.items || [];
  } else if (p === "help-tours") {
    state.helpTours = await api("/v1/product-tours").catch(() => []);
  }
}

async function helpDownload(url, filename) {
  try {
    const resp = await fetch(apiUrl(url), { headers: { Authorization: `Bearer ${getToken()}` } });
    if (!resp.ok) throw new Error("Download failed");
    const blob = await resp.blob();
    const u = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = u; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(u);
  } catch (error) { state.error = error.message; render(); }
}

function bindHelpEvents() {
  document.querySelector("[data-help-search]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const params = new URLSearchParams();
    const q = (fd.get("q") || "").toString().trim();
    if (q) params.set("q", q);
    if (fd.get("category")) params.set("category", fd.get("category"));
    void navigate(`/help/search?${params.toString()}`);
  });

  document.querySelector("[data-doc-dark]")?.addEventListener("click", () => {
    state.docDark = !docDarkOn();
    try { localStorage.setItem("docDark", state.docDark ? "1" : "0"); } catch { /* ignore */ }
    render();
  });

  document.querySelectorAll("[data-help-download]").forEach((el) => {
    el.addEventListener("click", async () => {
      const fmt = el.getAttribute("data-help-download");
      const articleId = el.getAttribute("data-article");
      const slug = el.getAttribute("data-slug") || "article";
      const manualGuide = el.getAttribute("data-manual");
      const ext = fmt === "markdown" ? "md" : fmt;
      if (manualGuide) {
        await helpDownload(`/v1/docs/manual?guide=${manualGuide}&format=${fmt}`, `nexora-${manualGuide}.${ext}`);
      } else if (articleId) {
        await helpDownload(`/v1/docs/articles/${articleId}/export?format=${fmt}`, `${slug}.${ext}`);
      }
    });
  });

  document.querySelector("[data-help-generate]")?.addEventListener("click", async () => {
    if (!canWriteResources()) { state.error = "You do not have permission to generate documentation."; render(); return; }
    state.helpGenerating = true; state.error = null; render();
    try {
      const res = await api("/v1/docs/generate", { method: "POST" });
      state.helpGenerating = false;
      state.message = `Documentation generated: ${res.articles_generated} articles from ${res.routes_scanned} routes.`;
      await loadHelpData();
      render();
    } catch (error) { state.helpGenerating = false; state.error = error.message; render(); }
  });

  document.querySelectorAll("[data-help-tour-start]").forEach((el) => {
    el.addEventListener("click", async () => {
      const key = el.getAttribute("data-help-tour-start");
      const restart = el.getAttribute("data-restart") === "1";
      try {
        await api("/v1/product-tours/start", { method: "POST", body: JSON.stringify({ tour_key: key, restart }) });
        state.message = restart ? "Tour restarted." : "Tour started.";
        await loadHelpData();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-help-tour-step]").forEach((el) => {
    el.addEventListener("click", async () => {
      const tourId = el.getAttribute("data-tour-id");
      const stepId = el.getAttribute("data-help-tour-step");
      try {
        await api(`/v1/product-tours/${tourId}/step`, { method: "POST", body: JSON.stringify({ step_id: stepId }) });
        await loadHelpData();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-help-tour-complete]").forEach((el) => {
    el.addEventListener("click", async () => {
      const tourId = el.getAttribute("data-help-tour-complete");
      try {
        await api(`/v1/product-tours/${tourId}/complete`, { method: "POST" });
        state.message = "Tour completed.";
        await loadHelpData();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
}

function renderHelpToolbar(activeCategory) {
  const cats = helpAllCats();
  const options = ['<option value="">All categories</option>']
    .concat(cats.map((c) => `<option value="${escapeHtml(c.key)}" ${activeCategory === c.key ? "selected" : ""}>${escapeHtml(c.name)}</option>`))
    .join("");
  const admin = canWriteResources()
    ? `<button class="btn btn-secondary" data-help-generate ${state.helpGenerating ? "disabled" : ""}>${state.helpGenerating ? "Generating…" : "↻ Generate Docs"}</button>`
    : "";
  return `
    <div class="help-toolbar">
      <form class="help-searchbar" data-help-search>
        ${navIcon("search")}
        <input name="q" placeholder="Search documentation…" value="${escapeHtml(state.route.q || "")}" autocomplete="off" />
        <select name="category" aria-label="Filter by category">${options}</select>
        <button class="btn btn-primary" type="submit">Search</button>
      </form>
      <div class="help-toolbar-actions">
        ${admin}
        <button class="btn btn-secondary btn-icon" data-doc-dark title="Toggle dark mode" aria-label="Toggle dark mode">${docDarkOn() ? "☀" : "☾"}</button>
      </div>
    </div>`;
}

function renderHelpTree(activeKey, activeArticleId) {
  const cats = state.helpNav?.categories || [];
  if (!cats.length) return `<p class="muted">No documentation yet.</p>`;
  const node = (c) => {
    const isActive = c.key === activeKey;
    const articles = (c.articles || []);
    return `
      <div class="help-tree-cat">
        <a class="help-tree-link ${isActive ? "active" : ""}" href="/help/c/${encodeURIComponent(c.key)}" data-nav="/help/c/${encodeURIComponent(c.key)}">
          <span>${escapeHtml(c.name)}</span><span class="help-pill">${c.article_count || articles.length || 0}</span>
        </a>
        ${isActive && articles.length ? `<div class="help-tree-articles">${articles.map((a) => `
          <a class="help-tree-article ${a.id === activeArticleId ? "active" : ""}" href="/help/a/${a.id}" data-nav="/help/a/${a.id}">${escapeHtml(a.title)}</a>`).join("")}</div>` : ""}
        ${(c.children || []).map(node).join("")}
      </div>`;
  };
  return `<p class="help-tree-title">Categories</p>${cats.map(node).join("")}`;
}

function renderBreadcrumbs(crumbs) {
  return `<nav class="help-crumbs">${crumbs.map((c, i) => {
    const last = i === crumbs.length - 1;
    if (last || !c.path) return `<span class="help-crumb current">${escapeHtml(c.label)}</span>`;
    return `<a href="${c.path}" data-nav="${c.path}">${escapeHtml(c.label)}</a><span class="help-crumb-sep">/</span>`;
  }).join("")}</nav>`;
}

function renderHelpLayout(crumbs, mainHtml, activeKey, activeArticleId) {
  return `
    <div class="container ${helpThemeClass()}">
      ${renderHeader("Help Center", "Guides, API reference, demos & product tours")}
      ${renderAlerts()}
      ${renderHelpToolbar(state.route.category || activeKey)}
      ${renderBreadcrumbs(crumbs)}
      <div class="help-grid">
        <aside class="help-tree card">${renderHelpTree(activeKey, activeArticleId)}</aside>
        <div class="help-content">${mainHtml}</div>
      </div>
    </div>`;
}

// Sprint 52B — parse customer-success metadata carried in article tags.
function parseDocMeta(tags) {
  const meta = { role: "", difficulty: "", reading: "", value: "", module: "" };
  (tags || []).forEach((t) => {
    const i = t.indexOf(":");
    if (i < 0) return;
    const k = t.slice(0, i);
    const v = t.slice(i + 1);
    if (k in meta) meta[k] = v;
  });
  return meta;
}

function difficultyClass(d) {
  const k = (d || "").toLowerCase();
  if (k === "beginner") return "diff-beginner";
  if (k === "intermediate") return "diff-intermediate";
  if (k === "advanced") return "diff-advanced";
  return "";
}

// Canonicalize a documentation screenshot URL so it always resolves to the
// dynamically-rendered screenshot endpoint (HTTP 200). Rewrites stale static
// PNG paths / base-path-less references; leaves genuine external images alone.
function helpImgSrc(url) {
  if (!url) return url;
  const canon = "/nexora-api/v1/customer-success/screenshots";
  if (url.indexOf(canon + "/") === 0) return url;
  const stale = url.indexOf("/static/docs/screenshots/") === 0;
  const isPng = /\.png(\?|#|$)/i.test(url);
  const relative = url.charAt(0) === "/" && url.indexOf("/nexora-api") !== 0;
  if (!stale && !isPng && !relative) return url;
  const base = url.split("?")[0].split("#")[0].replace(/\/+$/, "");
  const name = base.substring(base.lastIndexOf("/") + 1);
  const id = name.indexOf(".") >= 0 ? name.substring(0, name.lastIndexOf(".")) : name;
  return id ? canon + "/" + id : url;
}

// Reading order for the guides within a module, used by the article pager.
function helpGuideRank(title) {
  const t = (title || "").toLowerCase();
  if (t.includes("overview")) return 0;
  if (t.includes("walkthrough")) return 1;
  if (t.includes("use case")) return 2;
  if (t.includes("user guide")) return 3;
  if (t.includes("faq")) return 5;
  return 4;
}

function docMetaBadges(tags, { compact = false } = {}) {
  const m = parseDocMeta(tags);
  const out = [];
  if (m.reading) out.push(`<span class="doc-badge" title="Estimated reading time">⏱ ${escapeHtml(m.reading)} min</span>`);
  if (m.difficulty) out.push(`<span class="doc-badge ${difficultyClass(m.difficulty)}" title="Difficulty">${escapeHtml(m.difficulty)}</span>`);
  if (!compact && m.role) out.push(`<span class="doc-badge" title="Recommended role">${escapeHtml(m.role)}</span>`);
  if (m.value) out.push(`<span class="doc-badge value-${escapeHtml(m.value.toLowerCase())}" title="Business value">${escapeHtml(m.value)} value</span>`);
  return out.length ? `<div class="doc-badges">${out.join("")}</div>` : "";
}

function helpEmptyState(message) {
  const portalEmpty = (state.helpNav?.total_articles || 0) === 0;
  const cta = portalEmpty && canWriteResources()
    ? `<div style="margin-top:12px;"><button class="btn btn-primary" data-help-generate ${state.helpGenerating ? "disabled" : ""}>${state.helpGenerating ? "Generating…" : "Generate Documentation"}</button></div>
       <p class="muted" style="margin-top:8px;">This builds the full documentation portal from your live platform (one click).</p>`
    : (portalEmpty ? `<p class="muted" style="margin-top:8px;">No documentation has been generated yet. Please ask an administrator to generate it.</p>` : "");
  return `<div class="help-empty"><p class="muted">${message}</p>${cta}</div>`;
}

function helpArticleCard(a) {
  const cat = helpCatById(a.category_id);
  return `
    <a class="help-card" href="/help/a/${a.id}" data-nav="/help/a/${a.id}">
      <h3>${escapeHtml(a.title)}</h3>
      <p class="muted">${escapeHtml(a.summary || (cat ? cat.name : ""))}</p>
      ${docMetaBadges(a.tags, { compact: true })}
      <div class="help-card-meta">
        ${cat ? `<span class="help-pill">${escapeHtml(cat.name)}</span>` : ""}
        <span class="muted">${a.view_count || 0} views · ${helpFmtDate(a.updated_at)}</span>
      </div>
    </a>`;
}

function renderHelpHome() {
  const all = state.helpAllArticles || [];
  const popular = [...all].sort((a, b) => (b.view_count || 0) - (a.view_count || 0)).slice(0, 6);
  const recent = [...all].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at)).slice(0, 6);
  const cats = state.helpNav?.categories || [];
  const quick = [
    { label: "Getting Started", path: "/help/getting-started", icon: "book" },
    { label: "Onboarding", path: "/help/onboarding", icon: "wand" },
    { label: "API Reference", path: "/help/api", icon: "code" },
    { label: "Troubleshooting", path: "/help/troubleshooting", icon: "tools" },
    { label: "Demo Guides", path: "/help/demos", icon: "monitor" },
    { label: "Product Tours", path: "/help/tours", icon: "target" },
  ];
  const empty = !all.length;
  const main = `
    <section class="help-hero">
      <h2>How can we help?</h2>
      <p class="muted">Search the documentation or browse by category.</p>
      <form class="help-hero-search" data-help-search>
        ${navIcon("search")}
        <input name="q" placeholder="Search guides, API, troubleshooting…" autocomplete="off" />
        <button class="btn btn-primary" type="submit">Search</button>
      </form>
    </section>
    ${empty ? `<section class="card">${helpEmptyState("No documentation has been generated yet.")}</section>` : ""}
    <div class="help-quicklinks">
      ${quick.map((q) => `<a class="help-quick" href="${q.path}" data-nav="${q.path}">${navIcon(q.icon)}<span>${q.label}</span></a>`).join("")}
    </div>
    ${popular.length ? `<section class="help-section"><h3>Popular Articles</h3><div class="help-card-grid">${popular.map(helpArticleCard).join("")}</div></section>` : ""}
    ${recent.length ? `<section class="help-section"><h3>Recently Updated</h3><div class="help-card-grid">${recent.map(helpArticleCard).join("")}</div></section>` : ""}
    <section class="help-section">
      <h3>Browse by Category</h3>
      <div class="help-cat-grid">
        ${cats.map((c) => `<a class="help-cat-tile" href="/help/c/${encodeURIComponent(c.key)}" data-nav="/help/c/${encodeURIComponent(c.key)}"><span>${escapeHtml(c.name)}</span><span class="help-pill">${c.article_count || 0}</span></a>`).join("")}
      </div>
    </section>`;
  return renderHelpLayout([{ label: "Help Center" }], main);
}

function renderHelpSearch() {
  const results = state.helpSearchResults || [];
  const q = state.route.q || "";
  const main = `
    <section class="help-section">
      <h3>Search results</h3>
      <p class="muted">${state.helpSearchTotal || 0} result(s) ${q ? `for “${escapeHtml(q)}”` : ""}${state.route.category ? ` in ${escapeHtml((helpCatByKey(state.route.category) || {}).name || state.route.category)}` : ""}</p>
      ${results.length ? `<div class="help-card-grid">${results.map(helpArticleCard).join("")}</div>` : helpEmptyState("No matching articles. Try a different term or category.")}
    </section>`;
  return renderHelpLayout([{ label: "Help Center", path: "/help" }, { label: "Search" }], main, state.route.category);
}

function renderHelpCategory() {
  const cat = helpCatByKey(state.route.key);
  const arts = state.helpCategoryArticles || [];
  const main = `
    <section class="help-section">
      <h3>${escapeHtml(cat ? cat.name : "Category")}</h3>
      <p class="muted">${arts.length} article(s)</p>
      ${arts.length ? `<div class="help-card-grid">${arts.map(helpArticleCard).join("")}</div>` : helpEmptyState("No articles in this category yet.")}
    </section>`;
  return renderHelpLayout(
    [{ label: "Help Center", path: "/help" }, { label: cat ? cat.name : "Category" }],
    main, state.route.key
  );
}

// Install a single delegated click handler that enlarges documentation
// screenshots in a full-screen overlay. Idempotent across re-renders.
function ensureHelpLightbox() {
  if (window.__helpLightboxReady) return;
  window.__helpLightboxReady = true;
  document.addEventListener("click", (event) => {
    const img = event.target.closest && event.target.closest("img[data-zoom]");
    if (img) {
      const src = img.getAttribute("data-zoom") || img.src;
      const cap = img.getAttribute("alt") || "";
      const overlay = document.createElement("div");
      overlay.className = "help-lightbox";
      overlay.innerHTML =
        `<div class="help-lightbox-inner"><img src="${escapeHtml(src)}" alt="${escapeHtml(cap)}" />` +
        (cap ? `<div class="help-lightbox-cap">${escapeHtml(cap)}</div>` : "") +
        `<button class="help-lightbox-close" aria-label="Close">×</button></div>`;
      document.body.appendChild(overlay);
      document.body.style.overflow = "hidden";
      return;
    }
    if (event.target.closest && event.target.closest(".help-lightbox")) {
      const ov = document.querySelector(".help-lightbox");
      if (ov) ov.remove();
      document.body.style.overflow = "";
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      const ov = document.querySelector(".help-lightbox");
      if (ov) { ov.remove(); document.body.style.overflow = ""; }
    }
  });
}

function renderHelpArticle() {
  const a = state.helpArticle;
  if (!a) return renderHelpLayout([{ label: "Help Center", path: "/help" }, { label: "Article" }], `<section class="card"><p class="muted">${detailPendingMessage("article")}</p></section>`);
  const cat = helpCatById(a.category_id);
  const vids = (a.videos || []).filter((v) => v && v.url);
  // De-duplicate screenshots by their resolved image src so the same captured
  // page is not shown multiple times in the gallery.
  const seenShotSrc = new Set();
  const uniqueShots = [];
  (a.screenshots || []).forEach((s) => {
    if (!s || !s.url) return;
    const src = helpImgSrc(s.url);
    if (seenShotSrc.has(src)) return;
    seenShotSrc.add(src);
    uniqueShots.push({ src, caption: s.caption || "" });
  });
  ensureHelpLightbox();
  // When the article body already embeds inline step screenshots, skip the
  // separate gallery to avoid showing the same images twice.
  const hasInlineShots = typeof a.content === "string" && a.content.includes("![");
  const gallery = (!hasInlineShots && uniqueShots.length) ? `
    <section class="help-gallery">
      <h4>Screenshots</h4>
      <div class="help-shot-grid">
        ${uniqueShots.map((s) => `<figure class="help-shot"><img src="${escapeHtml(s.src)}" alt="${escapeHtml(s.caption)}" loading="lazy" data-zoom="${escapeHtml(s.src)}" title="Click to enlarge" /><figcaption>${escapeHtml(s.caption)}</figcaption></figure>`).join("")}
      </div>
    </section>` : "";
  const videos = vids.length ? `
    <section class="help-gallery">
      <h4>Videos</h4>
      <div class="help-video-grid">
        ${vids.map((v) => `<a class="help-video" href="${escapeHtml(v.url)}" target="_blank" rel="noopener">${navIcon("monitor")}<span>${escapeHtml(v.title || v.url)}</span></a>`).join("")}
      </div>
    </section>` : "";
  const meta = parseDocMeta(a.tags);
  const related = (state.helpRelated || []);
  // Split related into "next recommended guides" (same module, other guide types) and the rest.
  const nextGuides = meta.module
    ? related.filter((r) => parseDocMeta(r.tags).module === meta.module)
    : [];
  const nextIds = new Set(nextGuides.map((r) => r.id));
  const otherRelated = related.filter((r) => !nextIds.has(r.id));
  // Simple Previous / Next navigation across the guides in this module.
  const siblings = [a, ...nextGuides]
    .filter((r, i, all) => all.findIndex((x) => x.id === r.id) === i)
    .sort((x, y) => helpGuideRank(x.title) - helpGuideRank(y.title) || (x.title || "").localeCompare(y.title || ""));
  const curIdx = siblings.findIndex((r) => r.id === a.id);
  const prev = curIdx > 0 ? siblings[curIdx - 1] : null;
  const next = curIdx >= 0 && curIdx < siblings.length - 1 ? siblings[curIdx + 1] : null;
  const pagerLink = (art, dir) => {
    const label = dir === "prev" ? "← Previous" : "Next →";
    if (!art) return `<span class="help-pager-link is-disabled"><span class="help-pager-dir">${label}</span></span>`;
    return `<a class="help-pager-link ${dir}" href="/help/a/${art.id}" data-nav="/help/a/${art.id}">
        <span class="help-pager-dir">${label}</span>
        <strong>${escapeHtml(art.title)}</strong>
      </a>`;
  };
  const nextHtml = (prev || next)
    ? `<nav class="help-pager">${pagerLink(prev, "prev")}${pagerLink(next, "next")}</nav>`
    : "";
  const relatedHtml = otherRelated.length ? `
    <section class="help-section">
      <h3>Related Articles</h3>
      <div class="help-card-grid">${otherRelated.map(helpArticleCard).join("")}</div>
    </section>` : "";
  const main = `
    <article class="help-article card">
      <div class="help-article-head">
        <h2>${escapeHtml(a.title)}</h2>
        <div class="help-article-meta">
          ${cat ? `<a class="help-pill" href="/help/c/${encodeURIComponent(cat.key)}" data-nav="/help/c/${encodeURIComponent(cat.key)}">${escapeHtml(cat.name)}</a>` : ""}
          <span class="muted">v${a.version || 1} · ${a.view_count || 0} views · Updated ${helpFmtDate(a.updated_at)}</span>
        </div>
        ${docMetaBadges(a.tags)}
      </div>
      ${gallery}
      <div class="help-article-body">${mdToHtml(a.content)}</div>
      ${videos}
    </article>
    ${nextHtml}
    ${relatedHtml}`;
  return renderHelpLayout(
    [{ label: "Help Center", path: "/help" }, cat ? { label: cat.name, path: `/help/c/${cat.key}` } : { label: "Docs" }, { label: a.title }],
    main, cat ? cat.key : null, a.id
  );
}

function renderHelpApi() {
  const a = state.helpApiArticle;
  const main = `
    <section class="help-section">
      <div class="help-section-head">
        <h3>API Reference</h3>
        <div class="help-downloads">
          <button class="btn btn-secondary" data-help-download="pdf" data-manual="api">PDF</button>
          <button class="btn btn-secondary" data-help-download="html" data-manual="api">HTML</button>
          <button class="btn btn-secondary" data-help-download="markdown" data-manual="api">Markdown</button>
        </div>
      </div>
      ${a ? `<article class="help-article card"><div class="help-article-body help-api-body">${mdToHtml(a.content)}</div></article>`
          : `<section class="card">${helpEmptyState("No API reference yet.")}</section>`}
    </section>`;
  return renderHelpLayout([{ label: "Help Center", path: "/help" }, { label: "API Reference" }], main, "api-reference");
}

function renderHelpTroubleshooting() {
  const main = state.helpTroubleshootMain;
  const arts = state.helpTroubleshootArticles || [];
  const body = `
    <section class="help-section">
      <h3>Troubleshooting Center</h3>
      ${main ? `<article class="help-article card"><div class="help-article-body">${mdToHtml(main.content)}</div></article>` : ""}
      ${arts.length ? `<div class="help-card-grid">${arts.map(helpArticleCard).join("")}</div>` : helpEmptyState("No troubleshooting articles yet.")}
    </section>`;
  return renderHelpLayout([{ label: "Help Center", path: "/help" }, { label: "Troubleshooting" }], body, "troubleshooting");
}

function renderHelpGettingStarted() {
  const arts = state.helpGSArticles || [];
  const workflowLanes = [
    { order: 1, title: "Respond", when: "Something broke — alert fired, build failed, or customers impacted.", href: "/incidents" },
    { order: 2, title: "Connect", when: "First setup or adding a new tool to your estate.", href: "/integrations" },
    { order: 3, title: "Observe", when: "Proactive monitoring — catch degradation before customers do.", href: "/alerts" },
    { order: 4, title: "Deliver", when: "Releasing code or reviewing CI/CD health.", href: "/delivery" },
    { order: 5, title: "Improve", when: "After resolving — capture lessons and automate recovery.", href: "/incident-response/postmortems" },
  ];
  const workflowHtml = workflowLanes.map((flow) => `
    <article class="help-workflow-lane card">
      <div class="help-workflow-lane-head">
        <span class="ops-guide-flow-num">${flow.order}</span>
        <h4><a href="${escapeHtml(flow.href)}" data-nav="${escapeHtml(flow.href)}">${escapeHtml(flow.title)}</a></h4>
      </div>
      <p class="muted">${escapeHtml(flow.when)}</p>
    </article>`).join("");
  const roadmapHtml = `
    <section class="help-section card" style="margin-top:16px;">
      <h3>Integration roadmap</h3>
      <p class="muted">35 integrations ship today. Future roadmap:</p>
      <ul class="muted" style="margin:8px 0 0;padding-left:20px;">
        <li>Full Harness/Buildkite pipeline sync (ingest live today)</li>
        <li>Live Flux CD reconciliation from cluster API</li>
      </ul>
    </section>`;
  const body = `
    <section class="help-section">
      <h3>Getting Started</h3>
      <p class="muted">New to Nexora? Follow the five-lane SRE workflow below, then connect your estate.</p>
      <div class="help-workflow-grid">${workflowHtml}</div>
    </section>
    <section class="help-section">
      <h3>Guides & articles</h3>
      ${arts.length ? `<div class="help-card-grid">${arts.map(helpArticleCard).join("")}</div>` : helpEmptyState("No getting-started guides yet.")}
    </section>
    ${roadmapHtml}`;
  return renderHelpLayout([{ label: "Help Center", path: "/help" }, { label: "Getting Started" }], body, "getting-started");
}

function renderHelpOnboarding() {
  const arts = state.helpOnbArticles || [];
  const body = `
    <section class="help-section">
      <h3>Onboarding Guides</h3>
      <p class="muted">Step-by-step onboarding for your team.</p>
      ${arts.length ? `<div class="help-card-grid">${arts.map(helpArticleCard).join("")}</div>` : helpEmptyState("No onboarding guides yet.")}
      <p style="margin-top:14px;"><a class="btn btn-secondary" href="/help/tours" data-nav="/help/tours">▶ Start an interactive product tour</a></p>
    </section>`;
  return renderHelpLayout([{ label: "Help Center", path: "/help" }, { label: "Onboarding" }], body, "onboarding");
}

function renderHelpDemos() {
  const gallery = state.helpGallery || { sections: [], total_assets: 0 };
  const arts = state.helpDemoArticles || [];
  const shotSections = [];
  const videoItems = [];
  (gallery.sections || []).forEach((sec) => {
    const shots = (sec.assets || []).filter((x) => x.asset_type !== "VIDEO");
    const vids = (sec.assets || []).filter((x) => x.asset_type === "VIDEO");
    if (shots.length) {
      shotSections.push(`
        <div class="help-demo-group">
          <h4>${escapeHtml(sec.category)}</h4>
          <div class="help-shot-grid">${shots.map((s) => `<figure class="help-shot"><img src="${escapeHtml(s.url)}" alt="${escapeHtml(s.title || "")}" loading="lazy" /><figcaption>${escapeHtml(s.title || "")}</figcaption></figure>`).join("")}</div>
        </div>`);
    }
    vids.forEach((v) => videoItems.push(v));
  });
  const body = `
    <section class="help-section">
      <h3>Demo Guides</h3>
      <p class="muted">${gallery.total_assets || 0} demo asset(s) across ${(gallery.sections || []).length} categories.</p>
      ${arts.length ? `<div class="help-card-grid">${arts.map(helpArticleCard).join("")}</div>` : ""}
    </section>
    <section class="help-section">
      <h3>Screenshot Gallery</h3>
      ${shotSections.length ? shotSections.join("") : `<p class="muted">No screenshots uploaded yet.</p>`}
    </section>
    <section class="help-section">
      <h3>Video Gallery</h3>
      ${videoItems.length ? `<div class="help-video-grid">${videoItems.map((v) => `<a class="help-video" href="${escapeHtml(v.url)}" target="_blank" rel="noopener">${navIcon("monitor")}<span>${escapeHtml(v.title || v.url)}</span></a>`).join("")}</div>` : `<p class="muted">No demo videos uploaded yet.</p>`}
    </section>`;
  return renderHelpLayout([{ label: "Help Center", path: "/help" }, { label: "Demo Guides" }], body);
}

function renderHelpTours() {
  const tours = state.helpTours || [];
  const card = (t) => {
    const prog = t.progress;
    const pct = prog ? (prog.progress_percent || 0) : 0;
    const status = prog ? prog.status : "NOT_STARTED";
    return `
      <div class="help-tour card">
        <div class="help-tour-head">
          <div>
            <h4>${escapeHtml(t.name)}</h4>
            <p class="muted">${escapeHtml(t.description || "")}</p>
            <p class="muted">${escapeHtml(t.audience || "ALL")} · ${t.step_count || 0} steps${t.estimated_minutes ? ` · ~${t.estimated_minutes} min` : ""}</p>
          </div>
          <span class="help-pill">${escapeHtml(status.replace(/_/g, " "))}</span>
        </div>
        <div class="help-progress"><span style="width:${pct}%;"></span></div>
        <div class="help-tour-actions">
          <button class="btn btn-primary" data-help-tour-start="${escapeHtml(t.key)}">${prog && status !== "NOT_STARTED" ? "Resume" : "Start"}</button>
          ${prog && status !== "NOT_STARTED" ? `<button class="btn btn-secondary" data-help-tour-start="${escapeHtml(t.key)}" data-restart="1">Restart</button>` : ""}
          ${prog && status !== "COMPLETED" ? `<button class="btn btn-secondary" data-help-tour-complete="${t.id}">Mark complete</button>` : ""}
        </div>
      </div>`;
  };
  const body = `
    <section class="help-section">
      <h3>Interactive Product Tours</h3>
      <p class="muted">Guided, in-app walkthroughs. Progress is saved so you can resume anytime.</p>
      ${tours.length ? `<div class="help-tour-grid">${tours.map(card).join("")}</div>` : `<p class="muted">No product tours available.</p>`}
    </section>`;
  return renderHelpLayout([{ label: "Help Center", path: "/help" }, { label: "Product Tours" }], body);
}
