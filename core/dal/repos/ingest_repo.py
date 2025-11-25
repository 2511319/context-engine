from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from ..postgres import PgClient


class IngestRepo:
    """DAL операции для ingest/graphify: dp_datapoint, chunks, symbols, edges."""

    def __init__(self, pg: PgClient) -> None:
        self.pg = pg

    @contextmanager
    def cursor(self):
        with self.pg.connect() as conn:
            with conn.cursor() as cur:
                yield cur

    # ---------------------------- write helpers ----------------------------
    def cleanup_edges(self, project: str, allowed_edge_kinds: Iterable[str], cur=None) -> None:  # type: ignore[no-untyped-def]
        sql = """
            DELETE FROM dp_edge
            WHERE project=%s
              AND (
                  edge_kind IS NULL
                  OR from_uri IS NULL
                  OR to_uri IS NULL
                  OR NOT (edge_kind = ANY(%s))
              )
        """
        self._execute(sql, (project, list(allowed_edge_kinds)), cur)

    def insert_datapoint(
        self,
        project: str,
        kind: str,
        uri: str,
        module: Optional[str],
        commit_sha: str,
        fp_sha256: str,
        cur=None,  # type: ignore[no-untyped-def]
    ) -> None:
        sql = """
            INSERT INTO dp_datapoint(project, kind, uri, module, commit_sha, fp_sha256)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (project, uri, fp_sha256) DO NOTHING
        """
        self._execute(sql, (project, kind, uri, module, commit_sha, fp_sha256), cur)

    def delete_symbols_for_path(self, project: str, path: str, cur=None) -> None:  # type: ignore[no-untyped-def]
        self._execute("DELETE FROM symbols WHERE project=%s AND path=%s", (project, path), cur)

    def delete_symbol_refs_for_path(self, project: str, path: str, cur=None) -> None:  # type: ignore[no-untyped-def]
        self._execute("DELETE FROM symbol_refs WHERE project=%s AND from_path=%s", (project, path), cur)

    def delete_edges_for_code(self, project: str, file_uri: str, module_uri_prefix: str, cur=None) -> None:  # type: ignore[no-untyped-def]
        sql = """
            DELETE FROM dp_edge
            WHERE project=%s
              AND edge_kind IN ('DEFINED_IN','USES')
              AND (to_uri=%s OR from_uri LIKE %s)
        """
        self._execute(sql, (project, file_uri, module_uri_prefix), cur)

    def delete_doc_edges_for_section(self, project: str, section_uri: str, cur=None) -> None:  # type: ignore[no-untyped-def]
        sql = """
            DELETE FROM dp_edge WHERE project=%s AND edge_kind IN ('DESCRIBED_IN','REFERENCES') AND from_uri=%s
        """
        self._execute(sql, (project, section_uri), cur)

    def delete_edges_by_kind(self, project: str, kinds: Iterable[str], cur=None) -> None:  # type: ignore[no-untyped-def]
        sql = """
            DELETE FROM dp_edge
            WHERE project=%s AND edge_kind = ANY(%s)
        """
        self._execute(sql, (project, list(kinds)), cur)

    def insert_symbol(
        self,
        project: str,
        uri: str,
        module: str,
        path: str,
        kind: str,
        name: str,
        cur=None,  # type: ignore[no-untyped-def]
    ) -> None:
        sql = """
            INSERT INTO symbols(project, uri, module, path, kind, name)
            VALUES (%s,%s,%s,%s,%s,%s)
        """
        self._execute(sql, (project, uri, module, path, kind, name), cur)

    def insert_edge(
        self,
        project: str,
        edge_kind: str,
        from_uri: str,
        to_uri: str,
        src_uri: Optional[str],
        dst_uri: Optional[str],
        cur=None,  # type: ignore[no-untyped-def]
    ) -> None:
        sql = """
            INSERT INTO dp_edge(project, edge_kind, from_uri, to_uri, src_uri, dst_uri, rel)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """
        self._execute(sql, (project, edge_kind, from_uri, to_uri, src_uri, dst_uri, edge_kind), cur)

    def insert_symbol_ref(
        self,
        project: str,
        from_path: str,
        to_symbol: str,
        rel: str,
        from_uri: str,
        to_uri: str,
        cur=None,  # type: ignore[no-untyped-def]
    ) -> None:
        sql = """
            INSERT INTO symbol_refs(project, from_path, to_symbol, rel, from_uri, to_uri)
            VALUES (%s,%s,%s,%s,%s,%s)
        """
        self._execute(sql, (project, from_path, to_symbol, rel, from_uri, to_uri), cur)

    def insert_code_chunk(
        self,
        project: str,
        uri: str,
        path: str,
        module: Optional[str],
        content: str,
        embedding: Optional[List[float]],
        commit_sha: str,
        chunk_id: str,
        fp_sha256: str,
        cur=None,  # type: ignore[no-untyped-def]
    ) -> None:
        sql = """
            INSERT INTO code_chunks(project, uri, path, module, content, embedding, lex, commit_sha, chunk_id, fp_sha256)
            VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s)
        """
        self._execute(
            sql,
            (project, uri, path, module, content, embedding, commit_sha, chunk_id, fp_sha256),
            cur,
        )

    def insert_doc_chunk(
        self,
        project: str,
        uri: str,
        doc_name: str,
        section: str,
        kind: str,
        content: str,
        embedding: Optional[List[float]],
        commit_sha: str,
        chunk_id: str,
        fp_sha256: str,
        cur=None,  # type: ignore[no-untyped-def]
    ) -> None:
        sql = """
            INSERT INTO doc_chunks(project, uri, doc_name, section, kind, content, embedding, lex, commit_sha, chunk_id, fp_sha256)
            VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s)
        """
        self._execute(
            sql,
            (project, uri, doc_name, section, kind, content, embedding, commit_sha, chunk_id, fp_sha256),
            cur,
        )

    def update_lex(self, project: str, cur=None) -> None:  # type: ignore[no-untyped-def]
        sql_code = "UPDATE code_chunks SET lex = to_tsvector('simple', content) WHERE project=%s AND lex IS NULL;"
        sql_docs = "UPDATE doc_chunks SET lex = to_tsvector('simple', content) WHERE project=%s AND lex IS NULL;"
        self._execute(sql_code, (project,), cur)
        self._execute(sql_docs, (project,), cur)

    def deduplicate_chunks(self, project: str, cur=None) -> None:  # type: ignore[no-untyped-def]
        sql_code = """
            DELETE FROM code_chunks a USING code_chunks b
            WHERE a.id < b.id
              AND a.project = %s
              AND a.project = b.project
              AND a.fp_sha256 = b.fp_sha256;
        """
        sql_docs = """
            DELETE FROM doc_chunks a USING doc_chunks b
            WHERE a.id < b.id
              AND a.project = %s
              AND a.project = b.project
              AND a.fp_sha256 = b.fp_sha256;
        """
        self._execute(sql_code, (project,), cur)
        self._execute(sql_docs, (project,), cur)

    def analyze_chunks(self, cur=None) -> None:  # type: ignore[no-untyped-def]
        try:
            self._execute("ANALYZE code_chunks; ANALYZE doc_chunks;", (), cur)
        except Exception:
            # DIAG only: ошибки ANALYZE не критичны для ingest
            pass

    # ---------------------------- read helpers -----------------------------
    def fetch_code_nodes(self, project: str) -> List[Sequence[Any]]:
        sql = "SELECT uri, path, module FROM code_chunks WHERE project=%s"
        return self._fetchall(sql, (project,))

    def fetch_doc_nodes(self, project: str) -> List[Sequence[Any]]:
        sql = "SELECT uri, doc_name, section FROM doc_chunks WHERE project=%s"
        return self._fetchall(sql, (project,))

    def fetch_symbols(self, project: str) -> List[Sequence[Any]]:
        sql = "SELECT uri, name, module, path, kind FROM symbols WHERE project=%s"
        return self._fetchall(sql, (project,))

    def fetch_edges(self, project: str) -> List[Sequence[Any]]:
        sql = """
            SELECT COALESCE(edge_kind, rel) AS kind,
                   COALESCE(from_uri, src_uri) AS src,
                   COALESCE(to_uri, dst_uri) AS dst
            FROM dp_edge
            WHERE project=%s
        """
        return self._fetchall(sql, (project,))

    # ----------------------------- internals ------------------------------
    def _execute(self, sql: str, params: Iterable[Any] | Tuple[Any, ...], cur=None) -> None:  # type: ignore[no-untyped-def]
        if cur is not None:
            cur.execute(sql, tuple(params))
            return
        with self.cursor() as local_cur:
            local_cur.execute(sql, tuple(params))

    def _fetchall(self, sql: str, params: Iterable[Any] | Tuple[Any, ...]) -> List[Sequence[Any]]:
        with self.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()
