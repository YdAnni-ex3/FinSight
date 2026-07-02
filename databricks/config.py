# Databricks Free Edition — Medallion Pipeline
# Requires: Unity Catalog enabled (default), an External Location pointing at
# your Azure Blob `raw-statements` container (Catalog → External Locations).
#
# Run setup once via the Databricks workspace UI or Databricks Asset Bundles.
# All paths use the `abfss://` scheme from the external location.

STORAGE_ACCOUNT = "finsight10916e"            # your Azure Storage account name
CONTAINER       = "raw-statements"
EXTERNAL_LOC    = f"abfss://{CONTAINER}@{STORAGE_ACCOUNT}.dfs.core.windows.net"

CATALOG         = "finsight"                  # Unity Catalog name
BRONZE_SCHEMA   = "bronze"
SILVER_SCHEMA   = "silver"
GOLD_SCHEMA     = "gold"
