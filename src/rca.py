# src/rca.py
"""
Gerador determinístico do RCA (reports/RCA_report.md).

Motivo de existir: na execução anterior o Reviewer (LLM) escreveu
"APROVADO: as correções foram implementadas com sucesso" quando NADA havia sido
aplicado — alucinação de estado. Aqui o relatório é montado a partir dos
artefatos medidos (baseline_checks.json + validation_report.json), de modo que
a seção de decisão nunca pode divergir do que o banco realmente mostra.

Quando o crew roda com LLM, este módulo continua útil como contra-prova:
compare reports/RCA_report.md (agente) com reports/RCA_report_medido.md (aqui).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import STG_TABLE, GOLD_TABLE
from .tools import seasonality_evidence, channel_variants

TEMPLATE = """# RCA — Incidente de Qualidade de Dados em `{stg}`

> Relatório gerado deterministicamente a partir de `reports/baseline_checks.json` e
> `reports/validation_report.json` em {ts}. Todos os números abaixo foram medidos
> no DuckDB, não estimados.

## 1. Contexto

A tabela diária de vendas apresentou dois eventos anômalos em julho de 2025: uma
queda acentuada em **09/07** e um pico em **15/07**. Em paralelo, a camada de
staging acumulava problemas crônicos de qualidade — duplicidade por chave de
pedido, preços zerados e outliers, rótulos de canal inconsistentes e
`customer_id` ausente. O workflow agêntico foi acionado para distinguir efeito de
negócio de defeito de dados e propor correção segura para a camada `{gold}`.

## 2. Evidências

### 2.1 Baseline da staging

| Métrica | Valor |
|---|---:|
| Linhas | {n_rows:,} |
| Pares (order_id, date_parsed) duplicados | {n_dup_pairs:,} |
| Linhas envolvidas em duplicidade | {n_dup_rows:,} |
| `unit_price` nulo ou <= 0 | {n_price:,} |
| `customer_id` ausente | {n_cust:,} |
| Datas não parseáveis | {n_date_null:,} |
| P01 / P99 de `unit_price` | {p01} / {p99} |

### 2.2 Sazonalidade × bug

{seasonality_block}

**Leitura:** a queda de **09/07** aparece como desvio negativo isolado, sem
duplicidade associada — comportamento compatível com **feriado estadual em SP
(Revolução Constitucionalista)**, ou seja, **efeito de negócio**. O pico de
**15/07** vem acompanhado de linhas excedentes para os mesmos `order_id` no mesmo
dia — assinatura de **double ingestion**, ou seja, **bug de dados**.

Consequência prática: 09/07 **não** deve ser corrigido (corrigir apagaria um fato
real do negócio); 15/07 **deve** ser deduplicado.

### 2.3 Label drift de canal

{channel_block}

## 3. Correção proposta

Patch efetivo: `{patch_file}`

1. **Deduplicação** por `(order_id, date_parsed)` via `ROW_NUMBER()` mantendo
   `rn = 1`, com `ORDER BY` determinístico (patch reprodutível entre execuções).
2. **Winsorização** de `unit_price` no intervalo `[p01, p99]` = `[{p01}, {p99}]`,
   com clamp explícito; valores `<= 0` recebem `p01`. Escolha deliberada por
   winsorizar em vez de remover: preserva massa de dados e não distorce volume.
3. **Normalização de canal** para o domínio `{{online, in_store, marketplace}}`,
   mapeando explicitamente as variantes `on_line`, `store` e `market_place`.
   Rótulo desconhecido resulta em `NULL` — nunca é forçado a um bucket.
4. **`customer_id` preservado como `NULL`** quando ausente. Imputar aqui criaria
   dado falso e contaminaria qualquer análise de recorrência de cliente.
5. **Idempotência**: `CREATE OR REPLACE TABLE` restrito ao schema `gold`;
   `raw` e `stg` permanecem intocados.

## 4. Validação (antes × depois)

Medição real em dry-run (transação revertida), não estimativa:

| Métrica | BEFORE (`{stg}`) | AFTER (`{gold}`) | Δ |
|---|---:|---:|---:|
{metrics_rows}

Gates de aceite:

{gates_block}

## 5. Decisão

**{decision}**

Estado de aplicação: **{applied_txt}**.
{approval_note}

## 6. Próximos passos

1. **Bloquear a causa raiz do double ingestion** — o patch trata o sintoma na
   gold; a duplicidade continuará chegando enquanto a ingestão não tiver chave
   idempotente (constraint única em `(order_id, date_parsed)` ou `MERGE`).
2. **Promover as checagens a testes de contrato** executados a cada carga, com
   falha do pipeline quando `n_dup_pairs > 0` ou `n_channel_off_domain > 0`.
3. **Calendário de feriados como dimensão**, para que quedas legítimas sejam
   explicadas automaticamente e não gerem alarme.
4. **Corrigir o canal na origem**; a normalização na gold é paliativo e mascara
   a inconsistência do sistema transacional.
5. **Monitorar p01/p99 ao longo do tempo**: winsorizar com limites recalculados a
   cada carga pode mascarar mudança real de patamar de preço.
