-- 02_sku_profit.sql
-- Business question: which SKUs and categories make money after marketplace fees and
-- cost of goods, and which SKUs lose money?
-- Scope: completed orders, date_key <= 20261115. Profit is before ad spend (ads cannot
-- be attributed to a SKU in this data). All amounts in EUR excl. VAT.
-- Output: one row per SKU with overall rank, rank inside its category and a loss flag.
-- Loss-making SKUs are the ones with profit_before_ads < 0.

WITH sku AS (
    SELECT p.sku,
           p.product_name,
           p.category,
           SUM(f.qty)                                 AS units,
           SUM(f.net_ht)                              AS revenue_ht,
           SUM(f.platform_fee)                        AS platform_fee,
           SUM(f.cogs)                                AS cogs,
           SUM(f.net_ht - f.platform_fee - f.cogs)    AS profit_before_ads
    FROM fact_order_line AS f
    JOIN dim_product     AS p ON p.sku = f.sku
    WHERE f.status = 'completed'
      AND f.date_key <= 20261115
    GROUP BY p.sku, p.product_name, p.category
),
ranked AS (
    SELECT sku.*,
           RANK() OVER (ORDER BY profit_before_ads DESC)                         AS profit_rank,
           RANK() OVER (PARTITION BY category ORDER BY profit_before_ads DESC)   AS rank_in_category,
           SUM(profit_before_ads) OVER (PARTITION BY category)                   AS category_profit,
           SUM(revenue_ht)        OVER (PARTITION BY category)                   AS category_revenue
    FROM sku
)
SELECT profit_rank,
       sku,
       product_name,
       category,
       rank_in_category,
       units,
       ROUND(revenue_ht, 2)                              AS revenue_ht_eur,
       ROUND(profit_before_ads, 2)                       AS profit_before_ads_eur,
       ROUND(100 * profit_before_ads / revenue_ht, 1)    AS margin_pct,
       CASE WHEN profit_before_ads < 0 THEN 'LOSS' ELSE '' END AS loss_flag,
       ROUND(category_profit, 2)                         AS category_profit_eur,
       ROUND(100 * category_profit / category_revenue, 1) AS category_margin_pct
FROM ranked
ORDER BY profit_rank;
