from __future__ import annotations

import logging
import os

try:
    import psycopg
except Exception as exc:  # pragma: no cover
    psycopg = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("context_engine.tools.memify")


def main() -> None:
    if psycopg is None:
        raise RuntimeError("psycopg (psycopg3) is required")
    pg_dsn = os.getenv("PG_DSN")
    if not pg_dsn:
        raise RuntimeError("PG_DSN is not set")

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Lexical vectors
            logger.info("Updating lexical tsvectors...")
            try:
                cur.execute("UPDATE code_chunks SET lex = to_tsvector('simple', content) WHERE lex IS NULL;")
                cur.execute("UPDATE doc_chunks SET lex = to_tsvector('simple', content) WHERE lex IS NULL;")
            except Exception as exc:
                logger.error("Failed to update lex: %s", exc)

            # Remove exact duplicates by fp within project
            logger.info("Removing duplicate chunks (exact fp match)...")
            try:
                cur.execute(
                    """
                    DELETE FROM code_chunks a USING code_chunks b
                    WHERE a.id < b.id
                      AND a.project = b.project
                      AND a.fp_sha256 = b.fp_sha256;
                    """
                )
                cur.execute(
                    """
                    DELETE FROM doc_chunks a USING doc_chunks b
                    WHERE a.id < b.id
                      AND a.project = b.project
                      AND a.fp_sha256 = b.fp_sha256;
                    """
                )
            except Exception as exc:
                logger.error("Failed to deduplicate: %s", exc)

            try:
                cur.execute("ANALYZE code_chunks; ANALYZE doc_chunks;")
            except Exception as exc:
                logger.warning("ANALYZE failed: %s", exc)

    logger.info("memify completed")


if __name__ == "__main__":
    main()
