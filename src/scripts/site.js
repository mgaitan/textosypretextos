import "../styles/site.css";

const root = document.documentElement;
const body = document.body;
const navToggle = document.querySelector("[data-nav-toggle]");
const navPanel = document.querySelector("[data-nav-panel]");
const themeToggle = document.querySelector("[data-theme-toggle]");
const THEME_STORAGE_KEY = "typ:theme";

function resolveThemePreference() {
  const saved = root.dataset.theme;
  if (saved === "dark" || saved === "light") {
    return saved;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function syncThemeToggle(theme) {
  if (!themeToggle) return;
  const isDark = theme === "dark";
  themeToggle.setAttribute("aria-pressed", String(isDark));
  themeToggle.dataset.theme = theme;
  themeToggle.querySelector("[data-theme-icon]")?.replaceChildren(document.createTextNode(isDark ? "☀" : "☾"));
  themeToggle.querySelector("[data-theme-label]")?.replaceChildren(
    document.createTextNode(isDark ? "Modo claro" : "Modo oscuro")
  );
}

function applyTheme(theme) {
  root.dataset.theme = theme;
  syncThemeToggle(theme);
}

applyTheme(resolveThemePreference());

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch (_e) {
      // Ignore persistence failures.
    }
  });
}

if (navToggle && navPanel) {
  navToggle.addEventListener("click", () => {
    const expanded = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!expanded));
    navPanel.dataset.open = String(!expanded);
  });
}

window.addEventListener("load", () => {
  body.dataset.ready = "true";
  root.style.scrollBehavior = "smooth";
});

document.querySelectorAll("[data-comment-focus]").forEach((link) => {
  link.addEventListener("click", () => {
    window.setTimeout(() => {
      document.getElementById("comment-body")?.focus();
    }, 40);
  });
});

// ── Image modals ──────────────────────────────────────────────────────────────
// Modals must live directly on <body> so that `position:fixed` is not trapped
// inside a transformed ancestor (.reveal uses transform, creating a new
// stacking context that breaks fixed positioning).
document.querySelectorAll("[data-image-modal]").forEach((modal) => {
  document.body.appendChild(modal);
});

let activeImageModal = null;
let activeImageTrigger = null;

function closeImageModal(modal) {
  if (!modal) return;
  modal.hidden = true;
  modal.setAttribute("aria-hidden", "true");
  body.classList.remove("has-modal-open");
  activeImageModal = null;
  activeImageTrigger?.focus();
  activeImageTrigger = null;
}

function openImageModal(modal, trigger) {
  if (!modal) return;
  activeImageModal = modal;
  activeImageTrigger = trigger || null;
  modal.hidden = false;
  modal.setAttribute("aria-hidden", "false");
  body.classList.add("has-modal-open");
  modal.querySelector("[data-image-modal-close]")?.focus();
}

document.querySelectorAll("[data-image-modal-trigger]").forEach((trigger) => {
  trigger.addEventListener("click", (event) => {
    const modalId = trigger.getAttribute("data-image-modal-trigger");
    const modal = modalId ? document.getElementById(`image-modal-${modalId}`) : null;
    if (!modal) return;
    event.preventDefault();
    openImageModal(modal, trigger);
  });
});

document.querySelectorAll("[data-image-modal]").forEach((modal) => {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeImageModal(modal);
    }
  });

  modal.querySelectorAll("[data-image-modal-close]").forEach((button) => {
    button.addEventListener("click", () => closeImageModal(modal));
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && activeImageModal) {
    closeImageModal(activeImageModal);
  }
});

// ── Dynamic comments (D1-backed) ─────────────────────────────────────────────

const escapeHtml = (s) =>
  (s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);

function formatDate(unixSeconds) {
  if (!unixSeconds) return "";
  const d = new Date(unixSeconds * 1000);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("es-AR", { year: "numeric", month: "2-digit", day: "2-digit" });
}

