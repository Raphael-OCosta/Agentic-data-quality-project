# src/tools.py
"""
Ferramentas determinísticas do workflow.

Duas camadas:
  1. Funções puras (testáveis sem CrewAI/LLM) — usadas por apply_patch.py e testes.
  2. Wrappers @tool do CrewAI — entregues aos agentes em src/crew.py.

Correções em relação à versão original:
  - `validate_sql_safely` tinha falso-positivo: o padrão CREATE.+(raw|stg)\\. com
    DOTALL bloqueava QUALQUER patch legítimo que lesse `FROM stg.sales`. Agora só
    o ALVO do CREATE é inspecionado.
  - `simulate_before_after_metrics` abria SQLAlchemy e DuckDB ao mesmo tempo sobre
    o mesmo arquivo (lock) e não isolava o dry-run. Agora roda em conexão única,
    dentro de transação revertida.
  - Nenhuma ferramenta era entregue aos agentes; o módulo estava órfão.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import duckdb

from .config import DB_PATH, STG_TABLE, GOLD_TABLE

ALLOWED_CHANNELS = ("online", "in_store", "marketplace")


# ---------------------------------------------------------------------------
# Leitura de artefatos
# ---------------------------------------------------------------------------
def load_baseline() -> dict:
    p = Path("reports/baseline_checks.json")
    if not p.exists():
        raise FileNotFoundError(
            "reports/baseline_checks.json não encontrado; rode `python -m src.checks`."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def read_sql_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str, content: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Guardrails de SQL
# ---------------------------------------------------------------------------
PROHIBITED_PATTERNS = [
    (r"\bDROP\s+(TABLE|VIEW|SCHEMA)\s+(?!IF\s+EXISTS\s+gold\.)(raw|stg)\.", "DROP em raw/stg"),
    (r"\bALTER\s+(TABLE|SCHEMA)\s+(raw|stg)\.", "ALTER em raw/stg"),
    (r"\bUPDATE\s+(raw|stg)\.", "UPDATE em raw/stg"),
    (r"\bDELETE\s+FROM\s+(raw|stg)\.", "DELETE em raw/stg"),
    (r"\b(ATTACH|DETACH|VACUUM|PRAGMA|INSTALL|LOAD|COPY\s+\(?\s*SELECT.*\)?\s*TO\s+'/)\b", "comando fora do escopo"),
    (r"\bCREATE\s+(OR\s+REPLACE\s+)?(TABLE|VIEW)\s+(raw|stg)\.", "CREATE em raw/stg"),
]

# Um patch aceitável precisa materializar a gold de forma idempotente.
REQUIRED_PATTERNS = [
    (rf"\bCREATE\s+OR\s+REPLACE\s+TABLE\s+{re.escape(GOLD_TABLE)}\b", f"CREATE OR REPLACE TABLE {GOLD_TABLE}"),
    (r"\bROW_NUMBER\s*\(\s*\)\s*OVER", "deduplicação via ROW_NUMBER()"),
]


def validate_sql_safely(sql: str) -> dict:
    """Verifica guardrails estáticos. Não executa nada."""
    flags = re.IGNORECASE | re.MULTILINE
    blocked = [
        label for pat, label in PROHIBITED_PATTERNS if re.search(pat, sql, flags)
    ]
    missing = [
        label for pat, label in REQUIRED_PATTERNS if not re.search(pat, sql, flags)
    ]

    # colunas inexistentes citadas com frequência por LLM
    unknown_cols = [
        c for c in ("created_at", "updated_at", "ingested_at")
        if re.search(rf"\b{c}\b", sql, flags)
    ]
    # `channel` cru não existe na staging (só channel_norm / channel_raw).
    # Aliases de saída (`... AS channel`) são legítimos e não contam.
    sql_wo_alias = re.sub(r"\bAS\s+channel\b", "", sql, flags=flags)
    if re.search(r"(?<![_.\w])channel(?![_\w])", sql_wo_alias, flags):
        unknown_cols.append("channel (na staging use channel_norm ou channel_raw)")

    return {
        "blocked_commands": blocked,
        "missing_requirements": missing,
        "unknown_columns": unknown_cols,
        "safe": not blocked and not unknown_cols,
    }


# ---------------------------------------------------------------------------
# Métricas e dry-run
# ---------------------------------------------------------------------------
METRICS_SQL = """
WITH b AS (
  SELECT order_id, date_parsed, unit_price, customer_id, {chan} AS chan FROM {table}
)
SELECT
  COUNT(*)                                                        AS n,
  COUNT(*) - COUNT(DISTINCT order_id || '|' || CAST(date_parsed AS VARCHAR)) AS dup_est,
  SUM(CASE WHEN unit_price IS NULL OR unit_price <= 0 THEN 1 ELSE 0 END)     AS n_price_zero_or_null,
  SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END)            AS n_missing_customer,
  COUNT(DISTINCT chan)                                            AS n_channel_labels,
  SUM(CASE WHEN chan IS NULL OR chan NOT IN ('online','in_store','marketplace') THEN 1 ELSE 0 END) AS n_channel_off_domain,
  quantile_cont(unit_price, 0.01)                                 AS p01,
  quantile_cont(unit_price, 0.99)                                 AS p99
