"""Pydantic v2 data models for the Agentic DQ Observability Platform."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"


class DQStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class RuleCategory(str, Enum):
    COMPLETENESS = "completeness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"
    INTEGRITY = "integrity"
    FRESHNESS = "freshness"
    VOLUME = "volume"
    SCHEMA_DRIFT = "schema_drift"
    CONSISTENCY = "consistency"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class WorkflowStage(str, Enum):
    INIT = "init"
    METADATA_DISCOVERY = "metadata_discovery"
    TECHNICAL_RULES = "technical_rules"
    BUSINESS_RULES = "business_rules"
    RULE_ELICITATION = "rule_elicitation"
    APPROVAL_1 = "approval_1"
    SQL_GENERATION = "sql_generation"
    DAG_INTEGRATION = "dag_integration"
    MONITORING_CONFIG = "monitoring_config"
    APPROVAL_2 = "approval_2"
    REPORTING = "reporting"
    COMPLETE = "complete"


class BusinessType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    CURRENCY = "currency"
    DATE = "date"
    TIMESTAMP = "timestamp"
    STATUS = "status"
    ID = "id"
    NAME = "name"
    ADDRESS = "address"
    AMOUNT = "amount"
    PERCENTAGE = "percentage"
    FLAG = "flag"
    COUNTRY = "country"
    POSTAL_CODE = "postal_code"
    URL = "url"
    IP_ADDRESS = "ip_address"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Column & Table Metadata
# ---------------------------------------------------------------------------


class ColumnProfile(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool = True
    null_rate: float = Field(ge=0.0, le=1.0)
    null_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    distinct_count: int = Field(ge=0)
    cardinality_ratio: float = Field(ge=0.0, le=1.0)
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    avg_value: Optional[float] = None
    sample_values: list[str] = Field(default_factory=list)
    is_partition_key: bool = False
    is_clustering_key: bool = False


class ColumnSemantics(BaseModel):
    column_name: str
    business_type: BusinessType
    description: str
    pii_likely: bool = False
    recommended_rules: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class TableMetadata(BaseModel):
    project_id: str
    dataset_id: str
    table_name: str
    full_table_id: str
    row_count: int = 0
    size_bytes: int = 0
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    partition_column: Optional[str] = None
    partition_type: Optional[str] = None
    clustering_columns: list[str] = Field(default_factory=list)
    columns: list[ColumnProfile] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def set_full_table_id(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "full_table_id" not in values or not values["full_table_id"]:
            values["full_table_id"] = (
                f"{values.get('project_id', '')}"
                f".{values.get('dataset_id', '')}"
                f".{values.get('table_name', '')}"
            )
        return values


# ---------------------------------------------------------------------------
# DQ Rules
# ---------------------------------------------------------------------------


class DQRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    rule_name: str
    rule_category: RuleCategory
    description: str
    severity: Severity
    threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    execution_frequency: str = Field(default="daily")
    project_id: str
    dataset_name: str
    table_name: str
    column_name: Optional[str] = None
    sql_template: Optional[str] = None
    generated_sql: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: Optional[str] = None
    is_active: bool = True
    rule_set_version_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("rule_id")
    @classmethod
    def validate_rule_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rule_id cannot be empty")
        return v.strip()


class DQRuleSet(BaseModel):
    rule_set_version_id: str = Field(default_factory=lambda: f"rs_{uuid.uuid4().hex[:8]}")
    session_id: str
    project_id: str
    dataset_id: str
    table_names: list[str]
    rules: list[DQRule] = Field(default_factory=list)
    technical_rules: list[DQRule] = Field(default_factory=list)
    business_rules: list[DQRule] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    @property
    def all_rules(self) -> list[DQRule]:
        return self.technical_rules + self.business_rules + self.rules


# ---------------------------------------------------------------------------
# DQ Execution Results
# ---------------------------------------------------------------------------


class DQResult(BaseModel):
    run_id: str
    rule_id: str
    project_id: str
    dataset_name: str
    table_name: str
    column_name: Optional[str] = None
    rule_type: str
    severity: Severity
    status: DQStatus
    observed_value: Optional[str] = None
    expected_value: Optional[str] = None
    threshold_value: Optional[str] = None
    failure_count: Optional[int] = None
    execution_time: datetime = Field(default_factory=datetime.utcnow)
    execution_duration_seconds: Optional[float] = None
    query_executed: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DQRunResult(BaseModel):
    run_id: str
    session_id: str
    rule_set_version_id: str
    total_rules: int
    passed: int
    failed: int
    errors: int
    skipped: int
    pass_rate: float
    health_score: float
    results: list[DQResult] = Field(default_factory=list)
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


# ---------------------------------------------------------------------------
# Workflow State
# ---------------------------------------------------------------------------


class WorkflowState(BaseModel):
    session_id: str = Field(default_factory=lambda: f"session_{uuid.uuid4().hex[:12]}")
    current_stage: WorkflowStage = WorkflowStage.INIT
    project_id: str
    dataset_id: str
    table_names: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    profiling: dict[str, Any] = Field(default_factory=dict)
    semantics: dict[str, Any] = Field(default_factory=dict)
    rule_set: Optional[DQRuleSet] = None
    run_results: Optional[DQRunResult] = None
    approval_1_status: ApprovalStatus = ApprovalStatus.PENDING
    approval_2_status: ApprovalStatus = ApprovalStatus.PENDING
    dag_config: Optional[dict[str, Any]] = None
    monitoring_config: Optional[dict[str, Any]] = None
    consolidated_sp_name: Optional[str] = None
    errors: list[dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def advance_stage(self, next_stage: WorkflowStage) -> None:
        self.current_stage = next_stage
        self.updated_at = datetime.utcnow()

    def record_error(self, stage: str, error: str, recoverable: bool = True) -> None:
        self.errors.append(
            {
                "stage": stage,
                "error": error,
                "recoverable": recoverable,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        self.updated_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# Approval & Audit
# ---------------------------------------------------------------------------


class ApprovalRecord(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"appr_{uuid.uuid4().hex[:8]}")
    session_id: str
    stage: str
    status: ApprovalStatus
    approver_id: str
    approver_email: Optional[str] = None
    comments: Optional[str] = None
    rule_set_version_id: Optional[str] = None
    changes_made: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLogEntry(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:8]}")
    session_id: str
    action: str
    actor_id: str
    actor_email: Optional[str] = None
    resource_type: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Monitoring Configuration
# ---------------------------------------------------------------------------


class AlertConfig(BaseModel):
    slack_enabled: bool = False
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    email_enabled: bool = False
    email_recipients: list[str] = Field(default_factory=list)
    min_severity_to_alert: Severity = Severity.WARN
    escalation_rules: dict[str, Any] = Field(default_factory=dict)


class MonitoringConfig(BaseModel):
    session_id: str
    table_name: str
    sla_check_frequency: str = "hourly"
    freshness_lag_max_hours: float = 24.0
    volume_drop_threshold_pct: float = 0.3
    volume_spike_threshold_pct: float = 2.0
    health_score_min: float = 0.8
    alert_config: AlertConfig = Field(default_factory=AlertConfig)
    monitoring_schedule: str = "0 * * * *"
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# DAG Configuration
# ---------------------------------------------------------------------------


class DAGConfig(BaseModel):
    session_id: str
    dag_id: str
    schedule_interval: str = "@daily"
    inject_into_existing: bool = False
    existing_dag_path: Optional[str] = None
    upstream_task: Optional[str] = None
    downstream_task: Optional[str] = None
    dag_content: Optional[str] = None
    deployment_status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Reporting Views
# ---------------------------------------------------------------------------


class ReportingView(BaseModel):
    view_name: str
    view_sql: str
    description: str
    refresh_schedule: Optional[str] = None
    is_materialized: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# API Request / Response Models
# ---------------------------------------------------------------------------


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    message: Optional[str] = None
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)


class DiscoveryRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    dataset_id: str = Field(..., min_length=1)
    table_names: list[str] = Field(..., min_length=1)
    include_profiling: bool = True
    include_semantics: bool = True


class RuleGenerationRequest(BaseModel):
    session_id: str
    include_technical: bool = True
    include_business: bool = True
    custom_context: Optional[str] = None


class ApprovalRequest(BaseModel):
    session_id: str
    stage: str
    status: ApprovalStatus
    approver_id: str
    approver_email: Optional[str] = None
    comments: Optional[str] = None
    rule_modifications: list[dict[str, Any]] = Field(default_factory=list)


class SQLGenerationRequest(BaseModel):
    session_id: str
    output_formats: list[str] = Field(
        default=["bigquery_sql"],
        description="Options: bigquery_sql, stored_procedure, dbt_test, dataplex_auto_dq",
    )


class MonitoringConfigRequest(BaseModel):
    session_id: str
    monitoring_config: MonitoringConfig
