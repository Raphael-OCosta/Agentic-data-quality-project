CREATE OR REPLACE TABLE gold.sales_clean AS
WITH deduplicated AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY order_id, date_parsed ORDER BY order_id) AS rn
    FROM stg.sales
),
clamped AS (
    SELECT order_id,
           date_parsed,
           store_id,
           product_id,
           CASE
               WHEN unit_price < 33.8652 THEN 33.8652  -- p01
               WHEN unit_price > 229.2788 THEN 229.2788  -- p99
               ELSE unit_price
           END AS unit_price,
           quantity,
           customer_id,
           CASE
               WHEN channel_norm IN ('online', 'on_line') THEN 'online'
               WHEN channel_norm IN ('in_store', 'store') THEN 'in_store'
               WHEN channel_norm IN ('marketplace', 'market_place') THEN 'marketplace'
               ELSE NULL
           END AS channel_norm,
           channel_raw
    FROM deduplicated
    WHERE rn = 1
)
SELECT *
FROM clamped
WHERE unit_price > 0;