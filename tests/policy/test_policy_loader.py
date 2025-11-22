from __future__ import annotations

from pathlib import Path

from core.config.policy import PolicyLoader


def test_policy_loader_prefers_policy_file(tmp_path) -> None:
    policy_path = Path(tmp_path) / "policy.yml"
    engine_path = Path(tmp_path) / "engine.yml"
    policy_path.write_text(
        """
project: demo
observability:
  config_ttl_seconds: 5
routing:
  rules:
    - name: in_policy
      match:
        mode: keyword_any
        terms: ["foo"]
sensitive:
  - uri_pattern: "secret://*"
""",
        encoding="utf-8",
    )
    engine_path.write_text(
        """
project: fallback
policy:
  routing:
    rules:
      - name: from_engine
        match:
          mode: keyword_any
          terms: ["bar"]
""",
        encoding="utf-8",
    )

    loader = PolicyLoader(policy_path=policy_path, engine_path=engine_path, default_project="fallback", default_ttl=30)
    cfg = loader.get()

    assert cfg.project == "demo"
    assert cfg.source == str(policy_path)
    assert cfg.ttl_seconds == 5
    assert [r["name"] for r in cfg.routing_rules] == ["in_policy"]
    assert cfg.sensitive == [{"uri_pattern": "secret://*"}]


def test_policy_loader_falls_back_to_engine(tmp_path) -> None:
    policy_path = Path(tmp_path) / "policy.yml"
    engine_path = Path(tmp_path) / "engine.yml"
    engine_path.write_text(
        """
project: eng_proj
observability:
  config_ttl_seconds: 9
policy:
  routing:
    rules:
      - name: engine_rule
        match:
          mode: keyword_any
          terms: ["k"]
  sensitive:
    - uri_pattern: "hidden/*"
""",
        encoding="utf-8",
    )

    loader = PolicyLoader(policy_path=policy_path, engine_path=engine_path, default_project="default", default_ttl=3)
    cfg = loader.get()

    assert cfg.project == "eng_proj"
    assert cfg.source == str(engine_path)
    assert cfg.ttl_seconds == 9
    assert [r["name"] for r in cfg.routing_rules] == ["engine_rule"]
    assert cfg.sensitive == [{"uri_pattern": "hidden/*"}]
