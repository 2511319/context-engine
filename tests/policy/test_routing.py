from __future__ import annotations

from core.policy.routing import evaluate_routing, rules_from_dicts


def test_keyword_any_and_regex_matching() -> None:
    rules = rules_from_dicts(
        [
            {
                "name": "kw_gateway",
                "priority": 10,
                "match": {"mode": "keyword_any", "terms": ["gateway", "auth"]},
                "effects": {"boost_modules": {"module://project/gateway": 2.0}},
            },
            {
                "name": "regex_miniapp",
                "priority": 5,
                "match": {"mode": "regex", "terms": [r"mini[-\s]?app"]},
                "effects": {"add_tags": ["scope:miniapp"], "max_tokens_share": 0.6},
            },
        ]
    )
    effects = evaluate_routing("Добавь auth flow для mini app", rules)

    matched_names = {r.name for r in effects.matched_rules}
    assert matched_names == {"kw_gateway", "regex_miniapp"}
    assert effects.module_boosts["module://project/gateway"] == 2.0
    assert "scope:miniapp" in effects.add_tags
    assert effects.max_tokens_share == 0.6


def test_keyword_all_reduce_and_boost_docs() -> None:
    rules = rules_from_dicts(
        [
            {
                "name": "secure_api",
                "priority": 7,
                "match": {"mode": "keyword_all", "terms": ["secure", "api"]},
                "effects": {"reduce_code_weight": 0.7},
            },
            {
                "name": "docs_first",
                "priority": 3,
                "match": {"mode": "keyword_any", "terms": ["guide"]},
                "effects": {"boost_docs": 1.4},
            },
        ]
    )
    effects = evaluate_routing("secure api implementation guide", rules)

    assert effects.code_weight == 0.7
    assert effects.doc_weight == 1.4
    assert {r.name for r in effects.matched_rules} == {"secure_api", "docs_first"}


def test_rules_without_terms_are_ignored() -> None:
    rules = rules_from_dicts(
        [
            {"name": "empty_terms", "priority": 1, "match": {"mode": "keyword_any", "terms": []}},
            {"name": "good", "priority": 1, "match": {"mode": "keyword_any", "terms": ["ok"]}, "effects": {"boost_tags": ["x"]}},
        ]
    )
    effects = evaluate_routing("ok", rules)
    assert {r.name for r in effects.matched_rules} == {"good"}
    assert "x" in effects.boost_tags


def test_effects_accumulate_with_min_max() -> None:
    rules = rules_from_dicts(
        [
            {
                "name": "api_focus",
                "priority": 5,
                "match": {"mode": "keyword_any", "terms": ["api"]},
                "effects": {
                    "boost_modules": {"module://project/api": 1.5},
                    "reduce_code_weight": 0.6,
                    "boost_docs": 1.2,
                    "max_tokens_share": 0.7,
                },
            },
            {
                "name": "api_docs",
                "priority": 4,
                "match": {"mode": "keyword_all", "terms": ["api", "docs"]},
                "effects": {
                    "boost_modules": {"module://project/api": 1.0},
                    "reduce_code_weight": 0.4,
                    "boost_docs": 1.5,
                    "max_tokens_share": 0.3,
                },
            },
        ]
    )
    effects = evaluate_routing("api docs", rules)

    assert effects.module_boosts["module://project/api"] == 2.5
    assert effects.code_weight == 0.4
    assert effects.doc_weight == 1.5
    assert effects.max_tokens_share == 0.3


def test_invalid_regex_rule_is_skipped() -> None:
    rules = rules_from_dicts(
        [
            {"name": "broken", "priority": 5, "match": {"mode": "regex", "terms": ["[unclosed"]}},
            {
                "name": "fallback",
                "priority": 1,
                "match": {"mode": "keyword_any", "terms": ["ok"]},
                "effects": {"add_tags": ["safe"]},
            },
        ]
    )
    effects = evaluate_routing("ok", rules)

    assert {r.name for r in effects.matched_rules} == {"fallback"}
    assert "safe" in effects.add_tags
