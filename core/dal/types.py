from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChunkRow:
    """Unified representation of code/doc chunks rows returned from Postgres."""

    id: int
    project: str
    path: Optional[str] = None
    module: Optional[str] = None
    doc_name: Optional[str] = None
    section: Optional[str] = None
    kind: Optional[str] = None
    content: str = ""
    commit_sha: Optional[str] = None
    chunk_id: Optional[str] = None
    fp_sha256: Optional[str] = None
    dist: Optional[float] = None
    rank: Optional[float] = None
