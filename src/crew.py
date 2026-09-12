# src/crew.py
"""
Crew e DAG do workflow agêntico de qualidade de dados (pt-BR).

Fluxo sequencial:
  T0 Orchestrator -> reports/plan.json
  T1 Analyst      -> reports/analysis_findings.json
  T2 DataEngineer -> reports/patch.sql
  T3 Validator    -> reports/validation_report.json
  T4 Reviewer     -> reports/RCA_report.md

Correções em relação à versão anterior:
  - Os agentes agora RECEBEM ferramentas (src/tools.py estava órfão). Sem elas,
    Analyst e Validator só podiam alucinar números.
  - Cada Task tem callback de pós-processamento (src/postprocess.py) que remove
    cercas markdown e valida o schema — a causa dos JSONs inválidos anteriores.
  - As descrições passam o schema real da staging (channel_norm/channel_raw,
    date_parsed) e os percentis do baseline, eliminando `created_at`/`channel`
    e os p01/p99 inventados.
  - O Validator é obrigado a chamar a ferramenta de dry-run: o relatório de
    validação passa a conter métricas medidas, não estimativas em prosa.
"""

from crewai import Agent, Task, Crew, Process, LLM

from .config import STG_TABLE, GOLD_TABLE
from .postprocess import make_task_callback
from .prompts import (
    SYSTEM_ORCHESTRATOR,
    SYSTEM_ANALYST,
    SYSTEM_DATA_ENGINEER,
    SYSTEM_VALIDATOR,
    SYSTEM_REVIEWER,
)
from .tools import ANALYST_TOOLS, ENGINEER_TOOLS, VALIDATOR_TOOLS, load_baseline

# =========================
# Modelos LLM
# =========================
LLM_SOLID = LLM(model="openai/gpt-4o", temperature=0.0)
LLM_THINK = LLM(model="openai/gpt-4o-mini", temperature=0.1)

# =========================
# Cadeado de idioma
# =========================
LANG_LOCK = (
    "ATENÇÃO: responda EXCLUSIVAMENTE em português do Brasil (pt-BR). "
    "Devolva SOMENTE o conteúdo pedido, SEM cercas markdown (nada de ```json ou ```sql). "
    "Para saídas em JSON, mantenha as CHAVES exatamente como no schema; "
    "os textos/descrições DEVEM estar em pt-BR.\n"
)

# Contrato de dados repassado aos agentes — evita colunas inventadas.
SCHEMA_NOTE = (
    f"ESQUEMA REAL de {STG_TABLE} (use exatamente estes nomes): "
    "order_id VARCHAR, date_parsed DATE, store_id VARCHAR, product_id VARCHAR, "
    "unit_price DOUBLE, quantity INTEGER, customer_id VARCHAR, "
    "channel_norm VARCHAR, channel_raw VARCHAR. "
    "NÃO existem as colunas created_at, updated_at nem channel. "
    "Domínio válido de canal: {online, in_store, marketplace}.\n"
)


def _baseline_note() -> str:
    try:
        b = load_baseline()
    except FileNotFoundError:
        return "BASELINE: indisponível — chame a ferramenta 'Métricas de baseline'.\n"
    return (
        "BASELINE MEDIDO (reports/baseline_checks.json): "
        f"n_rows={b['n_rows']}, n_dup_pairs={b['n_dup_pairs']}, n_dup_rows={b['n_dup_rows']}, "
        f"n_missing_customer={b['n_missing_customer']}, "
        f"n_price_zero_or_null={b['n_price_zero_or_null']}, "
        f"p01={round(float(b['p01']), 4)}, p99={round(float(b['p99']), 4)}. "
        "Use ESTES valores; não invente percentis.\n"
    )


CTX = LANG_LOCK + SCHEMA_NOTE + _baseline_note()

