-- 06_rfm_segments.sql
-- Business question: which customers are the most valuable, which are slipping away,
-- and how large is each group?
-- RFM on completed orders up to the reference date 2026-11-15:
--   Recency   = days since the customer's last completed order
--   Frequency = number of distinct completed orders
--   Monetary  = revenue excl. VAT (SUM(net_ht)), EUR
-- Each dimension gets a score 1..5 from NTILE(5), where 5 is best (most recent, most
-- orders, most revenue). Most customers have exactly one order, so frequency has many
-- ties; ties are broken by monetary value so that the quintiles are deterministic.
-- Segment rules (R = recency score, F = frequency score):
--   Champions     R >= 4 and F >= 4
--   Loyal         R >= 3 and F >= 3 (not Champions)
--   New           R >= 4 and F <= 2
--   Promising     R  = 3 and F <= 2
--   At risk       R <= 2 and F >= 3
--   Hibernating   R  = 2 and F <= 2
--   Lost          R  = 1 and F <= 2

WITH customer AS (
    SELECT customer_key,
           DATEDIFF('2026-11-15', MAX(DATE(order_ts_local))) AS recency_days,
           COUNT(DISTINCT order_id)                          AS frequency,
           SUM(net_ht)                                       AS monetary
    FROM fact_order_line
    WHERE status = 'completed'
      AND date_key <= 20261115
    GROUP BY customer_key
),
scored AS (
    SELECT customer.*,
           NTILE(5) OVER (ORDER BY recency_days DESC, customer_key)       AS r_score,
           NTILE(5) OVER (ORDER BY frequency, monetary, customer_key)     AS f_score,
           NTILE(5) OVER (ORDER BY monetary, customer_key)                AS m_score
    FROM customer
),
segmented AS (
    SELECT scored.*,
           CASE
               WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
               WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal'
               WHEN r_score >= 4                  THEN 'New'
               WHEN r_score  = 3                  THEN 'Promising'
               WHEN r_score <= 2 AND f_score >= 3 THEN 'At risk'
               WHEN r_score  = 2                  THEN 'Hibernating'
               ELSE                                    'Lost'
           END AS segment
    FROM scored
)
SELECT segment,
       COUNT(*)                                          AS customers,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)  AS customers_pct,
       ROUND(AVG(recency_days), 1)                       AS avg_recency_days,
       ROUND(AVG(frequency), 2)                          AS avg_orders,
       ROUND(AVG(monetary), 2)                           AS avg_revenue_eur,
       ROUND(SUM(monetary), 2)                           AS total_revenue_eur,
       ROUND(100 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1) AS revenue_pct
FROM segmented
GROUP BY segment
ORDER BY total_revenue_eur DESC;
