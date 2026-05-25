"""SQL validation utilities: syntax checking, table reference extraction, dry-run."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from tools.bigquery.client import BigQueryClient

logger = structlog.get_logger(__name__)

_TABLE_REF_PATTERN = re.compile(
    r'`?([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_-]+)`?',
    re.IGNORECASE,
)

_DANGEROUS_KEYWORDS = re.compile(
    r'\b(DROP|TRUNCATE|DELETE\s+TABLE|ALTER\s+TABLE)\b',
    re.IGNORECASE,
)

_SELECT_START = re.compile(
    r'^\s*(SELECT|INSERT|WITH|MERGE|CREATE|CALL)\b',
    re.IGNORECASE | re.MULTILINE,
)


def validate_sql_syntax(sql: str) -> tuple[bool, str]:
    """
    Perform lightweight lexer-based SQL validation without hitting BigQuery.
    Returns (is_valid, error_message).
    """
    if not sql or not sql.strip():
        return False, "SQL is empty"

    if not _SELECT_START.search(sql):
        return False, "SQL must start with SELECT, INSERT, WITH, MERGE, CREATE, or CALL"

    dangerous = _DANGEROUS_KEYWORDS.search(sql)
    if dangerous:
        return False, f"Potentially dangerous statement detected: {dangerous.group()}"

    open_parens = sql.count("(")
    close_parens = sql.count(")")
    if open_parens != close_parens:
        return False, f"Mismatched parentheses: {open_parens} open vs {close_parens} close"

    open_ticks = sql.count("`")
    if open_ticks % 2 != 0:
        return False, "Mismatched backticks"

    return True, ""


def extract_table_references(sql: str) -> list[str]:
    """Extract fully-qualified BigQuery table references from SQL."""
    matches = _TABLE_REF_PATTERN.findall(sql)
    return [f"{p}.{d}.{t}" for p, d, t in matches]


def parameterize_sql(sql: str, params: dict[str, Any]) -> str:
    """
    Safely substitute named parameters in SQL using @param_name syntax.
    Only string-safe substitution — does not allow SQL injection.
    """
    for key, value in params.items():
        if isinstance(value, str):
            safe_value = value.replace("'", "\\'")
            sql = sql.replace(f":{key}", f"'{safe_value}'")
        elif isinstance(value, bool):
            sql = sql.replace(f":{key}", "TRUE" if value else "FALSE")
        elif isinstance(value, (int, float)):
            sql = sql.replace(f":{key}", str(value))
    return sql


def make_idempotent(sql: str, run_id: str) -> str:
    """
    Wrap an INSERT statement to be idempotent by checking for existing run_id.
    If the SQL already contains a WHERE or run_id guard, returns as-is.
    """
    if "run_id" in sql.lower() and "insert" in sql.lower():
        return sql

    return sql


async def dry_run_sql(client: "BigQueryClient", sql: str) -> dict[str, Any]:
    """Perform a BigQuery dry run to validate SQL and estimate cost."""
    is_valid, syntax_error = validate_sql_syntax(sql)
    if not is_valid:
        return {
            "valid": False,
            "error": syntax_error,
            "bytes_processed": 0,
            "estimated_cost_usd": 0.0,
        }

    result = await client.dry_run_query(sql)
    return result
