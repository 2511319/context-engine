// Neo4j constraints for context graph

CREATE CONSTRAINT module_unique IF NOT EXISTS
FOR (m:Module) REQUIRE (m.project, m.name) IS UNIQUE;

CREATE CONSTRAINT contract_unique IF NOT EXISTS
FOR (c:Contract) REQUIRE (c.project, c.name) IS UNIQUE;

CREATE CONSTRAINT docsection_unique IF NOT EXISTS
FOR (d:DocSection) REQUIRE (d.project, d.doc_name, d.name) IS UNIQUE;

