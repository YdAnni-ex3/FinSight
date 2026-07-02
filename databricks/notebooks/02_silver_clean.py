# Databricks notebook source
# MAGIC %md
# MAGIC # FinSight Medallion — 02 Silver (clean + conform)
# MAGIC
# MAGIC Parses bronze rows into a conformed transaction table: normalized columns,
# MAGIC a single **signed amount** (negative = outflow), PII redaction, rule-based
# MAGIC category, and de-duplication. Mirrors the logic in `finsight_common`.

# COMMAND ----------

dbutils.widgets.text("catalog", "finsight")
catalog = dbutils.widgets.get("catalog")

# COMMAND ----------

import re

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

bronze = spark.table(f"{catalog}.bronze.raw_transactions")


# Case-insensitive column resolver (bank statements vary a lot).
def col_like(df, *names):
    lookup = {c.lower().strip(): c for c in df.columns}
    for n in names:
        if n in lookup:
            return F.col(lookup[n])
    return F.lit(None)


def num(c):
    # strip currency symbols/commas, cast to double
    return F.regexp_replace(c.cast("string"), r"[,\u20b9\s]", "").cast("double")


date_c = col_like(bronze, "date", "txn date", "transaction date", "value date")
desc_c = col_like(bronze, "description", "narration", "details", "particulars")
debit_c = num(col_like(bronze, "debit", "withdrawal"))
credit_c = num(col_like(bronze, "credit", "deposit"))
amount_c = num(col_like(bronze, "amount", "txn amount"))
balance_c = num(col_like(bronze, "balance", "closing balance"))

# signed amount: explicit amount if present, else credit - debit
signed_amount = F.coalesce(amount_c, F.coalesce(credit_c, F.lit(0.0)) - F.coalesce(debit_c, F.lit(0.0)))

# COMMAND ----------

# PII redaction (email/UPI, PAN, Aadhaar, card, phone, long account numbers).
_PII = [
    (re.compile(r"\b[\w.+-]+@[\w.-]+\b"), "<EMAIL>"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "<PAN>"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "<CARD>"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "<AADHAAR>"),
    (re.compile(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b"), "<PHONE>"),
    (re.compile(r"\b\d{9,18}\b"), "<ACCOUNT>"),
]

_RULES = [
    ("income", ("salary", "payroll", "interest credit", "refund", "cashback")),
    ("rent", ("rent", "landlord", "lease")),
    ("groceries", ("grocery", "bigbasket", "dmart", "zepto")),
    ("dining", ("restaurant", "cafe", "swiggy", "zomato", "dominos", "starbucks")),
    ("transport", ("uber", "ola", "fuel", "petrol", "metro", "irctc", "fastag")),
    ("utilities", ("electricity", "water bill", "broadband", "airtel", "jio")),
    ("subscriptions", ("netflix", "spotify", "prime", "subscription", "hotstar")),
    ("shopping", ("amazon", "flipkart", "myntra", "ajio", "shopping")),
    ("health", ("pharmacy", "apollo", "hospital", "clinic", "1mg", "pharmeasy")),
    ("travel", ("makemytrip", "goibibo", "indigo", "hotel", "oyo")),
    ("fees", ("fee", "charge", "penalty", "gst")),
    ("transfers", ("upi", "neft", "imps", "transfer", "atm")),
]


@F.udf(StringType())
def redact(text):
    if not text:
        return text
    for pattern, label in _PII:
        text = pattern.sub(label, text)
    return text


@F.udf(StringType())
def categorize(text):
    low = (text or "").lower()
    for category, keywords in _RULES:
        if any(k in low for k in keywords):
            return category
    return "other"


# COMMAND ----------

silver = (
    bronze.select(
        F.to_date(date_c).alias("txn_date"),
        redact(desc_c.cast("string")).alias("description"),
        signed_amount.alias("amount"),
        balance_c.alias("balance"),
        F.col("_source_file"),
    )
    .where(F.col("txn_date").isNotNull())
    .withColumn("category", categorize(F.col("description")))
    .withColumn("is_outflow", F.col("amount") < 0)
    .dropDuplicates(["txn_date", "description", "amount", "_source_file"])
)

silver.write.mode("overwrite").saveAsTable(f"{catalog}.silver.transactions")
print(f"Silver rows: {silver.count()}")
display(silver.limit(10))
