from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_list_jobs(monkeypatch):
    from api.services import jobs as jobs_service

    monkeypatch.setattr(jobs_service, "list_jobs", lambda project=None: [{"job_id": "job-1"}])

    resp = client.get("/jobs?project=context_engine")
    assert resp.status_code == 200
    assert resp.json()["jobs"][0]["job_id"] == "job-1"


def test_get_job(monkeypatch):
    from api.services import jobs as jobs_service

    monkeypatch.setattr(jobs_service, "get_job", lambda job_id: {"job_id": job_id})

    resp = client.get("/jobs/job-2")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == "job-2"


def test_get_job_not_found(monkeypatch):
    from api.services import jobs as jobs_service

    monkeypatch.setattr(jobs_service, "get_job", lambda job_id: None)

    resp = client.get("/jobs/missing")
    assert resp.status_code == 404


def test_job_log(monkeypatch):
    from api.services import jobs as jobs_service

    monkeypatch.setattr(jobs_service, "read_log", lambda job_id: "hello")

    resp = client.get("/jobs/job-3/log")
    assert resp.status_code == 200
    assert resp.text == "hello"
