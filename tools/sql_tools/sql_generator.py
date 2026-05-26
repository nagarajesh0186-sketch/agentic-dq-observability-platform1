"""Programmatic BigQuery SQL generator for DQ rules.

Replaces the previous Jinja2 sql_templates/ approach. Each DQRule is rendered
to a single SELECT block that returns one row matching the dq_results schema
(see schemas.bq_schemas.DQ_RESULTS_SCHEMA). Rules are concatenated with
UNION ALL, and the whole block is wrapped in a single INSERT inside a
CREATE OR REPLACE PROCEDURE.

Why this design
---------------
* One uniform output row per rule — no per-rule-type INSERT variations.
* One INSERT for the whole run — fewer DML statements, atomic execution.
* The procedure takes a single STRING parameter `p_run_id` — no @-parameter
  / p_-parameter substitution gymnastics between standalone and SP modes.
* Adding a new rule type means adding one method that returns a SELECT block;
  no Jinja template, no per-rule INSERT plumbing.

dq_results columns produced (in this exact order):
  run_id, rule_id, project_id, dataset_name, table_name, column_name,
  rule_type, severity, status, observed_value, expected_value,
  threshold_value, failure_count, execution_time,
  execution_duration_seconds, query_executed, error_message, created_at
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from schemas.models import DQRule, RuleCategory, Severity


# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

# Fixed column ordering — must match schemas.bq_schemas.DQ_RESULTS_SCHEMA.
_RESULT_COLUMNS = (
    "run_id",
    "rule_id",
    "project_id",
    "dataset_name",
    "table_name",
    "column_name",
    "rule_type",
    "severity",
    "status",
    "observed_value",
    "expected_value",
    "threshold_value",
    "failure_count",
    "execution_time",
    "execution_duration_seconds",
    "query_executed",
    "error_message",
    "created_at",
)

_RESULT_COLUMNS_SQL = ",\n  ".join(_RESULT_COLUMNS)

# Reference for the run_id in standalone (named-parameter) vs SP (param) mode.
_STANDALONE_RUN_ID = "@run_id"
_SP_RUN_ID = "p_run_id"

# Severity-driven default status semantics:
#   INFO  → never marked FAIL (use 'PASS' regardless of observed value)
#   WARN  → marked FAIL only if observed exceeds threshold strictly
#   FAIL  → marked FAIL on any threshold breach
# All checks here use the same threshold-comparison logic — the severity is
# stamped onto the row so downstream consumers can filter / aggregate.


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _sql_str(value: Any) -> str:
    """Render a Python value as a BigQuery STRING literal (or NULL)."""
    if value is None:
        return "NULL"
    s = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+\-]\d{2}:?\d{2})?$")


def _sql_literal(value: Any) -> str:
    """Render a Python value as a typed BigQuery literal.

    - None → NULL
    - bool → TRUE / FALSE
    - int/float → as-is
    - 'YYYY-MM-DD' string → DATE 'YYYY-MM-DD'
    - 'YYYY-MM-DD HH:MM:SS[.fff][Z|±HH:MM]' string → TIMESTAMP '...'
    - anything else → escaped STRING literal

    Use this anywhere a parameter value lands directly inside an expression
    (range bounds, equality checks). _sql_str remains for cases where the
    value is always a string label.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        if _DATE_RE.match(value):
            return f"DATE '{value}'"
        if _TIMESTAMP_RE.match(value):
            return f"TIMESTAMP '{value}'"
        return _sql_str(value)
    return _sql_str(str(value))


def _quote_ident(name: str) -> str:
    """Backtick-quote a BigQuery identifier."""
    return f"`{name}`"


def _table_ref(project: str, dataset: str, table: str) -> str:
    return f"`{project}.{dataset}.{table}`"


def _query_hash(*parts: str) -> str:
    return hashlib.sha256("::".join(parts).encode()).hexdigest()[:16]


