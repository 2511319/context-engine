from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import requests

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            os.environ[key.strip()] = value.strip()
    except Exception:
        pass


_load_env(_PROJECT_ROOT / ".env")

from core.dal import PgClient
from core.dal.repos import IngestRepo
from core.uri import doc_uri, docsection_uri, file_uri, module_uri, slugify, symbol_uri
from tools.doc_links import (
    described_in_edges,
    extract_doc_links,
    extract_doc_mentions,
    extract_module_mentions,
    extract_symbol_mentions,
)


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("context_engine.tools.index_repo")
_GIT_AVAILABLE = True


CODE_EXT = {".py", ".ts", ".tsx"}
DOC_EXT = {".md", ".yaml", ".yml", ".json", ".toml", ".ini", ".proto", ".graphql"}
MAX_DOC_CHARS = 8000
ALLOWED_EDGE_KINDS = {"DEFINED_IN", "USES", "DESCRIBED_IN", "REFERENCES", "SIMILAR_TO", "TESTS"}
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
    except Exception as exc:
        raise RuntimeError(f"git ls-files failed: {exc}") from exc
    if not files:
        raise RuntimeError("git ls-files returned empty set; ensure repository is initialized and tracked")
    return files


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


def _infer_section_slug(content: str, start: int, end: int) -> str:
    first_line = ""
    for line in content.splitlines():
        if line.strip():
            first_line = line.strip()
            break
    first_line = re.sub(r"^#{1,6}\s*", "", first_line)
    return slugify(first_line or f"sec-{start}-{end}")


def _extract_doc_links(project: str, doc_name: str, section_slug: str, content: str) -> Iterator[Tuple[str, str]]:
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for match in link_re.finditer(content):
        target = match.group(1).strip()
        if not target:
            continue
        # strip anchors and query
        if "#" in target:
            url_part, anchor = target.split("#", 1)
        else:
            url_part, anchor = target, ""
        if url_part.startswith("#"):
            sec = url_part[1:] or anchor
            yield "REFERENCES", docsection_uri(project, doc_name, sec)
            continue
        rel_path = url_part
        if rel_path.endswith(".py"):
            yield "REFERENCES", file_uri(project, rel_path)
        elif rel_path.endswith(".md"):
            yield "REFERENCES", doc_uri(project, Path(rel_path).stem)
        elif rel_path:
            # assume code path without extension
            yield "REFERENCES", file_uri(project, rel_path.lstrip("/"))


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

def resolve_module_uri(project: str, module_index: Dict[str, str], name: str) -> str:
    dotted = name.replace("/", ".")
    slash = name.replace(".", "/")
    return module_index.get(slash) or module_index.get(dotted) or module_uri(project, slash)


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


