# Databricks Notebook — Bronze Layer
# Ingests raw uploaded files from Azure Blob into the Unity Catalog bronze table.
# Attach to a serverless cluster and run interactively, or schedule as a job.
#
# Prerequisite: External Location `finsight_raw` pointing at the
# `raw-statements` blob container (Catalog → External Locations → New).

# Databricks notebook source
# COMMAND ----------

from databricks.config import CATALOG, BRONZE_SCHEMA, EXTERNAL_LOC
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{BRONZE_SCHEMA}")

# COMMAND ----------
# Schema for raw CSV/XLSX rows stored as strings (parse in silver).
BRONZE_SCHEMA_DEF = StructType([
    StructField("_raw_date",        StringType()),
    StructField("_raw_description", StringType()),
    StructField("_raw_debit",       StringType()),
    StructField("_raw_credit",      StringType()),
    StructField("_raw_balance",     StringType()),
    StructField("_source_file",     StringType()),
    StructField("_ingested_at",     TimestampType()),
])

# COMMAND ----------
# Auto-loader: picks up new files incrementally and checkpoints position.
# Change format to "cloudFiles" for production; use "csv" for quick dev.
(
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", f"{EXTERNAL_LOC}/_checkpoints/bronze_schema")
    .option("header", "true")
    .option("inferSchema", "false")
    .load(EXTERNAL_LOC)
    .withColumn("_source_file", F.input_file_name())
    .withColumn("_ingested_at", F.current_timestamp())
    .selectExpr(
        "`Date`        AS _raw_date",
        "`Description` AS _raw_description",
        "`Debit`       AS _raw_debit",
        "`Credit`      AS _raw_credit",
        "`Balance`     AS _raw_balance",
        "_source_file",
        "_ingested_at",
    )
    .writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{EXTERNAL_LOC}/_checkpoints/bronze")
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .toTable(f"{CATALOG}.{BRONZE_SCHEMA}.raw_statements")
)

# COMMAND ----------
display(spark.table(f"{CATALOG}.{BRONZE_SCHEMA}.raw_statements").limit(5))
