import "../styles/site.css";

const root = document.documentElement;
const body = document.body;
const navToggle = document.querySelector("[data-nav-toggle]");
const navPanel = document.querySelector("[data-nav-panel]");

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
