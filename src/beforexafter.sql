WITH before AS (
  SELECT
    COUNT(*)                                                   AS n,
    COUNT(*) - COUNT(DISTINCT order_id||'|'||date_parsed)      AS dup_est,
    quantile_cont(unit_price, 0.01)                            AS p01,
    quantile_cont(unit_price, 0.99)                            AS p99
  FROM stg.sales
  WHERE unit_price IS NOT NULL
),
after AS (
  SELECT
    COUNT(*)                                                   AS n,
    COUNT(*) - COUNT(DISTINCT order_id||'|'||date_parsed)      AS dup_est,
    quantile_cont(unit_price, 0.01)                            AS p01,
    quantile_cont(unit_price, 0.99)                            AS p99
  FROM gold.sales_clean
  WHERE unit_price IS NOT NULL
)
SELECT
  b.n      AS n_before,   a.n      AS n_after,   (a.n - b.n)           AS n_delta,
  b.dup_est AS dup_before, a.dup_est AS dup_after, (a.dup_est - b.dup_est) AS dup_delta,
  b.p01    AS p01_before, a.p01    AS p01_after, (a.p01 - b.p01)       AS p01_delta,
  b.p99    AS p99_before, a.p99    AS p99_after, (a.p99 - b.p99)       AS p99_delta,
  CASE WHEN b.n=0 THEN NULL ELSE (a.n - b.n) * 1.0 / b.n END AS n_pct_delta
FROM before b, after a;