class PySymbolVisitor(ast.NodeVisitor):
    def __init__(self, project: str, module_name: str, module_uri: str, module_index: Dict[str, str]) -> None:
        self.project = project
        self.module_name = module_name
        self.module_uri = module_uri
        self.module_index = module_index
        self.symbols: List[Tuple[str, str, str, str]] = []  # uri, name, module, kind
        self.uses: List[Tuple[str, str]] = []  # from_uri, to_uri
        self.imports: List[Tuple[str, str]] = []  # module_uri -> imported module uri
        self.defs: Dict[str, str] = {}
        self.import_aliases: Dict[str, str] = {}
        self.current_stack: List[str] = []

    def _push(self, name: str, uri: str) -> None:
        self.current_stack.append(uri)
        self.defs[name] = uri

    def _pop(self) -> None:
        if self.current_stack:
            self.current_stack.pop()

    def _current(self) -> Optional[str]:
        return self.current_stack[-1] if self.current_stack else None

    def _register_alias(self, name: str, uri: str) -> None:
        self.import_aliases[name] = uri

    def _full_name(self, name: str) -> str:
        # flatten nested scopes into dotted names
        scopes = [uri.split("#", 1)[1] for uri in self.current_stack] if self.current_stack else []
        scopes.append(name)
        return ".".join(scopes)

    def _resolve_name(self, name: str) -> Optional[str]:
        return self.defs.get(name) or self.import_aliases.get(name)

    def _resolve_attr(self, node: ast.AST) -> Optional[str]:
        # resolve Name or Attribute chains to an alias/definition when possible
        if isinstance(node, ast.Name):
            return self._resolve_name(node.id)
        if isinstance(node, ast.Attribute):
            # try leaf attr first (maybe defined in current scope)
            if (leaf := self._resolve_name(node.attr)) is not None:
                return leaf
            # then try base alias (module alias, imported symbol)
            if isinstance(node.value, ast.Name):
                return self._resolve_name(node.value.id)
        return None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        full = self._full_name(node.name)
        uri = symbol_uri(self.project, self.module_name, full)
        kind = "method" if self.current_stack else "function"
        self.symbols.append((uri, node.name, self.module_name, kind))
        self.defs[node.name] = uri
        self.defs[full] = uri
        self._push(full, uri)
        self.generic_visit(node)
        self._pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        return self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        full = self._full_name(node.name)
        uri = symbol_uri(self.project, self.module_name, full)
        self.symbols.append((uri, node.name, self.module_name, "class"))
        self.defs[node.name] = uri
        self.defs[full] = uri
        self._push(full, uri)
        self.generic_visit(node)
        self._pop()

    def visit_Call(self, node: ast.Call) -> Any:
        current_uri = self._current()
        if current_uri:
            target_uri = self._resolve_attr(node.func)
            if target_uri and target_uri != current_uri:
                self.uses.append((current_uri, target_uri))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            mod_name = alias.name
            uri = resolve_module_uri(self.project, self.module_index, mod_name)
            self.imports.append((self.module_uri, uri))
            alias_name = alias.asname or mod_name.split(".")[0]
            self._register_alias(alias_name, uri)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module is None:
            return
        base_mod = node.module
        if node.level:
            parts = self.module_name.split("/")
            base_prefix = "/".join(parts[:-node.level]) if node.level <= len(parts) else ""
            base_mod = "/".join([p for p in [base_prefix, base_mod.replace(".", "/")] if p])
        mod_path = base_mod.replace(".", "/")
        base_mod_uri = resolve_module_uri(self.project, self.module_index, mod_path)
        for alias in node.names:
            if alias.name == "*":
                # import * — связываем модуль с модулем, алиасом выступает базовое имя
                base_alias = alias.asname or mod_path.split("/")[-1]
                self.imports.append((self.module_uri, base_mod_uri))
                self._register_alias(base_alias, base_mod_uri)
                continue
            sym_uri = symbol_uri(self.project, mod_path, alias.name)
            self.imports.append((self.module_uri, base_mod_uri))
            alias_name = alias.asname or alias.name
            # алиас может ссылаться и на символ, и на модуль — выбираем символ
            self._register_alias(alias_name, sym_uri)
        self.generic_visit(node)



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


def infer_test_target_from_path(rel_path: str) -> Optional[str]:
    """
    For test files like packages/foo/tests/test_bar.py -> packages/foo
    """
    if "/tests/" in rel_path:
        return rel_path.split("/tests/", 1)[0]
    return None


