CREATE TABLE IF NOT EXISTS memory_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_summaries (
  session_id TEXT PRIMARY KEY,
  updated_at TEXT NOT NULL,
  covered_until_id INTEGER NOT NULL,
  content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  session_id TEXT NOT NULL,
  action TEXT NOT NULL,
  tool TEXT NOT NULL,
  approved INTEGER NOT NULL,
  status TEXT NOT NULL,
  reason TEXT NOT NULL,
  details TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_session
ON memory_entries(session_id, id);

CREATE INDEX IF NOT EXISTS idx_audit_session
ON audit_events(session_id, id);
