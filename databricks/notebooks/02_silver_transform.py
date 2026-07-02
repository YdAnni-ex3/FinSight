# Databricks Notebook — Silver Layer
# Parses typed values from bronze, applies PII redaction, normalises into
# signed amounts, and writes to the silver Delta table.
#
# Runs the same finsight_common parsing + PII logic used in the API, installed
# as a %pip requirement at the top of the notebook (see below).

# Databricks notebook source
# COMMAND ----------

# %pip install --quiet pdfplumber openpyxl pandas presidio-analyzer presidio-anonymizer
# (restart kernel after first install; comment out on subsequent runs)

# COMMAND ----------

from databricks.config import CATALOG, BRONZE_SCHEMA, EXTERNAL_LOC, SILVER_SCHEMA
from pyspark.sql import DataFrame, functions as F, types as T
from finsight_common.pii import redact_text

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SILVER_SCHEMA}")

# COMMAND ----------

@F.udf(T.StringType())
def _udf_redact(text):
    """Spark UDF: PII-redact a description using the same regex as the API."""
    return redact_text(text) if text else text


@F.udf(T.DoubleType())
def _udf_signed_amount(debit, credit):
    """Signed amount: credit = positive (inflow), debit = negative (outflow)."""
    try:
        cr = float(str(credit).replace(",", "")) if credit and str(credit).strip() else 0.0
        dr = float(str(debit).replace(",", "")) if debit and str(debit).strip() else 0.0
        return cr - dr
    except (ValueError, TypeError):
        return None


# COMMAND ----------

bronze: DataFrame = spark.readStream.table(f"{CATALOG}.{BRONZE_SCHEMA}.raw_statements")

silver = (
    bronze
    .filter(F.col("_raw_date").isNotNull() & (F.trim(F.col("_raw_date")) != ""))
    .withColumn("txn_date", F.to_date(F.trim(F.col("_raw_date")), "yyyy-MM-dd"))
    .withColumn("description", _udf_redact(F.trim(F.col("_raw_description"))))
    .withColumn(
        "amount",
        _udf_signed_amount(
            F.when(F.col("_raw_debit") == "", None).otherwise(F.col("_raw_debit")),
            F.when(F.col("_raw_credit") == "", None).otherwise(F.col("_raw_credit")),
        ),
    )
    .withColumn("currency", F.lit("INR"))
    .withColumn("source_file", F.col("_source_file"))
    .withColumn("processed_at", F.current_timestamp())
    .select("txn_date", "description", "amount", "currency", "source_file", "processed_at")
    .filter(F.col("txn_date").isNotNull() & F.col("amount").isNotNull())
)

(
    silver
    .writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{EXTERNAL_LOC}/_checkpoints/silver")
    .trigger(availableNow=True)
    .toTable(f"{CATALOG}.{SILVER_SCHEMA}.transactions")
)

# COMMAND ----------
display(spark.table(f"{CATALOG}.{SILVER_SCHEMA}.transactions").limit(10))