def prune_obsolete(
    cur: "psycopg.Cursor[Any]",
    project: str,
    git_code_paths: set[str],
    git_doc_names: set[str],
) -> None:
    """
    Delete rows for files/docs absent in git ls-files.
    """
    if git_code_paths:
        cur.execute(
            "DELETE FROM symbols WHERE project=%s AND path <> ALL(%s)",
            (project, list(git_code_paths)),
        )
        cur.execute(
            "DELETE FROM code_chunks WHERE project=%s AND path <> ALL(%s)",
            (project, list(git_code_paths)),
        )
        cur.execute(
            "DELETE FROM symbol_refs WHERE project=%s AND from_path <> ALL(%s)",
            (project, list(git_code_paths)),
        )
    if git_doc_names:
        cur.execute(
            "DELETE FROM doc_chunks WHERE project=%s AND doc_name <> ALL(%s)",
            (project, list(git_doc_names)),
        )
    # Recompute allowed URIs after pruning nodes
    allowed: set[str] = set()
    for sql in (
        "SELECT uri FROM symbols WHERE project=%s",
        "SELECT uri FROM code_chunks WHERE project=%s",
        "SELECT uri FROM doc_chunks WHERE project=%s",
    ):
        cur.execute(sql, (project,))
        for (uri,) in cur.fetchall():
            if uri:
                allowed.add(uri)
    if allowed:
        allow_list = list(allowed)
        cur.execute(
            "DELETE FROM dp_edge WHERE project=%s AND ("
            "   (from_uri IS NOT NULL AND from_uri <> ALL(%s))"
            "   OR (to_uri IS NOT NULL AND to_uri <> ALL(%s))"
            ")",
            (project, allow_list, allow_list),
        )
        cur.execute(
            "DELETE FROM dp_datapoint WHERE project=%s AND uri <> ALL(%s)",
            (project, allow_list),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Index repository into Postgres (code/doc chunks)")
    parser.add_argument("--project", required=True)
    parser.add_argument("--since-commit", required=False)
    parser.add_argument(
        "--repo-root",
        required=False,
        help="Path to repository root to index (defaults to context_engine repo)",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune db rows for files/docs absent in git ls-files before indexing",
    )
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    pg_dsn = (os.getenv("PG_DSN") or os.getenv("PG_DSN_RO") or "").strip()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not pg_dsn:
        raise RuntimeError("PG_DSN is not set")
    pg = PgClient(pg_dsn)
    ingest = IngestRepo(pg)

    emb_cfg = EmbeddingConfig()

    files = [p for p in list_project_files(repo) if not blocked(p) and (p.suffix.lower() in CODE_EXT or p.suffix.lower() in DOC_EXT)]
    git_code_paths: set[str] = {p.relative_to(repo).as_posix() for p in files if p.suffix.lower() in CODE_EXT}
    git_doc_names: set[str] = {p.stem for p in files if p.suffix.lower() in DOC_EXT}
    module_index: Dict[str, str] = {}
    symbol_map: Dict[str, str] = {}
    for p in files:
        if p.suffix.lower() in CODE_EXT:
            rel = p.relative_to(repo).as_posix()
            mod_name = infer_module(repo, p) or rel
            mod_uri = module_uri(args.project, mod_name)
            module_index[mod_name] = mod_uri
    try:
        # load existing symbols to resolve text mentions conservatively
        existing_symbols = ingest._fetchall(  # type: ignore[attr-defined]
            "SELECT name, uri FROM symbols WHERE project=%s",
            (args.project,),
        )
        symbol_map = {name: uri for name, uri in existing_symbols if name and uri}
    except Exception:
        symbol_map = {}

    indexed_code = 0
    indexed_docs = 0
    embed_code_time = 0.0
    embed_doc_time = 0.0
    embed_code_fail = 0
    embed_doc_fail = 0
    start_ts = time.perf_counter()

    with ingest.cursor() as cur:
        if args.prune:
            logger.info("prune: removing rows not in git ls-files (code=%d, docs=%d)", len(git_code_paths), len(git_doc_names))
            prune_obsolete(cur, args.project, git_code_paths, git_doc_names)
        ingest.cleanup_edges(args.project, ALLOWED_EDGE_KINDS, cur=cur)
        total = len(files)
        for idx, f in enumerate(files, start=1):
            try:
                raw = f.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                logger.warning("skip unreadable %s: %s", f, exc)
                continue
            safe = sanitize(raw)
            commit_sha = file_commit_sha(repo, f)
            rel_path = f.relative_to(repo).as_posix()
            is_py = f.suffix.lower() == ".py"
            is_py = f.suffix.lower() == ".py"
            if f.suffix.lower() in CODE_EXT:
                file_uri_str = file_uri(args.project, rel_path)
                module_name = infer_module(repo, f) or rel_path
                test_target = infer_test_target_from_path(rel_path)
                ingest.insert_datapoint(
                    project=args.project,
                    kind="code_file",
                    uri=file_uri_str,
                    module=module_name,
                    commit_sha=commit_sha,
                    fp_sha256=sha256_hex(safe),
                    cur=cur,
                )
            else:
                doc_name = f.stem
                doc_uri_str = doc_uri(args.project, doc_name)
                ingest.insert_datapoint(
                    project=args.project,
                    kind="doc_file",
                    uri=doc_uri_str,
                    module=None,
                    commit_sha=commit_sha,
                    fp_sha256=sha256_hex(safe),
                    cur=cur,
                )
                file_uri_str = doc_uri_str
            if f.suffix.lower() in CODE_EXT:
                chunks: List[Chunk] = [Chunk(f, s, e, c) for s, e, c in chunk_code_by_lines(safe, 120)]
                if not chunks:
                    continue
                visitor = None
                if is_py:
                    try:
                        tree = ast.parse(safe)
                        visitor = PySymbolVisitor(args.project, module_name, module_uri(args.project, module_name), module_index)
                        visitor.visit(tree)
                    except Exception as exc:
                        # On parse failure clean any stale symbols/edges for this file to avoid orphan leftovers
                        logger.warning("symbol parse failed for %s: %s", f, exc)
                        ingest.delete_symbols_for_path(args.project, rel_path, cur=cur)
                        ingest.delete_edges_for_code(args.project, file_uri_str, f"{symbol_uri(args.project, module_name, '')}%", cur=cur)
                        ingest.delete_symbol_refs_for_path(args.project, rel_path, cur=cur)
                        visitor = None
                if visitor:
                    ingest.delete_symbols_for_path(args.project, rel_path, cur=cur)
                    ingest.delete_edges_for_code(args.project, file_uri_str, f"{symbol_uri(args.project, module_name, '')}%", cur=cur)
                    ingest.delete_symbol_refs_for_path(args.project, rel_path, cur=cur)
                    for sym_uri, name, mod, kind in visitor.symbols:
                        ingest.insert_symbol(args.project, sym_uri, mod, rel_path, kind, name, cur=cur)
                        ingest.insert_edge(args.project, "DEFINED_IN", sym_uri, file_uri_str, sym_uri, file_uri_str, cur=cur)
                    for from_uri, to_uri in visitor.uses:
                        ingest.insert_edge(args.project, "USES", from_uri, to_uri, from_uri, to_uri, cur=cur)
                        ingest.insert_symbol_ref(args.project, rel_path, to_uri, "REFERENCES", from_uri, to_uri, cur=cur)
                        if test_target:
                            # link test file directly to the symbol it exercises
                            ingest.insert_edge(args.project, "TESTS", file_uri_str, to_uri, file_uri_str, to_uri, cur=cur)
                    for frm, to in visitor.imports:
                        ingest.insert_edge(args.project, "USES", frm, to, frm, to, cur=cur)
                # Test coverage edge: file -> target module (if inferred)
                if test_target:
                    target_uri = module_uri(args.project, test_target)
                    ingest.insert_edge(args.project, "TESTS", file_uri_str, target_uri, file_uri_str, target_uri, cur=cur)
                vectors: Optional[List[List[float]]] = None
                try:
                    t0 = time.perf_counter()
                    vectors = embed([c.content for c in chunks], emb_cfg.code_model, emb_cfg.code_dims, api_key)
                    embed_code_time += time.perf_counter() - t0
                except Exception as exc:
                    embed_code_fail += 1
                    logger.error("embedding failed for code: %s", exc)
                for idx, ch in enumerate(chunks):
                    fp = sha256_hex(ch.content)
                    vec = vectors[idx] if vectors and idx < len(vectors) else None
                    chunk_id = f"{args.project}:{rel_path}:{ch.range_tag()}:{fp}"
                    ingest.insert_code_chunk(
                        project=args.project,
                        uri=file_uri_str,
                        path=rel_path,
                        module=module_name,
                        content=ch.content,
                        embedding=vec,
                        commit_sha=commit_sha,
                        chunk_id=chunk_id,
                        fp_sha256=fp,
                        cur=cur,
                    )
                    indexed_code += 1
            else:
                doc_name = f.stem
                sections = list(chunk_docs_by_headings(safe)) or [(1, len(safe.splitlines()), safe)]
                vectors: Optional[List[List[float]]] = None
                try:
                    t0 = time.perf_counter()
                    vectors = embed([c for _, _, c in sections], emb_cfg.doc_model, emb_cfg.doc_dims, api_key)
                    embed_doc_time += time.perf_counter() - t0
                except Exception as exc:
                    embed_doc_fail += 1
                    logger.error("embedding failed for docs: %s", exc)
                for idx, (s, e, content) in enumerate(sections):
                    section_title = _infer_section_slug(content, s, e)
                    section_uri = docsection_uri(args.project, doc_name, section_title)
                    fp = sha256_hex(content)
                    vec = vectors[idx] if vectors and idx < len(vectors) else None
                    ingest.delete_doc_edges_for_section(args.project, section_uri, cur=cur)
                    chunk_id = f"{args.project}:{doc_name}:{section_title}:{fp}"
                    ingest.insert_doc_chunk(
                        project=args.project,
                        uri=section_uri,
                        doc_name=doc_name,
                        section=section_title,
                        kind=normalize_kind(f),
                        content=content,
                        embedding=vec,
                        commit_sha=commit_sha,
                        chunk_id=chunk_id,
                        fp_sha256=fp,
                        cur=cur,
                    )
                    indexed_docs += 1
                    links = list(extract_doc_links(args.project, doc_name, content))
                    links.extend(extract_doc_mentions(args.project, doc_name, content))
                    links.extend(extract_module_mentions(args.project, content, module_index))
                    links.extend(extract_symbol_mentions(content, symbol_map))
                    for edge_kind, to_uri in links:
                        ingest.insert_edge(args.project, edge_kind, section_uri, to_uri, section_uri, to_uri, cur=cur)
                    for edge_kind, from_uri, to_uri in described_in_edges(args.project, section_uri, links):
                        ingest.insert_edge(args.project, edge_kind, from_uri, to_uri, from_uri, to_uri, cur=cur)
            if idx % 100 == 0 or idx == total:
                elapsed = time.perf_counter() - start_ts
                logger.info(
                    "progress files=%d/%d code_chunks=%d doc_chunks=%d embed_code_time=%.1fs embed_doc_time=%.1fs",
                    idx,
                    total,
                    indexed_code,
                    indexed_docs,
                    embed_code_time,
                    embed_doc_time,
                )
        ingest.update_lex(args.project, cur=cur)
        ingest.deduplicate_chunks(args.project, cur=cur)
        ingest.analyze_chunks(cur=cur)

    elapsed = time.perf_counter() - start_ts
    logger.info(
        "Indexed files=%d code_chunks=%d doc_chunks=%d embed_code_time=%.1fs embed_doc_time=%.1fs embed_fail_code=%d embed_fail_doc=%d elapsed=%.1fs",
        len(files),
        indexed_code,
        indexed_docs,
        embed_code_time,
        embed_doc_time,
        embed_code_fail,
        embed_doc_fail,
        elapsed,
    )


if __name__ == "__main__":
    main()
