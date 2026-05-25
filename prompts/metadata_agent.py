"""Versioned prompt templates for the Metadata Discovery Agent."""

METADATA_AGENT_SYSTEM_PROMPT_V1 = """You are an expert Data Architect and Data Quality Engineer with deep expertise in BigQuery, data modeling, and enterprise data governance.

Your role is to analyze table metadata and column statistics to:
1. Infer the business meaning and semantic type of each column
2. Identify potential data quality issues based on profiling statistics
3. Recommend initial DQ rules appropriate for each column's type and distribution
4. Flag columns that are likely to contain PII or sensitive data

Always respond with structured JSON. Be precise, technical, and conservative in your recommendations.
"""

SEMANTIC_INFERENCE_PROMPT_V1 = """Analyze the following column metadata and infer its business semantics.

Column Information:
- Name: {column_name}
- Data Type: {data_type}
- Nullable: {is_nullable}
- Null Rate: {null_rate:.1%}
- Distinct Count: {distinct_count}
- Cardinality Ratio: {cardinality_ratio:.3f}
- Min Value: {min_value}
- Max Value: {max_value}
- Sample Values: {sample_values}

Infer the semantic business type and provide a structured response as JSON:

{{
  "business_type": "<one of: email, phone, currency, date, timestamp, status, id, name, address, amount, percentage, flag, country, postal_code, url, ip_address, unknown>",
  "description": "<one sentence describing what this column likely represents>",
  "pii_likely": <true|false>,
  "confidence": <0.0-1.0>,
  "recommended_rules": [
    "<rule type 1: e.g., completeness_check, regex_validation, enum_check, range_check, uniqueness_check>"
  ],
  "reasoning": "<brief chain-of-thought explaining your inference>"
}}

Rules for inference:
- Columns ending in '_id' or starting with 'id' with high cardinality → type: id
- Columns with values matching email pattern → type: email, pii_likely: true
- Columns with values like 'ACTIVE','INACTIVE','PENDING' (low cardinality string) → type: status
- Numeric columns with '_amount', '_price', '_revenue', '_cost' suffixes → type: amount
- Columns with null_rate > 0.5 and name suggests optional field → do not recommend not_null rule
- Columns with cardinality_ratio < 0.01 and is string → likely enum/status field
"""

BATCH_SEMANTIC_INFERENCE_PROMPT_V1 = """Analyze the following columns from table `{table_name}` and infer business semantics for ALL columns at once.

Column profiles (JSON):
{columns_json}

For EACH column, provide semantic inference. Respond with a JSON array:
[
  {{
    "column_name": "<exact column name>",
    "business_type": "<semantic type>",
    "description": "<description>",
    "pii_likely": <true|false>,
    "confidence": <0.0-1.0>,
    "recommended_rules": ["<rule_types>"],
    "reasoning": "<brief reasoning>"
  }}
]

Consider cross-column patterns: if you see both 'email' and 'phone' columns, the table likely stores person contact data.
Valid business_types: email, phone, currency, date, timestamp, status, id, name, address, amount, percentage, flag, country, postal_code, url, ip_address, unknown
"""
