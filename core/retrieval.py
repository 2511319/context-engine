from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.dal.repos.code_repo import CodeRepo
from core.dal.repos.doc_repo import DocRepo
from core.dal.repos.feedback_repo import FeedbackRepo
from core.dal.types import ChunkRow
from core.uri import docsection_uri, file_uri

from .openai_embed import embed_batch
from .feedback import biases_for_uris

logger = logging.getLogger(__name__)


@dataclass
class RetrievalWeights:
    vector: float = 0.7
    bm25: float = 0.3


@dataclass
class RetrievalCandidates:
    vector_k: int = 120
    bm25_k: int = 120


@dataclass
class Candidate:
    kind: str  # code | doc
    project: str
    path: Optional[str] = None
    doc_name: Optional[str] = None
    section: Optional[str] = None
    content: str = ""
    commit_sha: Optional[str] = None
    chunk_id: Optional[str] = None
    fp_sha256: Optional[str] = None
    dist: Optional[float] = None
    rank: Optional[float] = None
    sim_vec: float = 0.0
    sim_bm25: float = 0.0
    score: float = 0.0
    bm25_rank_pos: int = 10**9
    bias_pin: float = 0.0
    penalty_neg: float = 0.0
    module: Optional[str] = None

    def uri(self) -> str:
        if self.kind == "code" and self.path:
            return file_uri(self.project, self.path)
        if self.kind == "doc" and self.doc_name and self.section:
            return docsection_uri(self.project, self.doc_name, self.section)
        return ""


def _range_from_chunk_id(chunk_id: Optional[str]) -> Tuple[int, int]:
    if not chunk_id:
        return (1, 1)
    try:
        parts = chunk_id.split(":")
        rng = parts[-2]
        a, b = rng.split("-")
        return (int(a), int(b))
    except Exception:
        return (1, 1)


def normalize_min_max(values: List[float]) -> List[float]:
    if not values:
        return []
    vmin = min(values)
    vmax = max(values)
    if vmax == vmin:
        return [0.0 for _ in values]
    return [(v - vmin) / (vmax - vmin) for v in values]


def hybrid_search(
    code_repo: CodeRepo,
    doc_repo: DocRepo,
    feedback_repo: FeedbackRepo,
    project: str,
    task: str,
    api_key: Optional[str],
    weights: RetrievalWeights,
    candidates: RetrievalCandidates,
    lex_cfg: str = "simple",
    emb_models: Tuple[str, int, str, int] = ("text-embedding-3-large", 1024, "text-embedding-3-small", 1024),
    task_fp: Optional[str] = None,
    apply_feedback: bool = True,
) -> Tuple[List[Candidate], List[Candidate]]:
    """
    Вернуть списки кандидатов (code, doc) с финальным score и отсортированные детерминированно.
    """
    code_model, code_dims, doc_model, doc_dims = emb_models

    # Embed task for both code and doc spaces (разные модели, одинаковая размерность)
    vecs = embed_batch([task, task], code_model, code_dims, api_key) if code_model == doc_model else None
    if vecs is None:
        code_vec = embed_batch([task], code_model, code_dims, api_key)[0]
        doc_vec = embed_batch([task], doc_model, doc_dims, api_key)[0]
    else:
        code_vec, doc_vec = vecs[0], vecs[1]

    # Fetch candidates
    v_code: List[ChunkRow] = code_repo.topk_vector(project, code_vec, candidates.vector_k)
    v_doc: List[ChunkRow] = doc_repo.topk_vector(project, doc_vec, candidates.vector_k)
    l_code: List[ChunkRow] = code_repo.topk_lex(project, task, candidates.bm25_k, lex_cfg)
    l_doc: List[ChunkRow] = doc_repo.topk_lex(project, task, candidates.bm25_k, lex_cfg)

    # Build union for normalization across both sources
    unions: List[Tuple[str, Optional[float], Optional[float]]] = []
    # store indexes for rank positions (for tie-break)
    bm25_positions: Dict[str, int] = {}

    def key_of_row(kind: str, r: ChunkRow) -> str:
        if kind == "code" and r.path:
            return file_uri(project, r.path)
        if kind == "doc" and r.doc_name and r.section:
            return docsection_uri(project, r.doc_name, r.section)
        return ""

    for r in v_code:
        unions.append((key_of_row("code", r), 1.0 - (r.dist or 0.0), None))
    for r in v_doc:
        unions.append((key_of_row("doc", r), 1.0 - (r.dist or 0.0), None))
    for pos, r in enumerate(l_code):
        unions.append((key_of_row("code", r), None, float(r.rank or 0.0)))
        bm25_positions.setdefault(key_of_row("code", r), pos)
    for pos, r in enumerate(l_doc):
        unions.append((key_of_row("doc", r), None, float(r.rank or 0.0)))
        bm25_positions.setdefault(key_of_row("doc", r), pos)

    # Build dict of signals
    vec_map: Dict[str, float] = {}
    bm_map: Dict[str, float] = {}
    for k, sv, sb in unions:
        if sv is not None:
            vec_map[k] = max(vec_map.get(k, 0.0), sv)
        if sb is not None:
            bm_map[k] = max(bm_map.get(k, 0.0), sb)

    # Normalize BM25 to [0,1] across union
    bm_vals = list(bm_map.values())
    bm_norm = normalize_min_max(bm_vals)
    bm_norm_map = {k: bm_norm[i] for i, k in enumerate(bm_map.keys())}

    # Prepare candidate objects merging signals
    merged: Dict[str, Candidate] = {}
    def attach(kind: str, r: ChunkRow) -> None:
        k = key_of_row(kind, r)
        c = merged.get(k)
        if c is None:
            c = Candidate(
                kind=kind,
                project=project,
                path=r.path if kind == "code" else None,
                doc_name=r.doc_name if kind == "doc" else None,
                section=r.section if kind == "doc" else None,
                content=r.content,
                commit_sha=r.commit_sha,
                chunk_id=r.chunk_id,
                fp_sha256=r.fp_sha256,
                dist=r.dist,
                rank=r.rank,
                module=r.module if kind == "code" else None,
            )
            merged[k] = c
        if r.dist is not None:
            c.sim_vec = max(c.sim_vec, 1.0 - float(r.dist))
        if r.rank is not None:
            c.sim_bm25 = max(c.sim_bm25, bm_norm_map.get(k, 0.0))
            c.bm25_rank_pos = min(c.bm25_rank_pos, bm25_positions.get(k, c.bm25_rank_pos))

    for r in v_code:
        attach("code", r)
    for r in v_doc:
        attach("doc", r)
    for r in l_code:
        attach("code", r)
    for r in l_doc:
        attach("doc", r)

    # Bias from feedback
    bias: Dict[str, Tuple[float, float]] = {}
    if apply_feedback and task_fp:
        bias = biases_for_uris(feedback_repo, project, task_fp, merged.keys())

    # Final score and sort
    for u, c in merged.items():
        b_pin, p_neg = bias.get(u, (0.0, 0.0))
        c.bias_pin = b_pin
        c.penalty_neg = p_neg
        c.score = weights.vector * c.sim_vec + weights.bm25 * c.sim_bm25 + b_pin - p_neg

    items = list(merged.values())
    items.sort(key=lambda x: (-x.score, (x.dist or 0.0), x.bm25_rank_pos, x.uri()))

    code = [c for c in items if c.kind == "code"]
    docs = [c for c in items if c.kind == "doc"]
    return code, docs
