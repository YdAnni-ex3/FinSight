# Databricks Notebook — Gold Layer
# Applies LLM categorisation to silver transactions, writes the enriched gold
# Delta table, and loads it into the Snowflake FACT_TRANSACTION star schema.
#
# Snowflake connection via the Spark Snowflake connector (JDBC) — no external
# library needed on Databricks; the connector is built-in.

# Databricks notebook source
# COMMAND ----------

# %pip install --quiet openai azure-identity

# COMMAND ----------

import os
from databricks.config import CATALOG, EXTERNAL_LOC, GOLD_SCHEMA, SILVER_SCHEMA
from pyspark.sql import functions as F, types as T
from finsight_common.categorize import categorize_by_rules
from finsight_common.models import Category

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{GOLD_SCHEMA}")

# COMMAND ----------
# Load secrets from Databricks Secret Scope (set up once via the CLI):
#   databricks secrets create-scope --scope finsight
#   databricks secrets put-secret --scope finsight --key snowflake-password --string-value '...'
#   databricks secrets put-secret --scope finsight --key azure-openai-key    --string-value '...'

SNOWFLAKE_OPTS = {
    "sfURL":        f"{dbutils.secrets.get('finsight', 'snowflake-account')}.snowflakecomputing.com",
    "sfUser":       dbutils.secrets.get("finsight", "snowflake-user"),
    "sfPassword":   dbutils.secrets.get("finsight", "snowflake-password"),
    "sfDatabase":   "FINSIGHT",
    "sfSchema":     "ANALYTICS",
    "sfWarehouse":  "COMPUTE_WH",
}

# COMMAND ----------

_valid = {c.value for c in Category}

@F.udf(T.StringType())
def _udf_categorize(description):
    """Rules-based categorization (fast, no LLM quota used at Spark scale)."""
    return categorize_by_rules(description or "").value if description else Category.OTHER.value


# COMMAND ----------

silver = spark.table(f"{CATALOG}.{SILVER_SCHEMA}.transactions")

# Idempotent gold merge: add category column, derive is_outflow.
gold = (
    silver
    .withColumn("category", _udf_categorize(F.col("description")))
    .withColumn("is_outflow", F.col("amount") < 0)
    .withColumn("loaded_at", F.current_timestamp())
)

(
    gold.write
    .format("delta")
    .mode("overwrite")                # replace on full reload; use MERGE for incremental
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.{GOLD_SCHEMA}.categorised_transactions")
)

# COMMAND ----------
# Load gold into Snowflake FACT_TRANSACTION.
# txn_id = source_file + row number for idempotency.
fact = (
    gold
    .withColumn(
        "txn_id",
        F.concat(F.col("source_file"), F.lit(":"), F.monotonically_increasing_id().cast("string")),
    )
    .withColumn("date_key", F.date_format(F.col("txn_date"), "yyyyMMdd").cast("int"))
    .withColumn(
        "category_key",
        F.when(F.col("category") == Category.INCOME.value, 0)
        .when(F.col("category") == Category.GROCERIES.value, 1)
        .when(F.col("category") == Category.DINING.value, 2)
        .when(F.col("category") == Category.TRANSPORT.value, 3)
        .when(F.col("category") == Category.UTILITIES.value, 4)
        .when(F.col("category") == Category.RENT.value, 5)
        .when(F.col("category") == Category.SHOPPING.value, 6)
        .when(F.col("category") == Category.ENTERTAINMENT.value, 7)
        .when(F.col("category") == Category.HEALTH.value, 8)
        .when(F.col("category") == Category.TRAVEL.value, 9)
        .when(F.col("category") == Category.SUBSCRIPTIONS.value, 10)
        .when(F.col("category") == Category.TRANSFERS.value, 11)
        .when(F.col("category") == Category.FEES.value, 12)
        .otherwise(13)
    )
    .select("txn_id", "date_key", "category_key", "description", "amount", "is_outflow", "currency", "source_file")
)

fact.write.format("snowflake").options(**SNOWFLAKE_OPTS).option("dbtable", "FACT_TRANSACTION").mode("append").save()
print(f"Loaded {fact.count()} rows into SNOWFLAKE.FINSIGHT.ANALYTICS.FACT_TRANSACTION")

# COMMAND ----------
display(spark.table(f"{CATALOG}.{GOLD_SCHEMA}.categorised_transactions").limit(10))
