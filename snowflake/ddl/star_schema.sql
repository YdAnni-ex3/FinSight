-- FinSight analytics warehouse: a classic star schema.
-- Run via: python -m uv run python scripts/setup_snowflake.py

CREATE DATABASE IF NOT EXISTS FINSIGHT;
CREATE SCHEMA IF NOT EXISTS FINSIGHT.ANALYTICS;

CREATE TABLE IF NOT EXISTS FINSIGHT.ANALYTICS.DIM_DATE (
    date_key    INT PRIMARY KEY,   -- yyyymmdd
    full_date   DATE,
    year        INT,
    month       INT,
    day         INT,
    month_name  STRING,
    weekday     STRING
);

CREATE TABLE IF NOT EXISTS FINSIGHT.ANALYTICS.DIM_CATEGORY (
    category_key   INT PRIMARY KEY,
    category_name  STRING UNIQUE
);

CREATE TABLE IF NOT EXISTS FINSIGHT.ANALYTICS.FACT_TRANSACTION (
    txn_id       STRING PRIMARY KEY,
    date_key     INT,
    category_key INT,
    description  STRING,
    amount       NUMBER(18,2),      -- signed: negative = outflow
    is_outflow   BOOLEAN,
    currency     STRING,
    source_file  STRING,
    loaded_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Gold-layer convenience view: monthly spend per category.
CREATE OR REPLACE VIEW FINSIGHT.ANALYTICS.VW_MONTHLY_CATEGORY_SPEND AS
SELECT
    d.year,
    d.month,
    c.category_name,
    SUM(CASE WHEN f.is_outflow THEN -f.amount ELSE 0 END) AS total_spend,
    COUNT(*) AS txn_count
FROM FINSIGHT.ANALYTICS.FACT_TRANSACTION f
JOIN FINSIGHT.ANALYTICS.DIM_DATE d ON f.date_key = d.date_key
LEFT JOIN FINSIGHT.ANALYTICS.DIM_CATEGORY c ON f.category_key = c.category_key
GROUP BY d.year, d.month, c.category_name;