FROM b
"""


def _channel_column(con: duckdb.DuckDBPyConnection, table: str) -> str:
    """
    A staging expõe `channel_norm`; a gold pode expor `channel`. As métricas
    precisam funcionar nos dois lados da comparação BEFORE/AFTER.
    """
    cols = {r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()}
    for candidate in ("channel_norm", "channel", "channel_raw"):
        if candidate in cols:
            return candidate
    return "NULL"


def _metrics(con: duckdb.DuckDBPyConnection, table: str) -> dict:
    sql = METRICS_SQL.format(table=table, chan=_channel_column(con, table))
    row = con.execute(sql).fetchdf().to_dict("records")[0]
    return {k: (float(v) if hasattr(v, "item") else v) for k, v in row.items()}


def dry_run_patch(patch_sql: str, db_path: str = DB_PATH) -> dict:
    """
    Executa o patch em SANDBOX: redireciona gold.sales_clean para uma tabela
    temporária e reverte a transação ao final. Nada é persistido.
    Retorna métricas BEFORE (staging) x AFTER (gold simulada) reais.
    """
    guard = validate_sql_safely(patch_sql)
    if guard["blocked_commands"]:
        return {"executed": False, "error": "guardrail", "guard": guard}

    con = duckdb.connect(db_path, read_only=False)
    try:
        before = _metrics(con, STG_TABLE)
        sandbox_sql = re.sub(
            rf"\b{re.escape(GOLD_TABLE)}\b",
            "_dryrun_sales_clean",
            patch_sql,
            flags=re.IGNORECASE,
        )
        # remove CREATE SCHEMA gold (desnecessário no sandbox) sem quebrar o resto
        sandbox_sql = re.sub(
            r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+gold\s*;", "", sandbox_sql, flags=re.IGNORECASE
        )
        con.execute("BEGIN TRANSACTION;")
        try:
            con.execute("DROP TABLE IF EXISTS _dryrun_sales_clean;")
            con.execute(sandbox_sql)
            after = _metrics(con, "_dryrun_sales_clean")
            sample = (
                con.execute("SELECT * FROM _dryrun_sales_clean LIMIT 5")
                .fetchdf()
                .to_dict("records")
            )
            error = None
        except Exception as exc:  # noqa: BLE001 — queremos reportar ao agente
            after, sample, error = None, [], f"{type(exc).__name__}: {exc}"
        finally:
            con.execute("ROLLBACK;")
    finally:
        con.close()

    return {
        "executed": error is None,
        "error": error,
        "guard": guard,
        "before_after": {"stg": before, "gold_simulated": after},
        "sample": sample,
    }


# compat com a assinatura antiga usada em notebooks da disciplina
def simulate_before_after_metrics(db_uri: str, stg_table: str, patch_sql: str) -> dict:
    return dry_run_patch(patch_sql)["before_after"]


# ---------------------------------------------------------------------------
# Evidência quantitativa: sazonalidade x bug
# ---------------------------------------------------------------------------
SEASONALITY_SQL = f"""
WITH d AS (
  SELECT date_parsed AS d,
         COUNT(*) AS n_rows,
         COUNT(DISTINCT order_id) AS n_orders,
         SUM(unit_price * quantity) AS revenue
  FROM {STG_TABLE}
  WHERE date_parsed IS NOT NULL
  GROUP BY 1
),
w AS (
  SELECT d, n_rows, n_orders, revenue,
         AVG(n_rows) OVER (ORDER BY d ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS ma7_prev,
         LAG(n_rows, 7) OVER (ORDER BY d) AS n_rows_wow
  FROM d
)
SELECT d, n_rows, n_orders, revenue, ma7_prev, n_rows_wow,
       CASE WHEN ma7_prev IS NULL OR ma7_prev = 0 THEN NULL
            ELSE (n_rows - ma7_prev) / ma7_prev END AS dev_vs_ma7,
       (n_rows - n_orders) AS dup_rows_no_dia
FROM w
WHERE d BETWEEN DATE '{{start}}' AND DATE '{{end}}'
ORDER BY d
"""


def seasonality_evidence(start: str = "2025-07-01", end: str = "2025-07-31") -> dict:
    """
    Série diária com média móvel de 7 dias, comparação week-over-week e
    contagem de linhas excedentes por pedido (indício de double ingestion).
    É a evidência que separa queda de negócio (feriado) de bug de dados.
    """
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        df = con.execute(SEASONALITY_SQL.format(start=start, end=end)).fetchdf()
    finally:
        con.close()

    rows = json.loads(df.to_json(orient="records", date_format="iso"))
    for r in rows:
        if r.get("d"):
            r["d"] = r["d"][:10]

    def _flag(r, kind):
        dev = r.get("dev_vs_ma7")
        if dev is None:
            return False
        return dev <= -0.20 if kind == "queda" else dev >= 0.30

    return {
        "serie": rows,
        "quedas_relevantes": [r["d"] for r in rows if _flag(r, "queda")],
        "picos_relevantes": [r["d"] for r in rows if _flag(r, "pico")],
        "dias_com_duplicidade": [r["d"] for r in rows if (r.get("dup_rows_no_dia") or 0) > 0],
    }


def channel_variants() -> dict:
    """Distribuição dos rótulos de canal — evidência de label drift."""
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        df = con.execute(
            f"SELECT channel_raw, channel_norm, COUNT(*) AS n FROM {STG_TABLE} "
            "GROUP BY 1,2 ORDER BY 3 DESC"
        ).fetchdf()
    finally:
        con.close()
    variants = json.loads(df.to_json(orient="records"))
    off = [v for v in variants if v["channel_norm"] not in ALLOWED_CHANNELS]
    return {
        "variantes": variants,
        "dominio_esperado": list(ALLOWED_CHANNELS),
        "fora_do_dominio": off,
    }


def run_readonly_query(sql: str) -> dict:
    """Consulta somente-leitura na staging (guardrail: apenas SELECT/WITH)."""
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        return {"error": "Apenas SELECT/WITH são permitidos nesta ferramenta."}
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        df = con.execute(sql).fetchdf().head(50)
        return {"rows": json.loads(df.to_json(orient="records", date_format="iso"))}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Wrappers CrewAI (opcionais — só se crewai estiver instalado)
# ---------------------------------------------------------------------------
def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


try:  # pragma: no cover
    from crewai.tools import tool

    @tool("Métricas de baseline")
    def tool_baseline() -> str:
        """Retorna as métricas objetivas já calculadas em reports/baseline_checks.json."""
        return _dumps(load_baseline())

    @tool("Consulta somente-leitura no DuckDB")
    def tool_query(sql: str) -> str:
        """Executa um SELECT/WITH na staging e devolve até 50 linhas em JSON."""
        return _dumps(run_readonly_query(sql))

    @tool("Evidência de sazonalidade x bug")
    def tool_seasonality(start: str = "2025-07-01", end: str = "2025-07-31") -> str:
        """Série diária com média móvel 7d, WoW e duplicidade por dia."""
        return _dumps(seasonality_evidence(start, end))

    @tool("Variantes de canal")
    def tool_channels() -> str:
        """Lista os rótulos de canal encontrados e os que estão fora do domínio."""
        return _dumps(channel_variants())

    @tool("Validar guardrails do SQL")
    def tool_validate_sql(sql: str) -> str:
        """Checa comandos proibidos, requisitos obrigatórios e colunas inexistentes."""
        return _dumps(validate_sql_safely(sql))

    @tool("Dry-run do patch")
    def tool_dry_run(sql: str) -> str:
        """Executa o patch em sandbox revertida e devolve métricas BEFORE/AFTER reais."""
        return _dumps(dry_run_patch(sql))

    ANALYST_TOOLS = [tool_baseline, tool_query, tool_seasonality, tool_channels]
    ENGINEER_TOOLS = [tool_baseline, tool_query, tool_validate_sql, tool_dry_run]
    VALIDATOR_TOOLS = [tool_validate_sql, tool_dry_run, tool_baseline]

except ImportError:  # crewai ausente: modo determinístico ainda funciona
    ANALYST_TOOLS = ENGINEER_TOOLS = VALIDATOR_TOOLS = []
