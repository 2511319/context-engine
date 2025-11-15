// Optional schema helpers (relationships are created by ingest/graphify phase)
// Relationship types used:
// (:Module)-[:IMPLEMENTS]->(:Contract)
// (:Module)-[:DESCRIBED_IN]->(:DocSection)
// (:DocSection)-[:APPLIES_TO]->(:Module)
// (:Module)-[:BEST_ACCESSED_VIA]->(:Tool)

// Index on Tool.name for quick lookup (optional)
CREATE INDEX tool_name_index IF NOT EXISTS FOR (t:Tool) ON (t.name);

