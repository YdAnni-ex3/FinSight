# Databricks notebook source
# MAGIC %md
# MAGIC # FinSight Medallion — 03 Gold (star schema)
# MAGIC
# MAGIC Builds the analytics star schema from Silver: `dim_date`, `dim_category`,
# MAGIC `fact_transaction`. Optionally publishes Gold to the **Snowflake** warehouse
# MAGIC so it matches `FINSIGHT.ANALYTICS` used by the app.

# COMMAND ----------

dbutils.widgets.text("catalog", "finsight")
dbutils.widgets.text("publish_to_snowflake", "false")
catalog = dbutils.widgets.get("catalog")

# COMMAND ----------

from pyspark.sql import functions as F

silver = spark.table(f"{catalog}.silver.transactions")

# COMMAND ----------

# dim_date
dim_date = (
    silver.select("txn_date")
    .distinct()
    .where(F.col("txn_date").isNotNull())
    .select(
        F.date_format("txn_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.col("txn_date").alias("full_date"),
        F.year("txn_date").alias("year"),
        F.month("txn_date").alias("month"),
        F.dayofmonth("txn_date").alias("day"),
        F.date_format("txn_date", "MMMM").alias("month_name"),
        F.date_format("txn_date", "EEEE").alias("weekday"),
    )
)
dim_date.write.mode("overwrite").saveAsTable(f"{catalog}.gold.dim_date")

# dim_category
from pyspark.sql import Window

dim_category = (
    silver.select("category")
    .distinct()
    .withColumn("category_key", F.dense_rank().over(Window.orderBy("category")))
    .select("category_key", F.col("category").alias("category_name"))
)
dim_category.write.mode("overwrite").saveAsTable(f"{catalog}.gold.dim_category")

# COMMAND ----------

# fact_transaction (surrogate keys via joins)
fact = (
    silver.withColumn("date_key", F.date_format("txn_date", "yyyyMMdd").cast("int"))
    .join(spark.table(f"{catalog}.gold.dim_category"), silver.category == F.col("category_name"), "left")
    .select(
        F.sha2(F.concat_ws("|", "date_key", "description", "amount", "_source_file"), 256).alias("txn_id"),
        "date_key",
        "category_key",
        "description",
        F.round("amount", 2).alias("amount"),
        "is_outflow",
        F.lit("INR").alias("currency"),
        F.col("_source_file").alias("source_file"),
    )
)
fact.write.mode("overwrite").saveAsTable(f"{catalog}.gold.fact_transaction")
print(f"Gold fact rows: {fact.count()}")
display(spark.table(f"{catalog}.gold.fact_transaction").limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Optional: publish Gold to Snowflake (FINSIGHT.MEDALLION)
# MAGIC Writes the Gold tables into a **separate `MEDALLION` schema** so this batch
# MAGIC pipeline never clobbers the app's real-time `ANALYTICS` tables (different key
# MAGIC conventions). Set the `publish_to_snowflake` widget to `true` and add creds
# MAGIC via Databricks **secrets** (scope `finsight`: `sf_account`, `sf_user`,
# MAGIC `sf_password`).

# COMMAND ----------

# MAGIC %pip install snowflake-connector-python -q

# COMMAND ----------

if dbutils.widgets.get("publish_to_snowflake").lower() == "true":
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas

    conn = snowflake.connector.connect(
        account=dbutils.secrets.get("finsight", "sf_account"),
        user=dbutils.secrets.get("finsight", "sf_user"),
        password=dbutils.secrets.get("finsight", "sf_password"),
        warehouse="COMPUTE_WH",
        database="FINSIGHT",
    )
    conn.cursor().execute("CREATE SCHEMA IF NOT EXISTS FINSIGHT.MEDALLION")
    conn.cursor().execute("USE SCHEMA FINSIGHT.MEDALLION")
    for table, target in [
        ("gold.dim_date", "DIM_DATE"),
        ("gold.dim_category", "DIM_CATEGORY"),
        ("gold.fact_transaction", "FACT_TRANSACTION"),
    ]:
        pdf = spark.table(f"{catalog}.{table}").toPandas()
        write_pandas(conn, pdf, target, auto_create_table=True, overwrite=True, quote_identifiers=False)
        print(f"Wrote {len(pdf)} rows to FINSIGHT.MEDALLION.{target}")
    conn.close()
    print("Published Gold to Snowflake FINSIGHT.MEDALLION.")
else:
    print("Skipped Snowflake publish (set publish_to_snowflake=true to enable).")
