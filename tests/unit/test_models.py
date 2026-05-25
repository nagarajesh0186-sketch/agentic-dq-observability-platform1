"""Unit tests for Pydantic v2 models."""

from __future__ import annotations

import pytest
from datetime import datetime
from schemas.models import (
    ApprovalStatus,
    ColumnProfile,
    ColumnSemantics,
    BusinessType,
    DQRule,
    DQRuleSet,
    DQStatus,
    RuleCategory,
    Severity,
    TableMetadata,
    WorkflowStage,
    WorkflowState,
)


class TestEnums:
    def test_severity_values(self):
        assert Severity.FAIL == "FAIL"
        assert Severity.WARN == "WARN"
        assert Severity.INFO == "INFO"

    def test_dq_status_values(self):
        assert DQStatus.PASS == "PASS"
        assert DQStatus.FAIL == "FAIL"
        assert DQStatus.ERROR == "ERROR"
        assert DQStatus.SKIPPED == "SKIPPED"

    def test_rule_category_values(self):
        assert RuleCategory.COMPLETENESS == "completeness"
        assert RuleCategory.UNIQUENESS == "uniqueness"
        assert RuleCategory.FRESHNESS == "freshness"


class TestColumnProfile:
    def test_create_column_profile(self):
        profile = ColumnProfile(
            column_name="email",
            data_type="STRING",
            is_nullable=True,
            null_rate=0.05,
            null_count=50,
            total_count=1000,
            distinct_count=950,
            cardinality_ratio=0.95,
            sample_values=["a@b.com", "c@d.com"],
        )
        assert profile.column_name == "email"
        assert profile.null_rate == 0.05
        assert len(profile.sample_values) == 2

    def test_null_rate_validation(self):
        with pytest.raises(Exception):
            ColumnProfile(
                column_name="test",
                data_type="STRING",
                null_rate=1.5,  # Invalid: > 1.0
                null_count=0,
                total_count=0,
                distinct_count=0,
                cardinality_ratio=0.0,
            )


class TestTableMetadata:
    def test_auto_full_table_id(self):
        meta = TableMetadata(
            project_id="my-project",
            dataset_id="my_dataset",
            table_name="my_table",
            full_table_id="",
        )
        assert meta.full_table_id == "my-project.my_dataset.my_table"

    def test_explicit_full_table_id_preserved(self):
        meta = TableMetadata(
            project_id="my-project",
            dataset_id="my_dataset",
            table_name="my_table",
            full_table_id="custom.full.id",
        )
        assert meta.full_table_id == "custom.full.id"


class TestDQRule:
    def test_create_rule(self):
        rule = DQRule(
            rule_name="Not Null Check",
            rule_category=RuleCategory.COMPLETENESS,
            description="Column must not be null",
            severity=Severity.FAIL,
            threshold=0.0,
            project_id="my-project",
            dataset_name="my_dataset",
            table_name="my_table",
            column_name="email",
        )
        assert rule.rule_name == "Not Null Check"
        assert rule.rule_id  # auto-generated
        assert rule.is_active is True

    def test_rule_id_auto_generated(self):
        rule1 = DQRule(
            rule_name="R1",
            rule_category=RuleCategory.COMPLETENESS,
            description="Test",
            severity=Severity.FAIL,
            threshold=0.0,
            project_id="p",
            dataset_name="d",
            table_name="t",
        )
        rule2 = DQRule(
            rule_name="R2",
            rule_category=RuleCategory.COMPLETENESS,
            description="Test",
            severity=Severity.FAIL,
            threshold=0.0,
            project_id="p",
            dataset_name="d",
            table_name="t",
        )
        assert rule1.rule_id != rule2.rule_id


class TestDQRuleSet:
    def test_all_rules_combines_lists(self):
        tech_rule = DQRule(
            rule_name="Tech Rule",
            rule_category=RuleCategory.COMPLETENESS,
            description="Tech",
            severity=Severity.FAIL,
            threshold=0.0,
            project_id="p",
            dataset_name="d",
            table_name="t",
        )
        biz_rule = DQRule(
            rule_name="Biz Rule",
            rule_category=RuleCategory.VALIDITY,
            description="Biz",
            severity=Severity.WARN,
            threshold=0.0,
            project_id="p",
            dataset_name="d",
            table_name="t",
        )

        rule_set = DQRuleSet(
            session_id="sess_123",
            project_id="p",
            dataset_id="d",
            table_names=["t"],
            technical_rules=[tech_rule],
            business_rules=[biz_rule],
        )

        assert len(rule_set.all_rules) == 2


class TestWorkflowState:
    def test_advance_stage(self):
        state = WorkflowState(
            project_id="p",
            dataset_id="d",
            table_names=["t"],
        )
        state.advance_stage(WorkflowStage.METADATA_DISCOVERY)
        assert state.current_stage == WorkflowStage.METADATA_DISCOVERY

    def test_record_error(self):
        state = WorkflowState(
            project_id="p",
            dataset_id="d",
            table_names=["t"],
        )
        state.record_error("metadata_discovery", "Connection timeout", recoverable=True)
        assert len(state.errors) == 1
        assert state.errors[0]["stage"] == "metadata_discovery"
        assert state.errors[0]["recoverable"] is True
