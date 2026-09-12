# src/finalize_gold.py
# Finaliza a tabela gold sem depender do patch.sql
import json
from datetime import datetime
from pathlib import Path

import duckdb
from src.config import DB_PATH, STG_TABLE, GOLD_TABLE

SQL_BUILD_NEW = f"""
CREATE SCHEMA IF NOT EXISTS gold;

CREATE OR REPLACE TABLE gold.sales_clean_new AS
WITH bounds AS (
  SELECT
    quantile_cont(unit_price, 0.01) AS p01,
    quantile_cont(unit_price, 0.99) AS p99
  FROM {STG_TABLE}
  WHERE unit_price IS NOT NULL AND unit_price > 0
),
ranked AS (
  SELECT
    s.*,
    ROW_NUMBER() OVER (
      PARTITION BY s.order_id, s.date_parsed
      ORDER BY
        hash(
          s.order_id,
          s.store_id,
          s.product_id,
          COALESCE(s.customer_id, ''),
          COALESCE(s.channel_norm, ''),
          COALESCE(s.channel_raw, ''),
          CAST(COALESCE(s.unit_price, 0) AS VARCHAR),
          CAST(COALESCE(s.quantity, 0) AS VARCHAR)
        )
    ) AS rn
  FROM {STG_TABLE} AS s
),
cleaned AS (
  SELECT
    r.order_id,
    r.date_parsed,
    GREATEST(LEAST(r.unit_price, b.p99), b.p01) AS unit_price,
    r.quantity,
    r.store_id,
    r.product_id,
    r.customer_id,
    CASE
      WHEN r.channel_norm IN ('online','in_store','marketplace') THEN r.channel_norm
      WHEN LOWER(REPLACE(REPLACE(r.channel_raw,'-','_'),' ','_')) IN ('online','in_store','marketplace')
        THEN LOWER(REPLACE(REPLACE(r.channel_raw,'-','_'),' ','_'))
      ELSE 'online'
    END AS channel_norm
  FROM ranked r
  CROSS JOIN bounds b
  WHERE r.rn = 1
)
SELECT * FROM cleaned;
"""

def metrics(con, table):
    q = f"""
    WITH b AS (SELECT order_id, date_parsed, unit_price FROM {table})
    SELECT
      COUNT(*)                                                   AS n,
      COUNT(*) - COUNT(DISTINCT order_id||'|'||date_parsed)      AS dup_est,
      quantile_cont(unit_price,0.01)                             AS p01,
      quantile_cont(unit_price,0.99)                             AS p99
    FROM b WHERE unit_price IS NOT NULL;
    """
    return con.execute(q).fetchdf().to_dict(orient="records")[0]

def table_exists(con, schema, name):
    q = """
    SELECT COUNT(*) AS c
    FROM information_schema.tables
    WHERE table_schema = ? AND table_name = ?;
    """
    return con.execute(q, [schema, name]).fetchone()[0] > 0

def main(show=10, snapshot=False):
    Path("reports").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=False)

    try:
        before = metrics(con, STG_TABLE)

        # build NEW
        con.execute("DROP TABLE IF EXISTS gold.sales_clean_new;")
        con.execute(SQL_BUILD_NEW)

        after = metrics(con, "gold.sales_clean_new")

        # gates simples (pode ajustar)
        drop_ratio = max(0.0, (before["n"] - after["n"]) / before["n"]) if before["n"] else 0.0
        gates_ok = (after["dup_est"] <= 0) and (after["p99"] <= before["p99"]) and (drop_ratio <= 0.20)

        print(json.dumps({
            "timestamp": datetime.utcnow().isoformat()+"Z",
            "before": before,
            "after_new": after,
            "gates": {
                "dup_est_to_zero": after["dup_est"] <= 0,
                "p99_non_increasing": after["p99"] <= before["p99"],
                "drop_ratio": drop_ratio,
                "drop_ratio_ok": drop_ratio <= 0.20
            },
            "gates_ok": gates_ok
        }, indent=2, ensure_ascii=False))

        # swap (backup + promote)
        con.execute("BEGIN TRANSACTION;")
        if table_exists(con, "gold", "sales_clean_backup"):
            con.execute("DROP TABLE gold.sales_clean_backup;")
        if table_exists(con, "gold", "sales_clean"):
            con.execute("ALTER TABLE gold.sales_clean RENAME TO sales_clean_backup;")
        con.execute("ALTER TABLE gold.sales_clean_new RENAME TO sales_clean;")
        con.execute("COMMIT;")

        if show > 0:
            df = con.execute(f"SELECT * FROM {GOLD_TABLE} LIMIT {int(show)}").fetchdf()
            print("\n=== Amostra gold.sales_clean ===")
            try:
                import pandas as pd
                with pd.option_context("display.max_colwidth", 40, "display.width", 160):
                    print(df.to_string(index=False))
            except Exception:
                print(df)

        if snapshot:
            con.execute("""
                COPY (SELECT * FROM gold.sales_clean)
                TO 'reports/gold_snapshot.csv' (HEADER, DELIMITER ',');
            """)
            print("[ok] Snapshot salvo em reports/gold_snapshot.csv")

    finally:
        con.close()

if __name__ == "__main__":
    # ajuste os flags aqui se quiser
    main(show=15, snapshot=True)
