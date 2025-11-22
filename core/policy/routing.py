from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from core.config.policy import PolicyConfig
from core.resolver import tokenize

logger = logging.getLogger(__name__)


@dataclass
class RuleEffects:
    boost_modules: Dict[str, float] = field(default_factory=dict)
    boost_tags: Set[str] = field(default_factory=set)
    add_tags: Set[str] = field(default_factory=set)
    reduce_code_weight: Optional[float] = None  # multiplicative коэффициент (<=1)
    boost_docs: Optional[float] = None  # multiplicative коэффициент (>=1)
    max_tokens_share: Optional[float] = None  # доля 0..1


@dataclass
class RoutingRule:
    name: str
    priority: int
    mode: str
    terms: List[str]
    effects: RuleEffects

    def match(self, text: str, tokens: Set[str]) -> Tuple[bool, List[str]]:
        """Проверка совпадения правила и возврат списка сработавших term'ов."""
        mode = self.mode.lower()
        matched_terms: List[str] = []
        if not self.terms:
            return False, matched_terms

        if mode == "keyword_any":
            matched_terms = [t for t in self.terms if _term_hits(t, text, tokens)]
            return bool(matched_terms), matched_terms
        if mode == "keyword_all":
            ok = all(_term_hits(t, text, tokens) for t in self.terms)
            if ok:
                matched_terms = list(self.terms)
            return ok, matched_terms
        if mode == "regex":
            for term in self.terms:
                try:
                    if re.search(term, text, re.IGNORECASE):
                        matched_terms.append(term)
                except re.error:
                    logger.debug("invalid regex in rule %s: %s", self.name, term)
                    continue
            return bool(matched_terms), matched_terms

        logger.debug("unknown mode %s in rule %s", self.mode, self.name)
        return False, matched_terms


@dataclass
class MatchedRule:
    name: str
    priority: int
    mode: str
    matched_terms: List[str]
    effects: RuleEffects


@dataclass
class RoutingEffects:
    module_boosts: Dict[str, float] = field(default_factory=dict)
    boost_tags: Set[str] = field(default_factory=set)
    add_tags: Set[str] = field(default_factory=set)
    code_weight: Optional[float] = None
    doc_weight: Optional[float] = None
    max_tokens_share: Optional[float] = None
    matched_rules: List[MatchedRule] = field(default_factory=list)


def rules_from_policy(cfg: PolicyConfig) -> List[RoutingRule]:
    """Построить список RoutingRule из PolicyConfig."""
    return rules_from_dicts(cfg.routing_rules)


def rules_from_dicts(entries: Iterable[Dict[str, Any]]) -> List[RoutingRule]:
    rules: List[RoutingRule] = []
    for idx, entry in enumerate(entries):
        try:
            rule = _parse_rule(entry)
        except Exception as exc:  # pragma: no cover - лог только для дебага
            logger.debug("skip invalid rule[%s]: %s (%s)", idx, entry, exc)
            rule = None
        if rule:
            rules.append(rule)
    rules.sort(key=lambda r: (-r.priority, r.name))
    return rules


def evaluate_routing(task_text: str, rules: Sequence[RoutingRule]) -> RoutingEffects:
    """Матч правил по task_text и агрегировать эффекты."""
    text = task_text.lower()
    tokens = set(tokenize(task_text))
    effects = RoutingEffects()
    for rule in rules:
        matched, terms = rule.match(text, tokens)
        if not matched:
            continue
        effects.matched_rules.append(MatchedRule(rule.name, rule.priority, rule.mode, terms, rule.effects))
        _apply_effects(effects, rule.effects)
    return effects


# --------------------------------------------------------------------------- helpers


def _term_hits(term: str, text: str, tokens: Set[str]) -> bool:
    lt = term.lower()
    return lt in tokens or lt in text


def _parse_rule(entry: Dict[str, Any]) -> Optional[RoutingRule]:
    name = str(entry.get("name", "")).strip()
    if not name:
        return None
    priority = int(entry.get("priority", 0))
    match = entry.get("match", {}) or {}
    if not isinstance(match, dict):
        match = {}
    mode = str(match.get("mode", "keyword_any")).strip().lower()
    terms_raw = match.get("terms")
    if terms_raw is None:
        # поддержка старого формата any/all для плавной миграции
        if mode == "keyword_all":
            terms_raw = match.get("all")
        else:
            terms_raw = match.get("any")
    terms = [str(t).lower() for t in (terms_raw or []) if str(t).strip()]
    effects = _parse_effects(entry.get("effects", {}) or entry)
    if not terms:
        return None
    return RoutingRule(name=name, priority=priority, mode=mode, terms=terms, effects=effects)


def _parse_effects(raw: Dict[str, Any]) -> RuleEffects:
    eff = RuleEffects()
    eff.boost_modules = _parse_boost_modules(raw.get("boost_modules"))
    eff.boost_tags = _parse_str_set(raw.get("boost_tags"))
    eff.add_tags = _parse_str_set(raw.get("add_tags"))
    eff.reduce_code_weight = _parse_float(raw.get("reduce_code_weight"), none_on_error=True)
    eff.boost_docs = _parse_float(raw.get("boost_docs"), none_on_error=True)
    eff.max_tokens_share = _parse_fraction(raw.get("max_tokens_share"))
    return eff


def _parse_boost_modules(value: Any) -> Dict[str, float]:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k:
                f = _parse_float(v, default=1.0, none_on_error=False)
                out[str(k)] = out.get(str(k), 0.0) + f
        return out
    if isinstance(value, list):
        out: Dict[str, float] = {}
        for item in value:
            if item:
                module = str(item)
                out[module] = out.get(module, 0.0) + 1.0
        return out
    return {}


def _parse_str_set(value: Any) -> Set[str]:
    if isinstance(value, (list, tuple, set)):
        return {str(v) for v in value if str(v).strip()}
    return set()


def _parse_float(value: Any, default: float = 0.0, none_on_error: bool = False) -> Optional[float]:
    if value is None:
        return None if none_on_error else default
    try:
        return float(value)
    except (TypeError, ValueError):
        return None if none_on_error else default


def _parse_fraction(value: Any) -> Optional[float]:
    val = _parse_float(value, none_on_error=True)
    if val is None:
        return None
    if val <= 0.0:
        return 0.0
    if val >= 1.0:
        return 1.0
    return val


def _apply_effects(acc: RoutingEffects, rule_eff: RuleEffects) -> None:
    for module, boost in rule_eff.boost_modules.items():
        acc.module_boosts[module] = acc.module_boosts.get(module, 0.0) + boost
    acc.boost_tags.update(rule_eff.boost_tags)
    acc.add_tags.update(rule_eff.add_tags)

    if rule_eff.reduce_code_weight is not None:
        current = acc.code_weight or 1.0
        acc.code_weight = min(current, rule_eff.reduce_code_weight)
    if rule_eff.boost_docs is not None:
        current = acc.doc_weight or 1.0
        acc.doc_weight = max(current, rule_eff.boost_docs)

    if rule_eff.max_tokens_share is not None:
        if acc.max_tokens_share is None:
            acc.max_tokens_share = rule_eff.max_tokens_share
        else:
            acc.max_tokens_share = min(acc.max_tokens_share, rule_eff.max_tokens_share)
