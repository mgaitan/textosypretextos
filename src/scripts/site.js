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
  themeToggle.setAttribute("aria-label", isDark ? "Activar modo claro" : "Activar modo oscuro");
  themeToggle.dataset.theme = theme;
  themeToggle.querySelector("[data-theme-icon]")?.replaceChildren(document.createTextNode(isDark ? "☀" : "☾"));
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

function buildArticleMap(docs) {
  const map = new Map();
  Object.entries(docs || {}).forEach(([url, doc]) => {
    let pathname = url;
    try {
      pathname = new URL(url).pathname;
    } catch (_e) {
      pathname = url;
    }
    const slug = slugFromUrl(url);
    if (!slug || map.has(slug)) return;
    map.set(slug, {
      url: pathname,
      title: doc?.title || slug,
    });
  });
  return map;
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

    const articleMap = buildArticleMap(docs);
    const html = comments
      .map((comment) => {
        const article = articleMap.get(comment.article_slug);
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
    } catch (_e) {
      status.textContent = "Error de red. Probá más tarde.";
      status.dataset.state = "error";
    }
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
  loadRecentComments(recentCommentsContainer);
}
