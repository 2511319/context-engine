from __future__ import annotations

import sys
from pathlib import Path

TARGET_ROOT = Path(r"D:\project\mimic_codex")
TARGET_EXT = {".py"}  # чистим только Python-файлы для symbol parsing
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build", "_data", "logs"}
BOM = "\ufeff"


def strip_bom(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        # не трогаем файлы с нестандартной кодировкой
        return False
    if text.startswith(BOM):
        path.write_text(text.lstrip(BOM), encoding="utf-8")
        return True
    return False


def main() -> None:
    cleaned = 0
    checked = 0
    for p in TARGET_ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in TARGET_EXT:
            checked += 1
            if strip_bom(p):
                cleaned += 1
                print(f"cleaned BOM: {p}")
    print(f"checked={checked} cleaned={cleaned}")


if __name__ == "__main__":
    sys.exit(main())
