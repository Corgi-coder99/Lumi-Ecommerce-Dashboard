-- 01_kpi_summary.sql
-- Business question: how is the store doing overall? Revenue, orders, gross profit,
-- ad spend, CIR (ad spend as a share of revenue) and blended ROAS.
-- Scope: completed orders only, date_key <= 20261115 (end of the data).
-- Definitions (all excl. VAT):
--   revenue      = SUM(net_ht)
--   gross profit = revenue - marketplace commission - cost of goods
--   CIR          = ad spend / revenue
--   blended ROAS = revenue / ad spend

WITH sales AS (
    SELECT COUNT(DISTINCT order_id)                    AS orders,
           COUNT(DISTINCT customer_key)                AS customers,
           SUM(net_ht)                                 AS revenue_ht,
           SUM(net_ht - platform_fee - cogs)           AS gross_profit
    FROM fact_order_line
    WHERE status = 'completed'
      AND date_key <= 20261115
),
ads AS (
    SELECT SUM(spend) AS ad_spend
    FROM fact_ads_daily
    WHERE date_key <= 20261115
)
SELECT s.orders,
       s.customers,
       ROUND(s.revenue_ht, 2)                                 AS revenue_ht_eur,
       ROUND(s.gross_profit, 2)                               AS gross_profit_eur,
       ROUND(100 * s.gross_profit / s.revenue_ht, 1)          AS gross_margin_pct,
       ROUND(a.ad_spend, 2)                                   AS ad_spend_eur,
       ROUND(s.gross_profit - a.ad_spend, 2)                  AS net_profit_eur,
       ROUND(100 * a.ad_spend / s.revenue_ht, 1)              AS cir_pct,
       ROUND(s.revenue_ht / a.ad_spend, 2)                    AS blended_roas
FROM sales AS s
CROSS JOIN ads AS a;
