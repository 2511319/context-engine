from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from core.dal.repos.code_repo import CodeRepo

logger = logging.getLogger(__name__)


@dataclass
class Rule:
    name: str
    priority: int
    mode: str
    any_tokens: List[str]
    none_tokens: List[str]
    module: str


def tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", text.lower()) if t]


def rule_from_cfg(entry: Dict) -> Optional[Rule]:  # type: ignore[type-arg]
    try:
        name = str(entry.get("name", ""))
        priority = int(entry.get("priority", 0))
        match = entry.get("match", {})
        mode = str(match.get("mode", "keyword"))
        any_tokens = [str(x).lower() for x in (match.get("any") or [])]
        none_tokens = [str(x).lower() for x in (match.get("none") or [])]
        module = str(entry.get("module"))
        if not module:
            return None
        return Rule(name=name, priority=priority, mode=mode, any_tokens=any_tokens, none_tokens=none_tokens, module=module)
    except Exception as exc:
        logger.error("invalid rule: %s", exc)
        return None


def apply_rules(task: str, rules: Iterable[Rule]) -> Optional[str]:
    tokens = tokenize(task)
    best: Optional[Tuple[int, int, str]] = None  # (priority, order, module)
    for idx, r in enumerate(rules):
        ok = False
        if r.mode == "keyword":
            if r.any_tokens:
                ok = any(tok in tokens or any(tok in t for t in tokens) for tok in r.any_tokens)
            else:
                ok = True
            if r.none_tokens and any(n in tokens for n in r.none_tokens):
                ok = False
        elif r.mode == "regex":
            try:
                ok = any(re.search(pat, task, re.IGNORECASE) for pat in r.any_tokens) and not any(
                    re.search(pat, task, re.IGNORECASE) for pat in r.none_tokens
                )
            except re.error:
                ok = False
        elif r.mode == "glob":
            from fnmatch import fnmatch

            ok = any(fnmatch(task.lower(), pat.lower()) for pat in r.any_tokens) and not any(
                fnmatch(task.lower(), pat.lower()) for pat in r.none_tokens
            )
        if ok:
            cand = (r.priority, -idx, r.module)
            if best is None or cand > best:
                best = cand
    return best[2] if best else None


def heuristic_module(task: str, code_repo: CodeRepo, project: str, neo_modules: List[str]) -> Optional[str]:
    tokens = tokenize(task)
    # S1: tokens vs module paths from PG
    pg_modules = code_repo.list_modules(project)
    s1_scores: Dict[str, float] = {}
    for m in pg_modules:
        lm = m.lower()
        s1 = sum(1.0 for t in tokens if t and t in lm) / max(1, len(tokens))
        if s1 > 0:
            s1_scores[m] = s1

    # S2: tokens vs names from Neo4j
    s2_scores: Dict[str, float] = {}
    for m in neo_modules:
        lm = m.lower()
        s2 = sum(1.0 for t in tokens if t and t in lm) / max(1, len(tokens))
        if s2 > 0:
            s2_scores[m] = s2

    # S3: out of scope here (needs doc mapping); use 0
    combined: Dict[str, float] = {}
    for m in set(list(s1_scores.keys()) + list(s2_scores.keys())):
        combined[m] = 0.5 * s1_scores.get(m, 0.0) + 0.3 * s2_scores.get(m, 0.0) + 0.2 * 0.0

    if not combined:
        return None
    mod, score = max(combined.items(), key=lambda kv: kv[1])
    return mod
