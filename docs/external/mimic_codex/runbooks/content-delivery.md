# Content Delivery Runbook

Goal: safely deliver a campaign content pack into staging with validation and observability.

Prerequisites
- Repo has `data/knowledge/campaigns/<campaign_id>.yaml` (see `ashen_moon_arc.yaml` example).
- CI job `content-validate` runs ingest dry-run.
- Services expose `/metrics` when `ENABLE_METRICS=true` (see services/*/observability.py).

Steps
1) Validate locally (optional)
   - `python -m memory37.cli ingest-file data/knowledge/campaigns/ashen_moon_arc.yaml --dry-run`
   - `python -m memory37.cli search "moon" --knowledge-file data/knowledge/campaigns/ashen_moon_arc.yaml --dry-run`
2) Open PR with changes under `data/knowledge/` and link to this runbook.
   - CI will run `content-validate` and fail on invalid YAML or ingest errors.
3) Merge to main and deploy to staging
   - Set `KNOWLEDGE_SOURCE_PATH=data/knowledge/campaigns/ashen_moon_arc.yaml` for Gateway.
   - Run UI smoke: `docs/runbooks/ui-smoke.md`.
4) Observe and adjust
   - Enable `/metrics` via `ENABLE_METRICS=true`.
   - Import Prometheus rules from `observability/prometheus/rules/app-rules.yaml`.
   - Calibrate SLO thresholds after 1–2 weeks of baseline.

Source of truth (reviewed 2025-10-31 18:36 UTC)
- JSON Schema 2020-12 — json-schema.org
- Prometheus alerting rules — prometheus.io
- OpenTelemetry docs — opentelemetry.io
