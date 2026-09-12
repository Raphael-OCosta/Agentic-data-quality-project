-- =====================================================================
-- patch.sql (referência determinística)
-- Origem : stg.sales
-- Destino: gold.sales_clean
-- Percentis do baseline (reports/baseline_checks.json):
--   p01 = 33.8652
--   p99 = 229.2788
-- Idempotente: CREATE OR REPLACE. Não toca em raw/stg.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS gold;

CREATE OR REPLACE TABLE gold.sales_clean AS
WITH bounds AS (
  -- limites de winsorização: recalculados aqui para o patch ser auto-contido,
  -- mas conferem com os valores documentados acima.
  SELECT
    quantile_cont(unit_price, 0.01) AS p01,
    quantile_cont(unit_price, 0.99) AS p99
  FROM stg.sales
  WHERE unit_price IS NOT NULL AND unit_price > 0
),
ranked AS (
  -- 1 linha por (order_id, date_parsed): resolve o double ingestion de 15/07.
  -- ORDER BY determinístico para o patch ser reprodutível entre execuções.
  SELECT
    s.*,
    ROW_NUMBER() OVER (
      PARTITION BY s.order_id, s.date_parsed
      ORDER BY
        s.store_id, s.product_id,
        COALESCE(s.customer_id, ''), COALESCE(s.channel_raw, ''),
        COALESCE(s.unit_price, 0), COALESCE(s.quantity, 0)
    ) AS rn
  FROM stg.sales AS s
),
cleaned AS (
  SELECT
    r.order_id,
    r.date_parsed,
    r.store_id,
    r.product_id,
    -- winsorização: clamp explícito em [p01, p99]; preços <= 0 viram p01.
    CASE
      WHEN r.unit_price IS NULL THEN NULL
      WHEN r.unit_price <= 0     THEN b.p01
      WHEN r.unit_price < b.p01  THEN b.p01
      WHEN r.unit_price > b.p99  THEN b.p99
      ELSE r.unit_price
    END AS unit_price,
    r.quantity,
    -- customer_id NUNCA é inventado: ausente permanece NULL.
    r.customer_id,
    -- normalização estrita de canal para o domínio permitido.
    CASE
      WHEN r.channel_norm IN ('online', 'on_line')                 THEN 'online'
      WHEN r.channel_norm IN ('in_store', 'store', 'instore')      THEN 'in_store'
      WHEN r.channel_norm IN ('marketplace', 'market_place')       THEN 'marketplace'
      ELSE NULL  -- rótulo desconhecido não é forçado a um bucket: fica explícito.
    END AS channel,
    r.channel_raw,
    -- flags de auditoria: permitem medir o efeito do patch sem reprocessar.
    (r.unit_price IS NOT NULL AND (r.unit_price < b.p01 OR r.unit_price > b.p99)) AS was_winsorized,
    (r.channel_norm NOT IN ('online', 'in_store', 'marketplace'))                 AS was_relabeled
  FROM ranked r
  CROSS JOIN bounds b
  WHERE r.rn = 1
)
SELECT * FROM cleaned;
