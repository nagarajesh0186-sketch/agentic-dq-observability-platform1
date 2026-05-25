-- ============================================================
-- Consolidated DQ Stored Procedure
-- Session   : real_run_2f082531
-- Procedure : `project-cbc8eabe-34e0-44df-a5e.dq_observability.sp_dq_real_run_2f082531`
-- Rules     : 22
-- Generated : 2026-05-19 00:50:05 UTC
--
-- To execute:
--   CALL `project-cbc8eabe-34e0-44df-a5e.dq_observability.sp_dq_real_run_2f082531`('<run_id>');
-- ============================================================

CREATE OR REPLACE PROCEDURE
  `project-cbc8eabe-34e0-44df-a5e.dq_observability.sp_dq_real_run_2f082531`(IN p_run_id STRING)
BEGIN
  INSERT INTO `project-cbc8eabe-34e0-44df-a5e.dq_observability.dq_results` (
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
  query_executed,
  error_message,
  created_at
  )
  WITH dq_run AS (
    -- [volume] VOLU_customer_profiles_7aac2b — Volume Check: customer_profiles
    -- query_hash: 9880e66b6d04aabc
    SELECT
      p_run_id AS run_id,
      'VOLU_customer_profiles_7aac2b' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      CAST(NULL AS STRING) AS column_name,
      'volume' AS rule_type,
      'WARN' AS severity,
      CASE WHEN total_count >= 15 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(total_count AS STRING) AS observed_value,
      '>= 15 rows' AS expected_value,
      '15' AS threshold_value,
      CAST(0 AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '9880e66b6d04aabc' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [schema_drift] SCHM_customer_profiles_cdd5b4 — Schema Drift: customer_profiles
    -- query_hash: d06481d12691062b
    SELECT
      p_run_id AS run_id,
      'SCHM_customer_profiles_cdd5b4' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      CAST(NULL AS STRING) AS column_name,
      'schema_drift' AS rule_type,
      'WARN' AS severity,
      CASE WHEN failure_count = 0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(failure_count AS STRING) AS observed_value,
      'schema matches baseline' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'd06481d12691062b' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT
          ARRAY_LENGTH(cur_arr) AS total_count,
          ((SELECT COUNT(*) FROM UNNEST(cur_arr) c WHERE c NOT IN UNNEST(base_arr))
           + (SELECT COUNT(*) FROM UNNEST(base_arr) b WHERE b NOT IN UNNEST(cur_arr))) AS failure_count
        FROM (
          SELECT
            ARRAY(SELECT CONCAT(column_name, ':', UPPER(data_type))
                  FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.INFORMATION_SCHEMA.COLUMNS`
                  WHERE table_name = 'customer_profiles'
                  ORDER BY column_name) AS cur_arr,
            ['account_balance:NUMERIC', 'account_status:STRING', 'country_code:STRING', 'created_at:TIMESTAMP', 'credit_score:INT64', 'customer_id:INT64', 'date_of_birth:DATE', 'email:STRING', 'first_name:STRING', 'gender:STRING', 'last_name:STRING', 'phone_number:STRING', 'updated_at:TIMESTAMP'] AS base_arr
        )) AS stats

    UNION ALL

    -- [completeness] COMP_customer_id_3bf08a — Not Null: customer_id
    -- query_hash: b19df2a2b375d08c
    SELECT
      p_run_id AS run_id,
      'COMP_customer_id_3bf08a' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'customer_id' AS column_name,
      'completeness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      '<= 0.0%' AS expected_value,
      '0.0' AS threshold_value,
      CAST(null_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'b19df2a2b375d08c' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`customer_id` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [uniqueness] UNIQ_customer_id_3d2aad — Uniqueness: customer_id
    -- query_hash: 37055cb70b69929b
    SELECT
      p_run_id AS run_id,
      'UNIQ_customer_id_3d2aad' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'customer_id' AS column_name,
      'uniqueness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN total_count = distinct_count THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(total_count - distinct_count AS STRING) AS observed_value,
      '0 duplicates' AS expected_value,
      '0.0' AS threshold_value,
      CAST(total_count - distinct_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '37055cb70b69929b' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNT(DISTINCT `customer_id`) AS distinct_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_first_name_4e74de — Not Null: first_name
    -- query_hash: 396506f37becb9c3
    SELECT
      p_run_id AS run_id,
      'COMP_first_name_4e74de' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'first_name' AS column_name,
      'completeness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      '<= 0.0%' AS expected_value,
      '0.0' AS threshold_value,
      CAST(null_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '396506f37becb9c3' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`first_name` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [uniqueness] UNIQ_first_name_d2d6cb — Uniqueness: first_name
    -- query_hash: f34279e78911c119
    SELECT
      p_run_id AS run_id,
      'UNIQ_first_name_d2d6cb' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'first_name' AS column_name,
      'uniqueness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN total_count = distinct_count THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(total_count - distinct_count AS STRING) AS observed_value,
      '0 duplicates' AS expected_value,
      '0.0' AS threshold_value,
      CAST(total_count - distinct_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'f34279e78911c119' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNT(DISTINCT `first_name`) AS distinct_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_last_name_872f06 — Not Null: last_name
    -- query_hash: d7d3a36da0261e98
    SELECT
      p_run_id AS run_id,
      'COMP_last_name_872f06' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'last_name' AS column_name,
      'completeness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      '<= 0.0%' AS expected_value,
      '0.0' AS threshold_value,
      CAST(null_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'd7d3a36da0261e98' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`last_name` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [uniqueness] UNIQ_last_name_25a8d9 — Uniqueness: last_name
    -- query_hash: 1f03eb2fc097ab7c
    SELECT
      p_run_id AS run_id,
      'UNIQ_last_name_25a8d9' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'last_name' AS column_name,
      'uniqueness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN total_count = distinct_count THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(total_count - distinct_count AS STRING) AS observed_value,
      '0 duplicates' AS expected_value,
      '0.0' AS threshold_value,
      CAST(total_count - distinct_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '1f03eb2fc097ab7c' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNT(DISTINCT `last_name`) AS distinct_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] VALD_EMAIL_email_52e5d6 — Email Format: email
    -- query_hash: 3aaadaab9d5486f1
    SELECT
      p_run_id AS run_id,
      'VALD_EMAIL_email_52e5d6' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'email' AS column_name,
      'validity' AS rule_type,
      'WARN' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.99 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'matches /^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}$/' AS expected_value,
      '0.99' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '3aaadaab9d5486f1' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`email` IS NOT NULL AND NOT REGEXP_CONTAINS(CAST(`email` AS STRING), r'''^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$''')) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_account_status_01d622 — Not Null: account_status
    -- query_hash: da6c8d963f4c2148
    SELECT
      p_run_id AS run_id,
      'COMP_account_status_01d622' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'account_status' AS column_name,
      'completeness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      '<= 0.0%' AS expected_value,
      '0.0' AS threshold_value,
      CAST(null_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'da6c8d963f4c2148' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`account_status` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] VALD_RANGE_credit_score_0c7b90 — Positive Amount: credit_score
    -- query_hash: bbe25c6a7bef12a0
    SELECT
      p_run_id AS run_id,
      'VALD_RANGE_credit_score_0c7b90' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'credit_score' AS column_name,
      'validity' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'min=0.0, max=None' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'bbe25c6a7bef12a0' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`credit_score` IS NOT NULL AND (`credit_score` < 0.0)) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] VALD_RANGE_account_balance_678059 — Positive Amount: account_balance
    -- query_hash: 9f0e016989d7cda6
    SELECT
      p_run_id AS run_id,
      'VALD_RANGE_account_balance_678059' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'account_balance' AS column_name,
      'validity' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'min=0.0, max=None' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '9f0e016989d7cda6' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`account_balance` IS NOT NULL AND (`account_balance` < 0.0)) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_country_code_d37363 — Not Null: country_code
    -- query_hash: 83c9ee5493829494
    SELECT
      p_run_id AS run_id,
      'COMP_country_code_d37363' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'country_code' AS column_name,
      'completeness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      '<= 0.0%' AS expected_value,
      '0.0' AS threshold_value,
      CAST(null_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '83c9ee5493829494' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`country_code` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_created_at_72cf5c — Not Null: created_at
    -- query_hash: 10e60a156422cd2b
    SELECT
      p_run_id AS run_id,
      'COMP_created_at_72cf5c' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'created_at' AS column_name,
      'completeness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      '<= 0.0%' AS expected_value,
      '0.0' AS threshold_value,
      CAST(null_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '10e60a156422cd2b' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`created_at` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [uniqueness] UNIQ_created_at_ac8722 — Uniqueness: created_at
    -- query_hash: db7dce3ad7b7adab
    SELECT
      p_run_id AS run_id,
      'UNIQ_created_at_ac8722' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'created_at' AS column_name,
      'uniqueness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN total_count = distinct_count THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(total_count - distinct_count AS STRING) AS observed_value,
      '0 duplicates' AS expected_value,
      '0.0' AS threshold_value,
      CAST(total_count - distinct_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'db7dce3ad7b7adab' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNT(DISTINCT `created_at`) AS distinct_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_updated_at_0ce2cc — Not Null: updated_at
    -- query_hash: c493e6c91577f82c
    SELECT
      p_run_id AS run_id,
      'COMP_updated_at_0ce2cc' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'updated_at' AS column_name,
      'completeness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(null_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      '<= 0.0%' AS expected_value,
      '0.0' AS threshold_value,
      CAST(null_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'c493e6c91577f82c' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`updated_at` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [freshness] FRSH_customer_profiles_c0aef8 — Freshness: customer_profiles
    -- query_hash: 4996a21ec90b64a9
    SELECT
      p_run_id AS run_id,
      'FRSH_customer_profiles_c0aef8' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'created_at' AS column_name,
      'freshness' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN lag_hours <= 24.0 OR lag_hours IS NULL THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(lag_hours AS STRING) AS observed_value,
      '<= 24.0h' AS expected_value,
      '24.0' AS threshold_value,
      CAST(CASE WHEN lag_hours > 24.0 THEN 1 ELSE 0 END AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '4996a21ec90b64a9' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(`created_at`), HOUR) AS lag_hours FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] BRUL_c7a2b91d — Logical Age Verification
    -- query_hash: 88dad0523491d915
    SELECT
      p_run_id AS run_id,
      'BRUL_c7a2b91d' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'date_of_birth' AS column_name,
      'validity' AS rule_type,
      'WARN' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'min=1900-01-01, max=2010-01-01' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '88dad0523491d915' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`date_of_birth` IS NOT NULL AND (`date_of_birth` < DATE '1900-01-01' OR `date_of_birth` > DATE '2010-01-01')) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [consistency] BRUL_e9f22c4a — Account Modification Consistency
    -- query_hash: 9987bd87222ab891
    SELECT
      p_run_id AS run_id,
      'BRUL_e9f22c4a' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      CAST(NULL AS STRING) AS column_name,
      'consistency' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'updated_at >= created_at' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '9987bd87222ab891' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`updated_at` < `created_at`) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] BRUL_a1b2c3d4 — Valid Account Status Enums
    -- query_hash: 52cdf048f6c87f6e
    SELECT
      p_run_id AS run_id,
      'BRUL_a1b2c3d4' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'account_status' AS column_name,
      'validity' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'one of 6 allowed values' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '52cdf048f6c87f6e' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`account_status` IS NOT NULL AND `account_status` NOT IN ('ACTIVE', 'PENDING', 'INACTIVE', 'SUSPENDED', 'INACTIVE_30D', 'INACTIVE_90D')) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] BRUL_8d7c6b5a — Credit Score Range Constraint
    -- query_hash: b811e335bb48738d
    SELECT
      p_run_id AS run_id,
      'BRUL_8d7c6b5a' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'credit_score' AS column_name,
      'validity' AS rule_type,
      'WARN' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'min=300, max=850' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'b811e335bb48738d' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`credit_score` IS NOT NULL AND (`credit_score` < 300 OR `credit_score` > 850)) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] BRUL_4f5e6d7c — Gender Enum Standardisation
    -- query_hash: 464c9a77f85ffcb6
    SELECT
      p_run_id AS run_id,
      'BRUL_4f5e6d7c' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'gender' AS column_name,
      'validity' AS rule_type,
      'INFO' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'one of 4 allowed values' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '464c9a77f85ffcb6' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`gender` IS NOT NULL AND `gender` NOT IN ('MALE', 'FEMALE', 'OTHER', 'UNKNOWN')) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats
  )
  SELECT * FROM dq_run;
END;