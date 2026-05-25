"""
Create and populate `sample_data.loan_applications` in BigQuery.

Run:  python tests/manual/create_loan_applications.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from google.cloud import bigquery

PROJECT = "project-cbc8eabe-34e0-44df-a5e"
DATASET = "sample_data"
TABLE   = "loan_applications"
FULL    = f"`{PROJECT}.{DATASET}.{TABLE}`"

DDL = f"""
CREATE OR REPLACE TABLE {FULL} (
    application_id      INT64       NOT NULL,
    customer_id         INT64       NOT NULL,
    loan_type           STRING      NOT NULL,
    requested_amount    FLOAT64     NOT NULL,
    approved_amount     FLOAT64,
    interest_rate       FLOAT64,
    loan_term_months    INT64,
    application_status  STRING      NOT NULL,
    application_date    DATE        NOT NULL,
    approval_date       DATE,
    disbursement_date   DATE,
    applicant_age       INT64,
    employment_status   STRING,
    annual_income       FLOAT64,
    debt_to_income_ratio FLOAT64,
    collateral_value    FLOAT64,
    risk_grade          STRING,
    loan_officer_id     INT64,
    branch_code         STRING,
    created_at          TIMESTAMP   NOT NULL
)
PARTITION BY application_date
CLUSTER BY loan_type, application_status;
"""

# ---------------------------------------------------------------------------
# 1000 rows of mock data using BigQuery SQL arithmetic
#    - ~900 clean rows + ~100 intentional DQ violations
# ---------------------------------------------------------------------------
INSERT_SQL = f"""
INSERT INTO {FULL} (
    application_id, customer_id, loan_type, requested_amount,
    approved_amount, interest_rate, loan_term_months, application_status,
    application_date, approval_date, disbursement_date,
    applicant_age, employment_status, annual_income,
    debt_to_income_ratio, collateral_value, risk_grade,
    loan_officer_id, branch_code, created_at
)

WITH

-- ─── Seed: 1000 rows, reproducible ───────────────────────────────────────
base AS (
    SELECT
        n,
        FARM_FINGERPRINT(CAST(n AS STRING))         AS h0,
        FARM_FINGERPRINT(CAST(n * 7919 AS STRING))  AS h1,
        FARM_FINGERPRINT(CAST(n * 6271 AS STRING))  AS h2,
        FARM_FINGERPRINT(CAST(n * 3571 AS STRING))  AS h3,
        FARM_FINGERPRINT(CAST(n * 1181 AS STRING))  AS h4
    FROM UNNEST(GENERATE_ARRAY(1, 1000)) AS n
),

-- ─── Lookup arrays ────────────────────────────────────────────────────────
enums AS (
    SELECT
        ['personal','mortgage','auto','business','student'] AS loan_types,
        ['pending','approved','rejected','disbursed','closed','defaulted'] AS statuses,
        ['employed','self_employed','unemployed','retired','student'] AS emp_statuses,
        ['A','B','C','D','E'] AS risk_grades,
        ['BR001','BR002','BR003','BR004','BR005','BR006','BR007','BR008'] AS branches
),

