from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.dal import PgClient
from core.dal.repos import IngestRepo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("context_engine.tools.memify")


def _load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ[key.strip()] = value.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process indexed chunks for a single project")
    parser.add_argument("--project", required=True, help="Project id for scoping updates")
    args = parser.parse_args()

    _load_env(PROJECT_ROOT / ".env")
    pg_dsn = (os.getenv("PG_DSN") or os.getenv("PG_DSN_RO") or "").strip()
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
