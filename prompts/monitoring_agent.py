"""Versioned prompt templates for the Monitoring Agent."""

MONITORING_SYSTEM_PROMPT_V1 = """You are a Data Reliability Engineer specializing in data observability, SLA management, and anomaly detection for enterprise data platforms.

Your role is to:
1. Analyze DQ run results and table health metrics
2. Recommend monitoring schedules and SLA thresholds
3. Detect anomalies in DQ metrics over time
4. Generate actionable alerts with severity-appropriate escalation paths
5. Compute health scores and trend analysis

Always respond in structured JSON. Base recommendations on actual data patterns observed.
"""

SLA_RECOMMENDATION_PROMPT_V1 = """Based on the following table profile and DQ history, recommend SLA thresholds.

Table: {table_name}
Profile:
- Row Count: {row_count}
- Partition Column: {partition_column}
- Update Frequency (estimated): {update_frequency}
- Business Criticality: {business_criticality}

Historical DQ Results (last 30 days):
{dq_history_json}

Recommend SLA thresholds:

{{
  "freshness_sla_hours": <number>,
  "min_pass_rate_pct": <number 0-100>,
  "health_score_min": <number 0-100>,
  "monitoring_schedule_cron": "<cron expression>",
  "alert_thresholds": {{
    "critical_failure_count_max": <integer>,
    "pass_rate_warn_below_pct": <number>,
    "pass_rate_fail_below_pct": <number>
  }},
  "rationale": {{
    "freshness": "<explanation>",
    "pass_rate": "<explanation>",
    "schedule": "<explanation>"
  }}
}}
"""

ANOMALY_DETECTION_PROMPT_V1 = """Analyze the following DQ metric time series and identify anomalies.

Table: {table_name}
Metric: {metric_name}
Time Series (date, value):
{time_series_json}

Statistical Context:
- Mean: {mean}
- Std Dev: {std_dev}
- Min: {min_val}
- Max: {max_val}
- P5: {p5}
- P95: {p95}

Identify anomalies and respond:

{{
  "anomalies_detected": <true|false>,
  "anomaly_points": [
    {{
      "date": "<ISO date>",
      "value": <number>,
      "expected_range": [<min>, <max>],
      "anomaly_type": "<spike|drop|trend_break|pattern_change>",
      "severity": "<INFO|WARN|FAIL>",
      "explanation": "<why this is anomalous>"
    }}
  ],
  "trend": "<improving|degrading|stable|volatile>",
  "recommendation": "<action to take>"
}}
"""

HEALTH_SCORE_PROMPT_V1 = """Compute an overall health score for the following table based on its DQ results.

Table: {table_name}
DQ Results Summary:
{results_summary_json}

Monitoring Config:
{monitoring_config_json}

Compute a health score (0-100) and categorize:

{{
  "health_score": <number 0-100>,
  "health_grade": "<A|B|C|D|F>",
  "components": {{
    "completeness_score": <0-100>,
    "uniqueness_score": <0-100>,
    "validity_score": <0-100>,
    "freshness_score": <0-100>,
    "volume_score": <0-100>
  }},
  "open_issues": [
    {{
      "rule_id": "<id>",
      "issue": "<description>",
      "severity": "<severity>",
      "impact_on_score": <number>
    }}
  ],
  "trend": "<improving|degrading|stable>",
  "recommended_actions": ["<action 1>", "<action 2>"]
}}

Scoring weights:
- Pass rate: 60%
- Critical failures penalty: -40% proportional
- Freshness SLA compliance: +bonus 10%
- Health grade: A=90-100, B=80-89, C=70-79, D=60-69, F<60
"""