-- ─── Clean base rows (n = 1..900) ────────────────────────────────────────
clean AS (
    SELECT
        b.n                                              AS application_id,
        /* customer_id: 1-30 to match customer_profiles */
        CAST(ABS(MOD(b.h0, 30)) + 1 AS INT64)           AS customer_id,

        e.loan_types[SAFE_OFFSET(ABS(MOD(b.h0, 5)))]    AS loan_type,

        /* requested_amount by type: personal 1k-50k, mortgage 50k-800k,
           auto 5k-60k, business 10k-500k, student 5k-80k  */
        CASE e.loan_types[SAFE_OFFSET(ABS(MOD(b.h0, 5)))]
            WHEN 'personal'  THEN ROUND(1000  + ABS(MOD(b.h1, 49000)),  -2)
            WHEN 'mortgage'  THEN ROUND(50000 + ABS(MOD(b.h1, 750000)), -3)
            WHEN 'auto'      THEN ROUND(5000  + ABS(MOD(b.h1, 55000)),  -2)
            WHEN 'business'  THEN ROUND(10000 + ABS(MOD(b.h1, 490000)), -2)
            ELSE                  ROUND(5000  + ABS(MOD(b.h1, 75000)),  -2)
        END                                              AS requested_amount,

        /* approved_amount: 70–100% of requested, NULL if rejected/pending */
        CASE
            WHEN ABS(MOD(b.h2, 10)) < 2 THEN NULL  -- rejected / pending
            ELSE ROUND(
                CAST((0.70 + 0.30 * ABS(MOD(b.h2, 100)) / 100.0) AS FLOAT64)
                * CASE e.loan_types[SAFE_OFFSET(ABS(MOD(b.h0, 5)))]
                    WHEN 'personal'  THEN ROUND(1000  + ABS(MOD(b.h1, 49000)),  -2)
                    WHEN 'mortgage'  THEN ROUND(50000 + ABS(MOD(b.h1, 750000)), -3)
                    WHEN 'auto'      THEN ROUND(5000  + ABS(MOD(b.h1, 55000)),  -2)
                    WHEN 'business'  THEN ROUND(10000 + ABS(MOD(b.h1, 490000)), -2)
                    ELSE                  ROUND(5000  + ABS(MOD(b.h1, 75000)),  -2)
                END,
            -1)
        END                                              AS approved_amount,

        /* interest_rate: 3.5–28% based on risk */
        ROUND(3.5 + ABS(MOD(b.h3, 245)) / 10.0, 2)     AS interest_rate,

        /* loan_term_months: 6, 12, 24, 36, 48, 60, 84, 120, 180, 240, 360 */
        CASE ABS(MOD(b.h3, 11))
            WHEN 0  THEN 6   WHEN 1  THEN 12  WHEN 2  THEN 24
            WHEN 3  THEN 36  WHEN 4  THEN 48  WHEN 5  THEN 60
            WHEN 6  THEN 84  WHEN 7  THEN 120 WHEN 8  THEN 180
            WHEN 9  THEN 240 ELSE         360
        END                                              AS loan_term_months,

        e.statuses[SAFE_OFFSET(ABS(MOD(b.h2, 6)))]      AS application_status,

        DATE_ADD(DATE '2023-01-01', INTERVAL CAST(ABS(MOD(b.h4, 700)) AS INT64) DAY)
                                                         AS application_date,

        /* approval_date: 1–14 days after application, NULL if pending/rejected */
        CASE
            WHEN ABS(MOD(b.h2, 6)) IN (0,2) THEN NULL  -- pending or rejected
            ELSE DATE_ADD(
                DATE_ADD(DATE '2023-01-01', INTERVAL CAST(ABS(MOD(b.h4, 700)) AS INT64) DAY),
                INTERVAL CAST(ABS(MOD(b.h1, 14)) + 1 AS INT64) DAY
            )
        END                                              AS approval_date,

        /* disbursement_date: 1–7 days after approval, only for disbursed/closed/defaulted */
        CASE
            WHEN ABS(MOD(b.h2, 6)) IN (3, 4, 5)
            THEN DATE_ADD(
                DATE_ADD(DATE '2023-01-01', INTERVAL CAST(ABS(MOD(b.h4, 700)) AS INT64) DAY),
                INTERVAL CAST(ABS(MOD(b.h1, 14)) + 1 + ABS(MOD(b.h0, 7)) + 1 AS INT64) DAY
            )
            ELSE NULL
        END                                              AS disbursement_date,

        /* applicant_age: 21–70 (valid) */
        CAST(21 + ABS(MOD(b.h0, 50)) AS INT64)          AS applicant_age,

        e.emp_statuses[SAFE_OFFSET(ABS(MOD(b.h1, 5)))]  AS employment_status,

        /* annual_income: $15k–$350k */
        ROUND(15000 + ABS(MOD(b.h2, 335000)), -2)       AS annual_income,

        /* DTI: 0.05–0.55 (healthy range) */
        ROUND(0.05 + ABS(MOD(b.h3, 50)) / 100.0, 3)    AS debt_to_income_ratio,

        /* collateral_value: only for mortgage and auto */
        CASE e.loan_types[SAFE_OFFSET(ABS(MOD(b.h0, 5)))]
            WHEN 'mortgage' THEN ROUND(60000 + ABS(MOD(b.h2, 900000)), -3)
            WHEN 'auto'     THEN ROUND(6000  + ABS(MOD(b.h3, 60000)),  -2)
            ELSE NULL
        END                                              AS collateral_value,

        /* risk_grade A–E based on credit proxy */
        e.risk_grades[SAFE_OFFSET(ABS(MOD(b.h3, 5)))]   AS risk_grade,

        CAST(100 + ABS(MOD(b.h4, 20)) AS INT64)         AS loan_officer_id,
        e.branches[SAFE_OFFSET(ABS(MOD(b.h4, 8)))]      AS branch_code,

        TIMESTAMP_ADD(
            TIMESTAMP '2023-01-01 08:00:00',
            INTERVAL CAST(ABS(MOD(b.h0, 50000000)) AS INT64) SECOND
        )                                                AS created_at

    FROM base b, enums e
    WHERE b.n BETWEEN 1 AND 900
),

