"""Rules API endpoints — rule generation, retrieval, and management."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from api.middleware.auth import verify_api_key
from api.routers.discovery import _sessions, _get_orchestrator
from schemas.models import APIResponse, DQRule, RuleCategory, RuleGenerationRequest, Severity

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/generate",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger rule generation",
    description="Generate technical and business DQ rules for a session.",
)
async def generate_rules(
    request: RuleGenerationRequest,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    state = _sessions.get(request.session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {request.session_id} not found",
        )

    orchestrator = _get_orchestrator()
    try:
        if request.include_technical:
            state = await orchestrator.run_stage_technical_rules(state)
        if request.include_business:
            state = await orchestrator.run_stage_business_rules(
                state, custom_context=request.custom_context
            )

        _sessions[request.session_id] = state

        all_rules = state.rule_set.all_rules if state.rule_set else []
        return APIResponse(
            success=True,
            data={
                "session_id": request.session_id,
                "stage": state.current_stage.value,
                "total_rules": len(all_rules),
                "technical_rules": len(state.rule_set.technical_rules) if state.rule_set else 0,
                "business_rules": len(state.rule_set.business_rules) if state.rule_set else 0,
                "message": "Rules generated. Submit approval via POST /approvals/submit",
            },
        )
    except Exception as exc:
        logger.error("rule_generation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/{session_id}",
    response_model=APIResponse,
    summary="Get generated rules",
    description="Retrieve all generated DQ rules for a session.",
)
async def get_rules(
    session_id: str,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    state = _sessions.get(session_id)
    if not state or not state.rule_set:
        raise HTTPException(status_code=404, detail=f"No rules found for session {session_id}")

    rules = [
        {
            "rule_id": r.rule_id,
            "rule_name": r.rule_name,
            "source": "business" if r.rule_id.startswith("BRUL_") else "technical",
            "category": r.rule_category.value,
            "severity": r.severity.value,
            "threshold": r.threshold,
            "table": r.table_name,
            "column": r.column_name,
            "description": r.description,
            "rationale": r.rationale,
            "has_sql": bool(r.generated_sql),
            "is_active": r.is_active,
        }
        for r in state.rule_set.all_rules
    ]

    return APIResponse(success=True, data={"session_id": session_id, "rules": rules, "total": len(rules)})


@router.post(
    "/add-custom",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a custom rule",
    description="Add a user-provided SQL rule to the session. The SQL must use @run_id as a named parameter.",
)
async def add_custom_rule(
    body: dict,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    state = _sessions.get(session_id)
    if not state or not state.rule_set:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or has no rule set")

    rule_name = body.get("rule_name", "").strip()
    custom_sql = body.get("custom_sql", "").strip()
    if not rule_name:
        raise HTTPException(status_code=400, detail="rule_name is required")
    if not custom_sql:
        raise HTTPException(status_code=400, detail="custom_sql is required")

    cat_str = body.get("category", "validity").lower()
    sev_str = body.get("severity", "WARN").upper()

    try:
        category = RuleCategory(cat_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {cat_str}")
    try:
        severity = Severity(sev_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {sev_str}")

    from datetime import datetime
    rule = DQRule(
        rule_id=f"CUST_{uuid.uuid4().hex[:8]}",
        rule_name=rule_name,
        rule_category=category,
        description=body.get("description", "User-provided custom rule"),
        severity=severity,
        threshold=float(body.get("threshold", 0.0)),
        project_id=state.project_id,
        dataset_name=state.dataset_id,
        table_name=body.get("table_name", ""),
        column_name=body.get("column_name") or None,
        generated_sql=custom_sql,
        rationale=body.get("rationale"),
        rule_set_version_id=state.rule_set.rule_set_version_id,
        is_active=True,
    )

    state.rule_set.business_rules.append(rule)
    _sessions[session_id] = state

    return APIResponse(
        success=True,
        data={
            "session_id": session_id,
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_name,
            "message": "Custom rule added. It will be included in SQL generation and the consolidated stored procedure.",
        },
    )


@router.post(
    "/llm-generate",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate DQ rule SQL from natural language",
    description="Use the LLM to generate a BigQuery DQ SELECT rule from a natural language description.",
)
async def llm_generate_rule(
    body: dict,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    import json as _json
    from agents.base import BaseAgent

    session_id = body.get("session_id")
    message = body.get("message", "").strip()
    chat_history = body.get("chat_history", [])

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    state = _sessions.get(session_id)
    if not state or not state.rule_set:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or has no rule set")

    project_id = state.project_id
    dataset_id = state.dataset_id
    metadata = state.metadata or {}
    tables = state.table_names or []

    table_schemas: dict = {}
    for tbl in tables:
        tbl_meta = metadata.get(tbl, {})
        if isinstance(tbl_meta, dict):
            cols = tbl_meta.get("columns", tbl_meta.get("schema", []))
            table_schemas[tbl] = cols

    existing_rules = [
        {"rule_name": r.rule_name, "category": r.rule_category.value, "description": r.description}
        for r in state.rule_set.all_rules[:12]
    ]

    system_prompt = f"""You are a BigQuery SQL expert building data quality (DQ) rules for an observability platform.

