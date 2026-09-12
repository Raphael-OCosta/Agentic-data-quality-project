# tests/test_pipeline.py
"""
Testes rápidos das partes determinísticas do workflow.
Rode com:  python -m tests.test_pipeline
(Não exige CrewAI nem chave de API.)
"""

import json
import sys

from src.postprocess import extract_json, strip_fences, sanitize_json_artifact
from src.tools import validate_sql_safely, dry_run_patch, read_sql_file

FAILS = []


def check(name, cond, detail=""):
    status = "ok " if cond else "FALHOU"
    print(f"[{status}] {name}{(' — ' + detail) if detail and not cond else ''}")
    if not cond:
        FAILS.append(name)


def main() -> int:
    # 1. sanitização de cercas markdown
    fenced = '```json\n{"findings": [{"problem": "dup"}], "notes": "ok"}\n```'
    data = extract_json(fenced)
    check("extract_json remove cerca ```json", data["notes"] == "ok")

    sql_fenced = "```sql\nSELECT 1;\n```"
    check("strip_fences remove cerca ```sql", strip_fences(sql_fenced) == "SELECT 1;")

    # 2. JSON malformado com prosa antes/depois
    messy = 'Segue o resultado:\n```json\n{"tasks": [{"id": "A1"}]}\n```\nEspero ter ajudado.'
    check("extract_json ignora prosa ao redor", extract_json(messy)["tasks"][0]["id"] == "A1")

    # 3. guardrails: patch de referência é seguro
    good = read_sql_file("reports/patch_reference.sql")
    g = validate_sql_safely(good)
    check("patch de referência passa nos guardrails", g["safe"], json.dumps(g))
    check("patch de referência cumpre requisitos", not g["missing_requirements"])

    # 4. guardrails: SQL perigoso é bloqueado
    bad = "DROP TABLE stg.sales; UPDATE raw.sales SET unit_price = 0;"
    b = validate_sql_safely(bad)
    check("DROP/UPDATE em raw/stg é bloqueado", len(b["blocked_commands"]) >= 2, json.dumps(b))

    # 5. guardrails: colunas inexistentes do erro original são detectadas
    old = (
        "CREATE OR REPLACE TABLE gold.sales_clean AS SELECT order_id, channel, "
        "ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY created_at DESC) rn FROM stg.sales;"
    )
    o = validate_sql_safely(old)
    check("created_at e channel são detectados", len(o["unknown_columns"]) == 2, json.dumps(o))

    # 6. dry-run reverte: a gold não muda ao validar
    res = dry_run_patch(good)
    check("dry-run executa o patch de referência", res["executed"], str(res["error"]))
    ba = res["before_after"]
    check("dry-run zera duplicatas", ba["gold_simulated"]["dup_est"] == 0)
    check("dry-run preserva customer_id nulo",
          ba["gold_simulated"]["n_missing_customer"] == ba["stg"]["n_missing_customer"])
    check("dry-run fecha o domínio de canal", ba["gold_simulated"]["n_channel_off_domain"] == 0)

    # 7. dry-run de SQL quebrado não derruba o pipeline
    broken = "CREATE OR REPLACE TABLE gold.sales_clean AS SELECT nao_existe FROM stg.sales;"
    r = dry_run_patch(broken)
    check("SQL inválido retorna erro sem exceção", not r["executed"] and r["error"])

    # 8. artefatos em reports/ são JSON válido
    res = sanitize_json_artifact("reports/validation_report.json")
    check("validation_report.json é JSON válido", res["ok"] or not res["problems"], json.dumps(res))

    print()
    if FAILS:
        print(f"{len(FAILS)} teste(s) falharam: {', '.join(FAILS)}")
        return 1
    print("Todos os testes passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