-- ─── Dirty rows (n = 901..1000) — intentional DQ violations ──────────────
dirty AS (
    SELECT
        /* ① Duplicate application_ids — reuse IDs from clean rows */
        CASE
            WHEN b.n BETWEEN 901 AND 910 THEN CAST(ABS(MOD(b.h0, 50)) + 1 AS INT64)   -- dup IDs
            ELSE b.n
        END                                              AS application_id,

        CAST(ABS(MOD(b.h0, 30)) + 1 AS INT64)           AS customer_id,

        /* ② Invalid loan_type */
        CASE
            WHEN b.n BETWEEN 911 AND 915 THEN 'crypto_loan'   -- not in allowed values
            WHEN b.n BETWEEN 916 AND 918 THEN 'PERSONAL'      -- wrong case
            ELSE e.loan_types[SAFE_OFFSET(ABS(MOD(b.h0, 5)))]
        END                                              AS loan_type,

        /* ③ Negative requested_amount */
        CASE
            WHEN b.n BETWEEN 919 AND 923 THEN -5000.0          -- negative amount
            WHEN b.n BETWEEN 924 AND 926 THEN 0.0              -- zero amount
            ELSE ROUND(1000 + ABS(MOD(b.h1, 49000)), -2)
        END                                              AS requested_amount,

        /* ④ approved_amount > requested_amount (business rule violation) */
        CASE
            WHEN b.n BETWEEN 927 AND 935
            THEN ROUND(1000 + ABS(MOD(b.h1, 49000)), -2) * 1.5  -- 50% over requested
            WHEN b.n BETWEEN 936 AND 940 THEN NULL
            ELSE ROUND((0.80 + 0.20 * ABS(MOD(b.h2, 100)) / 100.0)
                       * ROUND(1000 + ABS(MOD(b.h1, 49000)), -2), -1)
        END                                              AS approved_amount,

        /* ⑤ Invalid interest rates */
        CASE
            WHEN b.n BETWEEN 941 AND 945 THEN -2.5            -- negative rate
            WHEN b.n BETWEEN 946 AND 948 THEN 95.0            -- impossibly high
            ELSE ROUND(3.5 + ABS(MOD(b.h3, 245)) / 10.0, 2)
        END                                              AS interest_rate,

        CASE ABS(MOD(b.h3, 11))
            WHEN 0  THEN 6   WHEN 1  THEN 12  WHEN 2  THEN 24
            WHEN 3  THEN 36  WHEN 4  THEN 48  WHEN 5  THEN 60
            WHEN 6  THEN 84  WHEN 7  THEN 120 WHEN 8  THEN 180
            WHEN 9  THEN 240 ELSE         360
        END                                              AS loan_term_months,

        /* ⑥ Invalid status values */
        CASE
            WHEN b.n BETWEEN 949 AND 952 THEN 'APPROVED'       -- wrong case
            WHEN b.n BETWEEN 953 AND 955 THEN 'under_review'   -- not in enum
            ELSE e.statuses[SAFE_OFFSET(ABS(MOD(b.h2, 6)))]
        END                                              AS application_status,

        DATE_ADD(DATE '2023-01-01', INTERVAL CAST(ABS(MOD(b.h4, 700)) AS INT64) DAY)
                                                         AS application_date,

        /* ⑦ approval_date BEFORE application_date (temporal logic error) */
        CASE
            WHEN b.n BETWEEN 956 AND 962
            THEN DATE_SUB(
                DATE_ADD(DATE '2023-01-01', INTERVAL CAST(ABS(MOD(b.h4, 700)) AS INT64) DAY),
                INTERVAL 10 DAY
            )
            ELSE DATE_ADD(
                DATE_ADD(DATE '2023-01-01', INTERVAL CAST(ABS(MOD(b.h4, 700)) AS INT64) DAY),
                INTERVAL CAST(ABS(MOD(b.h1, 14)) + 1 AS INT64) DAY
            )
        END                                              AS approval_date,

        NULL                                             AS disbursement_date,

        /* ⑧ Underage applicants */
        CASE
            WHEN b.n BETWEEN 963 AND 968 THEN CAST(14 + ABS(MOD(b.h0, 4)) AS INT64)  -- 14–17
            ELSE CAST(21 + ABS(MOD(b.h0, 50)) AS INT64)
        END                                              AS applicant_age,

        e.emp_statuses[SAFE_OFFSET(ABS(MOD(b.h1, 5)))]  AS employment_status,

        /* ⑨ Negative income */
        CASE
            WHEN b.n BETWEEN 969 AND 973 THEN -25000.0         -- negative income
            ELSE ROUND(15000 + ABS(MOD(b.h2, 335000)), -2)
        END                                              AS annual_income,

        /* ⑩ DTI > 1.0 (impossible — debt exceeds income) */
        CASE
            WHEN b.n BETWEEN 974 AND 979 THEN ROUND(1.1 + ABS(MOD(b.h3, 100)) / 100.0, 3)
            ELSE ROUND(0.05 + ABS(MOD(b.h3, 50)) / 100.0, 3)
        END                                              AS debt_to_income_ratio,

        NULL                                             AS collateral_value,

        /* ⑪ Missing risk_grade for approved/disbursed loans (should be required) */
        CASE
            WHEN b.n BETWEEN 980 AND 990 THEN NULL             -- approved but no risk grade
            ELSE e.risk_grades[SAFE_OFFSET(ABS(MOD(b.h3, 5)))]
        END                                              AS risk_grade,

        CAST(100 + ABS(MOD(b.h4, 20)) AS INT64)         AS loan_officer_id,

        /* ⑫ Invalid branch codes */
        CASE
            WHEN b.n BETWEEN 991 AND 995 THEN 'BRHQ999'        -- not in allowed list
            WHEN b.n BETWEEN 996 AND 998 THEN ''                -- empty string
            ELSE e.branches[SAFE_OFFSET(ABS(MOD(b.h4, 8)))]
        END                                              AS branch_code,

        TIMESTAMP_ADD(
            TIMESTAMP '2023-01-01 08:00:00',
            INTERVAL CAST(ABS(MOD(b.h0, 50000000)) AS INT64) SECOND
        )                                                AS created_at

    FROM base b, enums e
    WHERE b.n BETWEEN 901 AND 1000
)

