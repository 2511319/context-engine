from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Ensure local virtualenv packages are importable even if server launched via system Python.
_VENV_PATH = _PROJECT_ROOT / ".venv"
_SITE_PACKAGES_CANDIDATES = [
    _VENV_PATH / "Lib" / "site-packages",  # Windows
    _VENV_PATH / "lib" / "site-packages",
]
if _VENV_PATH.exists():
    _SITE_PACKAGES_CANDIDATES.extend(_VENV_PATH.glob("lib/python*/site-packages"))

for candidate in _SITE_PACKAGES_CANDIDATES:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

try:
    os.chdir(_PROJECT_ROOT)
except Exception:
    pass


def _load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
    except Exception:
        pass


_load_env(_PROJECT_ROOT / ".env")

def _log_startup(message: str) -> None:
    try:
        log_path = _PROJECT_ROOT / "logs" / "mcp-server-start.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
    except Exception:
        pass

_log_startup(f"starting: exe={sys.executable} cwd={Path.cwd()}")

from context_engine.mcp.transport import StdioJSONRPCTransport
from core.config_loader import ConfigLoader
from core.config.policy import PolicyLoader
from core.graph import list_modules_neo4j, subgraph
from core.merger import dedup_overlaps
from core.dal import GraphClient, PgClient
from core.dal.repos import CodeRepo, DocRepo, FeedbackRepo, PlanRepo
from core.plan_log import PlanLogEntry, PlanLogger, new_plan_id
from core.retrieval import RetrievalCandidates, RetrievalWeights, hybrid_search
from core.resolver import heuristic_module
from core.token_budget import count_tokens
from core.policy.routing import evaluate_routing, rules_from_policy
from core.policy.feedback import FeedbackEffect, aggregate_by_module, get_feedback_effects
from core.uri import doc_uri, module_uri
from tools.task_fp import compute_task_fp

