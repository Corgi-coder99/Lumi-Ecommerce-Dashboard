-- 05_cohort_retention.sql
-- Business question: of the customers acquired in a given month, what share comes back
-- to buy again in the following months?
-- Cohort = calendar month (Paris time) of the customer's first completed order.
-- Retention in month N = customers of the cohort with at least one completed order in
-- the N-th calendar month after the cohort month / cohort size. Month 0 is always 100%.
-- Months that are not finished in the data (data ends 2026-11-15) are shown as NULL,
-- and the latest cohorts are partly incomplete (see README, Limitations).
-- Customers are matched across channels by customer_key (assumption A8).

WITH orders AS (
    SELECT DISTINCT
           f.customer_key,
           d.year * 12 + d.month AS month_no
    FROM fact_order_line AS f
    JOIN dim_date        AS d ON d.date_key = f.date_key
    WHERE f.status = 'completed'
      AND f.date_key <= 20261115
),
cohorts AS (
    SELECT customer_key,
           MIN(month_no) AS cohort_no
    FROM orders
    GROUP BY customer_key
),
activity AS (
    SELECT c.cohort_no,
           o.month_no - c.cohort_no AS month_index,
           COUNT(DISTINCT o.customer_key) AS active_customers
    FROM orders  AS o
    JOIN cohorts AS c ON c.customer_key = o.customer_key
    WHERE o.month_no - c.cohort_no BETWEEN 0 AND 6
    GROUP BY c.cohort_no, o.month_no - c.cohort_no
),
sized AS (
    SELECT a.*,
           MAX(CASE WHEN month_index = 0 THEN active_customers END)
               OVER (PARTITION BY cohort_no) AS cohort_size
    FROM activity AS a
)
SELECT CONCAT(FLOOR((cohort_no - 1) / 12), '-', LPAD(MOD(cohort_no - 1, 12) + 1, 2, '0')) AS cohort_month,
       MAX(cohort_size) AS cohort_size,
       -- 2026-11 is month_no 2026*12 + 11 = 24323; later months do not exist yet
       MAX(CASE WHEN month_index = 0 AND cohort_no + 0 <= 24323 THEN ROUND(100 * active_customers / cohort_size, 1) END) AS m0_pct,
       MAX(CASE WHEN month_index = 1 AND cohort_no + 1 <= 24323 THEN ROUND(100 * active_customers / cohort_size, 1) END) AS m1_pct,
       MAX(CASE WHEN month_index = 2 AND cohort_no + 2 <= 24323 THEN ROUND(100 * active_customers / cohort_size, 1) END) AS m2_pct,
       MAX(CASE WHEN month_index = 3 AND cohort_no + 3 <= 24323 THEN ROUND(100 * active_customers / cohort_size, 1) END) AS m3_pct,
       MAX(CASE WHEN month_index = 4 AND cohort_no + 4 <= 24323 THEN ROUND(100 * active_customers / cohort_size, 1) END) AS m4_pct,
       MAX(CASE WHEN month_index = 5 AND cohort_no + 5 <= 24323 THEN ROUND(100 * active_customers / cohort_size, 1) END) AS m5_pct,
       MAX(CASE WHEN month_index = 6 AND cohort_no + 6 <= 24323 THEN ROUND(100 * active_customers / cohort_size, 1) END) AS m6_pct
FROM sized
GROUP BY cohort_no
ORDER BY cohort_no;
