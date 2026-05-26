"""BigQuery table schemas, DDL statements, and reporting view SQL."""

from __future__ import annotations

from google.cloud import bigquery

# ---------------------------------------------------------------------------
# BigQuery SchemaField definitions
# ---------------------------------------------------------------------------

DQ_RESULTS_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rule_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("dataset_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("column_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("rule_type", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("severity", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("observed_value", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("expected_value", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("threshold_value", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("failure_count", "INT64", mode="NULLABLE"),
    bigquery.SchemaField("execution_time", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("execution_duration_seconds", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("query_executed", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
]

DQ_WORKFLOW_STATE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("current_stage", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("dataset_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("table_names", "STRING", mode="REQUIRED"),  # JSON array
    bigquery.SchemaField("approval_1_status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("approval_2_status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rule_set_version_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("state_json", "JSON", mode="NULLABLE"),
    bigquery.SchemaField("retry_count", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("errors_json", "JSON", mode="NULLABLE"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("completed_at", "TIMESTAMP", mode="NULLABLE"),
]

DQ_RULE_CONFIG_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("rule_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rule_set_version_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rule_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rule_category", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("severity", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("threshold", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("execution_frequency", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("dataset_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("column_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("generated_sql", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("parameters_json", "JSON", mode="NULLABLE"),
    bigquery.SchemaField("rationale", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("is_active", "BOOL", mode="REQUIRED"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
]

DQ_RULE_VERSIONS_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("rule_set_version_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("version_number", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("dataset_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("table_names_json", "JSON", mode="REQUIRED"),
    bigquery.SchemaField("rules_json", "JSON", mode="REQUIRED"),
    bigquery.SchemaField("approval_status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("approved_by", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("approved_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
]

DQ_AUDIT_LOG_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("audit_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("action", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("actor_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("actor_email", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("resource_type", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("resource_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("details_json", "JSON", mode="NULLABLE"),
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
]

DQ_EXECUTION_LOG_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("execution_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rule_set_version_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("total_rules", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("passed", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("failed", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("errors", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("skipped", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("pass_rate", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("health_score", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("completed_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("duration_seconds", "FLOAT64", mode="NULLABLE"),
]

DQ_MONITORING_CONFIG_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("config_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("sla_check_frequency", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("freshness_lag_max_hours", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("volume_drop_threshold_pct", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("volume_spike_threshold_pct", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("health_score_min", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("monitoring_schedule", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("alert_config_json", "JSON", mode="NULLABLE"),
    bigquery.SchemaField("enabled", "BOOL", mode="REQUIRED"),
    bigquery.SchemaField("approval_status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("approved_by", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("approved_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
]

DQ_DAG_SPECS_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("dag_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("table_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("spec_json", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("generated_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
]
    
DQ_TOKEN_USAGE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("usage_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("agent_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("model", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("input_tokens", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("output_tokens", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("total_tokens", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("estimated_cost_usd", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("duration_seconds", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("prompt_preview", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
]

# ---------------------------------------------------------------------------
# Table configuration mapping
# ---------------------------------------------------------------------------

TABLE_SCHEMAS: dict[str, list[bigquery.SchemaField]] = {
    "dq_results": DQ_RESULTS_SCHEMA,
    "dq_workflow_state": DQ_WORKFLOW_STATE_SCHEMA,
    "dq_rule_config": DQ_RULE_CONFIG_SCHEMA,
    "dq_rule_versions": DQ_RULE_VERSIONS_SCHEMA,
    "dq_audit_log": DQ_AUDIT_LOG_SCHEMA,
    "dq_execution_log": DQ_EXECUTION_LOG_SCHEMA,
    "dq_monitoring_config": DQ_MONITORING_CONFIG_SCHEMA,
    "dq_dag_specs": DQ_DAG_SPECS_SCHEMA,
    "dq_token_usage": DQ_TOKEN_USAGE_SCHEMA,
}

# ---------------------------------------------------------------------------
# DDL CREATE TABLE statements
# ---------------------------------------------------------------------------

CREATE_TABLE_SQLS: dict[str, str] = {
    "dq_results": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_results` (
    run_id                      STRING       NOT NULL,
    rule_id                     STRING       NOT NULL,
    project_id                  STRING       NOT NULL,
    dataset_name                STRING       NOT NULL,
    table_name                  STRING       NOT NULL,
    column_name                 STRING,
    rule_type                   STRING       NOT NULL,
    severity                    STRING       NOT NULL,
    status                      STRING       NOT NULL,
    observed_value              STRING,
    expected_value              STRING,
    threshold_value             STRING,
    failure_count               INT64,
    execution_time              TIMESTAMP    NOT NULL,
    execution_duration_seconds  FLOAT64,
    query_executed              STRING,
    error_message               STRING,
    created_at                  TIMESTAMP    NOT NULL
)
PARTITION BY DATE(execution_time)
CLUSTER BY table_name, rule_type, severity;
""",
    "dq_workflow_state": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_workflow_state` (
    session_id          STRING       NOT NULL,
    current_stage       STRING       NOT NULL,
    project_id          STRING       NOT NULL,
    dataset_id          STRING       NOT NULL,
    table_names         STRING       NOT NULL,
    approval_1_status   STRING       NOT NULL,
    approval_2_status   STRING       NOT NULL,
    rule_set_version_id STRING,
    state_json          JSON,
    retry_count         INT64        NOT NULL,
    errors_json         JSON,
    created_at          TIMESTAMP    NOT NULL,
    updated_at          TIMESTAMP    NOT NULL,
    completed_at        TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY session_id, current_stage;
""",
    "dq_rule_config": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_rule_config` (
    rule_id              STRING    NOT NULL,
    rule_set_version_id  STRING    NOT NULL,
    session_id           STRING    NOT NULL,
    rule_name            STRING    NOT NULL,
    rule_category        STRING    NOT NULL,
    description          STRING,
    severity             STRING    NOT NULL,
    threshold            FLOAT64   NOT NULL,
    execution_frequency  STRING    NOT NULL,
    project_id           STRING    NOT NULL,
    dataset_name         STRING    NOT NULL,
    table_name           STRING    NOT NULL,
    column_name          STRING,
    generated_sql        STRING,
    parameters_json      JSON,
    rationale            STRING,
    is_active            BOOL      NOT NULL,
    created_at           TIMESTAMP NOT NULL,
    updated_at           TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY table_name, rule_category, severity;
""",
    "dq_rule_versions": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_rule_versions` (
    rule_set_version_id  STRING    NOT NULL,
    session_id           STRING    NOT NULL,
    version_number       INT64     NOT NULL,
    project_id           STRING    NOT NULL,
    dataset_id           STRING    NOT NULL,
    table_names_json     JSON      NOT NULL,
    rules_json           JSON      NOT NULL,
    approval_status      STRING    NOT NULL,
    approved_by          STRING,
    approved_at          TIMESTAMP,
    created_at           TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY session_id, approval_status;
""",
    "dq_audit_log": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_audit_log` (
    audit_id       STRING    NOT NULL,
    session_id     STRING    NOT NULL,
    action         STRING    NOT NULL,
    actor_id       STRING    NOT NULL,
    actor_email    STRING,
    resource_type  STRING    NOT NULL,
    resource_id    STRING    NOT NULL,
    details_json   JSON,
    timestamp      TIMESTAMP NOT NULL
)
PARTITION BY DATE(timestamp)
CLUSTER BY session_id, action, actor_id;
""",
    "dq_execution_log": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_execution_log` (
    execution_id         STRING    NOT NULL,
    run_id               STRING    NOT NULL,
    session_id           STRING    NOT NULL,
    rule_set_version_id  STRING    NOT NULL,
    total_rules          INT64     NOT NULL,
    passed               INT64     NOT NULL,
    failed               INT64     NOT NULL,
    errors               INT64     NOT NULL,
    skipped              INT64     NOT NULL,
    pass_rate            FLOAT64   NOT NULL,
    health_score         FLOAT64   NOT NULL,
    started_at           TIMESTAMP NOT NULL,
    completed_at         TIMESTAMP,
    duration_seconds     FLOAT64
)
PARTITION BY DATE(started_at)
CLUSTER BY session_id, run_id;
""",
    "dq_monitoring_config": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_monitoring_config` (
    config_id                 STRING    NOT NULL,
    session_id                STRING    NOT NULL,
    table_name                STRING    NOT NULL,
    sla_check_frequency       STRING    NOT NULL,
    freshness_lag_max_hours   FLOAT64   NOT NULL,
    volume_drop_threshold_pct FLOAT64   NOT NULL,
    volume_spike_threshold_pct FLOAT64  NOT NULL,
    health_score_min          FLOAT64   NOT NULL,
    monitoring_schedule       STRING    NOT NULL,
    alert_config_json         JSON,
    enabled                   BOOL      NOT NULL,
    approval_status           STRING    NOT NULL,
    approved_by               STRING,
    approved_at               TIMESTAMP,
    created_at                TIMESTAMP NOT NULL,
    updated_at                TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY table_name, enabled;
""",

"dq_dag_specs": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_dag_specs` (
    session_id    STRING    NOT NULL,
    dag_id        STRING    NOT NULL,
    table_name    STRING,
    spec_json     STRING,
    generated_at  TIMESTAMP,
    created_at    TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY session_id, dag_id;
""",

"dq_token_usage": """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.dq_token_usage` (
    usage_id            STRING    NOT NULL,
    agent_name          STRING    NOT NULL,
    model               STRING    NOT NULL,
    input_tokens        INT64     NOT NULL,
    output_tokens       INT64     NOT NULL,
    total_tokens        INT64     NOT NULL,
    estimated_cost_usd  FLOAT64   NOT NULL,
    duration_seconds    FLOAT64,
    prompt_preview      STRING,
    created_at          TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY agent_name, model;
""",

}

# ---------------------------------------------------------------------------
# Reporting view SQL
# ---------------------------------------------------------------------------

REPORTING_VIEWS: dict[str, str] = {
    "v_dq_executive_kpi": """
CREATE OR REPLACE VIEW `{project}.{dataset}.v_dq_executive_kpi` AS
WITH latest_run AS (
    SELECT
        MAX(execution_time) AS max_execution_time
    FROM `{project}.{dataset}.dq_results`
    WHERE DATE(execution_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
),
run_stats AS (
    SELECT
        r.rule_type,
        r.severity,
        r.status,
        COUNT(*) AS rule_count
    FROM `{project}.{dataset}.dq_results` r
    CROSS JOIN latest_run lr
    WHERE r.execution_time >= lr.max_execution_time - INTERVAL 1 HOUR
    GROUP BY 1, 2, 3
),
kpi AS (
    SELECT
        SUM(rule_count) AS total_checks,
        SUM(CASE WHEN status = 'PASS' THEN rule_count ELSE 0 END) AS passed_checks,
        SUM(CASE WHEN status = 'FAIL' THEN rule_count ELSE 0 END) AS failed_checks,
        SUM(CASE WHEN status = 'FAIL' AND severity = 'FAIL' THEN rule_count ELSE 0 END) AS critical_failures,
        SAFE_DIVIDE(
            SUM(CASE WHEN status = 'PASS' THEN rule_count ELSE 0 END),
            SUM(rule_count)
        ) AS pass_rate
    FROM run_stats
)
SELECT
    total_checks,
    passed_checks,
    failed_checks,
    critical_failures,
    ROUND(pass_rate * 100, 2) AS pass_rate_pct,
    ROUND(
        (pass_rate * 0.6
        + (1 - SAFE_DIVIDE(critical_failures, NULLIF(total_checks, 0))) * 0.4)
        * 100, 2
    ) AS health_score,
    CURRENT_TIMESTAMP() AS report_generated_at
FROM kpi;
""",
    "v_dq_table_health": """
CREATE OR REPLACE VIEW `{project}.{dataset}.v_dq_table_health` AS
WITH latest_runs AS (
    SELECT
        table_name,
        MAX(execution_time) AS last_run_time
    FROM `{project}.{dataset}.dq_results`
    GROUP BY table_name
),
table_stats AS (
    SELECT
        r.table_name,
        COUNT(*) AS total_checks,
        SUM(CASE WHEN r.status = 'PASS' THEN 1 ELSE 0 END) AS passed,
        SUM(CASE WHEN r.status = 'FAIL' THEN 1 ELSE 0 END) AS failed,
        SUM(CASE WHEN r.status = 'FAIL' AND r.severity = 'FAIL' THEN 1 ELSE 0 END) AS critical_failures,
        SAFE_DIVIDE(
            SUM(CASE WHEN r.status = 'PASS' THEN 1 ELSE 0 END),
            COUNT(*)
        ) AS pass_rate,
        lr.last_run_time
    FROM `{project}.{dataset}.dq_results` r
    JOIN latest_runs lr ON r.table_name = lr.table_name
        AND r.execution_time = lr.last_run_time
    GROUP BY r.table_name, lr.last_run_time
)
SELECT
    table_name,
    total_checks,
    passed,
    failed,
    critical_failures,
    ROUND(pass_rate * 100, 2) AS pass_rate_pct,
    ROUND(
        (pass_rate * 0.7 + (1 - SAFE_DIVIDE(critical_failures, NULLIF(total_checks, 0))) * 0.3) * 100,
        2
    ) AS health_score,
    last_run_time,
    TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_run_time, HOUR) AS hours_since_last_run
FROM table_stats
ORDER BY health_score ASC;
""",
    "v_dq_trend_analysis": """
CREATE OR REPLACE VIEW `{project}.{dataset}.v_dq_trend_analysis` AS
SELECT
    DATE(execution_time) AS run_date,
    table_name,
    rule_type,
    severity,
    COUNT(*) AS total_checks,
    SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed,
    SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) AS failed,
    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) AS errors,
    ROUND(
        SAFE_DIVIDE(SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END), COUNT(*)) * 100,
        2
    ) AS pass_rate_pct,
    ROUND(AVG(execution_duration_seconds), 3) AS avg_duration_seconds
FROM `{project}.{dataset}.dq_results`
WHERE DATE(execution_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3, 4
ORDER BY run_date DESC, table_name, rule_type;
""",
    "v_dq_freshness_report": """
CREATE OR REPLACE VIEW `{project}.{dataset}.v_dq_freshness_report` AS
WITH freshness_rules AS (
    SELECT
        table_name,
        run_id,
        execution_time,
        observed_value,
        threshold_value,
        status,
        severity,
        failure_count
    FROM `{project}.{dataset}.dq_results`
    WHERE rule_type = 'freshness'
),
latest_freshness AS (
    SELECT
        table_name,
        MAX(execution_time) AS last_checked_at
    FROM freshness_rules
    GROUP BY table_name
)
SELECT
    fr.table_name,
    fr.execution_time AS last_checked_at,
    fr.observed_value AS current_lag,
    fr.threshold_value AS sla_max_lag_hours,
    fr.status AS sla_status,
    fr.severity,
    CASE
        WHEN fr.status = 'FAIL' THEN 'SLA_BREACH'
        WHEN SAFE_CAST(REGEXP_EXTRACT(fr.observed_value, r'^(\\d+)') AS FLOAT64)
             > SAFE_CAST(fr.threshold_value AS FLOAT64) * 0.8
            THEN 'AT_RISK'
        ELSE 'HEALTHY'
    END AS freshness_health
FROM freshness_rules fr
JOIN latest_freshness lf
    ON fr.table_name = lf.table_name
    AND fr.execution_time = lf.last_checked_at
ORDER BY fr.table_name;
""",
    "v_dq_failed_rules": """
CREATE OR REPLACE VIEW `{project}.{dataset}.v_dq_failed_rules` AS
WITH ranked_failures AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY table_name, rule_id
            ORDER BY execution_time DESC
        ) AS rn
    FROM `{project}.{dataset}.dq_results`
    WHERE status = 'FAIL'
    AND DATE(execution_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
)
SELECT
    run_id,
    rule_id,
    project_id,
    dataset_name,
    table_name,
    column_name,
    rule_type,
    severity,
    status,
    observed_value,
    expected_value,
    threshold_value,
    failure_count,
    execution_time,
    execution_duration_seconds,
    error_message,
    TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), execution_time, HOUR) AS hours_open
FROM ranked_failures
WHERE rn = 1
ORDER BY severity DESC, execution_time DESC;
""",

"v_dq_technical_health": """
CREATE OR REPLACE VIEW `{project}.{dataset}.v_dq_technical_health` AS
WITH latest_run AS (
    SELECT MAX(execution_time) AS max_time
    FROM `{project}.{dataset}.dq_results`
    WHERE DATE(execution_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
),
tech_stats AS (
    SELECT r.table_name, r.rule_type, r.severity, r.status, r.rule_id,
           r.observed_value, r.execution_time, r.failure_count
    FROM `{project}.{dataset}.dq_results` r
    CROSS JOIN latest_run lr
    WHERE r.execution_time >= lr.max_time - INTERVAL 1 HOUR
      AND r.rule_id NOT LIKE 'BRUL_%'
),
summary AS (
    SELECT
        table_name,
        COUNT(*) AS total_checks,
        SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed,
        SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) AS failed,
        SUM(CASE WHEN status = 'FAIL' AND severity = 'FAIL' THEN 1 ELSE 0 END) AS critical_failures,
        ROUND(SAFE_DIVIDE(SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END), COUNT(*)) * 100, 2) AS pass_rate_pct,
        MAX(execution_time) AS last_run_time,
        COUNTIF(rule_type = 'completeness') AS completeness_checks,
        COUNTIF(rule_type = 'uniqueness') AS uniqueness_checks,
        COUNTIF(rule_type = 'validity') AS validity_checks,
        COUNTIF(rule_type = 'freshness') AS freshness_checks,
        COUNTIF(rule_type = 'volume') AS volume_checks,
        COUNTIF(rule_type = 'schema_drift') AS schema_drift_checks
    FROM tech_stats GROUP BY table_name
)
SELECT *, ROUND((SAFE_DIVIDE(passed, NULLIF(total_checks,0))*0.7
    +(1-SAFE_DIVIDE(critical_failures,NULLIF(total_checks,0)))*0.3)*100,2) AS health_score,
    'technical' AS rule_layer
FROM summary ORDER BY pass_rate_pct ASC;
""",

    "v_dq_business_health": """
CREATE OR REPLACE VIEW `{project}.{dataset}.v_dq_business_health` AS
WITH latest_run AS (
    SELECT MAX(execution_time) AS max_time
    FROM `{project}.{dataset}.dq_results`
    WHERE DATE(execution_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
),
biz_stats AS (
    SELECT r.table_name, r.rule_type, r.severity, r.status, r.rule_id,
           r.observed_value, r.execution_time, r.failure_count,
           rc.rule_name
    FROM `{project}.{dataset}.dq_results` r
    CROSS JOIN latest_run lr
    LEFT JOIN (SELECT DISTINCT rule_id, rule_name FROM `{project}.{dataset}.dq_rule_config`) rc
        ON r.rule_id = rc.rule_id
    WHERE r.execution_time >= lr.max_time - INTERVAL 1 HOUR
      AND r.rule_id LIKE 'BRUL_%'
),
summary AS (
    SELECT
        table_name,
        COUNT(*) AS total_checks,
        SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed,
        SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) AS failed,
        SUM(CASE WHEN status = 'FAIL' AND severity = 'FAIL' THEN 1 ELSE 0 END) AS critical_failures,
        ROUND(SAFE_DIVIDE(SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END), COUNT(*)) * 100, 2) AS pass_rate_pct,
        MAX(execution_time) AS last_run_time,
        COUNTIF(rule_type = 'consistency') AS consistency_checks,
        COUNTIF(rule_type = 'validity') AS validity_checks,
        COUNTIF(rule_type = 'integrity') AS integrity_checks
    FROM biz_stats GROUP BY table_name
),
failed_rules AS (
    SELECT table_name,
        STRING_AGG(CONCAT(COALESCE(rule_name, rule_id),' [',severity,']'),', ' LIMIT 5) AS top_failures
    FROM biz_stats WHERE status = 'FAIL' GROUP BY table_name
)
SELECT s.*, f.top_failures,
    ROUND((SAFE_DIVIDE(s.passed,NULLIF(s.total_checks,0))*0.7
        +(1-SAFE_DIVIDE(s.critical_failures,NULLIF(s.total_checks,0)))*0.3)*100,2) AS health_score,
    'business' AS rule_layer
FROM summary s LEFT JOIN failed_rules f ON s.table_name = f.table_name
ORDER BY pass_rate_pct ASC;
""",
}


def get_table_id(project: str, dataset: str, table: str) -> str:
    """Return fully qualified BigQuery table ID."""
    return f"{project}.{dataset}.{table}"


def format_ddl(ddl_template: str, project: str, dataset: str) -> str:
    """Format a DDL template with project and dataset."""
    return ddl_template.format(project=project, dataset=dataset)


def format_view(view_template: str, project: str, dataset: str) -> str:
    """Format a view SQL template with project and dataset."""
    return view_template.format(project=project, dataset=dataset)
