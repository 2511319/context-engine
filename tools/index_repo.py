from __future__ import annotations

import argparse
import ast
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

from core.dal import PgClient
from core.dal.repos import IngestRepo
from core.uri import doc_uri, docsection_uri, file_uri, slugify, symbol_uri
from tools.doc_links import described_in_edges, extract_doc_links, extract_doc_mentions


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("context_engine.tools.index_repo")
_GIT_AVAILABLE = True


CODE_EXT = {".py", ".ts", ".tsx"}
DOC_EXT = {".md", ".yaml", ".yml", ".json", ".toml", ".ini", ".proto", ".graphql"}
MAX_DOC_CHARS = 8000
ALLOWED_EDGE_KINDS = {"DEFINED_IN", "USES", "DESCRIBED_IN", "REFERENCES"}
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

def _full_name(self, name: str) -> str:
        # flatten nested scopes into dotted names
        scopes = [uri.split("#", 1)[1] for uri in self.current_stack] if self.current_stack else []
        scopes.append(name)
        return ".".join(scopes)

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
            target_uri = None
            if isinstance(node.func, ast.Name):
                target_uri = self.defs.get(node.func.id)
                if target_uri is None:
                    target_uri = self.import_aliases.get(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                target_uri = self.defs.get(node.func.attr)
                if target_uri is None and isinstance(node.func.value, ast.Name):
                    mod_alias = node.func.value.id
                    target_uri = self.import_aliases.get(mod_alias)
            if target_uri and target_uri != current_uri:
                self.uses.append((current_uri, target_uri))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            mod_name = alias.name
            uri = resolve_module_uri(self.project, self.module_index, mod_name)
            self.imports.append((self.module_uri, uri))
            alias_name = alias.asname or mod_name.split(".")[0]
            self.import_aliases[alias_name] = uri
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module is None:
            return
        base_mod = node.module
        if node.level:
            parts = self.module_name.split("/")
            base_prefix = "/".join(parts[:-node.level]) if node.level <= len(parts) else ""
            base_mod = "/".join([p for p in [base_prefix, base_mod.replace(".", "/")] if p])
        for alias in node.names:
            if alias.name == "*":
                continue
            mod_path = base_mod.replace(".", "/")
            sym_uri = symbol_uri(self.project, mod_path, alias.name)
            mod_uri_val = resolve_module_uri(self.project, self.module_index, mod_path)
            self.imports.append((self.module_uri, mod_uri_val))
            alias_name = alias.asname or alias.name
            self.import_aliases[alias_name] = sym_uri
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Index repository into Postgres (code/doc chunks)")
    parser.add_argument("--project", required=True)
    parser.add_argument("--since-commit", required=False)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    pg_dsn = os.getenv("PG_DSN")
    api_key = os.getenv("OPENAI_API_KEY")
    if not pg_dsn:
        raise RuntimeError("PG_DSN is not set")
    pg = PgClient(pg_dsn)
    ingest = IngestRepo(pg)

    emb_cfg = EmbeddingConfig()

    files = [p for p in list_project_files(repo) if not blocked(p) and (p.suffix.lower() in CODE_EXT or p.suffix.lower() in DOC_EXT)]
    module_index: Dict[str, str] = {}
    for p in files:
        if p.suffix.lower() in CODE_EXT:
            rel = p.relative_to(repo).as_posix()
            mod_name = infer_module(repo, p) or rel
            mod_uri = module_uri(args.project, mod_name)
            module_index[mod_name] = mod_uri

    indexed_code = 0
    indexed_docs = 0

    with ingest.cursor() as cur:
        ingest.cleanup_edges(args.project, ALLOWED_EDGE_KINDS, cur=cur)
        for f in files:
            try:
                raw = f.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                logger.warning("skip unreadable %s: %s", f, exc)
                continue
            safe = sanitize(raw)
            commit_sha = file_commit_sha(repo, f)
            rel_path = f.relative_to(repo).as_posix()
            if f.suffix.lower() in CODE_EXT:
                file_uri_str = file_uri(args.project, rel_path)
                module_name = infer_module(repo, f) or rel_path
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
                try:
                    tree = ast.parse(safe)
                    visitor = PySymbolVisitor(args.project, module_name, module_uri(args.project, module_name), module_index)
                    visitor.visit(tree)
                except Exception as exc:
                    logger.warning("symbol parse failed for %s: %s", f, exc)
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
                    for frm, to in visitor.imports:
                        ingest.insert_edge(args.project, "USES", frm, to, frm, to, cur=cur)
                vectors: Optional[List[List[float]]] = None
                try:
                    vectors = embed([c.content for c in chunks], emb_cfg.code_model, emb_cfg.code_dims, api_key)
                except Exception as exc:
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
                    vectors = embed([c for _, _, c in sections], emb_cfg.doc_model, emb_cfg.doc_dims, api_key)
                except Exception as exc:
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
                    for edge_kind, to_uri in links:
                        ingest.insert_edge(args.project, edge_kind, section_uri, to_uri, section_uri, to_uri, cur=cur)
                    for edge_kind, from_uri, to_uri in described_in_edges(args.project, section_uri, links):
                        ingest.insert_edge(args.project, edge_kind, from_uri, to_uri, from_uri, to_uri, cur=cur)
        ingest.update_lex(args.project, cur=cur)
        ingest.deduplicate_chunks(args.project, cur=cur)
        ingest.analyze_chunks(cur=cur)

    logger.info("Indexed code=%d, docs=%d", indexed_code, indexed_docs)


if __name__ == "__main__":
    main()
