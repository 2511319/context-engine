from __future__ import annotations

import argparse
import json
import asyncio
import subprocess
import sys
from pathlib import Path

from api.services.admin import get_admin_service


ROOT = Path(__file__).resolve().parent


def _describe_command(name: str, cmd: list[str], cwd: Path) -> None:
    print(f"[manage.py] {name} -> {' '.join(cmd)} (cwd={cwd})")


def _pretty_print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_ingest(project: str) -> int:
    cmd = [sys.executable or "python", str(ROOT / "jobs" / "run_ingest.py"), "--project", project]
    _describe_command("ingest", cmd, ROOT)
    return subprocess.call(cmd, cwd=str(ROOT))


def cmd_build_graph(project: str, dry_run: bool) -> int:
    cmd = [sys.executable or "python", str(ROOT / "jobs" / "run_graphify.py"), "--project", project]
    if dry_run:
        cmd.append("--dry-run")
    _describe_command("build-graph", cmd, ROOT)
    return subprocess.call(cmd, cwd=str(ROOT))


def cmd_health(project: str) -> int:
    # Используем AdminService для согласованности с /api/admin/health, но без MCP (CLI контекст).
    service = get_admin_service()
    health = asyncio.run(service.health(project=project, include_mcp=False))
    _pretty_print(health)
    # считаем падение, если есть компоненты в статусе down
    down = any(comp.get("status") == "down" for comp in health.get("components", []))
    return 1 if down else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Context Engine management CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Run full ingest pipeline")
    p_ingest.add_argument("--project", required=True)

    p_graph = sub.add_parser("build-graph", help="Run graphify pipeline")
    p_graph.add_argument("--project", required=True)
    p_graph.add_argument("--dry-run", action="store_true")

    p_health = sub.add_parser("health-check", help="Run connectivity and metrics checks")
    p_health.add_argument("--project", required=True)

    args = parser.parse_args()
    if args.command == "ingest":
        code = cmd_ingest(args.project)
    elif args.command == "build-graph":
        code = cmd_build_graph(args.project, args.dry_run)
    elif args.command == "health-check":
        code = cmd_health(args.project)
    else:
        parser.error("Unknown command")
        return
    sys.exit(code)


if __name__ == "__main__":
    main()
