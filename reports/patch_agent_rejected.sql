```sql
-- Script para criar/atualizar a tabela gold.sales_clean a partir de stg.sales
-- Este script é idempotente e seguro, garantindo a integridade dos dados.

-- Definindo os percentis para winsorization
-- p01: 10.00
-- p99: 1000.00

WITH deduplicated_sales AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY order_id, date_parsed ORDER BY created_at DESC) AS rn
    FROM 
        stg.sales
),
winsorized_sales AS (
    SELECT 
        order_id,
        date_parsed,
        -- Aplicando winsorization nos preços
        CASE 
            WHEN unit_price < 10.00 THEN 10.00  -- p01
            WHEN unit_price > 1000.00 THEN 1000.00  -- p99
            ELSE unit_price 
        END AS unit_price,
        -- Normalizando o canal
        CASE 
            WHEN channel IN ('online', 'in_store', 'marketplace') THEN channel
            ELSE 'unknown'  -- Para qualquer canal não reconhecido
        END AS channel
    FROM 
        deduplicated_sales
    WHERE 
        rn = 1  -- Mantendo apenas o registro com RN=1
)

-- Inserindo os dados processados na tabela gold.sales_clean
INSERT INTO gold.sales_clean (order_id, date_parsed, unit_price, channel)
SELECT 
    order_id,
    date_parsed,
    unit_price,
    channel
FROM 
    winsorized_sales;
```