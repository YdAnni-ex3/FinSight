# Databricks notebook source
# MAGIC %md
# MAGIC # FinSight Medallion — 01 Bronze (raw ingest)
# MAGIC
# MAGIC Lands raw statement files **as-is** into a Delta table with lineage columns.
# MAGIC No parsing/cleaning here — that's Silver.
# MAGIC
# MAGIC **Source options** (set the `source_path` widget):
# MAGIC - A Unity Catalog **Volume** you upload CSVs to (simplest): `/Volumes/finsight/bronze/landing`
# MAGIC - An **external location** on the Azure Blob `raw-statements` container:
# MAGIC   `abfss://raw-statements@<account>.dfs.core.windows.net/`

# COMMAND ----------

dbutils.widgets.text("catalog", "finsight")
dbutils.widgets.text("source_path", "/Volumes/finsight/bronze/landing")

catalog = dbutils.widgets.get("catalog")
source_path = dbutils.widgets.get("source_path")

# COMMAND ----------

# Create the catalog + medallion schemas (Unity Catalog).
spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
for layer in ("bronze", "silver", "gold"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{layer}")

# A landing volume for uploads (used when source_path points at a Volume).
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.bronze.landing")

# COMMAND ----------

from pyspark.sql import functions as F

# Read every CSV in the source path; keep raw string columns (schema drift friendly).
raw = (
    spark.read.option("header", True).option("inferSchema", False).csv(f"{source_path}/*.csv")
    .withColumn("_source_file", F.col("_metadata.file_name"))
    .withColumn("_ingested_at", F.current_timestamp())
)

(
    raw.write.mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(f"{catalog}.bronze.raw_transactions")
)

print(f"Bronze rows now: {spark.table(f'{catalog}.bronze.raw_transactions').count()}")
display(spark.table(f"{catalog}.bronze.raw_transactions").limit(10))
