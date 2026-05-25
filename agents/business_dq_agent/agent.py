"""Business Rule Recommendation Agent — Stage 3 of the DQ workflow."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Iterable

import structlog

from agents.base import BaseAgent
from prompts.business_dq_agent import (
    BUSINESS_RULE_SYSTEM_PROMPT_V1,
    RULE_INFERENCE_PROMPT_V1,
)
from schemas.models import DQRule, RuleCategory, Severity

logger = structlog.get_logger(__name__)

_CATEGORY_MAP = {
    "completeness": RuleCategory.COMPLETENESS,
    "uniqueness": RuleCategory.UNIQUENESS,
    "validity": RuleCategory.VALIDITY,
    "integrity": RuleCategory.INTEGRITY,
    "freshness": RuleCategory.FRESHNESS,
    "volume": RuleCategory.VOLUME,
    "schema_drift": RuleCategory.SCHEMA_DRIFT,
    "consistency": RuleCategory.CONSISTENCY,
}

_SEVERITY_MAP = {
    "INFO": Severity.INFO,
    "WARN": Severity.WARN,
    "FAIL": Severity.FAIL,
}

_MAX_PROFILE_COLUMNS = 40
_PROFILE_KEEP_KEYS = (
    "column_name",
    "data_type",
    "null_rate",
    "distinct_count",
    "cardinality_ratio",
    "min_value",
    "max_value",
    "avg_value",
    "sample_values",
)
_MAX_SEMANTICS_COLUMNS = 60
_BACKTICK_IDENT_RE = re.compile(r"`([^`]+)`")

# Columns to sample actual data distributions for — low cardinality categorical
# and numeric columns benefit most from data-driven rules
_MAX_SAMPLE_COLUMNS = 10
_MAX_DISTINCT_FOR_ENUM = 20  # only sample full value list if <= this many distinct values


class BusinessRuleRecommendationAgent(BaseAgent):
    """Uses Claude to generate business-domain DQ rules from table schema, profiling and actual data."""

    def __init__(self) -> None:
        super().__init__(
            agent_name="BusinessRuleRecommendationAgent",
            system_prompt=BUSINESS_RULE_SYSTEM_PROMPT_V1,
        )

    async def run(
        self,
        project_id: str,
        dataset_id: str,
        table_name: str,
        metadata: dict[str, Any],
        profiles: dict[str, Any],
        semantics: dict[str, Any],
        rule_set_version_id: str,
        custom_context: str | None = None,
        existing_rules: list[DQRule] | None = None,
        dataplex_tags: list[dict[str, Any]] | None = None,
        bq_client: Any | None = None,
    ) -> list[DQRule]:
        """Generate LLM-inferred business DQ rules for a single table."""
        columns_meta = metadata.get("columns", []) or []
        known_columns = {c.get("column_name") for c in columns_meta if c.get("column_name")}

        self._log.info(
            "business_rule_inference_start",
            table=table_name,
            columns=len(columns_meta),
            existing_rules=len(existing_rules) if existing_rules else 0,
            has_custom_context=bool(custom_context),
        )

        # --- NEW: Sample actual data distributions from BigQuery ---
        data_samples: dict[str, Any] = {}
        if bq_client is not None:
            data_samples = await self._sample_data_distributions(
                bq_client, project_id, dataset_id, table_name,
                columns_meta, profiles
            )

        prompt = self._build_prompt(
            project_id=project_id,
            dataset_id=dataset_id,
            table_name=table_name,
            metadata=metadata,
            profiles=profiles,
            semantics=semantics,
            dataplex_tags=dataplex_tags or [],
            existing_rules=existing_rules or [],
            custom_context=custom_context,
            data_samples=data_samples,
        )

        try:
            result = await self._call_claude_json(prompt)
        except Exception as exc:
            self._log.error("business_rule_inference_failed", table=table_name, error=str(exc))
            return []

        self._log.info("claude_raw_result",
            result_keys=list(result.keys()) if isinstance(result, dict) else type(result).__name__,
            rules_count=len(result.get("rules", [])) if isinstance(result, dict) else 0)

        raw_rules = result.get("rules", []) if isinstance(result, dict) else []
        inferred_domain = result.get("inferred_domain", "") if isinstance(result, dict) else ""
        if inferred_domain:
            self._log.info("domain_inferred", table=table_name, domain=inferred_domain)

        parsed: list[DQRule] = []
        for raw in raw_rules:
            if not isinstance(raw, dict):
                continue
            rule = self._parse_rule(raw, project_id, dataset_id, table_name, rule_set_version_id)
            if not self._validate_column_refs(rule, known_columns):
                continue
            parsed.append(rule)

        self._log.info(
            "business_rules_generated",
            table=table_name,
            generated=len(parsed),
            dropped=len(raw_rules) - len(parsed),
        )
        return parsed

    # ------------------------------------------------------------------
    # Data sampling — NEW: queries actual BigQuery data
    # ------------------------------------------------------------------

    async def _sample_data_distributions(
        self,
        bq_client: Any,
        project_id: str,
        dataset_id: str,
        table_name: str,
        columns_meta: list[dict[str, Any]],
        profiles: dict[str, Any],
    ) -> dict[str, Any]:
        """Query BigQuery for actual value distributions to enable data-driven rules."""
        samples: dict[str, Any] = {}

        col_profiles = {
            p["column_name"]: p
            for p in (profiles.get("columns") or [])
            if p.get("column_name")
        }

        # Select columns to sample:
        # - Categorical/string columns with low cardinality → get all distinct values
        # - Numeric columns → get min, max, avg, percentiles
        string_types = {"STRING", "BYTES"}
        numeric_types = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC"}

        cols_to_sample = []
        for col in columns_meta[:_MAX_SAMPLE_COLUMNS]:
            col_name = col.get("column_name", "")
            data_type = col.get("data_type", "").upper()
            profile = col_profiles.get(col_name, {})
            distinct_count = profile.get("distinct_count", 999)

            if data_type in string_types and distinct_count and distinct_count <= _MAX_DISTINCT_FOR_ENUM:
                cols_to_sample.append(("enum", col_name))
            elif data_type in numeric_types:
                cols_to_sample.append(("numeric", col_name))

        src = f"`{project_id}.{dataset_id}.{table_name}`"

        for sample_type, col_name in cols_to_sample:
            try:
                if sample_type == "enum":
                    sql = (
                        f"SELECT `{col_name}` AS value, COUNT(*) AS cnt "
                        f"FROM {src} "
                        f"WHERE `{col_name}` IS NOT NULL "
                        f"GROUP BY 1 ORDER BY cnt DESC LIMIT 30"
                    )
                    rows = await bq_client.execute_query(sql)
                    samples[col_name] = {
                        "type": "enum",
                        "distinct_values": [r["value"] for r in rows if r.get("value") is not None],
                        "value_counts": {str(r["value"]): r["cnt"] for r in rows[:10]},
                    }
                elif sample_type == "numeric":
                    sql = (
                        f"SELECT "
                        f"MIN(`{col_name}`) AS min_val, "
                        f"MAX(`{col_name}`) AS max_val, "
                        f"AVG(`{col_name}`) AS avg_val, "
                        f"APPROX_QUANTILES(`{col_name}`, 4)[OFFSET(1)] AS p25, "
                        f"APPROX_QUANTILES(`{col_name}`, 4)[OFFSET(2)] AS p50, "
                        f"APPROX_QUANTILES(`{col_name}`, 4)[OFFSET(3)] AS p75, "
                        f"COUNTIF(`{col_name}` < 0) AS negative_count, "
                        f"COUNT(*) AS total_count "
                        f"FROM {src}"
                    )
                    rows = await bq_client.execute_query(sql)
                    if rows:
                        r = rows[0]
                        samples[col_name] = {
                            "type": "numeric",
                            "min": r.get("min_val"),
                            "max": r.get("max_val"),
                            "avg": round(float(r.get("avg_val") or 0), 2),
                            "p25": r.get("p25"),
                            "p50": r.get("p50"),
                            "p75": r.get("p75"),
                            "negative_count": r.get("negative_count", 0),
                            "total_count": r.get("total_count", 0),
                        }
            except Exception as exc:
                self._log.warning("data_sampling_failed", column=col_name, error=str(exc)[:100])
                continue

        if samples:
            self._log.info("data_sampling_complete", columns_sampled=len(samples), table=table_name)

        return samples

    # ------------------------------------------------------------------
    # Prompt assembly
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        *,
        project_id: str,
        dataset_id: str,
        table_name: str,
        metadata: dict[str, Any],
        profiles: dict[str, Any],
        semantics: dict[str, Any],
        dataplex_tags: list[dict[str, Any]],
        existing_rules: list[DQRule],
        custom_context: str | None,
        data_samples: dict[str, Any],
    ) -> str:
        schema_json = self._render_schema(
            metadata=metadata,
            semantics=semantics,
            dataplex_tags=dataplex_tags,
        )
        return RULE_INFERENCE_PROMPT_V1.format(
            project_id=project_id,
            dataset_id=dataset_id,
            table_name=table_name,
            table_description_section=self._render_table_description(metadata),
            schema_json=schema_json,
            profiles_section=self._render_profiles_section(profiles),
            semantics_section=self._render_semantics_section(semantics),
            data_samples_section=self._render_data_samples_section(data_samples),
            existing_rules_section=self._render_existing_rules_section(existing_rules, table_name),
            user_context_section=self._render_user_context_section(custom_context),
        )

    @staticmethod
    def _render_table_description(metadata: dict[str, Any]) -> str:
        bits: list[str] = []
        desc = (metadata.get("description") or "").strip()
        if desc:
            bits.append(f"Description: {desc}")
        row_count = metadata.get("row_count")
        if row_count:
            bits.append(f"Approx. rows: {row_count:,}")
        partition_col = metadata.get("partition_column")
        if partition_col:
            bits.append(f"Partition column: {partition_col}")
        clustering = metadata.get("clustering_columns") or []
        if clustering:
            bits.append(f"Clustering: {', '.join(clustering)}")
        labels = metadata.get("labels") or {}
        if labels:
            bits.append("Labels: " + ", ".join(f"{k}={v}" for k, v in labels.items()))
        if not bits:
            return ""
        return "\n" + "\n".join(bits)

    def _render_schema(
        self,
        *,
        metadata: dict[str, Any],
        semantics: dict[str, Any],
        dataplex_tags: list[dict[str, Any]],
    ) -> str:
        columns = metadata.get("columns", []) or []
        partition_col = metadata.get("partition_column")
        clustering = set(metadata.get("clustering_columns") or [])

        tag_index: dict[str, dict[str, Any]] = {}
        for tag in dataplex_tags:
            col = tag.get("column_name") or tag.get("column")
            if col:
                tag_index[col] = tag

        rows: list[dict[str, Any]] = []
        for c in columns:
            col_name = c.get("column_name", "")
            sem = semantics.get(col_name, {}) if isinstance(semantics, dict) else {}
            tag = tag_index.get(col_name, {})

            row: dict[str, Any] = {
                "column": col_name,
                "type": c.get("data_type", "STRING"),
                "nullable": c.get("is_nullable", "YES") == "YES",
            }
            description = (c.get("description") or "").strip()
            if description:
                row["description"] = description
            if col_name == partition_col:
                row["partition_key"] = True
            if col_name in clustering:
                row["clustering_key"] = True

            business_type = sem.get("business_type") if isinstance(sem, dict) else None
            if business_type and business_type != "unknown":
                row["business_type"] = business_type
            if isinstance(sem, dict) and sem.get("pii_likely"):
                row["pii_likely"] = True

            tag_pii = tag.get("pii") or tag.get("pii_type") or tag.get("sensitivity")
            if tag_pii:
                row["dataplex_pii"] = tag_pii

            rows.append(row)

        return json.dumps(rows, indent=2, default=str)

    def _render_profiles_section(self, profiles: dict[str, Any]) -> str:
        col_profiles = profiles.get("columns") if isinstance(profiles, dict) else None
        if not col_profiles:
            return ""
        trimmed = [
            {k: v for k, v in (p or {}).items() if k in _PROFILE_KEEP_KEYS}
            for p in col_profiles[:_MAX_PROFILE_COLUMNS]
        ]
        elided = max(0, len(col_profiles) - _MAX_PROFILE_COLUMNS)
        header = "## Column Profiles (statistics)"
        if elided:
            header += f"  ({elided} additional columns omitted)"
        return f"{header}\n{json.dumps(trimmed, indent=2, default=str)}"

    def _render_semantics_section(self, semantics: dict[str, Any]) -> str:
        if not isinstance(semantics, dict) or not semantics:
            return ""
        items = list(semantics.items())[:_MAX_SEMANTICS_COLUMNS]
        elided = max(0, len(semantics) - _MAX_SEMANTICS_COLUMNS)
        header = "## Inferred Column Semantics"
        if elided:
            header += f"  ({elided} additional columns omitted)"
        return f"{header}\n{json.dumps(dict(items), indent=2, default=str)}"

    @staticmethod
    def _render_data_samples_section(data_samples: dict[str, Any]) -> str:
        """NEW: Render actual data distributions for Claude to use."""
        if not data_samples:
            return ""

        lines = ["## Actual Data Distributions (sampled from BigQuery — use these for precise rules)"]
        for col_name, sample in data_samples.items():
            if sample["type"] == "enum":
                values = sample.get("distinct_values", [])
                counts = sample.get("value_counts", {})
                lines.append(f"\n### {col_name} (categorical)")
                lines.append(f"  Distinct values ({len(values)} total): {values}")
                if counts:
                    top = list(counts.items())[:5]
                    lines.append(f"  Top values by frequency: {dict(top)}")
            elif sample["type"] == "numeric":
                lines.append(f"\n### {col_name} (numeric)")
                lines.append(f"  Range: {sample.get('min')} to {sample.get('max')}")
                lines.append(f"  Average: {sample.get('avg')}")
                lines.append(f"  Percentiles — P25: {sample.get('p25')}, P50: {sample.get('p50')}, P75: {sample.get('p75')}")
                neg = sample.get("negative_count", 0)
                total = sample.get("total_count", 1)
                if neg:
                    lines.append(f"  WARNING: {neg} negative values found ({neg/total*100:.1f}% of rows)")

        return "\n".join(lines)

    def _render_existing_rules_section(
        self, existing_rules: list[DQRule], table_name: str
    ) -> str:
        relevant = [r for r in existing_rules if r.table_name == table_name]
        if not relevant:
            return ""
        summary = [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "category": r.rule_category.value,
                "column": r.column_name,
            }
            for r in relevant
        ]
        return (
            "## Existing technical rules already generated for this table — DO NOT duplicate\n"
            + json.dumps(summary, indent=2, default=str)
        )

    @staticmethod
    def _render_user_context_section(custom_context: str | None) -> str:
        if not custom_context:
            return ""
        return f"## Additional Business Context (provided by analyst)\n{custom_context}"

    # ------------------------------------------------------------------
    # Parsing & validation
    # ------------------------------------------------------------------

    def _parse_rule(
        self,
        raw: dict[str, Any],
        project: str,
        dataset: str,
        table: str,
        version_id: str,
    ) -> DQRule:
        category_str = (raw.get("rule_category") or "validity").lower()
        severity_str = (raw.get("severity") or "WARN").upper()

        return DQRule(
            rule_id=raw.get("rule_id") or f"BRUL_{uuid.uuid4().hex[:8]}",
            rule_name=raw.get("rule_name", "Unnamed Business Rule"),
            rule_category=_CATEGORY_MAP.get(category_str, RuleCategory.VALIDITY),
            description=raw.get("description", ""),
            severity=_SEVERITY_MAP.get(severity_str, Severity.WARN),
            threshold=float(raw.get("threshold", 0.0)),
            execution_frequency=raw.get("execution_frequency", "daily"),
            project_id=project,
            dataset_name=dataset,
            table_name=table,
            column_name=raw.get("column_name") or None,
            parameters=raw.get("parameters", {}) or {},
            rationale=raw.get("rationale"),
            rule_set_version_id=version_id,
        )

    def _validate_column_refs(self, rule: DQRule, known_columns: set[str]) -> bool:
        bad: list[str] = []

        if rule.column_name and rule.column_name not in known_columns:
            bad.append(rule.column_name)

        fail_cond = rule.parameters.get("fail_condition") if rule.parameters else None
        if isinstance(fail_cond, str):
            for ident in _BACKTICK_IDENT_RE.findall(fail_cond):
                if "." in ident:
                    continue
                if ident not in known_columns:
                    bad.append(ident)

        if bad:
            self._log.warning(
                "rule_dropped_hallucinated_columns",
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                missing_columns=sorted(set(bad)),
            )
            return False
        return True
