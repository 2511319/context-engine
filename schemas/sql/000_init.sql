-- context-engine MCP: initial schema (PostgreSQL >=16, pgvector >=0.7.4)
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================
-- Code chunks (source code)
-- =========================
CREATE TABLE IF NOT EXISTS code_chunks (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  workspace   text,
  user_id     text,
  path        text NOT NULL,
  module      text,
  content     text NOT NULL,
  embedding   vector(1024),
  lex         tsvector,
  commit_sha  text,
  chunk_id    text,           -- canonical: project:path:range:fp
  fp_sha256   text NOT NULL,
  updated_at  timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS code_chunks_proj_path_idx ON code_chunks (project, path);
CREATE INDEX IF NOT EXISTS code_chunks_proj_mod_idx  ON code_chunks (project, module);
CREATE INDEX IF NOT EXISTS code_chunks_lex_idx       ON code_chunks USING GIN(lex);

-- ============================
-- Doc chunks (docs/spec/config)
-- ============================
CREATE TABLE IF NOT EXISTS doc_chunks (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  workspace   text,
  user_id     text,
  doc_name    text NOT NULL,
  section     text,
  kind        text NOT NULL DEFAULT 'doc', -- doc|contract|spec|config
  content     text NOT NULL,
  embedding   vector(1024),
  lex         tsvector,
  commit_sha  text,
  chunk_id    text,           -- canonical: project:doc:section:fp
  fp_sha256   text NOT NULL,
  updated_at  timestamptz DEFAULT now(),
  CONSTRAINT doc_chunks_kind_chk CHECK (kind IN ('doc','contract','spec','config'))
);
CREATE INDEX IF NOT EXISTS doc_chunks_proj_doc_idx ON doc_chunks (project, doc_name);
CREATE INDEX IF NOT EXISTS doc_chunks_kind_idx     ON doc_chunks (project, kind);
CREATE INDEX IF NOT EXISTS doc_chunks_lex_idx      ON doc_chunks USING GIN(lex);

-- =====================================
-- Datapoints (provenance) and graph edges
-- =====================================
CREATE TABLE IF NOT EXISTS dp_datapoint (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  kind        text NOT NULL,   -- code | doc
  uri         text NOT NULL,   -- file://... | doc://...
  module      text,
  commit_sha  text,
  fp_sha256   text NOT NULL,
  created_at  timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS dp_unique ON dp_datapoint(project, uri, fp_sha256);

CREATE TABLE IF NOT EXISTS dp_edge (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  src_uri     text NOT NULL,
  rel         text NOT NULL,   -- IMPORTS | REFERENCES | DESCRIBED_IN | IMPLEMENTS
  dst_uri     text NOT NULL
);
CREATE INDEX IF NOT EXISTS dp_edge_proj_src_idx ON dp_edge (project, src_uri);

CREATE TABLE IF NOT EXISTS dp_feedback (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  task_fp     text NOT NULL,
  uri         text NOT NULL,
  label       smallint NOT NULL,  -- -1 | 0 | +1
  created_at  timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dp_feedback_proj_task_idx ON dp_feedback (project, task_fp);

-- ======================
-- Symbol index for code
-- ======================
CREATE TABLE IF NOT EXISTS symbols (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  module      text,
  path        text NOT NULL,
  kind        text NOT NULL,   -- class | func | router | const
  name        text NOT NULL,
  range       int4range,
  sig         text,
  commit_sha  text
);
CREATE INDEX IF NOT EXISTS symbols_proj_name_idx ON symbols (project, name);

CREATE TABLE IF NOT EXISTS symbol_refs (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  from_path   text NOT NULL,
  to_symbol   text NOT NULL,
  rel         text NOT NULL    -- DECLARES | REFERENCES
);
CREATE INDEX IF NOT EXISTS symbol_refs_proj_to_idx ON symbol_refs (project, to_symbol);

-- ==============
-- Plan log store
-- ==============
CREATE TABLE IF NOT EXISTS plan_log (
  plan_id uuid PRIMARY KEY,
  ts timestamptz NOT NULL,
  project text NOT NULL,
  module text,
  status text NOT NULL,
  route text,
  latency_ms integer,
  source_latencies jsonb NOT NULL DEFAULT '{}'::jsonb,
  result_sizes jsonb NOT NULL DEFAULT '{}'::jsonb,
  params jsonb NOT NULL DEFAULT '{}'::jsonb,
  token_budget jsonb,
  detail jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS plan_log_ts_idx ON plan_log (ts DESC);
CREATE INDEX IF NOT EXISTS plan_log_project_idx ON plan_log (project, ts DESC);

-- Note: HNSW vector indexes are created in a separate migration file.
