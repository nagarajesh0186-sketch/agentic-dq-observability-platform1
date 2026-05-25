"""
End-to-end example workflow demonstrating the full DQ platform pipeline.

Run with:
    python workflows/example_workflow.py

Requires:
    - .env file with valid GCP credentials and ANTHROPIC_API_KEY
    - BigQuery dataset with sample data
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.logging_config import configure_logging, get_logger
from configs.settings import get_settings

logger = get_logger(__name__)


async def run_example_workflow():
    """Demonstrate a complete DQ workflow for a sample BigQuery table."""
    configure_logging("INFO")
    settings = get_settings()

    # Example configuration — override with your actual values
    project_id = settings.gcp.project_id or "your-gcp-project"
    dataset_id = settings.gcp.dataset_id or "your_dataset"
    table_names = ["customers"]  # Replace with actual table names

    logger.info(
        "example_workflow_start",
        project=project_id,
        dataset=dataset_id,
        tables=table_names,
    )

    # =========================================================
    # STEP 1: Initialize Orchestrator
    # =========================================================
    from agents.orchestrator.agent import OrchestratorAgent
    orchestrator = OrchestratorAgent()

    # =========================================================
    # STEP 2: Start Workflow & Metadata Discovery
    # =========================================================
    print("\n" + "=" * 60)
    print("STAGE 1: Metadata Discovery")
    print("=" * 60)

    state = await orchestrator.start_workflow(project_id, dataset_id, table_names)
    print(f"Session ID: {state.session_id}")

    state = await orchestrator.run_stage_metadata_discovery(state)

    tables_discovered = list(state.metadata.keys())
    print(f"Tables discovered: {tables_discovered}")
    for table_name, table_data in state.metadata.items():
        meta = table_data.get("metadata", {})
        print(f"  {table_name}: {meta.get('row_count', 0):,} rows, {len(meta.get('columns', []))} columns")

    # =========================================================
    # STEP 3: Generate Technical DQ Rules
    # =========================================================
    print("\n" + "=" * 60)
    print("STAGE 2: Technical Rule Generation")
    print("=" * 60)

    state = await orchestrator.run_stage_technical_rules(state)
    tech_rules = state.rule_set.technical_rules if state.rule_set else []
    print(f"Technical rules generated: {len(tech_rules)}")
    for rule in tech_rules[:5]:
        print(f"  [{rule.severity.value}] {rule.rule_name} — {rule.rule_category.value}")

    # =========================================================
    # STEP 4: Generate Business Rules via Claude
    # =========================================================
    print("\n" + "=" * 60)
    print("STAGE 3: Business Rule Inference (Claude)")
    print("=" * 60)

    state = await orchestrator.run_stage_business_rules(state)
    biz_rules = state.rule_set.business_rules if state.rule_set else []
    print(f"Business rules inferred: {len(biz_rules)}")
    for rule in biz_rules[:5]:
        print(f"  [{rule.severity.value}] {rule.rule_name} — {rule.rationale or 'No rationale'}[:100]")

    # =========================================================
    # CHECKPOINT 1: Display Approval Request
    # =========================================================
    print("\n" + "=" * 60)
    print("CHECKPOINT 1: Rule Set Approval Required")
    print("=" * 60)

    approval_request = await orchestrator.create_approval_checkpoint_1(state)
    all_rules = approval_request.get("summary", {}).get("rules", [])
    print(f"Total rules pending approval: {len(all_rules)}")
    print(f"Approval ID: {approval_request.get('approval_id')}")
    print("\nRule Summary by Severity:")
    from collections import Counter
    severity_counts = Counter(r.get("severity") for r in all_rules)
    for sev, count in severity_counts.items():
        print(f"  {sev}: {count}")

    # Simulate auto-approval for demo purposes
    print("\n[DEMO] Auto-approving rule set...")
    from schemas.models import ApprovalStatus
    state = await orchestrator.process_approval_1(
        state=state,
        status=ApprovalStatus.APPROVED,
        approver_id="demo-user@example.com",
        comments="Approved for demonstration workflow",
    )
    print(f"Approval status: {state.approval_1_status.value}")

    # =========================================================
    # STEP 5: SQL Generation
    # =========================================================
    print("\n" + "=" * 60)
    print("STAGE 6: SQL Generation")
    print("=" * 60)

    state = await orchestrator.run_stage_sql_generation(state)
    all_rules_final = state.rule_set.all_rules if state.rule_set else []
    rules_with_sql = sum(1 for r in all_rules_final if r.generated_sql)
    print(f"SQL generated for {rules_with_sql}/{len(all_rules_final)} rules")

    # Show sample SQL for first rule
    first_with_sql = next((r for r in all_rules_final if r.generated_sql), None)
    if first_with_sql:
        print(f"\nSample SQL for rule '{first_with_sql.rule_name}':")
        print("-" * 40)
        print((first_with_sql.generated_sql or "")[:500])
        print("...")

    # =========================================================
    # STEP 6: Monitoring Configuration
    # =========================================================
    print("\n" + "=" * 60)
    print("STAGE 7: Monitoring Configuration")
    print("=" * 60)

    state = await orchestrator.run_stage_monitoring_config(state)
    print(f"Monitoring configured for {len(state.monitoring_config or {})} tables")

    # =========================================================
    # SUMMARY
    # =========================================================
    print("\n" + "=" * 60)
    print("WORKFLOW SUMMARY")
    print("=" * 60)
    print(f"Session ID:         {state.session_id}")
    print(f"Current Stage:      {state.current_stage.value}")
    print(f"Technical Rules:    {len(state.rule_set.technical_rules) if state.rule_set else 0}")
    print(f"Business Rules:     {len(state.rule_set.business_rules) if state.rule_set else 0}")
    print(f"Rules with SQL:     {rules_with_sql}")
    print(f"Errors:             {len(state.errors)}")
    print(f"Approval 1 Status:  {state.approval_1_status.value}")

    if state.errors:
        print("\nErrors encountered:")
        for err in state.errors:
            print(f"  [{err['stage']}] {err['error']}")

    print("\n✓ Example workflow complete.")
    print(f"  To continue: use session_id={state.session_id}")
    print(f"  Next steps: execute SQL via POST /api/v1/sql/execute")

    return state


if __name__ == "__main__":
    asyncio.run(run_example_workflow())
