"""Database schema explorer."""

from __future__ import annotations

from typing import Dict, List

from ..adapters import postgres


def list_tables() -> List[str]:
    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
        ORDER BY table_name
    """
    tables: List[str] = []
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            tables = [row[0] for row in cur.fetchall()]
    return tables


def describe_table(table_name: str) -> Dict[str, List[Dict[str, str]]]:
    columns_sql = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
    """
    indexes_sql = """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname='public' AND tablename=%s
        ORDER BY indexname
    """
    result = {"columns": [], "indexes": []}
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(columns_sql, (table_name,))
            result["columns"] = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2],
                    "default": row[3],
                }
                for row in cur.fetchall()
            ]
            cur.execute(indexes_sql, (table_name,))
            result["indexes"] = [{"name": row[0], "definition": row[1]} for row in cur.fetchall()]
    return result
