from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import List


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("context_engine.jobs.index_repo")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_command(project: str) -> List[str]:
    python = sys.executable or "python"
    return [
        python,
        str(_project_root() / "tools" / "index_repo.py"),
        "--project",
        project,
    ]


def _run_command(command: List[str]) -> None:
    try:
        subprocess.check_call(command, cwd=str(_project_root()))
    except subprocess.CalledProcessError as exc:  # pragma: no cover - surfaced via job log
        logger.error("index_repo command failed with code %s", exc.returncode)
        raise


def main() -> None:
    """Entry point for executing index_repo as a background job."""
    parser = argparse.ArgumentParser(description="Rebuild repository indexes for a project.")
    parser.add_argument("--project", required=True)
    args = parser.parse_args()

    command = _build_command(args.project)
    logger.info("Starting index_repo job for project %s", args.project)
    _run_command(command)
    logger.info("Index_repo job finished successfully")


if __name__ == "__main__":
    main()
