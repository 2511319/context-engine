from __future__ import annotations

from typing import Dict, List, Tuple

from .retrieval import Candidate
from .token_budget import count_tokens


def _overlap(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return not (a[1] < b[0] or b[1] < a[0])


def _parse_range(c: Candidate) -> Tuple[int, int]:
    if not c.chunk_id:
        return (1, 1)
    try:
        parts = c.chunk_id.split(":")
        rng = parts[-2]
        a, b = rng.split("-")
        return (int(a), int(b))
    except Exception:
        return (1, 1)


def dedup_overlaps(codes: List[Candidate], docs: List[Candidate]) -> Tuple[List[Candidate], List[Candidate]]:
    # Code: удаляем перекрывающиеся чанки в одном файле, оставляя с бОльшим score
    by_path: Dict[str, List[Candidate]] = {}
    for c in codes:
        if not c.path:
            continue
        by_path.setdefault(c.path, []).append(c)
    out_codes: List[Candidate] = []
    for path, items in by_path.items():
        items.sort(key=lambda x: -x.score)
        kept: List[Tuple[Tuple[int, int], Candidate]] = []
        for it in items:
            rng = _parse_range(it)
            if any(_overlap(rng, r) for r, _ in kept):
                continue
            kept.append((rng, it))
        out_codes.extend([it for _, it in kept])

    # Docs: не допускаем одинаковых секций записи (doc_name#section)
    seen: set[str] = set()
    out_docs: List[Candidate] = []
    for d in docs:
        u = d.uri()
        if u and u not in seen:
            seen.add(u)
            out_docs.append(d)
    return out_codes, out_docs


def apply_token_budget(codes: List[Candidate], docs: List[Candidate], budget: int = 6000) -> Tuple[List[Candidate], List[Candidate]]:
    # Сначала сокращаем docs, затем code
    code_texts = [c.content for c in codes]
    doc_texts = [d.content for d in docs]
    total = count_tokens(code_texts + doc_texts)
    if total <= budget:
        return codes, docs

    out_docs = docs[:]
    while out_docs and count_tokens(code_texts + [d.content for d in out_docs]) > budget:
        out_docs.pop()  # удаляем наименее значимые (конец списка после сортировки)

    if count_tokens(code_texts + [d.content for d in out_docs]) <= budget:
        return codes, out_docs

    out_codes = codes[:]
    while out_codes and count_tokens([c.content for c in out_codes] + [d.content for d in out_docs]) > budget:
        out_codes.pop()

    return out_codes, out_docs
