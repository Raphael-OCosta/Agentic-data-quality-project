# RCA — Incidente de Qualidade de Dados em `stg.sales`

> Relatório gerado deterministicamente a partir de `reports/baseline_checks.json` e
> `reports/validation_report.json` em 11/09/2026 14:42 UTC. Todos os números abaixo foram medidos
> no DuckDB, não estimados.

## 1. Contexto

A tabela diária de vendas apresentou dois eventos anômalos em julho de 2025: uma
queda acentuada em **09/07** e um pico em **15/07**. Em paralelo, a camada de
staging acumulava problemas crônicos de qualidade — duplicidade por chave de
pedido, preços zerados e outliers, rótulos de canal inconsistentes e
`customer_id` ausente. O workflow agêntico foi acionado para distinguir efeito de
negócio de defeito de dados e propor correção segura para a camada `gold.sales_clean`.

## 2. Evidências

### 2.1 Baseline da staging

| Métrica | Valor |
|---|---:|
| Linhas | 5,117 |
| Pares (order_id, date_parsed) duplicados | 26 |
| Linhas envolvidas em duplicidade | 52 |
| `unit_price` nulo ou <= 0 | 51 |
| `customer_id` ausente | 88 |
| Datas não parseáveis | 0 |
| P01 / P99 de `unit_price` | 33.87 / 229.28 |

### 2.2 Sazonalidade × bug

| Dia | Linhas | Pedidos distintos | Linhas excedentes | Desvio vs. média móvel 7d |
|---|---:|---:|---:|---:|
| 2025-07-08 | 48 | 48 | 0 | -14.1% |
| 2025-07-09 | 39 | 39 | 0 | -30.7% |
| 2025-07-10 | 53 | 53 | 0 | -2.9% |
| 2025-07-14 | 46 | 46 | 0 | -11.0% |
| 2025-07-15 | 83 | 57 | 26 | +59.6% |
| 2025-07-16 | 53 | 53 | 0 | -7.0% |

- Quedas relevantes detectadas: `2025-07-07, 2025-07-09, 2025-07-17, 2025-07-22, 2025-07-28`
- Picos relevantes detectados: `2025-07-05, 2025-07-06, 2025-07-15`
- Dias com linhas duplicadas: `2025-07-15`

**Leitura:** a queda de **09/07** aparece como desvio negativo isolado, sem
duplicidade associada — comportamento compatível com **feriado estadual em SP
(Revolução Constitucionalista)**, ou seja, **efeito de negócio**. O pico de
**15/07** vem acompanhado de linhas excedentes para os mesmos `order_id` no mesmo
dia — assinatura de **double ingestion**, ou seja, **bug de dados**.

Consequência prática: 09/07 **não** deve ser corrigido (corrigir apagaria um fato
real do negócio); 15/07 **deve** ser deduplicado.

### 2.3 Label drift de canal

| Rótulo bruto (`channel_raw`) | Normalizado (`channel_norm`) | Linhas | No domínio? |
|---|---|---:|---|
| `market_place` | `market_place` | 597 | **não** |
| `marketplace` | `marketplace` | 590 | sim |
| `MarketPlace` | `marketplace` | 578 | sim |
| `Online` | `online` | 458 | sim |
| `store` | `store` | 439 | **não** |
| `In-Store` | `in_store` | 425 | sim |
| `online` | `online` | 424 | sim |
| `IN_STORE` | `in_store` | 412 | sim |
| `in_store` | `in_store` | 406 | sim |
| `on-line` | `on_line` | 406 | **não** |
| `ONLINE` | `online` | 382 | sim |

**1,442 linhas** (3 rótulos) estão fora do domínio `{online, in_store, marketplace}`.

## 3. Correção proposta

Patch efetivo: `reports/patch.sql`

1. **Deduplicação** por `(order_id, date_parsed)` via `ROW_NUMBER()` mantendo
   `rn = 1`, com `ORDER BY` determinístico (patch reprodutível entre execuções).
2. **Winsorização** de `unit_price` no intervalo `[p01, p99]` = `[33.87, 229.28]`,
   com clamp explícito; valores `<= 0` recebem `p01`. Escolha deliberada por
   winsorizar em vez de remover: preserva massa de dados e não distorce volume.
3. **Normalização de canal** para o domínio `{online, in_store, marketplace}`,
   mapeando explicitamente as variantes `on_line`, `store` e `market_place`.
   Rótulo desconhecido resulta em `NULL` — nunca é forçado a um bucket.
4. **`customer_id` preservado como `NULL`** quando ausente. Imputar aqui criaria
   dado falso e contaminaria qualquer análise de recorrência de cliente.
5. **Idempotência**: `CREATE OR REPLACE TABLE` restrito ao schema `gold`;
   `raw` e `stg` permanecem intocados.

## 4. Validação (antes × depois)

Medição real em dry-run (transação revertida), não estimativa:

| Métrica | BEFORE (`stg.sales`) | AFTER (`gold.sales_clean`) | Δ |
|---|---:|---:|---:|
| Linhas | 5,117 | 5,091 | -26 |
| Duplicatas estimadas | 26 | 0 | -26 |
| `unit_price` <= 0 ou nulo | 51 | 0 | -51 |
| Canal fora do domínio | 1,442 | 0 | -1,442 |
| `customer_id` ausente | 88 | 88 | +0 |
| Rótulos distintos de canal | 6 | 3 | -3 |
| P01 de `unit_price` | 33.87 | 33.87 | +0.00 |
| P99 de `unit_price` | 229.28 | 229.28 | -0.00 |

Gates de aceite:

| Gate | Resultado |
|---|---|
| `dedupe_zerou_duplicatas` | ✅ passou |
| `p99_nao_aumentou` | ✅ passou |
| `canal_dentro_do_dominio` | ✅ passou |
| `customer_id_nao_inventado` | ✅ passou |
| `perda_de_linhas_aceitavel` | ✅ passou |

Perda de linhas: **0.51%** (limite: 20%).

## 5. Decisão

**APROVADO para aplicar**

Estado de aplicação: **patch APLICADO em `gold.sales_clean`**.
A materialização ocorreu após aprovação humana explícita (`--approve`).

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
