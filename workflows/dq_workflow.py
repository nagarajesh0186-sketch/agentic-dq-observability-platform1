"""LangGraph-based stateful DQ workflow definition."""

from __future__ import annotations

from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from agents.orchestrator.agent import OrchestratorAgent
from schemas.models import ApprovalStatus, WorkflowStage, WorkflowState

logger = structlog.get_logger(__name__)


class DQWorkflowInput(TypedDict):
    project_id: str
    dataset_id: str
    table_names: list[str]


class DQWorkflowOutput(TypedDict):
    session_id: str
    final_stage: str
    health_score: float
    errors: list[dict[str, Any]]


def build_dq_workflow() -> StateGraph:
    """Build the LangGraph state machine for the DQ workflow."""
    orchestrator = OrchestratorAgent()
    graph = StateGraph(dict)

    # Node functions
    async def node_init(state: dict) -> dict:
        workflow_state = await orchestrator.start_workflow(
            project_id=state["project_id"],
            dataset_id=state["dataset_id"],
            table_names=state["table_names"],
        )
        state["workflow_state"] = workflow_state
        state["session_id"] = workflow_state.session_id
        return state

    async def node_metadata_discovery(state: dict) -> dict:
        ws: WorkflowState = state["workflow_state"]
        ws = await orchestrator.run_stage_metadata_discovery(ws)
        state["workflow_state"] = ws
        return state

    async def node_technical_rules(state: dict) -> dict:
        ws: WorkflowState = state["workflow_state"]
        ws = await orchestrator.run_stage_technical_rules(ws)
        state["workflow_state"] = ws
        return state

    async def node_business_rules(state: dict) -> dict:
        ws: WorkflowState = state["workflow_state"]
        ws = await orchestrator.run_stage_business_rules(ws)
        state["workflow_state"] = ws
        return state

    async def node_approval_1_checkpoint(state: dict) -> dict:
        ws: WorkflowState = state["workflow_state"]
        approval_request = await orchestrator.create_approval_checkpoint_1(ws)
        state["approval_1_request"] = approval_request
        state["awaiting_approval"] = "approval_1"
        logger.info(
            "approval_1_requested",
            session_id=ws.session_id,
            approval_id=approval_request.get("approval_id"),
        )
        return state

    async def node_sql_generation(state: dict) -> dict:
        ws: WorkflowState = state["workflow_state"]
        ws = await orchestrator.run_stage_sql_generation(ws)
        state["workflow_state"] = ws
        return state

    async def node_monitoring_config(state: dict) -> dict:
        ws: WorkflowState = state["workflow_state"]
        ws = await orchestrator.run_stage_monitoring_config(ws)
        state["workflow_state"] = ws
        return state

    async def node_reporting(state: dict) -> dict:
        ws: WorkflowState = state["workflow_state"]
        ws = await orchestrator.run_stage_reporting(ws)
        state["workflow_state"] = ws
        return state

    # Edge conditions
    def should_proceed_after_metadata(state: dict) -> str:
        ws: WorkflowState = state.get("workflow_state")
        if not ws or not ws.metadata:
            return "error"
        return "technical_rules"

    def should_proceed_after_approval_1(state: dict) -> str:
        ws: WorkflowState = state.get("workflow_state")
        if not ws:
            return END
        if ws.approval_1_status == ApprovalStatus.APPROVED:
            return "sql_generation"
        elif ws.approval_1_status == ApprovalStatus.REJECTED:
            return END
        return "awaiting_approval_1"

    # Build graph
    graph.add_node("init", node_init)
    graph.add_node("metadata_discovery", node_metadata_discovery)
    graph.add_node("technical_rules", node_technical_rules)
    graph.add_node("business_rules", node_business_rules)
    graph.add_node("approval_1_checkpoint", node_approval_1_checkpoint)
    graph.add_node("sql_generation", node_sql_generation)
    graph.add_node("monitoring_config", node_monitoring_config)
    graph.add_node("reporting", node_reporting)

    graph.set_entry_point("init")
    graph.add_edge("init", "metadata_discovery")
    graph.add_conditional_edges(
        "metadata_discovery",
        should_proceed_after_metadata,
        {"technical_rules": "technical_rules", "error": END},
    )
    graph.add_edge("technical_rules", "business_rules")
    graph.add_edge("business_rules", "approval_1_checkpoint")
    graph.add_conditional_edges(
        "approval_1_checkpoint",
        should_proceed_after_approval_1,
        {
            "sql_generation": "sql_generation",
            "awaiting_approval_1": END,
            END: END,
        },
    )
    graph.add_edge("sql_generation", "monitoring_config")
    graph.add_edge("monitoring_config", "reporting")
    graph.add_edge("reporting", END)

    return graph


def get_compiled_workflow():
    """Return the compiled LangGraph workflow ready for execution."""
    graph = build_dq_workflow()
    return graph.compile()
