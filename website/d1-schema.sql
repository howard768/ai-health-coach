-- D1 schema for heymeld-waitlist.
-- Source of truth: functions/api/waitlist/subscribe.ts reads/writes these columns.
-- Re-runnable: every statement uses IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS waitlist_signups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  source TEXT,
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  utm_term TEXT,
  utm_content TEXT,
  referer TEXT,
  ip_hash TEXT,
  user_agent TEXT,
  cf_country TEXT,
  notified INTEGER NOT NULL DEFAULT 0,
  submissions INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_waitlist_created ON waitlist_signups(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_waitlist_source ON waitlist_signups(source);