async function loadDynamicComments(container, slug) {
  try {
    const res = await fetch(`/api/comments?slug=${encodeURIComponent(slug)}`, {
      headers: { accept: "application/json" },
    });
    if (!res.ok) return;
    const data = await res.json();
    const list = (data && data.comments) || [];
    if (!list.length) return;
    document.getElementById("no-comments-placeholder")?.remove();
    const html = list.map((c) => `
      <article class="comment-card" data-depth="0">
        <div class="meta-row">
          <span>${escapeHtml(c.author || "Anónimo")}</span>
          <span>${formatDate(c.created_at)}</span>
        </div>
        <div class="comment-body">${escapeHtml(c.body).replace(/\n/g, "<br>")}</div>
      </article>
    `).join("");
    container.innerHTML = html;
  } catch (_e) {
    // Silent: comment loading failure shouldn't break the page.
  }
}

async function ensureSearchIndexDocs() {
  if (window.searchIndex?.documentStore?.docs) {
    return window.searchIndex.documentStore.docs;
  }
  await new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/search_index.es.js";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("search index unavailable"));
    document.head.appendChild(script);
  });
  return window.searchIndex?.documentStore?.docs || null;
}

function slugFromUrl(value) {
  try {
    const url = new URL(value);
    const parts = url.pathname.split("/").filter(Boolean);
    return parts.at(-1) || "";
  } catch (_e) {
    return "";
  }
}

function toPathname(value) {
  try {
    return new URL(value).pathname;
  } catch (_e) {
    return value;
  }
}

function sectionMetaFromPath(pathname) {
  const sectionSlug = pathname.split("/").filter(Boolean)[0] || "";
  const sectionTitles = {
    blog: "Blog",
    "de-otros": "De otros",
    fotos: "Fotos",
    videos: "Videos",
    personal: "Personal",
  };

  return {
    sectionSlug,
    sectionTitle: sectionTitles[sectionSlug] || sectionSlug,
  };
}

function buildArticleIndexes(docs) {
  const bySlug = new Map();
  const byPath = new Map();
  Object.entries(docs || {}).forEach(([url, doc]) => {
    const pathname = toPathname(url);
    const slug = slugFromUrl(url);
    const article = {
      url: pathname,
      title: doc?.title || slug,
      ...sectionMetaFromPath(pathname),
    };

    if (pathname) {
      byPath.set(pathname, article);
    }

    if (slug && !bySlug.has(slug)) {
      bySlug.set(slug, article);
    }
  });
  return { bySlug, byPath };
}

async function loadRecentComments(container) {
  try {
    const [docs, response] = await Promise.all([
      ensureSearchIndexDocs(),
      fetch("/api/comments?recent=1&limit=5", {
        headers: { accept: "application/json" },
      }),
    ]);
    if (!response.ok || !docs) return;
    const payload = await response.json();
    const comments = (payload && payload.comments) || [];
    if (!comments.length) return;

    const { bySlug } = buildArticleIndexes(docs);
    const html = comments
      .map((comment) => {
        const article = bySlug.get(comment.article_slug);
        if (!article) return "";
        const excerpt = escapeHtml(comment.body || "").slice(0, 180);
        return `
          <article class="comment-snippet">
            <p class="story-kicker">${escapeHtml(comment.author || "Anónimo")} · ${formatDate(comment.created_at)}</p>
            <h3 class="story-title-xs">
              <a href="${article.url}">${escapeHtml(article.title)}</a>
            </h3>
            <p class="mt-2 text-sm leading-6 text-neutral-700">${excerpt}${excerpt.length >= 180 ? "…" : ""}</p>
          </article>
        `;
      })
      .filter(Boolean)
      .join("");
    if (html) {
      container.innerHTML = html;
    }
  } catch (_e) {
    // Keep the static fallback if dynamic loading fails.
  }
}

