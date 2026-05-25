"""End-to-end real run.

Runs the *unmocked* pipeline against:
  - real BigQuery (uses GCP_PROJECT_ID / GCP_DATASET_ID from .env)
  - real Gemini API (uses GEMINI_API_KEY)

It exercises:
  1. MetadataDiscoveryAgent  → metadata + profiling + semantics
  2. TechnicalRuleEngineAgent → standard rules (used as anti-context)
  3. BusinessRuleRecommendationAgent → LLM rules with all 6 fixes verified
  4. DQSQLGenerator           → consolidated CREATE OR REPLACE PROCEDURE
  5. BigQuery deploy + CALL  → executes against the source table
  6. Reads dq_results back

Run from repo root:
    python tests/manual/real_run_business_rules.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

# Ensure repo root on sys.path when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from agents.business_dq_agent.agent import BusinessRuleRecommendationAgent
from agents.metadata_agent.agent import MetadataDiscoveryAgent
from agents.technical_dq_agent.agent import TechnicalRuleEngineAgent
from configs.settings import get_settings
from tools.bigquery.client import BigQueryClient
from tools.bigquery.execution import ensure_dq_infrastructure
from tools.sql_tools.sql_generator import get_sql_generator


PROBES = (
    ("table description", "Description: "),
    ("partition info", "Partition column:"),
    ("clustering info", "Clustering:"),
    ("partition_key flag per col", '"partition_key": true'),
    ("clustering_key flag per col", '"clustering_key": true'),
    ("business_type merged", '"business_type"'),
    ("dataplex_pii merged", '"dataplex_pii"'),
    ("anti-context section", "Existing technical rules already generated"),
    ("custom_context section", "## Additional Business Context"),
    ("custom_context payload", "lifetime_value column was deprecated"),
    ("severity guidance", "## severity guidance"),
    ("category enum tightened", "<validity|integrity|consistency>"),
)


async def main() -> None:
    settings = get_settings()
    project = settings.gcp.project_id
    src_dataset = settings.gcp.dataset_id
    dq_dataset = settings.gcp.dq_dataset
    table_name = "customer_profiles"

    print(f"[setup] project={project} src={src_dataset} dq={dq_dataset} table={table_name}")
    print(f"[setup] gemini_model={settings.gemini.model}")
    bq = BigQueryClient(project_id=project)

    # ---------------------------------------------------------------
    # 1. Metadata + profiling + semantics
    # ---------------------------------------------------------------
    print()
    print("[1/6] metadata discovery — schema + profiling + semantic inference (Gemini)")
    md_agent = MetadataDiscoveryAgent(bq)
    discovery = await md_agent.run(
        project_id=project,
        dataset_id=src_dataset,
        table_names=[table_name],
    )
    table_data = discovery["tables"][table_name]
    metadata = table_data["metadata"]
    profiles = table_data["profiling"]
    semantics = table_data["semantics"]
    dataplex_tags = table_data.get("dataplex_tags") or []
    print(
        f"      columns={len(metadata.get('columns', []))} "
        f"profiled={len(profiles.get('columns', []) or [])} "
        f"semantics={len(semantics)} "
        f"dataplex_tags={len(dataplex_tags)}"
    )

    # ---------------------------------------------------------------
    # 2. Technical rules
    # ---------------------------------------------------------------
    print()
    print("[2/6] technical rules")
    tech_agent = TechnicalRuleEngineAgent()
    rule_set_version_id = f"rs_real_{uuid.uuid4().hex[:8]}"
    technical = await tech_agent.run(
        project_id=project,
        dataset_id=src_dataset,
        table_metadata={"tables": {table_name: table_data}},
        column_profiles={},
        column_semantics={},
        rule_set_version_id=rule_set_version_id,
    )
    print(f"      generated {len(technical)} technical rules")

    # ---------------------------------------------------------------
    # 3. Business rules — instrument _call_claude_json to capture the prompt
    # ---------------------------------------------------------------
    print()
    print("[3/6] business rules (Gemini) — capturing the actual prompt sent")
    biz_agent = BusinessRuleRecommendationAgent()
    captured_prompt: dict[str, str] = {}

    original_call = biz_agent._call_claude_json

    async def capturing_call(prompt: str) -> dict:
        captured_prompt["p"] = prompt
        return await original_call(prompt)

    biz_agent._call_claude_json = capturing_call  # type: ignore[assignment]

    business_rules = await biz_agent.run(
        project_id=project,
        dataset_id=src_dataset,
        table_name=table_name,
        metadata=metadata,
        profiles=profiles,
        semantics=semantics,
        rule_set_version_id=rule_set_version_id,
        custom_context=(
            "Note: the lifetime_value column was deprecated 2025-Q4, ignore it for new rules. "
            "Also: customer_status values 'INACTIVE_30D' and 'INACTIVE_90D' are valid states."
        ),
        existing_rules=technical,
        dataplex_tags=dataplex_tags,
    )
    print(f"      generated {len(business_rules)} business rules")
    for r in business_rules[:8]:
        print(f"        - {r.rule_id:24} [{r.rule_category.value:12}] sev={r.severity.value:5} col={r.column_name!r}")

    # Prompt probes
    print()
    print("[3b] prompt content verification — checking 12 expected signals")
    prompt = captured_prompt.get("p", "")
    if not prompt:
        print("      ERROR: no prompt captured")
    else:
        for label, needle in PROBES:
            status = "FOUND " if needle in prompt else "MISSING"
            print(f"      [{status}] {label}: {needle!r}")
        print(f"      prompt_chars={len(prompt)}")

    # Dump the rendered prompt for inspection.
    dump = Path("output/last_business_rule_prompt.txt")
    dump.parent.mkdir(parents=True, exist_ok=True)
    dump.write_text(prompt, encoding="utf-8")
    print(f"      full prompt written to {dump}")

    # ---------------------------------------------------------------
    # 4. SQL render + consolidated procedure
    # ---------------------------------------------------------------
    print()
    print("[4/6] render SQL + build consolidated procedure")
    gen = get_sql_generator(project, dq_dataset)
    all_rules = technical + business_rules
    rendered = sum(1 for r in all_rules if gen.standalone_insert(r))
    print(f"      rules total={len(all_rules)} renderable={rendered}")
    session_id = f"real_run_{uuid.uuid4().hex[:8]}"
    ddl, proc_name, n_in_sp = gen.build_procedure(session_id, all_rules)
    print(f"      sp_name={proc_name} rules_in_sp={n_in_sp} ddl_chars={len(ddl)}")
    Path("output").mkdir(exist_ok=True)
    Path(f"output/{proc_name}.sql").write_text(ddl, encoding="utf-8")
    print(f"      DDL written to output/{proc_name}.sql")

    # ---------------------------------------------------------------
    # 5. Deploy + CALL the procedure
    # ---------------------------------------------------------------
    print()
    print("[5/6] deploy procedure + CALL it against BigQuery")
    await ensure_dq_infrastructure(bq, project, dq_dataset)
    print("      dq_observability dataset + tables ensured")

    await bq.execute_ddl(ddl)
    print(f"      procedure created: `{project}.{dq_dataset}.{proc_name}`")

    run_id = f"run_real_{uuid.uuid4().hex[:8]}"
    print(f"      CALL with run_id={run_id}")
    t0 = time.monotonic()
    await bq.execute_ddl(
        f"CALL `{project}.{dq_dataset}.{proc_name}`('{run_id}')"
    )
    print(f"      CALL completed in {time.monotonic() - t0:.2f}s")

    # ---------------------------------------------------------------
    # 6. Read results back
    # ---------------------------------------------------------------
    print()
    print("[6/6] read dq_results for this run")
    rows = await bq.execute_query(
        f"""
        SELECT rule_id, rule_type, severity, status, observed_value,
               expected_value, failure_count
        FROM `{project}.{dq_dataset}.dq_results`
        WHERE run_id = @run_id
        ORDER BY status DESC, severity, rule_id
        """,
        params={"run_id": run_id},
    )
    print(f"      {len(rows)} result rows")
    fails = 0
    for row in rows:
        marker = "FAIL" if row["status"] == "FAIL" else "PASS"
        if marker == "FAIL":
            fails += 1
        print(
            f"      [{marker}] {row['rule_id']:30} {row['rule_type']:12} "
            f"sev={row['severity']:5} obs={row['observed_value']!s:24} "
            f"exp={row['expected_value']!s:24} failures={row['failure_count']}"
        )
    print()
    print(f"=== SUMMARY: {len(rows)} rules, {len(rows) - fails} PASS, {fails} FAIL ===")

    await bq.close()


if __name__ == "__main__":
    asyncio.run(main())