# =========================
# Agents
# =========================
orchestrator = Agent(
    name="Orchestrator",
    role="Coordenação e Planejamento",
    goal="Orquestrar análise → patch → validação → RCA",
    backstory="Coordena times e pipelines de dados com foco em confiabilidade.",
    verbose=True,
    llm=LLM_SOLID,
    system_prompt=SYSTEM_ORCHESTRATOR,
)

analyst = Agent(
    name="Analyst",
    role="Análise de Qualidade",
    goal="Separar queda sazonal de bug de dados com evidência quantitativa.",
    backstory="Analista de dados especializado em qualidade e métricas.",
    verbose=True,
    llm=LLM_THINK,
    tools=ANALYST_TOOLS,
    system_prompt=SYSTEM_ANALYST,
)

data_engineer = Agent(
    name="DataEngineer",
    role="Engenharia de Dados",
    goal="Gerar patch SQL seguro/idempotente para a camada gold.",
    backstory="Engenheiro de dados focado em segurança e reprodutibilidade.",
    verbose=True,
    llm=LLM_THINK,
    tools=ENGINEER_TOOLS,
    system_prompt=SYSTEM_DATA_ENGINEER,
)

validator = Agent(
    name="Validator",
    role="Validação (dry-run executado)",
    goal="Checar segurança, sintaxe e impacto REAL antes de aplicar.",
    backstory="QA de dados metódico e avesso a riscos.",
    verbose=True,
    llm=LLM_SOLID,
    tools=VALIDATOR_TOOLS,
    system_prompt=SYSTEM_VALIDATOR,
)

reviewer = Agent(
    name="Reviewer",
    role="Revisor & RCA",
    goal="Consolidar evidências e emitir parecer final honesto.",
    backstory="Especialista em RCA de incidentes de dados.",
    verbose=True,
    llm=LLM_SOLID,
    system_prompt=SYSTEM_REVIEWER,
)

# =========================
# Tasks (DAG sequencial)
# =========================
t0_plan = Task(
    description=(
        f"{CTX}"
        f"Gere o PLANO de execução (DuckDB) para o pipeline {STG_TABLE} → {GOLD_TABLE}. "
        "Respeite o OUTPUT JSON SCHEMA do prompt e inclua as etapas: "
        "Analisar baseline (A1), Propor Patch SQL (E1), Validar em dry-run (V1), "
        "Revisar e redigir RCA (R1). Explique como cada artefato é gerado em 'reports/'."
    ),
    agent=orchestrator,
    expected_output="JSON puro com a chave 'tasks' (A1, E1, V1, R1) conforme schema.",
    output_file="reports/plan.json",
    callback=make_task_callback("reports/plan.json"),
    config={},
)

t1_analysis = Task(
    description=(
        f"{CTX}"
        "OBRIGATÓRIO: use as ferramentas disponíveis antes de concluir — "
        "'Métricas de baseline', 'Evidência de sazonalidade x bug' (julho/2025) e "
        "'Variantes de canal'. Cada finding deve citar NÚMEROS retornados por elas.\n"
        "Responda explicitamente: a queda de 09/07 é sazonalidade de negócio (feriado em SP) "
        "ou bug? E o pico de 15/07 é demanda real ou double ingestion? "
        "Justifique com desvio vs. média móvel de 7 dias, comparação week-over-week e "
        "contagem de linhas duplicadas por dia.\n"
        f"Priorize os problemas da staging '{STG_TABLE}' (duplicidade por (order_id, date_parsed), "
        "outliers/zeros de unit_price, label drift de channel_norm, customer_id nulo) "
        "e siga o OUTPUT JSON SCHEMA do prompt (findings + notes)."
    ),
    agent=analyst,
    expected_output="JSON puro (analysis_findings.json) com findings[] contendo problem, evidence, business_impact, priority.",
    output_file="reports/analysis_findings.json",
    callback=make_task_callback("reports/analysis_findings.json"),
    context=[t0_plan],
    config={},
)