Generate a DQ check as a single SELECT statement that returns exactly ONE row per run.
The SELECT uses two special placeholders that the platform substitutes at deploy time:
  {{{{run_id_ref}}}}  — the run identifier (string parameter)
  {{{{rule_id}}}}     — the generated rule ID (string literal)

Required column order (18 columns):
  1.  {{{{run_id_ref}}}} AS run_id
  2.  {{{{rule_id}}}} AS rule_id
  3.  '{project_id}' AS project_id
  4.  '{dataset_id}' AS dataset_name
  5.  '<table_name>' AS table_name
  6.  '<column_name or CAST(NULL AS STRING)>' AS column_name
  7.  '<category>' AS rule_type
  8.  '<severity>' AS severity
  9.  <status_expr> AS status
  10. CAST(<metric> AS STRING) AS observed_value
  11. CAST(<expected> AS STRING) AS expected_value
  12. CAST(<threshold> AS STRING) AS threshold_value
  13. CAST(<failure_count> AS INT64) AS failure_count
  14. CURRENT_TIMESTAMP() AS execution_time
  15. CAST(NULL AS FLOAT64) AS execution_duration_seconds
  16. '<short_description>' AS query_executed
  17. CAST(NULL AS STRING) AS error_message
  18. CURRENT_TIMESTAMP() AS created_at

Rules:
- No CTEs at the top level — use subqueries in the FROM clause (required for UNION ALL in stored procs).
- Fully qualify all table references: `{project_id}.{dataset_id}.<table>`.
- Use SAFE_DIVIDE / NULLIF to avoid division-by-zero.
- The SELECT must be UNION-ALL compatible: no standalone semicolons, no BEGIN/END.
- For status: use CASE WHEN <metric exceeds threshold> THEN 'FAIL' ELSE 'PASS' END.

Respond with JSON only:
{{{{
  "sql": "<complete SELECT with {{{{run_id_ref}}}} and {{{{rule_id}}}} placeholders>",
  "rule_name": "<concise snake_case name>",
  "category": "<validity|completeness|uniqueness|integrity|freshness|volume|consistency>",
  "severity": "<FAIL|WARN|INFO>",
  "description": "<one sentence>",
  "table_name": "<table name>",
  "column_name": "<column name or null>",
  "explanation": "<what this checks and why>",
  "clarification_needed": null
}}}}

If you need more information before generating, set clarification_needed to your question and sql to null."""

    schema_ctx = _json.dumps(table_schemas, indent=2, default=str)[:3000]
    existing_ctx = _json.dumps(existing_rules, indent=2)

    conv_lines = [
        f"PROJECT: {project_id}  DATASET: {dataset_id}",
        f"TABLE SCHEMAS:\n{schema_ctx}",
        f"EXISTING RULES (avoid duplicating):\n{existing_ctx}",
        "",
    ]
    for hist_msg in (chat_history or [])[-6:]:
        role = hist_msg.get("role", "user").upper()
        conv_lines.append(f"{role}: {hist_msg.get('content', '')}")
    conv_lines.append(f"USER: {message}")

    full_prompt = "\n".join(conv_lines)

    agent = BaseAgent(agent_name="llm_rule_generator", system_prompt=system_prompt)
    try:
        result = await agent._call_claude_json(full_prompt)
    except Exception as exc:
        logger.error("llm_rule_generation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {exc}")

    return APIResponse(success=True, data=result)


@router.put(
    "/{rule_id}",
    response_model=APIResponse,
    summary="Update a rule",
    description="Update rule properties (severity, threshold, is_active).",
)
async def update_rule(
    rule_id: str,
    update: dict,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    session_id = update.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required in request body")

    state = _sessions.get(session_id)
    if not state or not state.rule_set:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    all_rules = state.rule_set.all_rules
    target = next((r for r in all_rules if r.rule_id == rule_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    from schemas.models import Severity
    from datetime import datetime
    if "severity" in update:
        target.severity = Severity(update["severity"].upper())
    if "threshold" in update:
        target.threshold = float(update["threshold"])
    if "is_active" in update:
        target.is_active = bool(update["is_active"])
    target.updated_at = datetime.utcnow()

    return APIResponse(success=True, data={"rule_id": rule_id, "updated": True}, message="Rule updated")


@router.delete(
    "/{rule_id}",
    response_model=APIResponse,
    summary="Remove a rule",
    description="Mark a rule as inactive.",
)
async def delete_rule(
    rule_id: str,
    session_id: str,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    state = _sessions.get(session_id)
    if not state or not state.rule_set:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    all_rules = state.rule_set.all_rules
    target = next((r for r in all_rules if r.rule_id == rule_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    target.is_active = False
    return APIResponse(success=True, data={"rule_id": rule_id, "deactivated": True})
