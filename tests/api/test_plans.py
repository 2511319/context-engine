from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.main import app
from api.services.plans import PlanRecordDTO

client = TestClient(app)


def test_list_plans(monkeypatch):
    sample = PlanRecordDTO(
        plan_id="plan-1",
        ts=datetime.now(timezone.utc),
        project="context_engine",
        module="core",
        status="ok",
        route="rule:test",
        latency_ms=120,
        source_latencies={"pg": 80},
        result_sizes={"code": 2, "docs": 1},
        params={"max_code_chunks": 8},
        token_budget={"budget": 6000},
        detail={"status": "ok"},
    )

    from api.services import plans as plans_service

    monkeypatch.setattr(plans_service, "fetch_recent_plans", lambda limit, project=None: [sample])

    resp = client.get("/plans?limit=1&project=context_engine")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["plan_id"] == "plan-1"


def test_get_plan(monkeypatch):
    sample = PlanRecordDTO(
        plan_id="plan-2",
        ts=datetime.now(timezone.utc),
        project="context_engine",
        module="core",
        status="ok",
        route="rule:test",
        latency_ms=95,
        source_latencies={"pg": 50, "neo4j": 20},
        result_sizes={"code": 3, "docs": 2},
        params={"task": "demo"},
        token_budget=None,
        detail={"explain": {"params": {}}},
    )
    from api.services import plans as plans_service

    monkeypatch.setattr(plans_service, "fetch_plan", lambda plan_id: sample if plan_id == "plan-2" else None)

    resp = client.get("/plans/plan-2")
    assert resp.status_code == 200
    assert resp.json()["plan_id"] == "plan-2"


def test_export_plans(monkeypatch):
    sample = PlanRecordDTO(
        plan_id="plan-3",
        ts=datetime.now(timezone.utc),
        project="context_engine",
        module=None,
        status="ok",
        route="rule:data",
        latency_ms=42,
        source_latencies={"pg": 20},
        result_sizes={"code": 1},
        params={"max_code_chunks": 8},
        token_budget=None,
        detail={"status": "ok"},
    )

    from api.services import plans as plans_service

    monkeypatch.setattr(plans_service, "fetch_recent_plans", lambda limit, project=None: [sample])

    resp = client.get("/plans/export?limit=1&project=context_engine")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    body_lines = [line for line in resp.text.splitlines() if line.strip()]
    assert body_lines
    assert '"plan_id": "plan-3"' in body_lines[0]