t2_patch = Task(
    description=(
        f"{CTX}"
        f"Gere um patch SQL idempotente que crie '{GOLD_TABLE}' a partir de '{STG_TABLE}'.\n"
        "Requisitos obrigatórios:\n"
        "- CREATE OR REPLACE TABLE (idempotência); escrever APENAS no schema gold;\n"
        "- Dedupe por (order_id, date_parsed) via ROW_NUMBER() mantendo rn=1, "
        "com ORDER BY determinístico;\n"
        "- Winsorizar unit_price em [p01, p99] do baseline com clamp explícito; "
        "preços <= 0 também devem ser tratados;\n"
        "- Normalizar canal via CASE WHEN sobre channel_norm, com o mapeamento COMPLETO:\n"
        "    'online' e 'on_line'        -> 'online'\n"
        "    'in_store' e 'store'        -> 'in_store'\n"
        "    'marketplace' e 'market_place' -> 'marketplace'\n"
        "    qualquer outro rótulo       -> NULL\n"
        "  ATENÇÃO: os rótulos que JÁ estão corretos ('online', 'in_store', 'marketplace') "
        "também precisam aparecer no CASE. Se caírem no ELSE, você destrói 3.675 linhas "
        "válidas — foi exatamente o erro da execução anterior;\n"
        "- NÃO inventar customer_id: ausente permanece NULL;\n"
        "- Documentar p01/p99 usados em comentários SQL.\n"
        "ANTES de entregar, chame 'Validar guardrails do SQL' e 'Dry-run do patch'. "
        "Se o dry-run falhar, CORRIJA o SQL e repita até executar com sucesso.\n"
        "Não use DROP/ALTER/UPDATE/DELETE em raw/stg."
    ),
    agent=data_engineer,
    expected_output="Arquivo SQL puro, comentado, que executa com sucesso no dry-run.",
    output_file="reports/patch.sql",
    callback=make_task_callback("reports/patch.sql"),
    context=[t1_analysis],
    config={},
)

t3_validate = Task(
    description=(
        f"{CTX}"
        "OBRIGATÓRIO: chame a ferramenta 'Dry-run do patch' passando o SQL recebido no "
        "contexto e REPRODUZA os números retornados. Não estime em prosa: os campos de "
        "before_after devem conter os valores numéricos medidos (n, dup_est, p01, p99, "
        "n_price_zero_or_null, n_channel_off_domain, n_missing_customer).\n"
        "Liste comandos proibidos encontrados (se houver) e conclua com syntax_ok "
        "refletindo se o SQL de fato executou. Siga o OUTPUT JSON SCHEMA do Validator."
    ),
    agent=validator,
    expected_output="JSON puro (validation_report.json) com before_after preenchido com números medidos.",
    output_file="reports/validation_report.json",
    callback=make_task_callback("reports/validation_report.json"),
    context=[t2_patch],
    config={},
)

t4_rca = Task(
    description=(
        f"{CTX}"
        "Com base nos achados (T1) e na validação (T3), redija o RCA em Markdown com: "
        "Contexto, Evidências (com números), Correção proposta, Validação (antes × depois), "
        "Decisão e Próximos passos.\n"
        "REGRA DE HONESTIDADE: o patch AINDA NÃO FOI APLICADO neste ponto do fluxo "
        "(REQUIRE_HUMAN_APPROVAL=True). A decisão deve ser 'APROVADO para aplicar' ou "
        "'NECESSITA REVISÃO'. NUNCA afirme que as correções já foram implementadas."
    ),
    agent=reviewer,
    expected_output="Markdown puro (RCA), sem cercas.",
    output_file="reports/RCA_report.md",
    callback=make_task_callback("reports/RCA_report.md"),
    context=[t1_analysis, t3_validate],
    config={},
)

# =========================
# Crew (sequencial)
# =========================
crew = Crew(
    agents=[orchestrator, analyst, data_engineer, validator, reviewer],
    tasks=[t0_plan, t1_analysis, t2_patch, t3_validate, t4_rca],
    process=Process.sequential,
    verbose=True,
)
