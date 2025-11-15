from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import List


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("context_engine.jobs.graphify")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_command(project: str, dry_run: bool) -> List[str]:
    python = sys.executable or "python"
    command: List[str] = [
        python,
        str(_project_root() / "tools" / "graphify.py"),
        "--project",
        project,
    ]
    if dry_run:
        command.append("--dry-run")
    return command


def _run_command(command: List[str]) -> None:
    try:
        subprocess.check_call(command, cwd=str(_project_root()))
    except subprocess.CalledProcessError as exc:  # pragma: no cover - surfaced via job log
        logger.error("graphify command failed with code %s", exc.returncode)
        raise


def main() -> None:
    """Entry point for executing graphify as a background job."""
    parser = argparse.ArgumentParser(description="Run graphify pipeline for a project.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    command = _build_command(args.project, args.dry_run)
    logger.info("Starting graphify job (dry_run=%s)", args.dry_run)
    _run_command(command)
    logger.info("Graphify job finished successfully")


if __name__ == "__main__":
    main()