logger = logging.getLogger("context_engine.mcp.server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

PROTOCOL_VERSION = "2025-06-18"


@dataclass
class Env:
    pg_dsn: Optional[str]
    neo4j_uri: Optional[str]
    neo4j_user: Optional[str]
    neo4j_pass: Optional[str]
    openai_key: Optional[str]

    @classmethod
    def load(cls) -> Env:
        return cls(
            pg_dsn=os.getenv("PG_DSN"),
            neo4j_uri=os.getenv("NEO4J_URI"),
            neo4j_user=os.getenv("NEO4J_USER"),
            neo4j_pass=os.getenv("NEO4J_PASS"),
            openai_key=os.getenv("OPENAI_API_KEY"),
        )


class ToolExecutionError(Exception):
    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.detail = detail or {}


class Health:
    @staticmethod
    def pg_ok(pg_dsn: Optional[str]) -> bool:
        if not pg_dsn:
            return False
        try:
            client = PgClient(pg_dsn)
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres client init failed: %s", exc)
            return False
        try:
            with client.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    _ = cur.fetchone()
            return True
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres health-check failed: %s", exc)
            return False

    @staticmethod
    def neo4j_ok(uri: Optional[str], user: Optional[str], password: Optional[str]) -> bool:
        if not uri or not user or not password:
            return False
        try:
            client = GraphClient(uri, user, password)
        except Exception as exc:  # pragma: no cover
            logger.error("Neo4j client init failed: %s", exc)
            return False
        try:
            with client.session() as session:
                session.run("RETURN 1 AS ok").single()
            return True
        except Exception as exc:  # pragma: no cover
            logger.error("Neo4j health-check failed: %s", exc)
            return False


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    title: Optional[str] = None


@dataclass
class JobInfo:
    job_id: str
    name: str
    command: List[str]
    plan_id: str
    project: str
    status: str = "queued"
    log_path: Path | None = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None


class JobManager:
    def __init__(self, project_root: Path, on_complete: Callable[[JobInfo], None]) -> None:
        self.project_root = project_root
        self.jobs_dir = project_root / "logs" / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.on_complete = on_complete
        self._jobs: Dict[str, JobInfo] = {}
        self._lock = threading.Lock()

    def start_job(self, name: str, command: List[str], plan_id: str, project: str) -> JobInfo:
        job_id = str(uuid.uuid4())
        job = JobInfo(
            job_id=job_id,
            name=name,
            command=command,
            plan_id=plan_id,
            project=project,
            log_path=self.jobs_dir / f"{job_id}.log",
        )
        with self._lock:
            self._jobs[job_id] = job
        self._persist(job)
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def list_jobs(self) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        for path in sorted(self.jobs_dir.glob("*.json"), reverse=True):
            try:
                jobs.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return jobs

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = self.jobs_dir / f"{job_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def log_file(self, job_id: str) -> Optional[Path]:
        path = self.jobs_dir / f"{job_id}.log"
        return path if path.exists() else None

    def _run_job(self, job: JobInfo) -> None:
        cmd = job.command
        job.started_at = datetime.now(timezone.utc)
        job.status = "running"
        self._persist(job)
        log_path = job.log_path or (self.jobs_dir / f"{job.job_id}.log")
        try:
            with log_path.open("w", encoding="utf-8") as log_file:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.project_root),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
                exit_code = proc.wait()
                job.exit_code = exit_code
                job.status = "success" if exit_code == 0 else "failed"
        except Exception as exc:  # pragma: no cover
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = datetime.now(timezone.utc)
            self._persist(job)
            self.on_complete(job)

    def _persist(self, job: JobInfo) -> None:
        payload = {
            "job_id": job.job_id,
            "name": job.name,
            "command": job.command,
            "plan_id": job.plan_id,
            "project": job.project,
            "status": job.status,
            "started_at": job.started_at.astimezone(timezone.utc).isoformat() if job.started_at else None,
            "finished_at": job.finished_at.astimezone(timezone.utc).isoformat() if job.finished_at else None,
            "exit_code": job.exit_code,
            "error": job.error,
            "log_path": str(job.log_path) if job.log_path else None,
        }
        json_path = self.jobs_dir / f"{job.job_id}.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class MCPServer:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.transport = StdioJSONRPCTransport()
        self.config = ConfigLoader(project_root / "config" / "engine.yml")
        self.policy_loader = PolicyLoader(
            policy_path=project_root / "config" / "policy.yml",
            engine_path=project_root / "config" / "engine.yml",
        )
        self.env = Env.load()
        self.plan_logger = PlanLogger(
            pg_dsn=self.env.pg_dsn,
            jsonl_path=project_root / "logs" / "context-engine.log",
        )
        self.job_manager = JobManager(project_root, self._on_job_complete)
        self.protocol_version = PROTOCOL_VERSION
        self.initialized = False
        self.tools = self._build_tools()

    def run_stdio(self) -> None:
        while True:
            message = self.transport.read_message()
            if message is None:
                break
            if "method" in message:
                if "id" in message:
                    response = self._handle_request(message)
                    if response is not None:
                        self.transport.write_message(response)
                else:
                    self._handle_notification(message)
            else:
                logger.debug("Ignoring message without method: %s", message)

    def _handle_request(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = message.get("method")
        request_id = message.get("id")
        if method == "initialize":
            result = {
                "serverInfo": {"name": "context-engine-mcp", "version": "0.1.0"},
                "protocolVersion": self.protocol_version,
                "capabilities": {"tools": {}},
                "instructions": "Use tools to retrieve repository context for IDE assistance.",
            }
            return self._jsonrpc_result(request_id, result)
        if method == "tools/list":
            tools = [self._tool_to_dict(tool) for tool in self.tools.values()]
            return self._jsonrpc_result(request_id, {"tools": tools})
        if method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str):
                return self._jsonrpc_error(request_id, -32602, "Tool name must be provided")
            tool = self.tools.get(name)
            if tool is None:
                return self._jsonrpc_error(request_id, -32601, f"Unknown tool: {name}")
            try:
                structured = tool.handler(arguments)
                result = {
                    "content": [{"type": "text", "text": f"{name} completed successfully"}],
                    "structuredContent": structured,
                }
            except ToolExecutionError as exc:
                result = {
                    "content": [{"type": "text", "text": str(exc)}],
                    "structuredContent": exc.detail,
                    "isError": True,
                }
            return self._jsonrpc_result(request_id, result)
        return self._jsonrpc_error(request_id, -32601, f"Unknown method: {method}")

    def _handle_notification(self, message: Dict[str, Any]) -> None:
        method = message.get("method")
        if method == "notifications/initialized":
            self.initialized = True
            return
        if method == "notifications/cancelled":
            return
        logger.debug("Ignoring notification %s", method)

    @staticmethod
    def _jsonrpc_result(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _jsonrpc_error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def _tool_to_dict(self, tool: ToolDefinition) -> Dict[str, Any]:
        schema = tool.input_schema.copy()
        schema.setdefault("type", "object")
        return {
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "inputSchema": schema,
        }

    def _build_tools(self) -> Dict[str, ToolDefinition]:
        return {
            "get_context": ToolDefinition(
                name="get_context",
                title="Get Context",
                description="Return code/doc artifacts and graph subgraph relevant to a task.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "project": {"type": "string"},
                        "max_code_chunks": {"type": "integer", "minimum": 1, "maximum": 50},
                        "max_doc_chunks": {"type": "integer", "minimum": 1, "maximum": 50},
                        "graph_depth": {"type": "integer", "minimum": 1, "maximum": 5},
                        "token_budget": {"type": "integer", "minimum": 1000, "maximum": 20000},
                        "retrieval": {
                            "type": "object",
                            "properties": {
                                "mode": {"type": "string", "enum": ["hybrid", "lexical", "vector"]},
                                "lexical_config": {"type": "string"},
                                "weights": {
                                    "type": "object",
                                    "properties": {
                                        "vector": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                        "bm25": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                    },
                                },
                                "candidates": {
                                    "type": "object",
                                    "properties": {
                                        "vector_k": {"type": "integer", "minimum": 1, "maximum": 400},
                                        "bm25_k": {"type": "integer", "minimum": 1, "maximum": 400},
                                    },
                                },
                            },
                        },
                    },
                    "required": ["task"],
                },
                handler=self._tool_get_context,
            ),
            "search_raw": ToolDefinition(
                name="search_raw",
                title="Search Raw",
                description="Execute a hybrid search across code/doc chunks.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project": {"type": "string"},
                        "query": {"type": "string"},
                        "scope": {"type": "string", "enum": ["code", "doc", "both"]},
                        "k": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["project", "query"],
                },
                handler=self._tool_search_raw,
            ),
            "ingest": ToolDefinition(
                name="ingest",
                title="Ingest Repository",
                description="Trigger repository re-indexing for the given project.",
                input_schema={
                    "type": "object",
                    "properties": {"project": {"type": "string"}},
                    "required": ["project"],
                },
                handler=self._tool_ingest,
            ),
            "graphify": ToolDefinition(
                name="graphify",
                title="Graphify",
                description="Project routing/doc graph into Neo4j (background job).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project": {"type": "string"},
                        "dry_run": {"type": "boolean"},
                    },
                },
                handler=self._tool_graphify,
            ),
            "index_repo": ToolDefinition(
                name="index_repo",
                title="Index Repository",
                description="Rebuild vector/lexical indexes via repository scan (background job).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project": {"type": "string"},
                    },
                },
                handler=self._tool_index_repo,
            ),
            "pin": ToolDefinition(
                name="pin",
                title="Pin Artifact",
                description="Record positive feedback (pin) for a URI under a task fingerprint.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project": {"type": "string"},
                        "uri": {"type": "string"},
                        "task": {"type": "string"},
                    },
                    "required": ["project", "uri", "task"],
                },
                handler=self._tool_pin,
            ),
            "forget": ToolDefinition(
                name="forget",
                title="Forget Artifact",
                description="Record negative feedback (forget) for a URI under a task fingerprint.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project": {"type": "string"},
                        "uri": {"type": "string"},
                        "task": {"type": "string"},
                    },
                    "required": ["project", "uri", "task"],
                },
                handler=self._tool_forget,
            ),
            "explain_plan": ToolDefinition(
                name="explain_plan",
                title="Explain Plan",
                description="Return the latest plan log entry or a specific plan_id.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "plan_id": {"type": "string"},
                        "last": {"type": "boolean"},
                        "project": {"type": "string"},
                    },
                },
                handler=self._tool_explain_plan,
            ),
        }

    # ------------------------------------------------------------------ tools

    def _tool_get_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        plan_id = new_plan_id()
        cfg = self.config.get()
        policy_cfg = self.policy_loader.get()

        project = str(params.get("project") or cfg.project)
        task = params.get("task", "")
        if not isinstance(task, str) or not task.strip():
            raise ToolExecutionError("task is required")

        if not Health.pg_ok(self.env.pg_dsn):
            detail = {"status": "down", "component": "postgres", "message": "postgres unavailable"}
            self._log_plan(
                plan_id,
                project,
                module=None,
                status="down",
                route="health-check",
                latency_ms=int((time.perf_counter() - start) * 1000),
                source_latencies={},
                result_sizes={},
                params=params,
                token_budget=None,
                detail=detail,
            )
            raise ToolExecutionError("postgres unavailable", detail)

        if not Health.neo4j_ok(self.env.neo4j_uri, self.env.neo4j_user, self.env.neo4j_pass):
            detail = {"status": "down", "component": "neo4j", "message": "neo4j unavailable"}
            self._log_plan(
                plan_id,
                project,
                module=None,
                status="down",
                route="health-check",
                latency_ms=int((time.perf_counter() - start) * 1000),
                source_latencies={},
                result_sizes={},
                params=params,
                token_budget=None,
                detail=detail,
            )
            raise ToolExecutionError("neo4j unavailable", detail)

        pg_client = PgClient(self.env.pg_dsn or "")
        code_repo = CodeRepo(pg_client)
        doc_repo = DocRepo(pg_client)
        feedback_repo = FeedbackRepo(pg_client)

        retr_cfg = cfg.raw.get("retrieval", {}) or {}
        defaults = cfg.raw.get("defaults", {}) or {}
        overrides = params.get("retrieval") or {}
        merged_retr = {
            "mode": overrides.get("mode", retr_cfg.get("mode", "hybrid")),
            "lexical_config": overrides.get("lexical_config", retr_cfg.get("lexical_config", "simple")),
            "weights": {**(retr_cfg.get("weights", {}) or {}), **(overrides.get("weights", {}) or {})},
            "candidates": {**(retr_cfg.get("candidates", {}) or {}), **(overrides.get("candidates", {}) or {})},
        }
        weights = RetrievalWeights(
            vector=float(merged_retr.get("weights", {}).get("vector", 0.7)),
            bm25=float(merged_retr.get("weights", {}).get("bm25", 0.3)),
        )
        candidates = RetrievalCandidates(
            vector_k=int(merged_retr.get("candidates", {}).get("vector_k", 120)),
            bm25_k=int(merged_retr.get("candidates", {}).get("bm25_k", 120)),
        )
        lex_cfg = str(merged_retr.get("lexical_config", "simple"))
        max_code = int(params.get("max_code_chunks", defaults.get("max_code_chunks", 8)))
        max_doc = int(params.get("max_doc_chunks", defaults.get("max_doc_chunks", 5)))
        depth = int(params.get("graph_depth", defaults.get("graph_depth", 3)))
        token_budget_limit = int(params.get("token_budget", 6000))

        try:
            task_fp = compute_task_fp(task)
        except Exception:
            task_fp = None

        timers: Dict[str, float] = {"pg": 0.0, "neo4j": 0.0}

        def _time_call(bucket: str, fn: Callable[[], Any]) -> Any:
            start_bucket = time.perf_counter()
            try:
                return fn()
            finally:
                timers[bucket] += time.perf_counter() - start_bucket

        code_cands, doc_cands = _time_call(
            "pg",
            lambda: hybrid_search(
                code_repo=code_repo,
                doc_repo=doc_repo,
                feedback_repo=feedback_repo,
                project=project,
                task=task,
                api_key=self.env.openai_key,
                weights=weights,
                candidates=candidates,
                lex_cfg=lex_cfg,
                task_fp=task_fp,
                apply_feedback=False,  # feedback переедет в policy-слой
            ),
        )

        code_cands = code_cands[: max_code * 2]
        doc_cands = doc_cands[: max_doc * 2]
        code_cands, doc_cands = dedup_overlaps(code_cands, doc_cands)
        code_cands = code_cands[:max_code]
        doc_cands = doc_cands[:max_doc]
        # ---------------------- Data-layer: агрегация модулей и подграф
        modules = self._aggregate_modules(project, code_cands, doc_cands)
        module_for_graph = next((m["name"] for m in modules.values() if m["name"] and m.get("has_code")), "")
        if not module_for_graph:
            neo_modules = list_modules_neo4j(
                self.env.neo4j_uri or "", self.env.neo4j_user or "", self.env.neo4j_pass or "", project
            )
            module_for_graph = heuristic_module(task, code_repo, project, neo_modules) or ""

        graph_obj = _time_call(
            "neo4j",
            lambda: subgraph(
                self.env.neo4j_uri or "",
                self.env.neo4j_user or "",
                self.env.neo4j_pass or "",
                project,
                module_for_graph or "",
                depth,
            ),
        )

        # ---------------------- Policy-layer: routing + feedback + sensitive
        routing_rules = rules_from_policy(policy_cfg)
        routing_effects = evaluate_routing(task, routing_rules) if routing_rules else None

        uri_to_module = self._uri_to_module_map(project, modules, code_cands, doc_cands)
        fb_by_uri = get_feedback_effects(
            feedback_repo=feedback_repo, project=project, task_fp=task_fp, uris=[c.uri() for c in code_cands + doc_cands]
        )
        fb_by_module = aggregate_by_module(fb_by_uri, uri_to_module)

        sensitive_filtered: List[str] = []
        code_cands, doc_cands, modules = self._apply_policy(
            project=project,
            code_cands=code_cands,
            doc_cands=doc_cands,
            modules=modules,
            routing_effects=routing_effects,
            fb_by_uri=fb_by_uri,
            fb_by_module=fb_by_module,
            sensitive_rules=policy_cfg.sensitive,
            sensitive_filtered=sensitive_filtered,
        )
        uri_to_module = self._uri_to_module_map(project, modules, code_cands, doc_cands)

        # ---------------------- Token budget и финальный выбор (учёт max_tokens_share)
        pre_budget_code = len(code_cands)
        pre_budget_docs = len(doc_cands)
        code_cands, doc_cands, token_budget_snapshot = self._select_with_budget(
            code_cands=code_cands,
            doc_cands=doc_cands,
            uri_to_module=uri_to_module,
            total_budget=token_budget_limit,
            max_module_share=routing_effects.max_tokens_share if routing_effects else None,
        )

        code_out = [
            {
                "path": c.path,
                "uri": c.uri(),
                "module_uri": uri_to_module.get(c.uri(), ""),
                "commit_sha": c.commit_sha or "",
                "chunk_id": c.chunk_id or "",
                "fp_sha256": c.fp_sha256 or "",
                "content": c.content,
                "score": c.score,
                "sim_vec": c.sim_vec,
                "sim_bm25": c.sim_bm25,
                "bm25_rank_pos": None if c.bm25_rank_pos >= 10**9 else c.bm25_rank_pos,
                "bias_pin": c.bias_pin,
                "penalty_neg": c.penalty_neg,
            }
            for c in code_cands
        ]
        docs_out = [
            {
                "doc": c.doc_name or "",
                "section": c.section or "",
                "uri": c.uri(),
                "module_uri": uri_to_module.get(c.uri(), "") or doc_uri(project, c.doc_name or ""),
                "commit_sha": c.commit_sha or "",
                "chunk_id": c.chunk_id or "",
                "fp_sha256": c.fp_sha256 or "",
                "content": c.content,
                "score": c.score,
                "sim_vec": c.sim_vec,
                "sim_bm25": c.sim_bm25,
                "bm25_rank_pos": None if c.bm25_rank_pos >= 10**9 else c.bm25_rank_pos,
                "bias_pin": c.bias_pin,
                "penalty_neg": c.penalty_neg,
            }
            for c in doc_cands
        ]

        explain_payload: Dict[str, Any] = {
            "plan_id": plan_id,
            "plan_schema_version": 1,
            "data_route": {
                "project": project,
                "code_candidates_top": self._top_candidates(code_cands, uri_to_module, limit=5),
                "doc_candidates_top": self._top_candidates(doc_cands, uri_to_module, limit=5),
                "modules_base": self._sorted_modules(modules, key_field="base_score"),
                "graph_stats": {"relations": len(graph_obj.get("relations", []) or [])},
            },
            "policy_route": {
                "routing_rules_matched": [
                    {
                        "rule_name": r.name,
                        "priority": r.priority,
                        "mode": r.mode,
                        "matched_terms": r.matched_terms,
                        "effects": {
                            "boost_modules": r.effects.boost_modules,
                            "boost_tags": list(r.effects.boost_tags),
                            "add_tags": list(r.effects.add_tags),
                            "reduce_code_weight": r.effects.reduce_code_weight,
                            "boost_docs": r.effects.boost_docs,
                            "max_tokens_share": r.effects.max_tokens_share,
                        },
                    }
                    for r in (routing_effects.matched_rules if routing_effects else [])
                ],
                "feedback_effects": [
                    {
                        "module_uri": m_uri,
                        "pin_bias": eff.pin_bias,
                        "forget_penalty": eff.forget_penalty,
                    }
                    for m_uri, eff in fb_by_module.items()
                ],
                "sensitive_filtered": sensitive_filtered,
            },
            "selection": {
                "final_modules": self._sorted_modules(modules, key_field="final_score"),
                "included_chunks": self._selection_chunks(code_cands, doc_cands, uri_to_module),
            },
            "sources": {"code": "postgres: code_chunks", "docs": "postgres: doc_chunks", "graph": "neo4j"},
            "params": {
                "max_code_chunks": max_code,
                "max_doc_chunks": max_doc,
                "graph_depth": depth,
                "retrieval": retr_cfg,
                "config_version": "v1",
                "config_checksum": cfg.checksum,
                "policy_checksum": policy_cfg.checksum,
                "token_budget": token_budget_snapshot,
            },
        }

        result: Dict[str, Any] = {
            "status": "ok",
            "plan_id": plan_id,
            "project": project,
            "module": module_for_graph or "",
            "code": code_out,
            "docs": docs_out,
            "graph": graph_obj,
            "explain": explain_payload,
        }

        latency_ms = int((time.perf_counter() - start) * 1000)
        self._log_plan(
            plan_id=plan_id,
            project=project,
            module=module_for_graph or None,
            status="ok",
            route="engine.yml",
            latency_ms=latency_ms,
            source_latencies={
                "postgres": int(timers["pg"] * 1000),
                "neo4j": int(timers["neo4j"] * 1000),
            },
            result_sizes={"code": len(code_out), "docs": len(docs_out)},
            params={
                "max_code_chunks": max_code,
                "max_doc_chunks": max_doc,
                "graph_depth": depth,
                "task": task,
                "project": project,
            },
            token_budget=token_budget_snapshot,
            detail=result,
        )
        return result

    # --------------------------- internal helpers (get_context)

    @staticmethod
    def _module_from_candidate(project: str, cand) -> tuple[str, str]:
        if getattr(cand, "kind", None) == "code":
            name = cand.module or (Path(cand.path or "").with_suffix("").as_posix() if cand.path else "")
        elif getattr(cand, "kind", None) == "doc":
            name = cand.doc_name or ""
        else:
            name = ""
        uri = module_uri(project, name) if name else ""
        return name, uri

    def _aggregate_modules(self, project: str, code_cands, doc_cands) -> Dict[str, Dict[str, Any]]:
        modules: Dict[str, Dict[str, Any]] = {}
        for cand in list(code_cands) + list(doc_cands):
            name, uri = self._module_from_candidate(project, cand)
            if not uri:
                continue
            entry = modules.setdefault(
                uri, {"name": name, "base_score": 0.0, "final_score": 0.0, "has_code": False}
            )
            entry["base_score"] += cand.score
            entry["final_score"] = entry["base_score"]
            if getattr(cand, "kind", None) == "code":
                entry["has_code"] = True
        return modules

    def _uri_to_module_map(self, project: str, modules: Dict[str, Dict[str, Any]], code_cands, doc_cands) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for cand in list(code_cands) + list(doc_cands):
            _, mod_uri = self._module_from_candidate(project, cand)
            if mod_uri:
                mapping[cand.uri()] = mod_uri
        for mod_uri in modules.keys():
            mapping.setdefault(mod_uri, mod_uri)
        return mapping

    @staticmethod
    def _is_sensitive(uri: str, sensitive_rules) -> bool:
        for rule in sensitive_rules or []:
            pattern = str(rule.get("uri_pattern") or rule.get("pattern") or "").strip()
            if pattern and fnmatch(uri, pattern):
                return True
        return False

    def _apply_policy(
        self,
        project: str,
        code_cands,
        doc_cands,
        modules: Dict[str, Dict[str, Any]],
        routing_effects,
        fb_by_uri: Dict[str, FeedbackEffect],
        fb_by_module: Dict[str, FeedbackEffect],
        sensitive_rules,
        sensitive_filtered: List[str],
    ):
        # финальный score модулей (routing + feedback)
        for m_uri, meta in modules.items():
            boost = (routing_effects.module_boosts.get(m_uri, 0.0) if routing_effects else 0.0)
            fb_eff = fb_by_module.get(m_uri)
            pin_bias = fb_eff.pin_bias if fb_eff else 0.0
            forget_penalty = fb_eff.forget_penalty if fb_eff else 0.0
            meta["final_score"] = meta["base_score"] + boost + pin_bias - forget_penalty

        def adjust(cands):
            out = []
            for cand in cands:
                uri = cand.uri()
                if self._is_sensitive(uri, sensitive_rules):
                    sensitive_filtered.append(uri)
                    continue
                mod_uri = self._module_from_candidate(project, cand)[1]
                module_delta = 0.0
                if mod_uri in modules:
                    module_delta = modules[mod_uri]["final_score"] - modules[mod_uri]["base_score"]

                fb_eff_uri = fb_by_uri.get(uri)
                if fb_eff_uri:
                    cand.bias_pin = fb_eff_uri.pin_bias
                    cand.penalty_neg = fb_eff_uri.forget_penalty

                score = cand.score
                if routing_effects:
                    if cand.kind == "code" and routing_effects.code_weight:
                        score *= routing_effects.code_weight
                    if cand.kind == "doc" and routing_effects.doc_weight:
                        score *= routing_effects.doc_weight
                score += module_delta
                cand.score = score
                out.append(cand)
            out.sort(key=lambda c: (-c.score, c.uri()))
            return out
        adj_code = adjust(code_cands)
        adj_doc = adjust(doc_cands)

        # удалить модули, по которым не осталось чанков после sensitive/score adjustments
        used_modules = {self._module_from_candidate(project, c)[1] for c in adj_code + adj_doc if c.uri()}
        removed_modules = [m_uri for m_uri in modules.keys() if m_uri not in used_modules]
        modules = {m_uri: m for m_uri, m in modules.items() if m_uri in used_modules}
        sensitive_filtered.extend(removed_modules)

        return adj_code, adj_doc, modules

    def _select_with_budget(
        self,
        code_cands,
        doc_cands,
        uri_to_module: Dict[str, str],
        total_budget: int,
        max_module_share: Optional[float] = None,
    ):
        # комбинируем, сортируем по score, применяем общее ограничение и ограничение на модуль
        combined = [(c, count_tokens([c.content])) for c in list(code_cands) + list(doc_cands)]
        combined.sort(key=lambda x: (-x[0].score, x[0].uri()))

        max_per_module = int(total_budget * max_module_share) if max_module_share else total_budget
        total_tokens = 0
        per_module: Dict[str, int] = {}
        selected: List = []
        for cand, tok in combined:
            mod_uri = uri_to_module.get(cand.uri(), "")
            per_mod = per_module.get(mod_uri, 0)
            if total_tokens + tok > total_budget:
                continue
            if max_module_share and per_mod + tok > max_per_module:
                continue
            selected.append((cand, tok))
            total_tokens += tok
            per_module[mod_uri] = per_mod + tok

        sel_codes = [c for c, _ in selected if getattr(c, "kind", None) == "code"]
        sel_docs = [c for c, _ in selected if getattr(c, "kind", None) == "doc"]
        pre_code_count = len(code_cands)
        pre_doc_count = len(doc_cands)
        snapshot = {
            "budget": total_budget,
            "code_tokens": sum(tok for c, tok in selected if getattr(c, "kind", None) == "code"),
            "doc_tokens": sum(tok for c, tok in selected if getattr(c, "kind", None) == "doc"),
            "total_tokens": total_tokens,
            "code_count": len(sel_codes),
            "doc_count": len(sel_docs),
            "truncated_code": max(0, pre_code_count - len(sel_codes)),
            "truncated_docs": max(0, pre_doc_count - len(sel_docs)),
            "max_module_share": max_module_share,
        }
        return sel_codes, sel_docs, snapshot

    @staticmethod
    def _sorted_modules(modules: Dict[str, Dict[str, Any]], key_field: str) -> List[Dict[str, Any]]:
        return [
            {
                "module_uri": m_uri,
                "module_name": m["name"],
                "module_base_score": m["base_score"],
                "final_module_score": m["final_score"],
            }
            for m_uri, m in sorted(modules.items(), key=lambda kv: (-kv[1].get(key_field, 0.0), kv[0]))
        ]

    @staticmethod
    def _top_candidates(items, uri_to_module: Dict[str, str], limit: int = 5) -> List[Dict[str, Any]]:
        out = []
        for c in sorted(items, key=lambda x: (-x.score, x.uri()))[:limit]:
            out.append({"uri": c.uri(), "module_uri": uri_to_module.get(c.uri(), ""), "score": c.score})
        return out

    @staticmethod
    def _selection_chunks(code_cands, doc_cands, uri_to_module: Dict[str, str]) -> List[Dict[str, Any]]:
        items = list(code_cands) + list(doc_cands)
        items.sort(key=lambda x: (-x.score, x.uri()))
        out = []
        for c in items:
            out.append(
                {
                    "uri": c.uri(),
                    "module_uri": uri_to_module.get(c.uri(), ""),
                    "chunk_id": c.chunk_id,
                    "type": c.kind,
                    "approx_tokens": len(c.content.split()),
                    "score": c.score,
                }
            )
        return out

    def _tool_search_raw(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not Health.pg_ok(self.env.pg_dsn):
            raise ToolExecutionError("postgres unavailable", {"component": "postgres"})
        project = str(params.get("project") or self.config.get().project)
        query = params.get("query", "")
        if not isinstance(query, str) or not query.strip():
            raise ToolExecutionError("query is required")
        scope = params.get("scope", "both")
        k = int(params.get("k", 10))
        cfg = self.config.get()
        retr = cfg.raw.get("retrieval", {}) or {}
        weights = RetrievalWeights(
            vector=float(retr.get("weights", {}).get("vector", 0.7)),
            bm25=float(retr.get("weights", {}).get("bm25", 0.3)),
        )
        rcand = RetrievalCandidates(vector_k=k, bm25_k=k)
        pg_client = PgClient(self.env.pg_dsn or "")
        code_repo = CodeRepo(pg_client)
        doc_repo = DocRepo(pg_client)
        feedback_repo = FeedbackRepo(pg_client)
        code, docs = hybrid_search(
            code_repo=code_repo,
            doc_repo=doc_repo,
            feedback_repo=feedback_repo,
            project=project,
            task=query,
            api_key=self.env.openai_key,
            weights=weights,
            candidates=rcand,
            lex_cfg=str(retr.get("lexical_config", "simple")),
        )
        items: list[dict[str, Any]] = []
        if scope in ("both", "code"):
            for c in code[:k]:
                items.append({"uri": c.uri(), "path_or_doc": c.path or "", "score": c.score, "content": c.content})
        if scope in ("both", "doc"):
            for d in docs[:k]:
                items.append({"uri": d.uri(), "path_or_doc": d.doc_name or "", "score": d.score, "content": d.content})
        return {"status": "ok", "items": items}

    def _tool_ingest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        project = params.get("project") or self.config.get().project
        warnings: list[str] = []
        if not Health.pg_ok(self.env.pg_dsn):
            raise ToolExecutionError("postgres unavailable", {"component": "postgres"})
        if not Health.neo4j_ok(self.env.neo4j_uri, self.env.neo4j_user, self.env.neo4j_pass):
            warnings.append("neo4j unavailable: graph phase may fail")

        plan_id = new_plan_id()
        command = [
            sys.executable or "python",
            str(self.project_root / "jobs" / "run_ingest.py"),
            "--project",
            project,
        ]
        job = self.job_manager.start_job("jobs.ingest", command, plan_id, project)
        detail = {"job": self._job_summary(job), "warnings": warnings}
        self._log_plan(
            plan_id=plan_id,
            project=project,
            module=None,
            status="queued",
            route="jobs.ingest",
            latency_ms=None,
            source_latencies={},
            result_sizes={},
            params={"project": project},
            token_budget=None,
            detail=detail,
        )
        return {"status": "queued", "plan_id": plan_id, "job_id": job.job_id, "warnings": warnings}

    def _tool_graphify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        project = params.get("project") or self.config.get().project
        dry_run = bool(params.get("dry_run", False))
        if not Health.pg_ok(self.env.pg_dsn):
            raise ToolExecutionError("postgres unavailable", {"component": "postgres"})
        if not Health.neo4j_ok(self.env.neo4j_uri, self.env.neo4j_user, self.env.neo4j_pass):
            raise ToolExecutionError("neo4j unavailable", {"component": "neo4j"})

        plan_id = new_plan_id()
        command = [
            sys.executable or "python",
            str(self.project_root / "jobs" / "run_graphify.py"),
            "--project",
            project,
        ]
        if dry_run:
            command.append("--dry-run")

        job = self.job_manager.start_job("jobs.graphify", command, plan_id, project)
        detail = {"job": self._job_summary(job), "dry_run": dry_run}
        self._log_plan(
            plan_id=plan_id,
            project=project,
            module=None,
            status="queued",
            route="jobs.graphify",
            latency_ms=None,
            source_latencies={},
            result_sizes={},
            params={"project": project, "dry_run": dry_run},
            token_budget=None,
            detail=detail,
        )
        return {
            "status": "queued",
            "plan_id": plan_id,
            "job_id": job.job_id,
            "dry_run": dry_run,
        }

    def _tool_index_repo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        project = params.get("project") or self.config.get().project
        if not Health.pg_ok(self.env.pg_dsn):
            raise ToolExecutionError("postgres unavailable", {"component": "postgres"})
        if not self.env.openai_key:
            raise ToolExecutionError("OPENAI_API_KEY is not configured", {"component": "openai"})

        plan_id = new_plan_id()
        command = [
            sys.executable or "python",
            str(self.project_root / "jobs" / "run_index_repo.py"),
            "--project",
            project,
        ]
        job = self.job_manager.start_job("jobs.index_repo", command, plan_id, project)
        detail = {"job": self._job_summary(job)}
        self._log_plan(
            plan_id=plan_id,
            project=project,
            module=None,
            status="queued",
            route="jobs.index_repo",
            latency_ms=None,
            source_latencies={},
            result_sizes={},
            params={"project": project},
            token_budget=None,
            detail=detail,
        )
        return {"status": "queued", "plan_id": plan_id, "job_id": job.job_id}

    def _tool_pin(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._store_feedback(params, label=1)

    def _tool_forget(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._store_feedback(params, label=-1)

    def _store_feedback(self, params: Dict[str, Any], label: int) -> Dict[str, Any]:
        if not Health.pg_ok(self.env.pg_dsn):
            raise ToolExecutionError("postgres unavailable", {"component": "postgres"})
        project = str(params.get("project") or self.config.get().project)
        uri = params.get("uri", "")
        task = params.get("task", "")
        if not (isinstance(uri, str) and uri.strip() and isinstance(task, str) and task.strip()):
            raise ToolExecutionError("project, uri and task are required")
        task_fp = compute_task_fp(task)
        pg_client = PgClient(self.env.pg_dsn or "")
        feedback_repo = FeedbackRepo(pg_client)
        feedback_repo.insert_feedback(project, task_fp, uri, label)
        return {"status": "ok", "project": project, "uri": uri, "label": label}

    def _tool_explain_plan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = params.get("plan_id")
        last = params.get("last", True)
        project = params.get("project")
        if not Health.pg_ok(self.env.pg_dsn):
            raise ToolExecutionError("postgres unavailable", {"component": "postgres"})
        pg_client = PgClient(self.env.pg_dsn or "")
        plan_repo = PlanRepo(pg_client)
        row = None
        if plan_id:
            row = plan_repo.fetch_one(plan_id)
        elif project:
            rows = plan_repo.fetch_recent(limit=1, project=project)
            row = rows[0] if rows else None
        elif last:
            rows = plan_repo.fetch_recent(limit=1)
            row = rows[0] if rows else None
        if not row:
            raise ToolExecutionError("plan not found", {"plan_id": plan_id})
        return {"plan_id": row[0], "detail": row[11] if len(row) > 11 else None}

    def _log_plan(
        self,
        plan_id: str,
        project: str,
        module: Optional[str],
        status: str,
        route: Optional[str],
        latency_ms: Optional[int],
        source_latencies: Dict[str, Any],
        result_sizes: Dict[str, Any],
        params: Dict[str, Any],
        token_budget: Optional[Dict[str, Any]],
        detail: Dict[str, Any],
    ) -> None:
        entry = PlanLogEntry(
            plan_id=plan_id,
            ts=datetime.now(timezone.utc),
            project=project,
            module=module,
            status=status,
            route=route,
            latency_ms=latency_ms,
            source_latencies=source_latencies,
            result_sizes=result_sizes,
            params=params,
            token_budget=token_budget,
            detail=detail,
        )
        self.plan_logger.log(entry)

    def _job_summary(self, job: JobInfo) -> Dict[str, Any]:
        return {
            "job_id": job.job_id,
            "name": job.name,
            "command": job.command,
            "status": job.status,
            "log_path": str(job.log_path) if job.log_path else None,
            "started_at": job.started_at.astimezone(timezone.utc).isoformat() if job.started_at else None,
            "finished_at": job.finished_at.astimezone(timezone.utc).isoformat() if job.finished_at else None,
            "exit_code": job.exit_code,
            "error": job.error,
        }

    def _on_job_complete(self, job: JobInfo) -> None:
        latency_ms = None
        if job.started_at and job.finished_at:
            latency_ms = int((job.finished_at - job.started_at).total_seconds() * 1000)
        detail = {"job": self._job_summary(job)}
        status = "ok" if job.status == "success" else "down"
        self._log_plan(
            plan_id=job.plan_id,
            project=job.project,
            module=None,
            status=status,
            route=job.name,
            latency_ms=latency_ms,
            source_latencies={},
            result_sizes={},
            params={"job_id": job.job_id},
            token_budget=None,
            detail=detail,
        )

    @staticmethod
    def _token_budget_snapshot(
        codes,
        docs,
        pre_code_count: int,
        pre_doc_count: int,
        budget: int,
    ) -> Dict[str, Any]:
        code_tokens = count_tokens([c.content for c in codes])
        doc_tokens = count_tokens([d.content for d in docs])
        return {
            "budget": budget,
            "code_tokens": code_tokens,
            "doc_tokens": doc_tokens,
            "total_tokens": code_tokens + doc_tokens,
            "code_count": len(codes),
            "doc_count": len(docs),
            "truncated_code": max(0, pre_code_count - len(codes)),
            "truncated_docs": max(0, pre_doc_count - len(docs)),
        }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    server = MCPServer(project_root=root)
    server.run_stdio()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - startup diagnostics
        error_path = _PROJECT_ROOT / "logs" / "mcp-server-error.log"
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text(f"{datetime.now(timezone.utc).isoformat()} {exc}\n", encoding="utf-8")
        raise
