# src/checks.py
# Baseline de qualidade (staging) com métricas essenciais.
# Gera reports/baseline_checks.json

import json
from pathlib import Path
import duckdb
from .config import DB_PATH, STG_TABLE


def _ensure_reports_dir() -> None:
    """Garante que a pasta reports/ exista (para salvar o JSON)."""
    Path("reports").mkdir(exist_ok=True)


def _stg_exists(con: duckdb.DuckDBPyConnection) -> bool:
    """Confere se a view stg.sales (ou o que estiver em STG_TABLE) existe."""
    try:
        schema, name = STG_TABLE.split(".", 1)
    except ValueError:
        # Caso STG_TABLE não tenha ponto, tenta como está
        schema, name = "stg", STG_TABLE
    q = """
      SELECT 1
      FROM information_schema.views
      WHERE table_schema = ? AND table_name = ?
      LIMIT 1
    """
    return con.execute(q, [schema, name]).fetchone() is not None


def baseline_checks() -> dict:
    """Executa as checagens na staging e retorna o dicionário de métricas."""
    _ensure_reports_dir()

    con = duckdb.connect(DB_PATH, read_only=False)

    # Segurança: avisa se a staging não existe (ex.: faltou rodar `python -m src.ingest`)
    if not _stg_exists(con):
        con.close()
        raise RuntimeError(
            f"A view de staging '{STG_TABLE}' não existe. "
            "Rode primeiro: `python -m src.ingest`."
        )

    # CTEs:
    # - base   : recorte dos campos que vamos avaliar
    # - dup    : grupos com duplicidade (order_id, date_parsed)
    # - stats  : contagens de problemas + total de linhas (inclui n_date_null)
    # - ptiles : percentis P01 e P99 de unit_price (para justificar winsorize)
    q = f"""
    WITH base AS (
      SELECT
        order_id, date_parsed, store_id, product_id,
        unit_price, quantity, customer_id, channel_norm
      FROM {STG_TABLE}
    ),
    dup AS (
      SELECT order_id, date_parsed, COUNT(*) AS cnt
      FROM base
      GROUP BY 1,2
      HAVING COUNT(*) > 1
    ),
    stats AS (
      SELECT
        COUNT(*) AS n_rows,
        SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END)             AS n_missing_customer,
        SUM(CASE WHEN unit_price IS NULL OR unit_price <= 0 THEN 1 ELSE 0 END) AS n_price_zero_or_null,
        SUM(CASE WHEN quantity   IS NULL OR quantity   <= 0 THEN 1 ELSE 0 END) AS n_qty_invalid,
        SUM(CASE WHEN date_parsed IS NULL THEN 1 ELSE 0 END)             AS n_date_null
      FROM base
    ),
    ptiles AS (
      SELECT
        quantile_cont(unit_price, 0.01) AS p01,
        quantile_cont(unit_price, 0.99) AS p99
      FROM base
      WHERE unit_price IS NOT NULL
    )
    SELECT
      (SELECT n_rows FROM stats)                           AS n_rows,
      (SELECT COUNT(*) FROM dup)                           AS n_dup_pairs,
      COALESCE((SELECT SUM(cnt) FROM dup), 0)              AS n_dup_rows,  -- COALESCE p/ evitar NULL quando não houver duplicatas
      (SELECT n_missing_customer FROM stats)               AS n_missing_customer,
      (SELECT n_price_zero_or_null FROM stats)             AS n_price_zero_or_null,
      (SELECT n_qty_invalid FROM stats)                    AS n_qty_invalid,
      (SELECT n_date_null FROM stats)                      AS n_date_null,
      (SELECT p01 FROM ptiles)                             AS p01,
      (SELECT p99 FROM ptiles)                             AS p99;
    """

    res = con.execute(q).fetchdf().to_dict(orient="records")[0]
    con.close()

    # Salva JSON
    out_path = "reports/baseline_checks.json"
    with open(out_path, "w") as f:
        json.dump(res, f, indent=2, default=str)

    # Também retorna para quem chamar programaticamente
    return res


if __name__ == "__main__":
    metrics = baseline_checks()
    print("Baseline checks:", json.dumps(metrics, indent=2, default=str))
