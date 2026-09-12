# Agentic Data Quality Workflow (LangChain + CrewAI + DuckDB)

Projeto prático do **Módulo 7 — Projeto Prático com Agentic Workflows com LLM**
(disciplina *LLM's – Engenharias Avançadas*).

Um time multiagente atua como **SRE de dados**: observa a tabela de vendas,
distingue **queda sazonal de negócio** de **bug de dados**, propõe SQL de
remediação, valida o impacto em **dry-run** e emite um **RCA rastreável** — tudo
em sandbox DuckDB, com guardrails e aprovação humana antes de materializar.

---

## Problema

| Sintoma | Natureza |
|---|---|
| Queda de vendas em **09/07** | **Negócio** — feriado estadual em SP |
| Pico em **15/07** | **Bug** — *double ingestion* (26 pedidos duplicados) |
| `unit_price` zerado ou com outliers 10× | Qualidade |
| `customer_id` ausente (88 linhas) | Qualidade |
| *Label drift* em `channel` (`online`/`Online`/`on-line`/`store`/`market_place`…) | Qualidade |
| Datas em formatos mistos | Qualidade |

A armadilha didática: um agente afobado "corrige" também o 09/07 e apaga um fato
real do negócio. O workflow precisa **provar** a diferença antes de agir.

---

## Arquitetura

```
CSV → raw.sales ──ingest──→ stg.sales ──crew──→ (dry-run sandbox) ──aprovação──→ gold.sales_clean
                                │                      │                             │
                          checks.py              tools.py (dedupe/winsor/normaliza)  snapshot
                                ↓                      ↓                             ↓
                     baseline_checks.json      validation_report.json          gold_snapshot.csv
```

**Agentes (CrewAI, sequencial):**

| # | Agente | Entrega | Ferramentas |
|---|---|---|---|
| T0 | Orchestrator | `reports/plan.json` | — (planner) |
| T1 | Analyst | `reports/analysis_findings.json` | baseline, query read-only, sazonalidade, variantes de canal |
| T2 | DataEngineer | `reports/patch.sql` | baseline, query, validar guardrails, dry-run |
| T3 | Validator | `reports/validation_report.json` | validar guardrails, dry-run |
| T4 | Reviewer | `reports/RCA_report.md` | — (síntese) |

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env
```

## Execução

```bash
# pipeline completo (usa a API do LLM)
python -m src.run_workflow

# trilha determinística, sem custo de LLM — útil para testar/depurar
python -m src.run_workflow --skip-crew

# revisar o patch e então materializar a gold
python -m src.apply_patch --approve

# relatório RCA gerado a partir das métricas medidas (contra-prova do agente)
python -m src.rca
```

Passo a passo manual:

```bash
python -m src.ingest            # raw + stg (parse de datas, normalização inicial)
python -m src.checks            # baseline_checks.json
python -m src.reference_patch   # patch de referência (gabarito/fallback)
python -m src.apply_patch       # guardrails + dry-run, SEM aplicar
python -m src.postprocess       # sanitiza artefatos do LLM manualmente, se preciso
```

> **Human-in-the-loop:** `REQUIRE_HUMAN_APPROVAL=True` em `src/config.py`.
> Nada é escrito em `gold` sem `--approve` explícito.

---

## Guardrails

**Estáticos** (`tools.validate_sql_safely`): bloqueiam `DROP`/`ALTER`/`UPDATE`/
`DELETE` em `raw`/`stg`, `ATTACH`/`DETACH`/`PRAGMA`/`VACUUM`, `CREATE` fora de
`gold`; exigem `CREATE OR REPLACE` + `ROW_NUMBER()`; e detectam colunas
inexistentes (`created_at`, `channel`) — erro recorrente do LLM.

**Dinâmicos** (`tools.dry_run_patch`): o patch roda contra uma tabela temporária
dentro de transação **revertida**. O banco real nunca é tocado no dry-run.

**Gates de aceite** (`apply_patch`): duplicatas zeradas, P99 não aumenta, canal
dentro do domínio, `customer_id` não inventado, perda de linhas ≤ 20%.

**Sanitização de saída** (`postprocess`): remove cercas markdown e valida o
schema de cada JSON como callback de cada Task.

---

## Resultado medido

| Métrica | BEFORE (`stg.sales`) | AFTER (`gold.sales_clean`) |
|---|---:|---:|
| Linhas | 5.117 | 5.091 |
| Duplicatas | 26 | 0 |
| `unit_price` ≤ 0 ou nulo | 51 | 0 |
| Canal fora do domínio | 1.442 | 0 |
| Rótulos distintos de canal | 6 | 3 |
| `customer_id` ausente | 88 | 88 *(preservado, não inventado)* |
| P01 / P99 | 33,87 / 229,28 | 36,92 / 226,82 |

Perda de linhas: **0,51%** — apenas as duplicatas.

---

## Estrutura

```
agentic-data-quality/
  data/sales_raw.csv
  reports/
    baseline_checks.json        # checagens determinísticas
    plan.json                   # T0 Orchestrator
    analysis_findings.json      # T1 Analyst
    patch.sql                   # T2 DataEngineer
    patch_reference.sql         # gabarito determinístico / fallback
    patch_agent_rejected.sql    # patch do agente que falhou no dry-run (auditoria)
    validation_report.json      # T3 Validator — métricas BEFORE/AFTER reais
    RCA_report.md               # T4 Reviewer
    RCA_report_medido.md        # RCA determinístico (contra-prova)
    gold_snapshot.csv
  src/
    config.py            # URIs, tabelas, flag REQUIRE_HUMAN_APPROVAL
    ingest.py            # raw/stg, parse de datas multi-formato
    checks.py            # KPIs objetivos → baseline_checks.json
    tools.py             # ferramentas dos agentes + guardrails + dry-run
    postprocess.py       # sanitização e validação de schema das saídas do LLM
    prompts.py           # prompts de sistema por papel
    crew.py              # agentes, tasks e DAG
    reference_patch.py   # patch determinístico (gabarito/fallback)
    apply_patch.py       # portão humano, aplicação, métricas BEFORE/AFTER
    rca.py               # RCA determinístico a partir das métricas
    run_workflow.py      # orquestração ponta a ponta
    quick_validate.py    # atalho legado (constrói a gold sem passar pelos agentes)
```

---

## Decisões de design

- **Winsorização em vez de remoção** de outliers: preserva massa de dados e não
  distorce volume de vendas.
- **`customer_id` permanece `NULL`**: imputar criaria dado falso e contaminaria
  análise de recorrência.
- **Canal desconhecido vira `NULL`**, não um bucket-padrão: mascarar rótulo novo
  é pior que expô-lo.
- **`ORDER BY` determinístico no `ROW_NUMBER()`**: sem isso, qual duplicata
  sobrevive muda entre execuções e o patch deixa de ser reprodutível.
- **Fallback auditado**: se o patch do agente não executa, o de referência assume
  e o patch rejeitado é preservado para discussão em sala.
- **RCA determinístico paralelo**: impede que o Reviewer declare "aplicado com
  sucesso" quando nada foi aplicado.


## Testes

```bash
python -m tests.test_pipeline   # 13 checagens, sem LLM e sem chave de API
```
