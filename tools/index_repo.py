from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

import requests

try:
    import psycopg
except Exception as exc:  # pragma: no cover
    psycopg = None  # type: ignore


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("context_engine.tools.index_repo")
_GIT_AVAILABLE = True


CODE_EXT = {".py", ".ts", ".tsx"}
DOC_EXT = {".md", ".yaml", ".yml", ".json", ".toml", ".ini", ".proto", ".graphql"}
MAX_DOC_CHARS = 8000
DENY_GLOBS = [
    "deploy/**",
    "observability/**",
    "qa/**",
    "**/__pycache__/**",
    "**/node_modules/**",
    "**/.venv/**",
    "**/.git/**",
    "_build/**",
    "_data/**",
    "logs/**",
    "build/**",
    "dist/**",
    "neo4j/**",
]
FALLBACK_SKIP_DIRS = {".git", ".hg", ".svn", ".venv", "node_modules", "__pycache__", "_data", "logs", "dist", "build", "neo4j", "_build"}
SECRET_PATTERNS: List[Tuple[str, str]] = [
    (r"\bsk-[A-Za-z0-9]{20,}\b", "[REDACTED:OPENAI_KEY]"),
    (r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED:AWS_ACCESS_KEY]"),
    (r"(?i)\baws(.{0,20})secret(.{0,3})[:=]\s*([A-Za-z0-9/+=]{40})", "[REDACTED:AWS_SECRET]"),
    (r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[REDACTED:JWT]"),
    (r"-----BEGIN (RSA )?PRIVATE KEY-----[\s\S]+?-----END (RSA )?PRIVATE KEY-----", "[REDACTED:PRIVATE_KEY]"),
]


@dataclass
class EmbeddingConfig:
    code_model: str = "text-embedding-3-large"
    code_dims: int = 1024
    doc_model: str = "text-embedding-3-small"
    doc_dims: int = 1024


@dataclass
class Chunk:
    path: Path
    start_line: int
    end_line: int
    content: str

    def range_tag(self) -> str:
        return f"{self.start_line}-{self.end_line}"


def run_git(args: Sequence[str], cwd: Path) -> str:
    global _GIT_AVAILABLE
    if not _GIT_AVAILABLE:
        raise RuntimeError("git unavailable in this workspace")
    out = subprocess.check_output(["git", *args], cwd=str(cwd))
    return out.decode("utf-8", errors="ignore").strip()


def list_git_files(cwd: Path) -> List[Path]:
    out = run_git(["ls-files"], cwd)
    files = [cwd / p for p in out.splitlines() if p]
    return files


def list_project_files(cwd: Path) -> List[Path]:
    try:
        files = list_git_files(cwd)
        if files:
            return files
    except Exception as exc:
        global _GIT_AVAILABLE
        _GIT_AVAILABLE = False
        logger.warning("git ls-files failed, falling back to os.walk scan: %s", exc)

    collected: List[Path] = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in FALLBACK_SKIP_DIRS]
        for name in files:
            collected.append(Path(root) / name)
    return collected


def blocked(path: Path) -> bool:
    from fnmatch import fnmatch

    p = str(path).replace("\\", "/")
    for pat in DENY_GLOBS:
        if fnmatch(p, pat):
            return True
    return False


def sanitize(text: str) -> str:
    try:
        s = text
        for pat, repl in SECRET_PATTERNS:
            s = re.sub(pat, repl, s, flags=re.MULTILINE)
        return s
    except Exception as exc:  # pragma: no cover
        logger.exception("sanitize failed: %s", exc)
        return text


def chunk_code_by_lines(text: str, block: int = 120) -> Iterator[Tuple[int, int, str]]:
    lines = text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        j = min(n, i + block)
        yield i + 1, j, "\n".join(lines[i:j])
        i = j


def chunk_docs_by_headings(text: str) -> Iterator[Tuple[int, int, str]]:
    # split on #, ##, ### heading lines while preserving ranges
    lines = text.splitlines()
    starts = [0]
    for idx, line in enumerate(lines):
        if re.match(r"^#{1,3}\\s+", line):
            if idx not in starts:
                starts.append(idx)
    if starts[-1] != len(lines):
        starts.append(len(lines))
    for a, b in zip(starts, starts[1:]):
        if a == b:
            continue
        section_lines = lines[a:b]
        yield from _chunk_section_with_limit(section_lines, a + 1)


def _chunk_section_with_limit(section_lines: List[str], start_line: int) -> Iterator[Tuple[int, int, str]]:
    if not section_lines:
        return
    buffer: List[str] = []
    current_start = start_line
    current_length = 0
    for offset, line in enumerate(section_lines):
        addition = (1 if buffer else 0) + len(line)
        if buffer and current_length + addition > MAX_DOC_CHARS:
            end_line = current_start + len(buffer) - 1
            yield current_start, end_line, "\n".join(buffer)
            buffer = [line]
            current_start = start_line + offset
            current_length = len(line)
        else:
            buffer.append(line)
            current_length += addition
    if buffer:
        end_line = current_start + len(buffer) - 1
        yield current_start, end_line, "\n".join(buffer)


