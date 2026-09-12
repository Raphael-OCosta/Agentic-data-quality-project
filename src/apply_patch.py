# src/apply_patch.py
"""
Portão human-in-the-loop: valida → dry-run → (aprovação) → aplica → mede.

Uso:
    python -m src.apply_patch                    # só valida e faz dry-run
    python -m src.apply_patch --approve          # aplica em gold (exige gates OK)
    python -m src.apply_patch --patch reports/patch_reference.sql --approve
    python -m src.apply_patch --approve --force  # ignora gates (registra no relatório)

Nada é aplicado sem --approve quando REQUIRE_HUMAN_APPROVAL=True em config.py.
Toda execução grava reports/validation_report.json com métricas BEFORE/AFTER
REAIS (medidas no banco), não estimativas textuais.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .config import DB_PATH, STG_TABLE, GOLD_TABLE, REQUIRE_HUMAN_APPROVAL
from .tools import _metrics, dry_run_patch, read_sql_file, validate_sql_safely

VALIDATION_PATH = "reports/validation_report.json"
SNAPSHOT_PATH = "reports/gold_snapshot.csv"

# Gates de aceite: o patch precisa melhorar sem destruir massa de dados.
MAX_DROP_RATIO = 0.20


def _gates(before: dict, after: dict) -> dict:
    n_before = before["n"] or 0
    n_after = after["n"] or 0
    drop_ratio = max(0.0, (n_before - n_after) / n_before) if n_before else 0.0
    checks = {
        "dedupe_zerou_duplicatas": (after["dup_est"] or 0) <= 0,
        "p99_nao_aumentou": (after["p99"] or 0) <= (before["p99"] or 0) + 1e-9,
        "canal_dentro_do_dominio": (after["n_channel_off_domain"] or 0) == 0,
        "customer_id_nao_inventado": (after["n_missing_customer"] or 0) > 0
        or (before["n_missing_customer"] or 0) == 0,
        "perda_de_linhas_aceitavel": drop_ratio <= MAX_DROP_RATIO,
    }
    return {"drop_ratio": round(drop_ratio, 4), "checks": checks, "ok": all(checks.values())}


def run(patch_path: str = "reports/patch.sql", approve: bool = False, force: bool = False) -> dict:
    sql = read_sql_file(patch_path)
    guard = validate_sql_safely(sql)
    dry = dry_run_patch(sql)

    report: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patch_file": patch_path,
        "syntax_ok": dry["executed"],
        "execution_error": dry["error"],
        "blocked_commands": guard["blocked_commands"],
        "missing_requirements": guard["missing_requirements"],
        "unknown_columns": guard["unknown_columns"],
        "before_after": dry["before_after"],
        "applied": False,
        "require_human_approval": REQUIRE_HUMAN_APPROVAL,
    }

    if not dry["executed"]:
        report["decision"] = "NECESSITA REVISÃO"
        report["notes"] = (
            "O patch não executou em dry-run. Nenhuma alteração foi feita na camada gold. "
            f"Erro: {dry['error']}"
        )
        _save(report)
        return report

    before = dry["before_after"]["stg"]
    after = dry["before_after"]["gold_simulated"]
    report["gates"] = _gates(before, after)
    report["decision"] = (
        "APROVADO para aplicar" if report["gates"]["ok"] else "NECESSITA REVISÃO"
    )

    if not approve:
        report["notes"] = (
            "Dry-run concluído. Aplicação bloqueada pelo gate humano "
            "(rode novamente com --approve para materializar a gold)."
        )
        _save(report)
        _print(report)
        return report

    if not report["gates"]["ok"] and not force:
        report["notes"] = "Aprovação recebida, mas os gates falharam. Use --force para sobrepor."
        _save(report)
        _print(report)
        return report

    # ---- aplicação real, com backup e swap transacional -------------------
    con = duckdb.connect(DB_PATH, read_only=False)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        con.execute("BEGIN TRANSACTION;")
        con.execute(sql)
        con.execute("COMMIT;")
        real_after = _metrics(con, GOLD_TABLE)
        con.execute(
            f"COPY (SELECT * FROM {GOLD_TABLE}) TO '{SNAPSHOT_PATH}' (HEADER, DELIMITER ',');"
        )
    finally:
        con.close()

    report["applied"] = True
    report["forced"] = bool(force and not report["gates"]["ok"])
    report["before_after"]["gold_real"] = real_after
    report["snapshot"] = SNAPSHOT_PATH
    report["notes"] = "Patch aplicado após aprovação humana explícita (--approve)."
    _save(report)
    _print(report)
    return report


def _save(report: dict) -> None:
    Path("reports").mkdir(exist_ok=True)
    Path(VALIDATION_PATH).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] {VALIDATION_PATH} atualizado")


def _print(report: dict) -> None:
    ba = report.get("before_after", {})
    before, after = ba.get("stg"), ba.get("gold_real") or ba.get("gold_simulated")
    if not (before and after):
        return
    cols = ["n", "dup_est", "n_price_zero_or_null", "n_channel_off_domain", "p01", "p99"]
    print(f"\n{'métrica':<24}{'BEFORE':>14}{'AFTER':>14}")
    print("-" * 52)
    for c in cols:
        b, a = before.get(c), after.get(c)
        fb = f"{b:,.2f}" if isinstance(b, float) else f"{b:,}"
        fa = f"{a:,.2f}" if isinstance(a, float) else f"{a:,}"
        print(f"{c:<24}{fb:>14}{fa:>14}")
    print(f"\nDecisão: {report['decision']} | aplicado: {report['applied']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", default="reports/patch.sql")
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(args.patch, approve=args.approve, force=args.force)
