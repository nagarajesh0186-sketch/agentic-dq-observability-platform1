"""Unit tests for SQL builder utilities."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from tools.sql_tools.validator import (
    extract_table_references,
    validate_sql_syntax,
    parameterize_sql,
)


class TestSQLValidator:
    def test_valid_select(self):
        sql = "SELECT * FROM `project.dataset.table` WHERE id = 1"
        is_valid, error = validate_sql_syntax(sql)
        assert is_valid is True
        assert error == ""

    def test_valid_insert(self):
        sql = "INSERT INTO `project.dataset.table` SELECT 1 AS id"
        is_valid, error = validate_sql_syntax(sql)
        assert is_valid is True

    def test_valid_with_clause(self):
        sql = "WITH cte AS (SELECT 1) SELECT * FROM cte"
        is_valid, error = validate_sql_syntax(sql)
        assert is_valid is True

    def test_empty_sql_invalid(self):
        is_valid, error = validate_sql_syntax("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_dangerous_drop_rejected(self):
        sql = "DROP TABLE `project.dataset.table`"
        is_valid, error = validate_sql_syntax(sql)
        assert is_valid is False
        assert "dangerous" in error.lower()

    def test_dangerous_truncate_rejected(self):
        sql = "TRUNCATE TABLE `project.dataset.table`"
        is_valid, error = validate_sql_syntax(sql)
        assert is_valid is False

    def test_mismatched_parens(self):
        sql = "SELECT COUNT( FROM `t`"
        is_valid, error = validate_sql_syntax(sql)
        assert is_valid is False
        assert "parentheses" in error.lower()

    def test_no_statement_keyword_invalid(self):
        sql = "FROM `project.dataset.table` WHERE id = 1"
        is_valid, error = validate_sql_syntax(sql)
        assert is_valid is False


class TestTableReferenceExtraction:
    def test_extract_single_reference(self):
        sql = "SELECT * FROM `project.dataset.table`"
        refs = extract_table_references(sql)
        assert "project.dataset.table" in refs

    def test_extract_multiple_references(self):
        sql = """
        SELECT a.*, b.*
        FROM `proj.ds.table1` a
        JOIN `proj.ds.table2` b ON a.id = b.id
        """
        refs = extract_table_references(sql)
        assert len(refs) == 2

    def test_no_references(self):
        sql = "SELECT 1 AS one"
        refs = extract_table_references(sql)
        assert refs == []


class TestParameterize:
    def test_string_substitution(self):
        sql = "SELECT * FROM t WHERE col = :name"
        result = parameterize_sql(sql, {"name": "test_value"})
        assert "'test_value'" in result

    def test_numeric_substitution(self):
        sql = "SELECT * FROM t WHERE count > :min_count"
        result = parameterize_sql(sql, {"min_count": 100})
        assert "100" in result

    def test_sql_injection_prevented(self):
        sql = "SELECT * FROM t WHERE col = :name"
        result = parameterize_sql(sql, {"name": "'; DROP TABLE t; --"})
        assert "DROP" not in result or "\\'" in result
