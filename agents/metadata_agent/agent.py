"""Metadata Discovery Agent — Stage 1 of the DQ workflow."""

from __future__ import annotations

import json
from typing import Any

import structlog

from agents.base import BaseAgent
from prompts.metadata_agent import (
    BATCH_SEMANTIC_INFERENCE_PROMPT_V1,
    METADATA_AGENT_SYSTEM_PROMPT_V1,
)
from tools.bigquery.client import BigQueryClient
from tools.bigquery.schema_discovery import get_table_metadata, profile_table
from tools.dataplex.client import get_dataplex_client

logger = structlog.get_logger(__name__)


class MetadataDiscoveryAgent(BaseAgent):
    """Discovers table metadata, profiles columns, and infers business semantics."""

    def __init__(self, bq_client: BigQueryClient) -> None:
        super().__init__(
            agent_name="MetadataDiscoveryAgent",
            system_prompt=METADATA_AGENT_SYSTEM_PROMPT_V1,
        )
        self._bq_client = bq_client

    async def run(
        self,
        project_id: str,
        dataset_id: str,
        table_names: list[str],
        include_profiling: bool = True,
        include_semantics: bool = True,
    ) -> dict[str, Any]:
        """Execute full metadata discovery for a list of tables."""
        self._log.info(
            "metadata_discovery_start",
            project=project_id,
            dataset=dataset_id,
            tables=table_names,
        )

        results: dict[str, Any] = {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "tables": {},
        }

        for table_name in table_names:
            self._log.info("processing_table", table=table_name)
            table_result = await self._process_table(
                project_id, dataset_id, table_name, include_profiling, include_semantics
            )
            results["tables"][table_name] = table_result

        self._log.info("metadata_discovery_complete", tables_processed=len(table_names))
        return results

    async def _process_table(
        self,
        project: str,
        dataset: str,
        table: str,
        include_profiling: bool,
        include_semantics: bool,
    ) -> dict[str, Any]:
        # Step 1: Fetch structural metadata
        metadata = await get_table_metadata(self._bq_client, project, dataset, table)

        # Step 2: Column profiling
        profiling: dict[str, Any] = {}
        if include_profiling and metadata.get("columns"):
            profiling = await profile_table(
                self._bq_client, project, dataset, table, metadata["columns"]
            )

        # Step 3: Dataplex enrichment (best-effort)
        dataplex_client = get_dataplex_client(project)
        dataplex_tags = await dataplex_client.get_column_tags(project, dataset, table)
        lineage = await dataplex_client.get_lineage(project, dataset, table)

        # Step 4: Semantic inference via Claude
        semantics: dict[str, Any] = {}
        if include_semantics and profiling.get("columns"):
            semantics = await self._infer_semantics(table, profiling["columns"])

        return {
            "metadata": metadata,
            "profiling": profiling,
            "dataplex_tags": dataplex_tags,
            "lineage": lineage,
            "semantics": semantics,
        }

    async def _infer_semantics(
        self, table_name: str, column_profiles: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Use Claude to infer business semantics for all columns."""
        prompt = BATCH_SEMANTIC_INFERENCE_PROMPT_V1.format(
            table_name=table_name,
            columns_json=json.dumps(column_profiles, indent=2, default=str),
        )

        try:
            result = await self._call_claude_json(prompt)
            items = result.get("items", result) if isinstance(result, dict) else result
            if isinstance(items, list):
                return {item["column_name"]: item for item in items if "column_name" in item}
            return {}
        except Exception as exc:
            self._log.error("semantic_inference_failed", error=str(exc))
            return {}
