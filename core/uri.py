from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


def file_uri(project: str, relative_path: str) -> str:
    rel = _normalize_path(relative_path)
    return f"file://{project}/{rel}"


def module_uri(project: str, module_name: str) -> str:
    mod = module_name.strip().strip("/")
    return f"module://{project}/{mod}"


def symbol_uri(project: str, module_name: str, symbol_name: str) -> str:
    mod = module_name.strip().strip("/")
    sym = symbol_name.strip()
    return f"symbol://{project}/{mod}#{sym}"


def doc_uri(project: str, doc_name: str) -> str:
    return f"doc://{project}/{slugify(doc_name)}"


def docsection_uri(project: str, doc_name: str, section_id: str) -> str:
    return f"docsection://{project}/{slugify(doc_name)}#{slugify(section_id)}"


def _normalize_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("/")


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9/_#.+-]", "-", text.replace(" ", "-"))
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "section"
