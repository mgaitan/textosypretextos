CREATE TABLE IF NOT EXISTS page_views (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_slug TEXT NOT NULL,
  article_url TEXT NOT NULL,
  section_slug TEXT NOT NULL,
  visitor_hash TEXT NOT NULL,
  user_agent TEXT,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_page_views_article_created
  ON page_views(article_slug, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_page_views_visitor_created
  ON page_views(visitor_hash, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_page_views_created
  ON page_views(created_at DESC);
