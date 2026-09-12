# src/ingest.py
import duckdb
from pathlib import Path
from .config import DB_PATH, RAW_TABLE, STG_TABLE, DATA_CSV

# ...
from .config import DB_PATH, RAW_TABLE, STG_TABLE, DATA_CSV

# escapa apóstrofos para uso seguro dentro de string SQL
DATA_CSV_SQL = DATA_CSV.replace("'", "''")


DDL = f"""
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS gold;

DROP TABLE IF EXISTS {RAW_TABLE};
CREATE TABLE {RAW_TABLE} AS
SELECT * FROM read_csv_auto('{DATA_CSV_SQL}', header=True, IGNORE_ERRORS=True);

-- Camada de staging com limpeza mínima (parsing de datas e tipos)
DROP VIEW IF EXISTS {STG_TABLE};
CREATE VIEW {STG_TABLE} AS
SELECT
  order_id,
  COALESCE(
    CAST(try_strptime(date, '%Y-%m-%d') AS DATE),
    CAST(try_strptime(date, '%d/%m/%Y') AS DATE),
    CAST(try_strptime(date, '%Y/%m/%d') AS DATE)
  ) AS date_parsed,

  store_id,
  product_id,
  TRY_CAST(unit_price AS DOUBLE) AS unit_price,
  TRY_CAST(quantity AS INTEGER) AS quantity,
  NULLIF(trim(customer_id), '') AS customer_id,
  lower(replace(replace(channel, '-', '_'), ' ', '_')) AS channel_norm,
  channel AS channel_raw
FROM {RAW_TABLE};
"""

def ensure_duckdb_loaded():
    Path('reports').mkdir(exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=False)  # <-- DB_PATH aqui
    con.execute(DDL)
    con.close()
    print("Ingestão concluída. Tabelas RAW e STG prontas.")

if __name__ == "__main__":
    ensure_duckdb_loaded()