def file_commit_sha(cwd: Path, file: Path) -> str:
    if not _GIT_AVAILABLE:
        return ""
    try:
        out = run_git(["log", "-n", "1", "--pretty=format:%H", "--", str(file.relative_to(cwd))], cwd)
        return out or ""
    except Exception:
        return ""


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def embed(texts: List[str], model: str, dims: int, api_key: Optional[str]) -> List[List[float]]:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "input": texts, "dimensions": dims}
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    resp.raise_for_status()
    data = resp.json()
    vectors = [item["embedding"] for item in data["data"]]
    return vectors


def upsert_code_chunk(cur: "psycopg.Cursor[Any]", project: str, path: Path, module: Optional[str], content: str, commit_sha: str, start: int, end: int, fp: str, emb: Optional[List[float]]) -> None:
    cur.execute(
        """
        INSERT INTO code_chunks(project, path, module, content, embedding, lex, commit_sha, chunk_id, fp_sha256)
        VALUES (%s,%s,%s,%s,%s,NULL,%s,%s,%s)
        """,
        (
            project,
            str(path).replace("\\", "/"),
            module,
            content,
            emb,
            commit_sha,
            f"{project}:{str(path).replace('\\','/')}:" + f"{start}-{end}:{fp}",
            fp,
        ),
    )


def upsert_doc_chunk(cur: "psycopg.Cursor[Any]", project: str, doc_name: str, section: str, kind: str, content: str, commit_sha: str, fp: str, emb: Optional[List[float]]) -> None:
    cur.execute(
        """
        INSERT INTO doc_chunks(project, doc_name, section, kind, content, embedding, lex, commit_sha, chunk_id, fp_sha256)
        VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s)
        """,
        (
            project,
            doc_name,
            section,
            kind,
            content,
            emb,
            commit_sha,
            f"{project}:{doc_name}:{section}:{fp}",
            fp,
        ),
    )


def normalize_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".proto", ".graphql"}:
        return "contract"
    if ext == ".md":
        return "doc"
    if ext in {".yaml", ".yml", ".json", ".toml", ".ini"}:
        return "config"
    return "doc"


def infer_module(repo_root: Path, path: Path) -> Optional[str]:
    # simple heuristic: take first two segments if under services/apps/packages
    rel = path.relative_to(repo_root).as_posix()
    for prefix in ("services/", "apps/", "packages/"):
        if rel.startswith(prefix):
            parts = rel.split("/")
            if len(parts) >= 2:
                return "/".join(parts[:2])
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Index repository into Postgres (code/doc chunks)")
    parser.add_argument("--project", required=True)
    parser.add_argument("--since-commit", required=False)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    pg_dsn = os.getenv("PG_DSN")
    api_key = os.getenv("OPENAI_API_KEY")
    if psycopg is None:
        raise RuntimeError("psycopg (psycopg3) is required")
    if not pg_dsn:
        raise RuntimeError("PG_DSN is not set")

    emb_cfg = EmbeddingConfig()

    files = [p for p in list_project_files(repo) if not blocked(p) and (p.suffix.lower() in CODE_EXT or p.suffix.lower() in DOC_EXT)]

    indexed_code = 0
    indexed_docs = 0

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("SET client_encoding TO 'UTF8'")
        with conn.cursor() as cur:
            for f in files:
                try:
                    raw = f.read_text(encoding="utf-8", errors="ignore")
                except Exception as exc:
                    logger.warning("skip unreadable %s: %s", f, exc)
                    continue
                safe = sanitize(raw)
                commit_sha = file_commit_sha(repo, f)
                if f.suffix.lower() in CODE_EXT:
                    # chunk by 120 lines (AST specialization может быть добавлена позже)
                    chunks: List[Chunk] = [
                        Chunk(f, s, e, c) for s, e, c in chunk_code_by_lines(safe, 120)
                    ]
                    if not chunks:
                        continue
                    vectors: Optional[List[List[float]]] = None
                    try:
                        vectors = embed([c.content for c in chunks], emb_cfg.code_model, emb_cfg.code_dims, api_key)
                    except Exception as exc:
                        logger.error("embedding failed for code: %s", exc)
                    for idx, ch in enumerate(chunks):
                        fp = sha256_hex(ch.content)
                        vec = vectors[idx] if vectors and idx < len(vectors) else None
                        upsert_code_chunk(cur, args.project, f, infer_module(repo, f), ch.content, commit_sha, ch.start_line, ch.end_line, fp, vec)
                        indexed_code += 1
                else:
                    # docs
                    doc_name = f.name
                    sections = list(chunk_docs_by_headings(safe)) or [(1, len(safe.splitlines()), safe)]
                    vectors: Optional[List[List[float]]] = None
                    try:
                        vectors = embed([c for _, _, c in sections], emb_cfg.doc_model, emb_cfg.doc_dims, api_key)
                    except Exception as exc:
                        logger.error("embedding failed for docs: %s", exc)
                    for idx, (s, e, content) in enumerate(sections):
                        section_title = f"sec-{s}-{e}"
                        fp = sha256_hex(content)
                        vec = vectors[idx] if vectors and idx < len(vectors) else None
                        upsert_doc_chunk(cur, args.project, doc_name, section_title, normalize_kind(f), content, commit_sha, fp, vec)
                        indexed_docs += 1
            # ANALYZE to refresh planner stats
            try:
                cur.execute("ANALYZE code_chunks; ANALYZE doc_chunks;")
            except Exception as exc:
                logger.warning("ANALYZE failed: %s", exc)

    logger.info("Indexed code=%d, docs=%d", indexed_code, indexed_docs)


if __name__ == "__main__":
    main()
