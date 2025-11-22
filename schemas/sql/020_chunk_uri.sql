-- Add URI columns for chunks to support canonical identifiers
ALTER TABLE code_chunks ADD COLUMN IF NOT EXISTS uri text;
ALTER TABLE doc_chunks ADD COLUMN IF NOT EXISTS uri text;

CREATE INDEX IF NOT EXISTS code_chunks_uri_idx ON code_chunks (project, uri);
CREATE INDEX IF NOT EXISTS doc_chunks_uri_idx ON doc_chunks (project, uri);
