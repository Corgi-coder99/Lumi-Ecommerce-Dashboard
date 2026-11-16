-- 08_returns_by_channel.sql
-- Business question: where are returns concentrated? Return rate by sales channel and
-- product category.
-- Unlike the other queries this one needs returned orders, so it does NOT filter on
-- status = 'completed'. It uses completed + returned order lines (cancelled orders never
-- shipped and are excluded) with date_key <= 20261115.
-- Return rate = returned lines / (completed + returned lines), also shown by value
-- (net_ht excl. VAT). Return rates differ by channel largely because of an assumption in
-- the data generator (A12), not because of a real-market finding.
-- Output: one row per channel x category, plus channel subtotals and a grand total
-- (ROLLUP), with a rank of the category inside each channel.

WITH order_lines AS (
    SELECT pl.display_name AS channel,
           p.category,
           f.status,
           f.net_ht
    FROM fact_order_line AS f
    JOIN dim_platform    AS pl ON pl.platform = f.platform
    JOIN dim_product     AS p  ON p.sku = f.sku
    WHERE f.status IN ('completed', 'returned')
      AND f.date_key <= 20261115
),
agg AS (
    SELECT channel,
           category,
           COUNT(*)                                            AS lines_shipped,
           SUM(status = 'returned')                            AS lines_returned,
           SUM(CASE WHEN status = 'returned' THEN net_ht END)  AS value_returned,
           SUM(net_ht)                                         AS value_shipped,
           GROUPING(channel)                                   AS g_channel,
           GROUPING(category)                                  AS g_category
    FROM order_lines
    GROUP BY channel, category WITH ROLLUP
)
SELECT COALESCE(channel, 'All channels')                       AS channel,
       COALESCE(category, 'All categories')                    AS category,
       lines_shipped,
       lines_returned,
       ROUND(100 * lines_returned / lines_shipped, 1)          AS return_rate_pct,
       ROUND(100 * value_returned / value_shipped, 1)          AS return_value_pct,
       CASE WHEN g_category = 0
            THEN RANK() OVER (PARTITION BY channel, g_category
                              ORDER BY lines_returned / lines_shipped DESC)
       END                                                     AS rank_in_channel
FROM agg
ORDER BY g_channel, channel, g_category, return_rate_pct DESC;
