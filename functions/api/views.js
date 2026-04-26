const ALLOWED_METHODS = ["GET", "POST", "OPTIONS"];
const RECENT_VISIT_WINDOW_SECONDS = 30 * 60;
const VIEW_RETENTION_SECONDS = 180 * 24 * 60 * 60;
const VALID_SECTION_SLUGS = new Set(["blog", "de-otros", "fotos", "videos", "personal"]);
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

function isTrustedViewRequest(request) {
  const requestOrigin = new URL(request.url).origin;
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");

  if (origin && origin !== requestOrigin) {
    return false;
  }

  if (fetchSite && !["same-origin", "same-site", "none"].includes(fetchSite)) {
    return false;
  }

  return true;
}

function isBotRequest(request) {
  const ua = request.headers.get("user-agent") || "";
  return BOT_UA_PATTERN.test(ua);
}

function getTrustedArticleContext(request, articleSlug) {
  const requestOrigin = new URL(request.url).origin;
  const referer = request.headers.get("referer");
  if (!referer) return null;

  let refererUrl;
  try {
    refererUrl = new URL(referer);
  } catch (_e) {
    return null;
  }

  if (refererUrl.origin !== requestOrigin) {
    return null;
  }

  const parts = refererUrl.pathname.split("/").filter(Boolean);
  if (parts.length < 2) {
    return null;
  }

  const [sectionSlug, pathSlug] = parts;
  if (!VALID_SECTION_SLUGS.has(sectionSlug) || pathSlug !== articleSlug) {
    return null;
  }

  const articleUrl = `/${sectionSlug}/${pathSlug}/`;
  if (!isValidArticleUrl(articleUrl)) {
    return null;
  }

  return { articleUrl, sectionSlug };
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
        allow: "GET, POST, OPTIONS",
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
        `WITH ranked_page_views AS (
           SELECT
             article_slug,
             article_url,
             section_slug,
             created_at,
             COUNT(*) OVER (PARTITION BY article_slug) AS views,
             ROW_NUMBER() OVER (
               PARTITION BY article_slug
               ORDER BY created_at DESC
             ) AS metadata_rank
           FROM page_views
         )
         SELECT
           article_slug,
           article_url,
           section_slug,
           views
         FROM ranked_page_views
         WHERE metadata_rank = 1
         ORDER BY views DESC, created_at DESC
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

  if (!isTrustedViewRequest(request)) {
    return jsonResponse({ error: "Forbidden" }, 403);
  }

  let payload;
  try {
    payload = await readPayload(request);
  } catch (_e) {
    return jsonResponse({ error: "Invalid JSON" }, 400);
  }

  const articleSlug = clean(payload.slug, 220);

  if (!isValidSlug(articleSlug)) {
    return jsonResponse({ error: "Invalid article" }, 400);
  }

  const articleContext = getTrustedArticleContext(request, articleSlug);
  if (!articleContext) {
    return jsonResponse({ error: "Untrusted article context" }, 400);
  }

  const visitorHash = await hashVisitor(request, env.COMMENT_SALT || "tyt");
  const now = Math.floor(Date.now() / 1000);

  try {
    const insertResult = await env.DB.prepare(
      `INSERT INTO page_views (
         article_slug,
         article_url,
         section_slug,
         visitor_hash,
         user_agent,
         created_at
       )
       SELECT ?1, ?2, ?3, ?4, ?5, ?6
       WHERE NOT EXISTS (
         SELECT 1
         FROM page_views
         WHERE article_slug = ?1
           AND visitor_hash = ?4
           AND created_at >= ?7
       )`
    )
      .bind(
        articleSlug,
        articleContext.articleUrl,
        articleContext.sectionSlug,
        visitorHash,
        clean(request.headers.get("user-agent") || "", 255) || null,
        now,
        now - RECENT_VISIT_WINDOW_SECONDS
      )
      .run();

    if (!insertResult.meta?.changes) {
      return jsonResponse({ ok: true, skipped: "duplicate" });
    }
  } catch (_e) {
    return jsonResponse({ error: "Write failed" }, 500);
  }

  env.DB.prepare(
    `DELETE FROM page_views
     WHERE created_at < ?1`
  )
    .bind(now - VIEW_RETENTION_SECONDS)
    .run()
    .catch(() => {});

  return jsonResponse({ ok: true });
}
