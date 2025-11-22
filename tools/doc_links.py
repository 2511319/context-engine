from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Iterator, Tuple

from core.uri import doc_uri, docsection_uri, file_uri, module_uri


def extract_doc_links(project: str, doc_name: str, content: str) -> Iterator[Tuple[str, str]]:
    """
    Yield (edge_kind, to_uri) for markdown links found in content.
    edge_kind: REFERENCES
    """
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for match in link_re.finditer(content):
        target = match.group(1).strip()
        if not target:
            continue
        url_part, anchor = _split_anchor(target)
        if url_part.startswith("#"):
            sec = url_part[1:] or anchor
            yield "REFERENCES", docsection_uri(project, doc_name, sec)
            continue
        rel_path = url_part.lstrip("/")
        if rel_path.endswith(".py"):
            yield "REFERENCES", file_uri(project, rel_path)
        elif rel_path.endswith(".md"):
            if anchor:
                yield "REFERENCES", docsection_uri(project, Path(rel_path).stem, anchor)
            else:
                yield "REFERENCES", doc_uri(project, Path(rel_path).stem)
        elif rel_path:
            yield "REFERENCES", file_uri(project, rel_path)


def described_in_edges(project: str, section_uri: str, links: Iterable[Tuple[str, str]]) -> Iterator[Tuple[str, str, str]]:
    """
    Yield dp_edge rows for DESCRIBED_IN when doc section references code modules/files.
    Returns tuples (edge_kind, from_uri, to_uri).
    """
    seen = set()
    for edge_kind, to_uri in links:
        if edge_kind != "REFERENCES":
            continue
        if to_uri.startswith("file://"):
            mod_path = to_uri.split("file://", 1)[1]
            mod_uri = module_uri(project, Path(mod_path).with_suffix("").as_posix())
            key = (mod_uri, section_uri)
            if key in seen:
                continue
            seen.add(key)
            yield "DESCRIBED_IN", mod_uri, section_uri


def extract_doc_mentions(project: str, doc_name: str, content: str) -> Iterator[Tuple[str, str]]:
    """
    Extract simple textual mentions of code paths (foo/bar.py) to produce REFERENCES edges.
    """
    mention_re = re.compile(r"\b([A-Za-z0-9_./-]+\.py)\b")
    for match in mention_re.finditer(content):
        path = match.group(1)
        yield "REFERENCES", file_uri(project, path.lstrip("/"))


def _split_anchor(target: str) -> Tuple[str, str]:
    if "#" in target:
        base, anchor = target.split("#", 1)
        return base, anchor
    return target, ""