async function loadPopularReads(container) {
  try {
    const [docs, response] = await Promise.all([
      ensureSearchIndexDocs(),
      fetch("/api/views?limit=5", {
        headers: { accept: "application/json" },
      }),
    ]);
    if (!response.ok || !docs) return;
    const payload = await response.json();
    const items = (payload && payload.items) || [];
    if (!items.length) return;
    const { bySlug, byPath } = buildArticleIndexes(docs);

    const html = items
      .map((item, index) => {
        const article = byPath.get(item.article_url || "") || bySlug.get(item.article_slug);
        if (!article) return "";
        return `
          <article class="index-row">
            <div class="feed-index">${index + 1 < 10 ? "0" : ""}${index + 1}</div>
            <div>
              <p class="story-kicker">${escapeHtml(article.sectionTitle || article.sectionSlug || "")}</p>
              <h3 class="story-title-xs"><a href="${escapeHtml(article.url || "/")}">${escapeHtml(article.title || item.article_slug || "")}</a></h3>
            </div>
          </article>
        `;
      })
      .filter(Boolean)
      .join("");

    if (html) {
      container.innerHTML = html;
    }
  } catch (_e) {
    // Keep the static fallback if dynamic loading fails.
  }
}

const RECENT_COMMENTS_REFRESH_KEY = "typ:last-comment-at";

function announceRecentCommentRefresh() {
  try {
    localStorage.setItem(RECENT_COMMENTS_REFRESH_KEY, String(Date.now()));
  } catch (_e) {
    // Best-effort only.
  }
  window.dispatchEvent(new CustomEvent("typ:recent-comments-refresh"));
}

function bindRecentCommentsRefresh(container) {
  const refresh = () => {
    loadRecentComments(container);
  };

  refresh();

  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      refresh();
    }
  });
  window.addEventListener("typ:recent-comments-refresh", refresh);
  window.addEventListener("storage", (event) => {
    if (event.key === RECENT_COMMENTS_REFRESH_KEY) {
      refresh();
    }
  });
}

function bindCommentForm(form, dynamicContainer, slug) {
  const status = form.querySelector("[data-status]");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const payload = {
      slug,
      author: data.get("author") || "",
      email: data.get("email") || "",
      body: data.get("body") || "",
      website: data.get("website") || "",
    };
    status.textContent = "Enviando…";
    status.removeAttribute("data-state");
    try {
      const res = await fetch("/api/comments", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const out = await res.json().catch(() => ({}));
      if (!res.ok || out.error) {
        status.textContent = out.error || "Error al enviar";
        status.dataset.state = "error";
        return;
      }
      status.textContent = "¡Gracias! Tu comentario fue publicado.";
      status.dataset.state = "ok";
      form.reset();
      await loadDynamicComments(dynamicContainer, slug);
      announceRecentCommentRefresh();
    } catch (_e) {
      status.textContent = "Error de red. Probá más tarde.";
      status.dataset.state = "error";
    }
  });
}

function trackArticleView(node) {
  const payload = {
    slug: node.dataset.articleSlug || "",
  };

  if (!payload.slug) return;

  const body = JSON.stringify(payload);

  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon("/api/views", blob);
      return;
    }
  } catch (_e) {
    // Fallback to fetch below.
  }

  fetch("/api/views", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {
    // Ignore analytics failures.
  });
}

const dynamicContainer = document.getElementById("dynamic-comments");
const commentForm = document.getElementById("comment-form");
if (dynamicContainer && commentForm) {
  const slug = dynamicContainer.dataset.articleSlug;
  if (slug) {
    loadDynamicComments(dynamicContainer, slug);
    bindCommentForm(commentForm, dynamicContainer, slug);
  }
}

const recentCommentsContainer = document.querySelector("[data-recent-comments]");
if (recentCommentsContainer) {
  bindRecentCommentsRefresh(recentCommentsContainer);
}

const popularReadsContainer = document.querySelector("[data-popular-reads]");
if (popularReadsContainer) {
  loadPopularReads(popularReadsContainer);
}

const articleTracker = document.querySelector("[data-track-article-view]");
if (articleTracker) {
  trackArticleView(articleTracker);
}
