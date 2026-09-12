# src/run_workflow.py
"""
Orquestrador ponta a ponta do Agentic Data Quality Workflow.

    python -m src.run_workflow                # pipeline completo (ingest→checks→crew→validação)
    python -m src.run_workflow --skip-crew    # só a trilha determinística (sem custo de LLM)
    python -m src.run_workflow --approve      # aplica o patch após os gates passarem

Etapas:
  1. Ingestão (raw → stg) e checagens determinísticas (baseline_checks.json)
  2. Patch de referência determinístico (reports/patch_reference.sql) — gabarito e fallback
  3. Crew multiagente (plan → findings → patch → validation → RCA)
  4. Validação real do patch do agente: guardrails + dry-run em sandbox revertida
  5. Fallback auditado: se o patch do agente não executar, o de referência assume
  6. Portão humano: nada é materializado em gold sem --approve
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .config import REQUIRE_HUMAN_APPROVAL

AGENT_PATCH = "reports/patch.sql"
REFERENCE_PATCH = "reports/patch_reference.sql"
FALLBACK_NOTE = "reports/fallback_notice.json"


def _step(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main(skip_crew: bool = False, approve: bool = False, force: bool = False) -> dict:
    from .ingest import ensure_duckdb_loaded
    from .checks import baseline_checks
    from .reference_patch import main as build_reference
    from .apply_patch import run as apply_run
    from .tools import dry_run_patch, read_sql_file

    Path("reports").mkdir(exist_ok=True)

    _step("1/5 Ingestão (raw → stg)")
    ensure_duckdb_loaded()

    _step("2/5 Checagens determinísticas")
    baseline = baseline_checks()
    print(json.dumps(baseline, indent=2, default=str))

    _step("3/5 Patch de referência (gabarito/fallback)")
    build_reference(REFERENCE_PATCH)

    if not skip_crew:
        _step("4/5 Crew multiagente (CrewAI + LangChain + OpenAI)")
        from .crew import crew  # import tardio: só custa se for usar

        crew.kickoff()
    else:
        _step("4/5 Crew multiagente — PULADO (--skip-crew)")

    _step("5/5 Validação do patch e portão humano")
    patch_path = AGENT_PATCH
    fallback_used = False

    if not Path(AGENT_PATCH).exists():
        print(f"[aviso] {AGENT_PATCH} não existe; usando o patch de referência.")
        patch_path, fallback_used = REFERENCE_PATCH, True
    else:
        probe = dry_run_patch(read_sql_file(AGENT_PATCH))
        if not probe["executed"]:
            print(f"[aviso] patch do agente falhou no dry-run: {probe['error']}")
            print("[aviso] assumindo o patch de referência (fallback auditado).")
            shutil.copyfile(AGENT_PATCH, "reports/patch_agent_rejected.sql")
            patch_path, fallback_used = REFERENCE_PATCH, True

    if fallback_used:
        Path(FALLBACK_NOTE).write_text(
            json.dumps(
                {
                    "fallback_acionado": True,
                    "motivo": "patch gerado pelo agente não executou em dry-run",
                    "patch_do_agente_preservado_em": "reports/patch_agent_rejected.sql",
                    "patch_efetivo": REFERENCE_PATCH,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    report = apply_run(patch_path, approve=approve, force=force)

    print("\n[workflow] concluído. Artefatos em reports/.")
    if REQUIRE_HUMAN_APPROVAL and not report.get("applied"):
        print(
            "[human-in-the-loop] revise reports/patch.sql (ou patch_reference.sql) e "
            "rode `python -m src.apply_patch --approve` para materializar a gold."
        )
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-crew", action="store_true", help="não chama a API do LLM")
    ap.add_argument("--approve", action="store_true", help="aprova e aplica o patch")
    ap.add_argument("--force", action="store_true", help="aplica mesmo com gate falhando")
    args = ap.parse_args()
    main(skip_crew=args.skip_crew, approve=args.approve, force=args.force)