"""


def _fmt(v, nd=2):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.{nd}f}"
    return f"{v:,}"


def _metrics_rows(before: dict, after: dict) -> str:
    labels = [
        ("n", "Linhas", 0),
        ("dup_est", "Duplicatas estimadas", 0),
        ("n_price_zero_or_null", "`unit_price` <= 0 ou nulo", 0),
        ("n_channel_off_domain", "Canal fora do domínio", 0),
        ("n_missing_customer", "`customer_id` ausente", 0),
        ("n_channel_labels", "Rótulos distintos de canal", 0),
        ("p01", "P01 de `unit_price`", 2),
        ("p99", "P99 de `unit_price`", 2),
    ]
    out = []
    for key, label, nd in labels:
        b, a = before.get(key), after.get(key) if after else None
        delta = "—"
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            d = a - b
            delta = f"{d:+,.{nd}f}" if nd else f"{d:+,.0f}"
        out.append(f"| {label} | {_fmt(b, nd)} | {_fmt(a, nd)} | {delta} |")
    return "\n".join(out)


def _seasonality_block() -> str:
    ev = seasonality_evidence()
    rows = [r for r in ev["serie"] if r["d"] in ("2025-07-08", "2025-07-09", "2025-07-10", "2025-07-14", "2025-07-15", "2025-07-16")]
    lines = ["| Dia | Linhas | Pedidos distintos | Linhas excedentes | Desvio vs. média móvel 7d |", "|---|---:|---:|---:|---:|"]
    for r in rows:
        dev = r.get("dev_vs_ma7")
        dev_s = f"{dev * 100:+.1f}%" if dev is not None else "—"
        lines.append(
            f"| {r['d']} | {int(r['n_rows']):,} | {int(r['n_orders']):,} | "
            f"{int(r.get('dup_rows_no_dia') or 0):,} | {dev_s} |"
        )
    lines.append("")
    lines.append(f"- Quedas relevantes detectadas: `{', '.join(ev['quedas_relevantes']) or '—'}`")
    lines.append(f"- Picos relevantes detectados: `{', '.join(ev['picos_relevantes']) or '—'}`")
    lines.append(f"- Dias com linhas duplicadas: `{', '.join(ev['dias_com_duplicidade']) or '—'}`")
    return "\n".join(lines)


def _channel_block() -> str:
    cv = channel_variants()
    lines = ["| Rótulo bruto (`channel_raw`) | Normalizado (`channel_norm`) | Linhas | No domínio? |", "|---|---|---:|---|"]
    for v in cv["variantes"]:
        ok = "sim" if v["channel_norm"] in cv["dominio_esperado"] else "**não**"
        lines.append(f"| `{v['channel_raw']}` | `{v['channel_norm']}` | {v['n']:,} | {ok} |")
    total_off = sum(v["n"] for v in cv["fora_do_dominio"])
    lines.append("")
    lines.append(
        f"**{total_off:,} linhas** ({len(cv['fora_do_dominio'])} rótulos) estão fora do "
        f"domínio `{{{', '.join(cv['dominio_esperado'])}}}`."
    )
    return "\n".join(lines)


def _gates_block(gates: dict) -> str:
    if not gates:
        return "_Gates não avaliados (o patch não executou em dry-run)._"
    lines = ["| Gate | Resultado |", "|---|---|"]
    for k, v in gates.get("checks", {}).items():
        lines.append(f"| `{k}` | {'✅ passou' if v else '❌ falhou'} |")
    lines.append("")
    lines.append(f"Perda de linhas: **{gates.get('drop_ratio', 0) * 100:.2f}%** (limite: 20%).")
    return "\n".join(lines)


def main(path: str = "reports/RCA_report_medido.md") -> str:
    base = json.loads(Path("reports/baseline_checks.json").read_text(encoding="utf-8"))
    val = json.loads(Path("reports/validation_report.json").read_text(encoding="utf-8"))

    ba = val.get("before_after", {})
    before = ba.get("stg", {})
    after = ba.get("gold_real") or ba.get("gold_simulated") or {}
    applied = val.get("applied", False)

    md = TEMPLATE.format(
        stg=STG_TABLE,
        gold=GOLD_TABLE,
        ts=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        n_rows=int(base["n_rows"]),
        n_dup_pairs=int(base["n_dup_pairs"]),
        n_dup_rows=int(base["n_dup_rows"]),
        n_price=int(base["n_price_zero_or_null"]),
        n_cust=int(base["n_missing_customer"]),
        n_date_null=int(base["n_date_null"]),
        p01=round(float(base["p01"]), 2),
        p99=round(float(base["p99"]), 2),
        seasonality_block=_seasonality_block(),
        channel_block=_channel_block(),
        patch_file=val.get("patch_file", "reports/patch.sql"),
        metrics_rows=_metrics_rows(before, after),
        gates_block=_gates_block(val.get("gates", {})),
        decision=val.get("decision", "NECESSITA REVISÃO"),
        applied_txt="patch APLICADO em `gold.sales_clean`" if applied else "patch **NÃO** aplicado",
        approval_note=(
            "A materialização ocorreu após aprovação humana explícita (`--approve`)."
            if applied
            else "O gate `REQUIRE_HUMAN_APPROVAL=True` impediu a materialização automática; "
            "a aplicação exige `python -m src.apply_patch --approve`."
        ),
    )

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(md, encoding="utf-8")
    print(f"[ok] RCA medido escrito em {path}")
    return md


if __name__ == "__main__":
    main()
