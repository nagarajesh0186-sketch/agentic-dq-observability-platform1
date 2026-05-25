"""Technical DQ Rule Engine Agent — Stage 2 of the DQ workflow."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import structlog
import yaml

from schemas.models import DQRule, RuleCategory, Severity

logger = structlog.get_logger(__name__)

_RULE_LIBRARY_PATH = Path(__file__).parent.parent.parent / "dq_rules" / "rule_library.yaml"

_NUMERIC_TYPES = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC", "DECIMAL"}
_DATE_TYPES = {"DATE", "TIMESTAMP", "DATETIME"}
_STRING_TYPES = {"STRING", "BYTES"}


class TechnicalRuleEngineAgent:
    """Generates standard technical DQ rules from metadata and column profiles."""

    def __init__(self) -> None:
        self._log = logger.bind(agent="TechnicalRuleEngineAgent")
        self._rule_library = self._load_rule_library()

    def _load_rule_library(self) -> list[dict[str, Any]]:
        try:
            with open(_RULE_LIBRARY_PATH) as f:
                data = yaml.safe_load(f)
                return data.get("rules", [])
        except Exception as exc:
            self._log.error("rule_library_load_failed", error=str(exc))
            return []

    async def run(
        self,
        project_id: str,
        dataset_id: str,
        table_metadata: dict[str, Any],
        column_profiles: dict[str, Any],
        column_semantics: dict[str, Any],
        rule_set_version_id: str,
    ) -> list[DQRule]:
        """Generate technical DQ rules for all tables in the metadata."""
        rules: list[DQRule] = []

        for table_name, table_data in table_metadata.get("tables", {}).items():
            meta = table_data.get("metadata", {})
            profiles = table_data.get("profiling", {}).get("columns", [])
            semantics = table_data.get("semantics", {})

            table_rules = self._generate_table_rules(
                project_id, dataset_id, table_name, meta, profiles, semantics, rule_set_version_id
            )
            rules.extend(table_rules)
            self._log.info("table_rules_generated", table=table_name, count=len(table_rules))

        return rules

    def _generate_table_rules(
        self,
        project: str,
        dataset: str,
        table: str,
        metadata: dict[str, Any],
        profiles: list[dict[str, Any]],
        semantics: dict[str, Any],
        rule_set_version_id: str,
    ) -> list[DQRule]:
        rules: list[DQRule] = []
        profile_map = {p["column_name"]: p for p in profiles}

        # Volume checks (table-level)
        row_count = metadata.get("row_count", 0)
        if row_count > 0:
            rules.append(self._build_volume_rule(project, dataset, table, row_count, rule_set_version_id))

        # Schema drift check
        baseline_columns = [
            {"column_name": c["column_name"], "data_type": c["data_type"]}
            for c in metadata.get("columns", [])
        ]
        rules.append(self._build_schema_drift_rule(project, dataset, table, baseline_columns, rule_set_version_id))

        # Per-column rules
        for col_meta in metadata.get("columns", []):
            col_name = col_meta["column_name"]
            data_type = col_meta.get("data_type", "STRING").upper()
            is_nullable = col_meta.get("is_nullable", "YES") == "YES"
            profile = profile_map.get(col_name, {})
            sem = semantics.get(col_name, {})
            business_type = sem.get("business_type", "unknown")

            col_rules = self._generate_column_rules(
                project, dataset, table, col_name, data_type, is_nullable,
                profile, business_type, rule_set_version_id
            )
            rules.extend(col_rules)

        # Freshness checks (table-level, requires timestamp column)
        ts_col = self._find_timestamp_column(metadata.get("columns", []))
        if ts_col:
            rules.append(self._build_freshness_rule(project, dataset, table, ts_col, rule_set_version_id))

        return rules

    def _generate_column_rules(
        self,
        project: str,
        dataset: str,
        table: str,
        column: str,
        data_type: str,
        is_nullable: bool,
        profile: dict[str, Any],
        business_type: str,
        rule_set_version_id: str,
    ) -> list[DQRule]:
        rules: list[DQRule] = []
        null_rate = profile.get("null_rate", 0.0)
        distinct_count = profile.get("distinct_count", 0)
        total_count = profile.get("total_count", 1)
        cardinality_ratio = distinct_count / max(total_count, 1)

        # Completeness check
        if not is_nullable:
            rules.append(DQRule(
                rule_id=f"COMP_{column}_{uuid.uuid4().hex[:6]}",
                rule_name=f"Not Null: {column}",
                rule_category=RuleCategory.COMPLETENESS,
                description=f"Column {column} must not contain null values (not nullable)",
                severity=Severity.FAIL,
                threshold=0.0,
                project_id=project,
                dataset_name=dataset,
                table_name=table,
                column_name=column,
                sql_template="completeness_check.sql.j2",
                parameters={"threshold": 0.0, "threshold_pct": 0.0, "partition_filter": ""},
                rule_set_version_id=rule_set_version_id,
            ))
        elif null_rate > 0.8:
            rules.append(DQRule(
                rule_id=f"COMP_{column}_{uuid.uuid4().hex[:6]}",
                rule_name=f"Sparse Field Alert: {column}",
                rule_category=RuleCategory.COMPLETENESS,
                description=f"Column {column} has {null_rate:.0%} nulls — sparse data alert",
                severity=Severity.INFO,
                threshold=0.8,
                project_id=project,
                dataset_name=dataset,
                table_name=table,
                column_name=column,
                sql_template="completeness_check.sql.j2",
                parameters={"threshold": 0.8, "threshold_pct": 80.0, "partition_filter": ""},
                rule_set_version_id=rule_set_version_id,
            ))

        # Uniqueness check for high-cardinality / ID columns
        if cardinality_ratio > 0.95 or business_type == "id":
            rules.append(DQRule(
                rule_id=f"UNIQ_{column}_{uuid.uuid4().hex[:6]}",
                rule_name=f"Uniqueness: {column}",
                rule_category=RuleCategory.UNIQUENESS,
                description=f"Column {column} (ID-like) must have no duplicate values",
                severity=Severity.FAIL,
                threshold=0.0,
                project_id=project,
                dataset_name=dataset,
                table_name=table,
                column_name=column,
                sql_template="uniqueness_check.sql.j2",
                parameters={"columns": [column], "columns_str": f"`{column}`", "partition_filter": ""},
                rule_set_version_id=rule_set_version_id,
            ))

        # Email regex validation
        if business_type == "email":
            rules.append(DQRule(
                rule_id=f"VALD_EMAIL_{column}_{uuid.uuid4().hex[:6]}",
                rule_name=f"Email Format: {column}",
                rule_category=RuleCategory.VALIDITY,
                description=f"Column {column} must contain valid email addresses",
                severity=Severity.WARN,
                threshold=0.99,
                project_id=project,
                dataset_name=dataset,
                table_name=table,
                column_name=column,
                sql_template="validity_regex_check.sql.j2",
                parameters={
                    "regex_pattern": r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
                    "threshold": 0.99,
                    "partition_filter": "",
                },
                rule_set_version_id=rule_set_version_id,
            ))

        # Positive range check for amount fields
        if business_type in ("amount", "currency") and data_type in _NUMERIC_TYPES:
            rules.append(DQRule(
                rule_id=f"VALD_RANGE_{column}_{uuid.uuid4().hex[:6]}",
                rule_name=f"Positive Amount: {column}",
                rule_category=RuleCategory.VALIDITY,
                description=f"Column {column} must not contain negative values",
                severity=Severity.FAIL,
                threshold=0.0,
                project_id=project,
                dataset_name=dataset,
                table_name=table,
                column_name=column,
                sql_template="range_check.sql.j2",
                parameters={"min_value": 0.0, "has_min": True, "has_max": False, "partition_filter": ""},
                rule_set_version_id=rule_set_version_id,
            ))

        # Status enum check for low-cardinality string fields
        if business_type == "status" and data_type in _STRING_TYPES and cardinality_ratio < 0.01:
            sample_values = profile.get("sample_values", [])
            if sample_values:
                rules.append(DQRule(
                    rule_id=f"VALD_ENUM_{column}_{uuid.uuid4().hex[:6]}",
                    rule_name=f"Status Enum: {column}",
                    rule_category=RuleCategory.VALIDITY,
                    description=f"Column {column} must contain only observed allowed values",
                    severity=Severity.WARN,
                    threshold=0.0,
                    project_id=project,
                    dataset_name=dataset,
                    table_name=table,
                    column_name=column,
                    sql_template="enum_values_check.sql.j2",
                    parameters={
                        "allowed_values": sample_values[:10],
                        "allowed_values_str": ", ".join(f"'{v}'" for v in sample_values[:10]),
                        "partition_filter": "",
                    },
                    rule_set_version_id=rule_set_version_id,
                ))

        return rules

    def _build_volume_rule(
        self, project: str, dataset: str, table: str, row_count: int, version_id: str
    ) -> DQRule:
        min_rows = max(1, int(row_count * 0.5))
        return DQRule(
            rule_id=f"VOLU_{table}_{uuid.uuid4().hex[:6]}",
            rule_name=f"Volume Check: {table}",
            rule_category=RuleCategory.VOLUME,
            description=f"Row count must be at least {min_rows} (50% of baseline {row_count})",
            severity=Severity.WARN,
            threshold=0.5,
            project_id=project,
            dataset_name=dataset,
            table_name=table,
            sql_template="volume_check.sql.j2",
            parameters={"min_rows": min_rows, "has_max_rows": False, "partition_filter": ""},
            rule_set_version_id=version_id,
        )

    def _build_schema_drift_rule(
        self, project: str, dataset: str, table: str, baseline_columns: list[dict[str, Any]], version_id: str
    ) -> DQRule:
        import json
        return DQRule(
            rule_id=f"SCHM_{table}_{uuid.uuid4().hex[:6]}",
            rule_name=f"Schema Drift: {table}",
            rule_category=RuleCategory.SCHEMA_DRIFT,
            description="Alert if columns are added, removed, or change type",
            severity=Severity.WARN,
            threshold=0.0,
            project_id=project,
            dataset_name=dataset,
            table_name=table,
            sql_template="schema_drift_check.sql.j2",
            parameters={"baseline_columns_json": json.dumps(baseline_columns)},
            rule_set_version_id=version_id,
        )

    def _build_freshness_rule(
        self, project: str, dataset: str, table: str, ts_column: str, version_id: str
    ) -> DQRule:
        return DQRule(
            rule_id=f"FRSH_{table}_{uuid.uuid4().hex[:6]}",
            rule_name=f"Freshness: {table}",
            rule_category=RuleCategory.FRESHNESS,
            description=f"Table must have data loaded within 24 hours (via {ts_column})",
            severity=Severity.FAIL,
            threshold=0.0,
            project_id=project,
            dataset_name=dataset,
            table_name=table,
            column_name=ts_column,
            sql_template="freshness_check.sql.j2",
            parameters={"timestamp_column": ts_column, "max_lag_hours": 24.0},
            rule_set_version_id=version_id,
        )

    def _find_timestamp_column(self, columns: list[dict[str, Any]]) -> str | None:
        date_hints = ("created_at", "updated_at", "timestamp", "event_time", "load_time", "dt")
        for col in columns:
            if col.get("data_type", "").upper() in ("TIMESTAMP", "DATETIME", "DATE"):
                cname = col["column_name"].lower()
                if any(h in cname for h in date_hints):
                    return col["column_name"]
        for col in columns:
            if col.get("data_type", "").upper() in ("TIMESTAMP", "DATETIME", "DATE"):
                return col["column_name"]
        return None
