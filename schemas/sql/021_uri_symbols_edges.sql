-- Add URI fields for symbols, symbol_refs, dp_edge and backfill from existing columns

-- symbols
ALTER TABLE symbols ADD COLUMN IF NOT EXISTS uri text;
CREATE INDEX IF NOT EXISTS symbols_uri_idx ON symbols (project, uri);

-- symbol_refs
ALTER TABLE symbol_refs ADD COLUMN IF NOT EXISTS from_uri text;
ALTER TABLE symbol_refs ADD COLUMN IF NOT EXISTS to_uri text;
CREATE INDEX IF NOT EXISTS symbol_refs_from_uri_idx ON symbol_refs (project, from_uri);
CREATE INDEX IF NOT EXISTS symbol_refs_to_uri_idx ON symbol_refs (project, to_uri);

-- dp_edge canonical columns
ALTER TABLE dp_edge ADD COLUMN IF NOT EXISTS edge_kind text;
ALTER TABLE dp_edge ADD COLUMN IF NOT EXISTS from_uri text;
ALTER TABLE dp_edge ADD COLUMN IF NOT EXISTS to_uri text;
CREATE INDEX IF NOT EXISTS dp_edge_kind_from_to_idx ON dp_edge (project, edge_kind, from_uri, to_uri);

-- backfill from legacy columns if present
UPDATE dp_edge
SET
    edge_kind = COALESCE(edge_kind, rel),
    from_uri = COALESCE(from_uri, src_uri),
    to_uri = COALESCE(to_uri, dst_uri)
WHERE edge_kind IS NULL OR from_uri IS NULL OR to_uri IS NULL;
