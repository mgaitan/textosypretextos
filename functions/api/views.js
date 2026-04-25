const ALLOWED_METHODS = ["GET", "POST", "OPTIONS"];
const RECENT_VISIT_WINDOW_SECONDS = 30 * 60;
const BOT_UA_PATTERN =
  /bot|crawler|crawl|spider|slurp|preview|headless|lighthouse|facebookexternalhit|whatsapp|telegrambot|discordbot|slackbot|embedly|quora link preview|ia_archiver/i;

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function clean(text, maxLen) {
  if (typeof text !== "string") return "";
  return text.replace(/\u0000/g, "").trim().slice(0, maxLen);
}

function isValidSlug(slug) {
  return typeof slug === "string" && /^[a-z0-9][a-z0-9-]{0,200}$/i.test(slug);
}

function isValidArticleUrl(url) {
  return typeof url === "string" && /^\/[a-z0-9/_-]*$/i.test(url);
}

function isBotRequest(request) {
  const ua = request.headers.get("user-agent") || "";
  return BOT_UA_PATTERN.test(ua);
}

async function hashVisitor(request, salt) {
  const ip = request.headers.get("cf-connecting-ip") || "";
  const ua = request.headers.get("user-agent") || "";
  const payload = new TextEncoder().encode(`${salt || "tyt"}|${ip}|${ua}`);
  const buf = await crypto.subtle.digest("SHA-256", payload);
  return Array.from(new Uint8Array(buf))
    .slice(0, 16)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function readPayload(request) {
  const contentType = request.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return request.json();
  }
  const raw = await request.text();
  return JSON.parse(raw || "{}");
}

export async function onRequest(context) {
  const { request, env } = context;
  const method = request.method.toUpperCase();

  if (!ALLOWED_METHODS.includes(method)) {
    return new Response("Method Not Allowed", { status: 405 });
  }

  if (method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, POST, OPTIONS",
        "access-control-allow-headers": "content-type",
      },
    });
  }

  if (!env.DB) {
    return jsonResponse({ error: "Database not configured" }, 500);
  }

  if (method === "GET") {
    const url = new URL(request.url);
    const rawLimit = Number.parseInt(url.searchParams.get("limit") || "5", 10);
    const limit = Math.max(1, Math.min(10, Number.isFinite(rawLimit) ? rawLimit : 5));

    try {
      const { results } = await env.DB.prepare(
        `SELECT article_slug, article_url, article_title, section_slug, section_title, COUNT(*) AS views
         FROM page_views
         GROUP BY article_slug, article_url, article_title, section_slug, section_title
         ORDER BY views DESC, MAX(created_at) DESC
         LIMIT ?1`
      )
        .bind(limit)
        .all();

      return jsonResponse({ items: results || [] });
    } catch (_e) {
      return jsonResponse({ error: "Read failed" }, 500);
    }
  }

  if (isBotRequest(request)) {
    return jsonResponse({ ok: true, skipped: "bot" });
  }

  let payload;
  try {
    payload = await readPayload(request);
  } catch (_e) {
    return jsonResponse({ error: "Invalid JSON" }, 400);
  }

  const articleSlug = clean(payload.slug, 220);
  const articleUrl = clean(payload.url, 255);
  const articleTitle = clean(payload.title, 180);
  const sectionSlug = clean(payload.sectionSlug, 80);
  const sectionTitle = clean(payload.sectionTitle, 80);

  if (!isValidSlug(articleSlug) || !isValidArticleUrl(articleUrl)) {
    return jsonResponse({ error: "Invalid article" }, 400);
  }

  if (!articleTitle || !sectionSlug || !sectionTitle) {
    return jsonResponse({ error: "Missing article metadata" }, 400);
  }

  const visitorHash = await hashVisitor(request, env.COMMENT_SALT || "tyt");
  const now = Math.floor(Date.now() / 1000);

  try {
    const existing = await env.DB.prepare(
      `SELECT id
       FROM page_views
       WHERE article_slug = ?1
         AND visitor_hash = ?2
         AND created_at >= ?3
       LIMIT 1`
    )
      .bind(articleSlug, visitorHash, now - RECENT_VISIT_WINDOW_SECONDS)
      .first();

    if (existing?.id) {
      return jsonResponse({ ok: true, skipped: "duplicate" });
    }

    await env.DB.prepare(
      `INSERT INTO page_views (
         article_slug,
         article_url,
         article_title,
         section_slug,
         section_title,
         visitor_hash,
         user_agent,
         created_at
       )
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)`
    )
      .bind(
        articleSlug,
        articleUrl,
        articleTitle,
        sectionSlug,
        sectionTitle,
        visitorHash,
        clean(request.headers.get("user-agent") || "", 255) || null,
        now
      )
      .run();
  } catch (_e) {
    return jsonResponse({ error: "Write failed" }, 500);
  }

  return jsonResponse({ ok: true });
}
