-- 07_repeat_rate.sql
-- Business question: which acquisition channel brings customers who buy again?
-- A customer is "repeat" if they have 2 or more distinct completed orders.
-- Channel = sales platform of the customer's first completed order (ties on the same
-- timestamp are broken by order_id). Customers are matched across channels
-- (assumption A8), so a repeat order may be placed on another platform.
-- Scope: completed orders, date_key <= 20261115. A total row is added at the bottom.

WITH orders AS (
    SELECT customer_key,
           order_id,
           platform,
           MIN(order_ts_local) AS order_ts
    FROM fact_order_line
    WHERE status = 'completed'
      AND date_key <= 20261115
    GROUP BY customer_key, order_id, platform
),
numbered AS (
    SELECT o.*,
           ROW_NUMBER() OVER (PARTITION BY customer_key ORDER BY order_ts, order_id) AS order_no,
           COUNT(*)     OVER (PARTITION BY customer_key)                            AS total_orders
    FROM orders AS o
),
customer AS (
    SELECT customer_key,
           platform     AS first_platform,
           total_orders
    FROM numbered
    WHERE order_no = 1
)
SELECT COALESCE(p.display_name, 'All channels')                       AS first_channel,
       COUNT(*)                                                       AS customers,
       SUM(c.total_orders >= 2)                                       AS repeat_customers,
       ROUND(100 * SUM(c.total_orders >= 2) / COUNT(*), 1)            AS repeat_rate_pct,
       ROUND(AVG(c.total_orders), 2)                                  AS avg_orders_per_customer
FROM customer AS c
JOIN dim_platform AS p ON p.platform = c.first_platform
GROUP BY p.display_name WITH ROLLUP
ORDER BY GROUPING(p.display_name), repeat_rate_pct DESC;
