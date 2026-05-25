"""Unit tests for Airflow DAG generation."""

from __future__ import annotations

import pytest
from tools.airflow.dag_builder import generate_standalone_dag, _safe_task_id


class TestDAGBuilder:
    def test_generate_standalone_dag_basic(self):
        rules = [
            {
                "rule_id": "COMP_001",
                "rule_name": "Not Null Check",
                "severity": "FAIL",
                "generated_sql": "SELECT 1",
            }
        ]
        dag_content = generate_standalone_dag(
            session_id="sess_abc123",
            rules=rules,
            schedule="@daily",
            gcp_project="my-project",
            gcp_dataset="my_dataset",
        )

        assert "dq_pipeline_sess_abc123" in dag_content
        assert "@daily" in dag_content
        assert "my-project" in dag_content
        assert "my_dataset" in dag_content
        assert "from airflow" in dag_content.lower() or "from airflow" in dag_content

    def test_generate_dag_with_multiple_rules(self):
        rules = [
            {"rule_id": f"RULE_{i:03d}", "rule_name": f"Rule {i}", "severity": "WARN", "generated_sql": f"SELECT {i}"}
            for i in range(5)
        ]
        dag_content = generate_standalone_dag(
            session_id="sess_multi",
            rules=rules,
            schedule="0 6 * * *",
            gcp_project="p",
            gcp_dataset="d",
        )
        assert "sess_multi" in dag_content
        assert "0 6 * * *" in dag_content

    def test_safe_task_id_with_special_chars(self):
        task_id = _safe_task_id("RULE-001/test.check")
        assert "/" not in task_id
        assert "." not in task_id
        assert "-" not in task_id
        assert len(task_id) <= 63

    def test_safe_task_id_truncation(self):
        long_id = "a" * 100
        task_id = _safe_task_id(long_id)
        assert len(task_id) <= 63
