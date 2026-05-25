-- ============================================================
-- Consolidated DQ Stored Procedure
-- Session   : real_run_9b016663
-- Procedure : `project-cbc8eabe-34e0-44df-a5e.dq_observability.sp_dq_real_run_9b016663`
-- Rules     : 22
-- Generated : 2026-05-19 00:47:40 UTC
--
-- To execute:
--   CALL `project-cbc8eabe-34e0-44df-a5e.dq_observability.sp_dq_real_run_9b016663`('<run_id>');
-- ============================================================

CREATE OR REPLACE PROCEDURE
  `project-cbc8eabe-34e0-44df-a5e.dq_observability.sp_dq_real_run_9b016663`(IN p_run_id STRING)
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
    -- [volume] VOLU_customer_profiles_b89613 — Volume Check: customer_profiles
    -- query_hash: 404cd35bd809a581
    SELECT
      p_run_id AS run_id,
      'VOLU_customer_profiles_b89613' AS rule_id,
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
      '404cd35bd809a581' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [schema_drift] SCHM_customer_profiles_70b083 — Schema Drift: customer_profiles
    -- query_hash: acbcd0fc0a5549c8
    SELECT
      p_run_id AS run_id,
      'SCHM_customer_profiles_70b083' AS rule_id,
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
      'acbcd0fc0a5549c8' AS query_executed,
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

    -- [completeness] COMP_customer_id_86e8e2 — Not Null: customer_id
    -- query_hash: 1246ff6e02b765fd
    SELECT
      p_run_id AS run_id,
      'COMP_customer_id_86e8e2' AS rule_id,
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
      '1246ff6e02b765fd' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`customer_id` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [uniqueness] UNIQ_customer_id_35e854 — Uniqueness: customer_id
    -- query_hash: d649fc26232048b8
    SELECT
      p_run_id AS run_id,
      'UNIQ_customer_id_35e854' AS rule_id,
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
      'd649fc26232048b8' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNT(DISTINCT `customer_id`) AS distinct_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_first_name_d95d35 — Not Null: first_name
    -- query_hash: 936836f136e6f7c6
    SELECT
      p_run_id AS run_id,
      'COMP_first_name_d95d35' AS rule_id,
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
      '936836f136e6f7c6' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`first_name` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [uniqueness] UNIQ_first_name_582ce6 — Uniqueness: first_name
    -- query_hash: ac0d05b7f1ec8f03
    SELECT
      p_run_id AS run_id,
      'UNIQ_first_name_582ce6' AS rule_id,
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
      'ac0d05b7f1ec8f03' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNT(DISTINCT `first_name`) AS distinct_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_last_name_d0b528 — Not Null: last_name
    -- query_hash: b8e0c2ec4ed24199
    SELECT
      p_run_id AS run_id,
      'COMP_last_name_d0b528' AS rule_id,
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
      'b8e0c2ec4ed24199' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`last_name` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [uniqueness] UNIQ_last_name_c63ac8 — Uniqueness: last_name
    -- query_hash: 6c0f372b177b4c30
    SELECT
      p_run_id AS run_id,
      'UNIQ_last_name_c63ac8' AS rule_id,
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
      '6c0f372b177b4c30' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNT(DISTINCT `last_name`) AS distinct_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] VALD_EMAIL_email_05f065 — Email Format: email
    -- query_hash: afb56f3f940affa1
    SELECT
      p_run_id AS run_id,
      'VALD_EMAIL_email_05f065' AS rule_id,
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
      'afb56f3f940affa1' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`email` IS NOT NULL AND NOT REGEXP_CONTAINS(CAST(`email` AS STRING), r'''^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$''')) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_account_status_237aef — Not Null: account_status
    -- query_hash: a297642dfab92915
    SELECT
      p_run_id AS run_id,
      'COMP_account_status_237aef' AS rule_id,
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
      'a297642dfab92915' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`account_status` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] VALD_RANGE_credit_score_cd1f41 — Positive Amount: credit_score
    -- query_hash: f6151158f01b2207
    SELECT
      p_run_id AS run_id,
      'VALD_RANGE_credit_score_cd1f41' AS rule_id,
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
      'f6151158f01b2207' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`credit_score` IS NOT NULL AND (`credit_score` < 0.0)) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] VALD_RANGE_account_balance_83d234 — Positive Amount: account_balance
    -- query_hash: 4c93f4f0d3a8088e
    SELECT
      p_run_id AS run_id,
      'VALD_RANGE_account_balance_83d234' AS rule_id,
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
      '4c93f4f0d3a8088e' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`account_balance` IS NOT NULL AND (`account_balance` < 0.0)) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_country_code_92db40 — Not Null: country_code
    -- query_hash: fde4693ce4493784
    SELECT
      p_run_id AS run_id,
      'COMP_country_code_92db40' AS rule_id,
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
      'fde4693ce4493784' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`country_code` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_created_at_ff3522 — Not Null: created_at
    -- query_hash: fc233c0a7cd3b25b
    SELECT
      p_run_id AS run_id,
      'COMP_created_at_ff3522' AS rule_id,
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
      'fc233c0a7cd3b25b' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`created_at` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [uniqueness] UNIQ_created_at_753a12 — Uniqueness: created_at
    -- query_hash: d4f922f2ef59a085
    SELECT
      p_run_id AS run_id,
      'UNIQ_created_at_753a12' AS rule_id,
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
      'd4f922f2ef59a085' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNT(DISTINCT `created_at`) AS distinct_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [completeness] COMP_updated_at_878313 — Not Null: updated_at
    -- query_hash: 4cb6c12b418d9085
    SELECT
      p_run_id AS run_id,
      'COMP_updated_at_878313' AS rule_id,
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
      '4cb6c12b418d9085' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`updated_at` IS NULL) AS null_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [freshness] FRSH_customer_profiles_d7da04 — Freshness: customer_profiles
    -- query_hash: 25c3884db32c7e5e
    SELECT
      p_run_id AS run_id,
      'FRSH_customer_profiles_d7da04' AS rule_id,
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
      '25c3884db32c7e5e' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(`created_at`), HOUR) AS lag_hours FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] BRUL_c04a9d21 — Logical Age Range Boundary
    -- query_hash: 464e653e3deffe4c
    SELECT
      p_run_id AS run_id,
      'BRUL_c04a9d21' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'date_of_birth' AS column_name,
      'validity' AS rule_type,
      'WARN' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'min=1900-01-01, max=2010-12-31' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '464e653e3deffe4c' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`date_of_birth` IS NOT NULL AND (`date_of_birth` < 1900-01-01 OR `date_of_birth` > 2010-12-31)) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [consistency] BRUL_e9f1a2b8 — Account Audit Timestamp Consistency
    -- query_hash: bd4ee0841375b2f1
    SELECT
      p_run_id AS run_id,
      'BRUL_e9f1a2b8' AS rule_id,
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
      'bd4ee0841375b2f1' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`updated_at` < `created_at`) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] BRUL_d88b4f62 — Valid Account Status Enums
    -- query_hash: a96e1e0d247cfd62
    SELECT
      p_run_id AS run_id,
      'BRUL_d88b4f62' AS rule_id,
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
      'a96e1e0d247cfd62' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`account_status` IS NOT NULL AND `account_status` NOT IN ('ACTIVE', 'PENDING', 'INACTIVE', 'SUSPENDED', 'INACTIVE_30D', 'INACTIVE_90D')) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] BRUL_f3a7c1e5 — Credit Score Range Constraint
    -- query_hash: 6bfbd1210c6e0dc7
    SELECT
      p_run_id AS run_id,
      'BRUL_f3a7c1e5' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'credit_score' AS column_name,
      'validity' AS rule_type,
      'FAIL' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'min=300, max=850' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      '6bfbd1210c6e0dc7' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`credit_score` IS NOT NULL AND (`credit_score` < 300 OR `credit_score` > 850)) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats

    UNION ALL

    -- [validity] BRUL_b4e9d2f1 — Gender Field Normalization
    -- query_hash: f75a9522ca2c4095
    SELECT
      p_run_id AS run_id,
      'BRUL_b4e9d2f1' AS rule_id,
      'project-cbc8eabe-34e0-44df-a5e' AS project_id,
      'sample_data' AS dataset_name,
      'customer_profiles' AS table_name,
      'gender' AS column_name,
      'validity' AS rule_type,
      'INFO' AS severity,
      CASE WHEN SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) <= 0.0 THEN 'PASS' ELSE 'FAIL' END AS status,
      CAST(ROUND(SAFE_DIVIDE(failure_count, NULLIF(total_count, 0)) * 100, 4) AS STRING) AS observed_value,
      'one of 5 allowed values' AS expected_value,
      '0.0' AS threshold_value,
      CAST(failure_count AS INT64) AS failure_count,
      CURRENT_TIMESTAMP() AS execution_time,
      CAST(NULL AS FLOAT64) AS execution_duration_seconds,
      'f75a9522ca2c4095' AS query_executed,
      CAST(NULL AS STRING) AS error_message,
      CURRENT_TIMESTAMP() AS created_at
    FROM (SELECT COUNT(*) AS total_count, COUNTIF(`gender` IS NOT NULL AND `gender` NOT IN ('MALE', 'FEMALE', 'NON-BINARY', 'PREFER_NOT_TO_SAY', 'UNKNOWN')) AS failure_count FROM `project-cbc8eabe-34e0-44df-a5e.sample_data.customer_profiles`) AS stats
  )
  SELECT * FROM dq_run;
END;