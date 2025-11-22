from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_step(cmd: list[str], cwd: Path) -> None:
    subprocess.check_call(cmd, cwd=str(cwd))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full ingest pipeline")
    parser.add_argument("--project", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    python = sys.executable or "python"

    steps = [
        [python, str(root / "tools" / "index_repo.py"), "--project", args.project],
        [python, str(root / "tools" / "memify.py"), "--project", args.project],
        [python, str(root / "tools" / "graphify.py"), "--project", args.project],
    ]

    env = os.environ.copy()
    for cmd in steps:
        run_step(cmd, root)


if __name__ == "__main__":
    main()
