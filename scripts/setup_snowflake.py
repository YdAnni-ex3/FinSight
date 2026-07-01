"""Create the FinSight Snowflake star schema and seed the category dimension.

Add your Snowflake creds to .env first (FINSIGHT_SNOWFLAKE_*), then:
    python -m uv run python scripts/setup_snowflake.py
"""

from __future__ import annotations

from pathlib import Path

from finsight_common.config import get_settings
from finsight_common.models import Category

_SEED_CATEGORY = (
    "MERGE INTO FINSIGHT.ANALYTICS.DIM_CATEGORY t "
    "USING (SELECT %s AS category_key, %s AS category_name) s ON t.category_key = s.category_key "
    "WHEN NOT MATCHED THEN INSERT (category_key, category_name) "
    "VALUES (s.category_key, s.category_name)"
)


def _statements(ddl: str) -> list[str]:
    # Drop comment lines, then split on ';'.
    body = "\n".join(ln for ln in ddl.splitlines() if not ln.strip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def main() -> None:
    settings = get_settings()
    if not settings.snowflake_configured:
        raise SystemExit("Set FINSIGHT_SNOWFLAKE_ACCOUNT/USER/PASSWORD in .env first.")

    import snowflake.connector

    ddl = Path("snowflake/ddl/star_schema.sql").read_text(encoding="utf-8")

    conn = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        warehouse=settings.snowflake_warehouse,
        role=settings.snowflake_role or None,
    )
    try:
        cur = conn.cursor()
        for stmt in _statements(ddl):
            print(f"-> {stmt.splitlines()[0][:72]}")
            cur.execute(stmt)
        for i, category in enumerate(Category):
            cur.execute(_SEED_CATEGORY, (i, category.value))
        conn.commit()
    finally:
        conn.close()

    print(
        "Snowflake star schema ready: "
        "FINSIGHT.ANALYTICS (DIM_DATE, DIM_CATEGORY, FACT_TRANSACTION)."
    )


if __name__ == "__main__":
    main()