# ----------------------------------------------------------------------------
# Rendered-SQL container
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderedRule:
    """A single rule rendered as a SELECT block ready for UNION ALL."""
    rule_id: str
    rule_name: str
    rule_category: str
    select_sql: str
    query_hash: str

    def as_standalone_insert(self, dq_project: str, dq_dataset: str) -> str:
        """Wrap this single SELECT in its own INSERT — used for inspection."""
        return (
            f"-- DQ Rule: {self.rule_name}\n"
            f"-- Rule ID: {self.rule_id}\n"
            f"-- Category: {self.rule_category}\n"
            f"INSERT INTO `{dq_project}.{dq_dataset}.dq_results` (\n"
            f"  {_RESULT_COLUMNS_SQL}\n"
            f")\n"
            f"{self.select_sql};"
        )


# ----------------------------------------------------------------------------
# The generator
# ----------------------------------------------------------------------------


class DQSQLGenerator:
    """Build per-rule SELECTs and consolidated stored procedures.

    Usage::

        gen = DQSQLGenerator(dq_project="my-proj", dq_dataset="dq_observability")
        rendered = [gen.render_rule(rule, run_id_ref="p_run_id") for rule in rules]
        ddl = gen.build_procedure(session_id, rendered)
    """

    def __init__(self, dq_project: str, dq_dataset: str) -> None:
        self._dq_project = dq_project
        self._dq_dataset = dq_dataset

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_rule(
        self,
        rule: DQRule,
        run_id_ref: str = _STANDALONE_RUN_ID,
    ) -> Optional[RenderedRule]:
        """Render one DQRule to a SELECT block. Returns None if unsupported."""
        # LLM-generated custom rules store a SELECT block with {{run_id_ref}} and
        # {{rule_id}} placeholders that we substitute here. The placeholder check
        # guards against pre-existing manually-pasted INSERT SQL which has no placeholders.
        if rule.rule_id.startswith("CUST_") and rule.generated_sql and "{{run_id_ref}}" in rule.generated_sql:
            select_sql = rule.generated_sql
            select_sql = select_sql.replace("{{run_id_ref}}", run_id_ref)
            select_sql = select_sql.replace("{{rule_id}}", _sql_str(rule.rule_id))
            return RenderedRule(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                rule_category=rule.rule_category.value,
                select_sql=select_sql,
                query_hash=_query_hash(rule.rule_category.value, rule.rule_id),
            )

        cat = rule.rule_category
        params = rule.parameters or {}

        try:
            if cat == RuleCategory.COMPLETENESS:
                select_sql = self._render_completeness(rule, params, run_id_ref)
            elif cat == RuleCategory.UNIQUENESS:
                select_sql = self._render_uniqueness(rule, params, run_id_ref)
            elif cat == RuleCategory.VALIDITY:
                select_sql = self._render_validity(rule, params, run_id_ref)
            elif cat == RuleCategory.FRESHNESS:
                select_sql = self._render_freshness(rule, params, run_id_ref)
            elif cat == RuleCategory.VOLUME:
                select_sql = self._render_volume(rule, params, run_id_ref)
            elif cat == RuleCategory.INTEGRITY:
                select_sql = self._render_integrity(rule, params, run_id_ref)
            elif cat == RuleCategory.SCHEMA_DRIFT:
                select_sql = self._render_schema_drift(rule, params, run_id_ref)
            elif cat == RuleCategory.CONSISTENCY:
                select_sql = self._render_consistency(rule, params, run_id_ref)
            else:
                return None
        except _UnsupportedRule:
            return None

        if not select_sql:
            return None

        return RenderedRule(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            rule_category=cat.value,
            select_sql=select_sql,
            query_hash=_query_hash(cat.value, rule.rule_id),
        )

    def standalone_insert(self, rule: DQRule) -> Optional[str]:
        """Build a single, parameterized INSERT for a rule.

        Uses @run_id as the run_id parameter. Suitable for per-rule execution
        from the validation engine when no stored procedure is in play.
        Stored on DQRule.generated_sql for inspection in dq_rule_config.
        """
        rendered = self.render_rule(rule, run_id_ref=_STANDALONE_RUN_ID)
        if not rendered:
            return None
        return rendered.as_standalone_insert(self._dq_project, self._dq_dataset)

    def build_procedure(
        self,
        session_id: str,
        rules: list[DQRule],
        procedure_name: Optional[str] = None,
    ) -> tuple[str, str, int]:
        """Build a single CREATE OR REPLACE PROCEDURE for all rules.

        Returns (procedure_ddl, procedure_name, rule_count_included).
        """
        proc_name = procedure_name or _safe_sp_name(session_id)
        rendered: list[RenderedRule] = []
        for rule in rules:
            if not rule.is_active:
                continue
            r = self.render_rule(rule, run_id_ref=_SP_RUN_ID)
            if r is not None:
                rendered.append(r)

        if not rendered:
            return ("", proc_name, 0)

        union_body = self._union_all(rendered)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        results_ref = f"`{self._dq_project}.{self._dq_dataset}.dq_results`"

        ddl = (
            f"-- ============================================================\n"
            f"-- Consolidated DQ Stored Procedure\n"
            f"-- Session   : {session_id}\n"
            f"-- Procedure : `{self._dq_project}.{self._dq_dataset}.{proc_name}`\n"
            f"-- Rules     : {len(rendered)}\n"
            f"-- Generated : {ts}\n"
            f"--\n"
            f"-- To execute:\n"
            f"--   CALL `{self._dq_project}.{self._dq_dataset}.{proc_name}`('<run_id>');\n"
            f"-- ============================================================\n\n"
            f"CREATE OR REPLACE PROCEDURE\n"
            f"  `{self._dq_project}.{self._dq_dataset}.{proc_name}`(IN p_run_id STRING)\n"
            f"OPTIONS (strict_mode=false)\n"
            f"BEGIN\n"
            f"  INSERT INTO {results_ref} (\n"
            f"    {_RESULT_COLUMNS_SQL}\n"
            f"  )\n"
            f"  WITH dq_run AS (\n"
            f"{_indent(union_body, '    ')}\n"
            f"  )\n"
            f"  SELECT * FROM dq_run;\n"
            f"END;"
        )
        return ddl, proc_name, len(rendered)

    def build_standalone_script(self, rules: list[DQRule], run_id: str) -> str:
        """A runnable .sql script that executes every rule once with `run_id`.

        Useful for debugging / reproducible audit; not part of the SP path.
        """
        pieces = [
            f"DECLARE run_id STRING DEFAULT {_sql_str(run_id)};",
        ]
        for rule in rules:
            if not rule.is_active:
                continue
            r = self.render_rule(rule, run_id_ref="run_id")
            if r is None:
                continue
            pieces.append(r.as_standalone_insert(self._dq_project, self._dq_dataset))
        return "\n\n".join(pieces)

    # ------------------------------------------------------------------
    # Per-category SELECT builders — all produce the same column shape
    # ------------------------------------------------------------------

    def _render_completeness(
        self, rule: DQRule, params: dict[str, Any], run_id_ref: str
    ) -> Optional[str]:
        column = rule.column_name
        if not column:
            raise _UnsupportedRule("completeness rule missing column_name")

        threshold = float(params.get("threshold", rule.threshold or 0.0))
        partition_filter = params.get("partition_filter") or None
        src = _table_ref(rule.project_id, rule.dataset_name, rule.table_name)
        where = f" WHERE {partition_filter}" if partition_filter else ""

        threshold_pct = round(threshold * 100, 2)
        stats_subq = (
            f"(SELECT COUNT(*) AS total_count, "
            f"COUNTIF({_quote_ident(column)} IS NULL) AS null_count "
            f"FROM {src}{where})"
        )

        return self._build_select(
            rule,
            run_id_ref=run_id_ref,
            from_clause=f"{stats_subq} AS stats",
            status_expr=(
                f"CASE WHEN SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) "
                f"<= {threshold} THEN 'PASS' ELSE 'FAIL' END"
            ),
            observed_expr=(
                "CONCAT(CAST(null_count AS STRING), ' of ', "
                "CAST(total_count AS STRING), ' rows are null')"
            ),
            expected_expr=_sql_str(f"null rate <= {threshold_pct}%"),
            threshold_expr=_sql_str(threshold),
            failure_count_expr="null_count",
        )

    def _render_uniqueness(
        self, rule: DQRule, params: dict[str, Any], run_id_ref: str
    ) -> Optional[str]:
        columns = params.get("columns") or ([rule.column_name] if rule.column_name else [])
        columns = [c for c in columns if c]
        if not columns:
            raise _UnsupportedRule("uniqueness rule missing column(s)")

        src = _table_ref(rule.project_id, rule.dataset_name, rule.table_name)
        partition_filter = params.get("partition_filter") or None
        where = f" WHERE {partition_filter}" if partition_filter else ""

        if len(columns) == 1:
            col_q = _quote_ident(columns[0])
            distinct_expr = f"COUNT(DISTINCT {col_q})"
            # Collect up to 5 actual duplicate values in a single pass via ARRAY_AGG
            dup_sample_expr = (
                f"ARRAY_TO_STRING("
                f"ARRAY_AGG(DISTINCT CASE WHEN _cnt > 1 THEN CAST({col_q} AS STRING) END "
                f"IGNORE NULLS LIMIT 5), ', ')"
            )
            from_inner = (
                f"(SELECT {col_q}, COUNT(*) OVER (PARTITION BY {col_q}) AS _cnt, "
                f"COUNT(*) AS total_count "
                f"FROM {src}{where})"
            )
            stats_subq = (
                f"(SELECT COUNT(*) AS total_count, {distinct_expr} AS distinct_count, "
                f"{dup_sample_expr} AS sample_values "
                f"FROM {src}{where})"
            )
            # simpler: use a correlated subquery for dup samples (one extra scan, limited)
            dup_subq = (
                f"(SELECT STRING_AGG(v, ', ') FROM ("
                f"SELECT DISTINCT CAST({col_q} AS STRING) AS v "
                f"FROM {src}{where} GROUP BY {col_q} HAVING COUNT(*) > 1 LIMIT 5))"
            )
            stats_subq = (
                f"(SELECT COUNT(*) AS total_count, {distinct_expr} AS distinct_count, "
                f"{dup_subq} AS sample_values "
                f"FROM {src}{where})"
            )
        else:
            concat = " , '|' , ".join(
                f"CAST({_quote_ident(c)} AS STRING)" for c in columns
            )
            key_expr = f"CONCAT({concat})"
            distinct_expr = f"COUNT(DISTINCT {key_expr})"
            dup_subq = (
                f"(SELECT STRING_AGG(k, ', ') FROM ("
                f"SELECT {key_expr} AS k "
                f"FROM {src}{where} GROUP BY {', '.join(str(i+1) for i in range(len(columns)))} "
                f"HAVING COUNT(*) > 1 LIMIT 5))"
            )
            stats_subq = (
                f"(SELECT COUNT(*) AS total_count, {distinct_expr} AS distinct_count, "
                f"{dup_subq} AS sample_values "
                f"FROM {src}{where})"
            )

        return self._build_select(
            rule,
            run_id_ref=run_id_ref,
            from_clause=f"{stats_subq} AS stats",
            status_expr=(
                "CASE WHEN total_count = distinct_count THEN 'PASS' ELSE 'FAIL' END"
            ),
            observed_expr=(
                "CONCAT(CAST(total_count - distinct_count AS STRING), ' duplicate(s)'"
                ", CASE WHEN total_count > distinct_count "
                "AND sample_values IS NOT NULL AND sample_values != '' "
                "THEN CONCAT(' — e.g. [', sample_values, ']') ELSE '' END)"
            ),
            expected_expr=_sql_str("0 duplicates"),
            threshold_expr=_sql_str(0.0),
            failure_count_expr="total_count - distinct_count",
        )

    def _render_validity(
        self, rule: DQRule, params: dict[str, Any], run_id_ref: str
    ) -> Optional[str]:
        column = rule.column_name
        if not column:
            raise _UnsupportedRule("validity rule missing column_name")

        src = _table_ref(rule.project_id, rule.dataset_name, rule.table_name)
        partition_filter = params.get("partition_filter") or None
        where = f" WHERE {partition_filter}" if partition_filter else ""

        threshold_pct = float(params.get("threshold", rule.threshold or 0.0))

        if params.get("regex_pattern"):
            pattern = params["regex_pattern"]
            fail_cond = (
                f"{_quote_ident(column)} IS NOT NULL "
                f"AND NOT REGEXP_CONTAINS(CAST({_quote_ident(column)} AS STRING), r'''{pattern}''')"
            )
            expected_label = f"matches /{pattern}/"
        elif params.get("allowed_values"):
            quoted = ", ".join(_sql_str(v) for v in params["allowed_values"])
            fail_cond = (
                f"{_quote_ident(column)} IS NOT NULL "
                f"AND {_quote_ident(column)} NOT IN ({quoted})"
            )
            expected_label = f"one of {len(params['allowed_values'])} allowed values"
        elif params.get("has_min") or params.get("has_max"):
            conds = []
            if params.get("has_min"):
                conds.append(f"{_quote_ident(column)} < {_sql_literal(params['min_value'])}")
            if params.get("has_max"):
                conds.append(f"{_quote_ident(column)} > {_sql_literal(params['max_value'])}")
            fail_cond = (
                f"{_quote_ident(column)} IS NOT NULL AND (" + " OR ".join(conds) + ")"
            )
            parts = []
            if params.get("has_min"):
                parts.append(f">= {params['min_value']}")
            if params.get("has_max"):
                parts.append(f"<= {params['max_value']}")
            expected_label = " and ".join(parts)
        elif params.get("fail_condition"):
            fail_cond = params["fail_condition"]
            expected_label = params.get("expected_label", "validity passes")
        else:
            raise _UnsupportedRule("validity rule has no recognizable parameters")

        # Collect up to 5 actual bad column values in a correlated subquery (one extra scan)
        sample_subq = (
            f"(SELECT STRING_AGG(DISTINCT CAST({_quote_ident(column)} AS STRING), ', ') "
            f"FROM (SELECT {_quote_ident(column)} FROM {src}{where} "
            f"WHERE {fail_cond} LIMIT 5))"
        )

        stats_subq = (
            f"(SELECT COUNT(*) AS total_count, "
            f"COUNTIF({fail_cond}) AS failure_count, "
            f"{sample_subq} AS sample_values "
            f"FROM {src}{where})"
        )

        return self._build_select(
            rule,
            run_id_ref=run_id_ref,
            from_clause=f"{stats_subq} AS stats",
            status_expr=(
                f"CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) "
                f"<= {threshold_pct} THEN 'PASS' ELSE 'FAIL' END"
            ),
            observed_expr=(
                "CONCAT(CAST(failure_count AS STRING), ' of ', "
                "CAST(total_count AS STRING), ' rows invalid'"
                ", CASE WHEN failure_count > 0 "
                "AND sample_values IS NOT NULL AND sample_values != '' "
                "THEN CONCAT(' — e.g. [', sample_values, ']') ELSE '' END)"
            ),
            expected_expr=_sql_str(expected_label),
            threshold_expr=_sql_str(f"<= {threshold_pct} failure rate"),
            failure_count_expr="failure_count",
        )

    def _render_freshness(
        self, rule: DQRule, params: dict[str, Any], run_id_ref: str
    ) -> Optional[str]:
        ts_col = rule.column_name or params.get("timestamp_column")
        if not ts_col:
            raise _UnsupportedRule("freshness rule missing timestamp_column")
        max_lag_hours = float(params.get("max_lag_hours", 24.0))
        src = _table_ref(rule.project_id, rule.dataset_name, rule.table_name)

        # Pull max timestamp in same scan — shows exact last-record time alongside lag
        stats_subq = (
            f"(SELECT COUNT(*) AS total_count, "
            f"TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX({_quote_ident(ts_col)}), HOUR) AS lag_hours, "
            f"FORMAT_TIMESTAMP('%Y-%m-%d %H:%M UTC', MAX({_quote_ident(ts_col)})) AS last_ts "
            f"FROM {src})"
        )

        return self._build_select(
            rule,
            run_id_ref=run_id_ref,
            from_clause=f"{stats_subq} AS stats",
            status_expr=(
                f"CASE WHEN lag_hours <= {max_lag_hours} OR lag_hours IS NULL "
                f"THEN 'PASS' ELSE 'FAIL' END"
            ),
            observed_expr=(
                "CONCAT(CAST(lag_hours AS STRING), ' hrs behind"
                " (last: ', COALESCE(last_ts, 'no data'), ')')"
            ),
            expected_expr=_sql_str(f"<= {max_lag_hours} hours"),
            threshold_expr=_sql_str(str(max_lag_hours)),
            failure_count_expr=(
                f"CASE WHEN lag_hours > {max_lag_hours} THEN 1 ELSE 0 END"
            ),
        )

    def _render_volume(
        self, rule: DQRule, params: dict[str, Any], run_id_ref: str
    ) -> Optional[str]:
        src = _table_ref(rule.project_id, rule.dataset_name, rule.table_name)
        partition_filter = params.get("partition_filter") or None
        where = f" WHERE {partition_filter}" if partition_filter else ""

        min_rows = int(params.get("min_rows", 1))
        max_rows = params.get("max_rows")

        if max_rows is not None:
            status_expr = (
                f"CASE WHEN total_count BETWEEN {min_rows} AND {int(max_rows)} "
                f"THEN 'PASS' ELSE 'FAIL' END"
            )
            expected = f"between {min_rows} and {int(max_rows)} rows"
            threshold_lit = f"{min_rows}..{int(max_rows)}"
        else:
            status_expr = (
                f"CASE WHEN total_count >= {min_rows} THEN 'PASS' ELSE 'FAIL' END"
            )
            expected = f">= {min_rows} rows"
            threshold_lit = str(min_rows)

        stats_subq = f"(SELECT COUNT(*) AS total_count FROM {src}{where})"

        return self._build_select(
            rule,
            run_id_ref=run_id_ref,
            from_clause=f"{stats_subq} AS stats",
            status_expr=status_expr,
            observed_expr="CAST(total_count AS STRING)",
            expected_expr=_sql_str(expected),
            threshold_expr=_sql_str(threshold_lit),
            failure_count_expr="0",
        )

    def _render_integrity(
        self, rule: DQRule, params: dict[str, Any], run_id_ref: str
    ) -> Optional[str]:
        column = rule.column_name
        if not column:
            raise _UnsupportedRule("integrity rule missing column_name")

        ref_table = params.get("ref_table")
        if not ref_table:
            raise _UnsupportedRule("integrity rule missing ref_table")
        ref_project = params.get("ref_project", rule.project_id)
        ref_dataset = params.get("ref_dataset", rule.dataset_name)
        ref_column = params.get("ref_column", column)

        src = _table_ref(rule.project_id, rule.dataset_name, rule.table_name)
        ref = _table_ref(ref_project, ref_dataset, ref_table)

        col_q = _quote_ident(column)
        ref_col_q = _quote_ident(ref_column)
        orphan_cond = f"s.{col_q} IS NOT NULL AND r.{ref_col_q} IS NULL"

        # Single JOIN pass: aggregate counts and sample orphaned FK values together
        stats_subq = (
            f"(SELECT COUNT(*) AS total_count, "
            f"COUNTIF({orphan_cond}) AS failure_count, "
            f"ARRAY_TO_STRING("
            f"ARRAY_AGG(DISTINCT CASE WHEN {orphan_cond} "
            f"THEN CAST(s.{col_q} AS STRING) END IGNORE NULLS LIMIT 5), ', '"
            f") AS sample_values "
            f"FROM {src} s "
            f"LEFT JOIN {ref} r "
            f"ON s.{col_q} = r.{ref_col_q})"
        )

        return self._build_select(
            rule,
            run_id_ref=run_id_ref,
            from_clause=f"{stats_subq} AS stats",
            status_expr="CASE WHEN failure_count = 0 THEN 'PASS' ELSE 'FAIL' END",
            observed_expr=(
                "CONCAT(CAST(failure_count AS STRING), ' orphaned FK(s)'"
                ", CASE WHEN failure_count > 0 "
                "AND sample_values IS NOT NULL AND sample_values != '' "
                "THEN CONCAT(' — e.g. [', sample_values, ']') ELSE '' END)"
            ),
            expected_expr=_sql_str(f"all FKs present in {ref_table}"),
            threshold_expr=_sql_str(0.0),
            failure_count_expr="failure_count",
        )

    def _render_schema_drift(
        self, rule: DQRule, params: dict[str, Any], run_id_ref: str
    ) -> Optional[str]:
        raw = params.get("baseline_columns_json") or params.get("baseline_columns") or "[]"
        baseline = json.loads(raw) if isinstance(raw, str) else raw
        baseline_set = sorted(
            f"{c.get('column_name', '')}:{c.get('data_type', '').upper()}"
            for c in baseline
        )
        baseline_array = "[" + ", ".join(_sql_str(s) for s in baseline_set) + "]"

        info_schema = (
            f"`{rule.project_id}.{rule.dataset_name}.INFORMATION_SCHEMA.COLUMNS`"
        )

        # Single self-contained subquery: arrays of current + baseline column signatures,
        # then symmetric-difference count as failure_count.
        stats_subq = (
            "(SELECT\n"
            "      ARRAY_LENGTH(cur_arr) AS total_count,\n"
            "      ((SELECT COUNT(*) FROM UNNEST(cur_arr) c "
            "WHERE c NOT IN UNNEST(base_arr))\n"
            "       + (SELECT COUNT(*) FROM UNNEST(base_arr) b "
            "WHERE b NOT IN UNNEST(cur_arr))) AS failure_count\n"
            f"    FROM (\n"
            f"      SELECT\n"
            f"        ARRAY(SELECT CONCAT(column_name, ':', UPPER(data_type))\n"
            f"              FROM {info_schema}\n"
            f"              WHERE table_name = {_sql_str(rule.table_name)}\n"
            f"              ORDER BY column_name) AS cur_arr,\n"
            f"        {baseline_array} AS base_arr\n"
            f"    ))"
        )

        return self._build_select(
            rule,
            run_id_ref=run_id_ref,
            from_clause=f"{stats_subq} AS stats",
            status_expr="CASE WHEN failure_count = 0 THEN 'PASS' ELSE 'FAIL' END",
            observed_expr="CAST(failure_count AS STRING)",
            expected_expr=_sql_str("schema matches baseline"),
            threshold_expr=_sql_str(0.0),
            failure_count_expr="failure_count",
        )

    def _render_consistency(
        self, rule: DQRule, params: dict[str, Any], run_id_ref: str
    ) -> Optional[str]:
        """Cross-column / business-rule consistency check.

        Requires `params["fail_condition"]`: a BigQuery row-level boolean
        expression where TRUE = row fails. This is how AI-inferred
        cross-column rules express themselves.
        """
        fail_cond = params.get("fail_condition")
        if not fail_cond:
            raise _UnsupportedRule("consistency rule missing fail_condition")
        
        fail_cond = re.sub(
            r'TIMESTAMP_SUB\(([^,]+),\s*INTERVAL\s+(\d+)\s+YEAR\)',
            lambda m: f'TIMESTAMP_SUB({m.group(1)}, INTERVAL {int(m.group(2)) * 365} DAY)',
            fail_cond,
            flags=re.IGNORECASE,
        )
        
        # Fix table alias references — remove t1., t2., s., r. etc
        fail_cond = re.sub(r'\bt\d+\.', '', fail_cond)
        fail_cond = re.sub(r'\b[a-zA-Z]\w*\.`', '`', fail_cond)
        
        # Fix DIV operator — not supported in BQ stored procedures
        fail_cond = re.sub(
            r'(\w+)\s+DIV\s+(\w+)',
            r'CAST(\1 / \2 AS INT64)',
            fail_cond,
            flags=re.IGNORECASE,   
        )
        src = _table_ref(rule.project_id, rule.dataset_name, rule.table_name)
        threshold_pct = float(params.get("threshold", rule.threshold or 0.0))

        stats_subq = (
            f"(SELECT COUNT(*) AS total_count, "
            f"COUNTIF({fail_cond}) AS failure_count "
            f"FROM {src})"
        )

        return self._build_select(
            rule,
            run_id_ref=run_id_ref,
            from_clause=f"{stats_subq} AS stats",
            status_expr=(
                f"CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) "
                f"<= {threshold_pct} THEN 'PASS' ELSE 'FAIL' END"
            ),
            observed_expr=(
                "CONCAT(CAST(failure_count AS STRING), ' of ', "
                "CAST(total_count AS STRING), ' rows fail')"
            ),
            expected_expr=_sql_str(params.get("expected_label", "row condition holds")),
            threshold_expr=_sql_str(f"<= {threshold_pct} failure rate"),
            failure_count_expr="failure_count",
        )

    # ------------------------------------------------------------------
    # Shared row-shape builder
    # ------------------------------------------------------------------

    def _build_select(
        self,
        rule: DQRule,
        *,
        run_id_ref: str,
        from_clause: str,
        status_expr: str,
        observed_expr: str,
        expected_expr: str,
        threshold_expr: str,
        failure_count_expr: str,
    ) -> str:
        """Emit a full single-statement SELECT producing one dq_results row.

        The returned SQL is UNION-ALL-safe: no CTEs at the top level, just
        SELECT … FROM <subquery>. This is what allows N rules to be combined
        into one INSERT inside the stored procedure.
        """
        col = rule.column_name
        query_hash = _query_hash(rule.rule_category.value, rule.rule_id)

        lines = [
            "SELECT",
            f"  {run_id_ref} AS run_id,",
            f"  {_sql_str(rule.rule_id)} AS rule_id,",
            f"  {_sql_str(rule.project_id)} AS project_id,",
            f"  {_sql_str(rule.dataset_name)} AS dataset_name,",
            f"  {_sql_str(rule.table_name)} AS table_name,",
            f"  {_sql_str(col) if col else 'CAST(NULL AS STRING)'} AS column_name,",
            f"  {_sql_str(rule.rule_category.value)} AS rule_type,",
            f"  {_sql_str(rule.severity.value)} AS severity,",
            f"  {status_expr} AS status,",
            f"  {observed_expr} AS observed_value,",
            f"  {expected_expr} AS expected_value,",
            f"  {threshold_expr} AS threshold_value,",
            f"  CAST({failure_count_expr} AS INT64) AS failure_count,",
            f"  CURRENT_TIMESTAMP() AS execution_time,",
            f"  CAST(NULL AS FLOAT64) AS execution_duration_seconds,",
            f"  {_sql_str(query_hash)} AS query_executed,",
            f"  CAST(NULL AS STRING) AS error_message,",
            f"  CURRENT_TIMESTAMP() AS created_at",
            f"FROM {from_clause}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _union_all(rendered: Iterable[RenderedRule]) -> str:
        pieces: list[str] = []
        for r in rendered:
            header = (
                f"-- [{r.rule_category}] {r.rule_id} — {r.rule_name}\n"
                f"-- query_hash: {r.query_hash}"
            )
            pieces.append(f"{header}\n{r.select_sql}")
        return "\n\nUNION ALL\n\n".join(pieces)


# ----------------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------------


class _UnsupportedRule(Exception):
    """Raised internally when a rule cannot be rendered."""


def _safe_sp_name(identifier: str) -> str:
    """Return a BigQuery-safe stored procedure name."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", identifier)
    return f"sp_dq_{safe}"


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def get_sql_generator(dq_project: str, dq_dataset: str) -> DQSQLGenerator:
    return DQSQLGenerator(dq_project=dq_project, dq_dataset=dq_dataset)