SELECT * FROM clean
UNION ALL
SELECT * FROM dirty;
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT)

    print(f"Creating table {PROJECT}.{DATASET}.{TABLE} …")
    ddl_job = client.query(DDL)
    ddl_job.result()
    print("  Table created.")

    print("Inserting 1,000 rows (900 clean + 100 with intentional DQ violations) …")
    ins_job = client.query(INSERT_SQL)
    ins_job.result()
    print(f"  Done. Rows affected: {ins_job.num_dml_affected_rows}")

    # Quick sanity check
    count_sql = f"SELECT COUNT(*) AS n FROM {FULL}"
    rows = list(client.query(count_sql).result())
    print(f"  Total rows in table: {rows[0].n}")
    print()
    print("DQ violations inserted:")
    violations = {
        "① Duplicate application_id (n 901–910)":      "10 rows",
        "② Invalid loan_type (n 911–918)":             "8 rows",
        "③ Negative/zero requested_amount (n 919–926)":"8 rows",
        "④ approved_amount > requested_amount (n 927–935)":"9 rows",
        "⑤ Negative/impossible interest_rate (n 941–948)": "8 rows",
        "⑥ Invalid application_status (n 949–955)":    "7 rows",
        "⑦ approval_date < application_date (n 956–962)":"7 rows",
        "⑧ Underage applicants age 14–17 (n 963–968)": "6 rows",
        "⑨ Negative annual_income (n 969–973)":        "5 rows",
        "⑩ DTI > 1.0 (n 974–979)":                    "6 rows",
        "⑪ NULL risk_grade on approved loans (n 980–990)":"11 rows",
        "⑫ Invalid/empty branch_code (n 991–998)":     "8 rows",
    }
    for desc, count in violations.items():
        print(f"   {desc}: {count}")


if __name__ == "__main__":
    main()
