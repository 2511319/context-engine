from __future__ import annotations

import argparse
import logging
import os

from core.dal import PgClient
from core.dal.repos import IngestRepo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("context_engine.tools.memify")


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process indexed chunks for a single project")
    parser.add_argument("--project", required=True, help="Project id for scoping updates")
    args = parser.parse_args()

    pg_dsn = os.getenv("PG_DSN")
    if not pg_dsn:
        raise RuntimeError("PG_DSN is not set")
    pg = PgClient(pg_dsn)
    ingest = IngestRepo(pg)

    with ingest.cursor() as cur:
        logger.info("Updating lexical tsvectors for project=%s...", args.project)
        try:
            ingest.update_lex(args.project, cur=cur)
        except Exception as exc:
            logger.error("Failed to update lex: %s", exc)

        logger.info("Removing duplicate chunks (exact fp match) for project=%s...", args.project)
        try:
            ingest.deduplicate_chunks(args.project, cur=cur)
        except Exception as exc:
            logger.error("Failed to deduplicate: %s", exc)

        try:
            ingest.analyze_chunks(cur=cur)
        except Exception as exc:
            logger.warning("ANALYZE failed: %s", exc)

    logger.info("memify completed")


if __name__ == "__main__":
    main()
