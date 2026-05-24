-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL DEFAULT 'local',
  agent_id        TEXT NOT NULL,             -- 'workflows' for workflow-led conversations
  workflow_id     TEXT,                       -- nullable for non-workflow chats
  workflow_version TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  metadata_json   TEXT
);
CREATE INDEX IF NOT EXISTS ix_conversations_tenant_agent
  ON conversations(tenant_id, agent_id, updated_at DESC);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  role            TEXT NOT NULL,              -- user | agent | system
  content         TEXT NOT NULL,
  created_at      TEXT NOT NULL,
  metadata_json   TEXT
);
CREATE INDEX IF NOT EXISTS ix_messages_conv ON messages(conversation_id, created_at);

-- Tool calls (a thin convenience view; also logged via audit_events)
CREATE TABLE IF NOT EXISTS tool_calls (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  capability_uri  TEXT NOT NULL,
  input_json      TEXT,
  output_json     TEXT,
  error           TEXT,
  trace_id        TEXT,
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tool_calls_conv ON tool_calls(conversation_id, created_at);

-- Approvals (workflow human_approval)
CREATE TABLE IF NOT EXISTS approvals (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  workflow_id     TEXT NOT NULL,
  workflow_version TEXT NOT NULL,
  step_id         TEXT NOT NULL,
  status          TEXT NOT NULL,              -- pending | approved | denied | expired
  request_json    TEXT,
  response_json   TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_approvals_pending
  ON approvals(status) WHERE status = 'pending';

-- Artifacts
CREATE TABLE IF NOT EXISTS artifacts (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  path            TEXT NOT NULL,
  mime_type       TEXT,
  size_bytes      INTEGER,
  sha256          TEXT,
  metadata_json   TEXT,
  created_at      TEXT NOT NULL
);

-- Audit events (closed event_type taxonomy)
CREATE TABLE IF NOT EXISTS audit_events (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL DEFAULT 'local',
  agent_id        TEXT,
  workflow_id     TEXT,
  workflow_version TEXT,
  step_id         TEXT,
  conversation_id TEXT,
  capability_uri  TEXT,
  trace_id        TEXT,
  span_id         TEXT,
  event_type      TEXT NOT NULL,
  event_json      TEXT,
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_trace ON audit_events(trace_id);
CREATE INDEX IF NOT EXISTS ix_audit_event_type ON audit_events(event_type, created_at);
CREATE INDEX IF NOT EXISTS ix_audit_conv ON audit_events(conversation_id, created_at);

-- Idempotency
CREATE TABLE IF NOT EXISTS idempotency (
  id              TEXT PRIMARY KEY,           -- sha256(tenant_id || uri || idempotency_key)
  tenant_id       TEXT NOT NULL,
  capability_uri  TEXT NOT NULL,
  result_json     TEXT NOT NULL,
  expires_at      TEXT NOT NULL,
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_idempotency_expiry ON idempotency(expires_at);

-- Remote agent health (consumed by /admin/remotes)
CREATE TABLE IF NOT EXISTS remote_agent_health (
  id              TEXT PRIMARY KEY,           -- remote agent id
  state           TEXT NOT NULL,              -- closed | half_open | open
  failure_count   INTEGER NOT NULL DEFAULT 0,
  last_error      TEXT,
  updated_at      TEXT NOT NULL
);
