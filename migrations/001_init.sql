CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_slug TEXT NOT NULL,
  author TEXT NOT NULL,
  email TEXT,
  body TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  ip_hash TEXT,
  status TEXT NOT NULL DEFAULT 'published'
);

CREATE INDEX IF NOT EXISTS idx_comments_slug_status ON comments(article_slug, status);
CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at);
