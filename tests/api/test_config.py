from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_get_config(monkeypatch):
    from api.services import config as config_service

    class StubService:
        def current(self):
            return {"project": "context_engine", "checksum": "abc", "ttl_seconds": 30, "raw": {}, "file_text": "yaml"}

    stub = StubService()
    monkeypatch.setattr(config_service, "_service", stub)
    monkeypatch.setattr(config_service, "get_config_service", lambda: stub)

    resp = client.get("/config")
    assert resp.status_code == 200
    assert resp.json()["checksum"] == "abc"
