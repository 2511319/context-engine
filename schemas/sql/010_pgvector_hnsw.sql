-- pgvector HNSW indexes (cosine) for approximate nearest neighbors
-- Requires pgvector >= 0.7.4

CREATE INDEX IF NOT EXISTS code_chunks_emb_hnsw
  ON code_chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m=16, ef_construction=200);

CREATE INDEX IF NOT EXISTS doc_chunks_emb_hnsw
  ON doc_chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m=16, ef_construction=200);

-- At query time, set search parameter as needed (example):
--   SET hnsw.ef_search = 40;

