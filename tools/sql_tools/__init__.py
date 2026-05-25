"""SQL tooling for the DQ platform.

Public surface:
  - DQSQLGenerator / get_sql_generator: programmatic builder that turns
    DQRule objects into BigQuery SELECT blocks (uniform dq_results shape),
    UNIONs them, and wraps the whole thing in a CREATE OR REPLACE PROCEDURE.
  - validate_sql_syntax / extract_table_references / parameterize_sql:
    lightweight string-level checks.
"""

from tools.sql_tools.sql_generator import (
    DQSQLGenerator,
    RenderedRule,
    get_sql_generator,
)
from tools.sql_tools.validator import (
    extract_table_references,
    parameterize_sql,
    validate_sql_syntax,
)

__all__ = [
    "DQSQLGenerator",
    "RenderedRule",
    "get_sql_generator",
    "extract_table_references",
    "parameterize_sql",
    "validate_sql_syntax",
]
