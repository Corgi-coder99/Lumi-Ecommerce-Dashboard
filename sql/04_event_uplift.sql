-- 04_event_uplift.sql
-- Business question: how much more revenue does the store make on sale-event days
-- (Prime Day, French Days, Soldes, Singles Day...) than on ordinary days?
-- Scope: completed orders, calendar days 2026-05-01 to 2026-11-15 (dim_date also holds
-- 2026-04-30 and 2026-11-16 as padding; these are excluded). Days with no sale count as 0.
-- Uplift = average daily revenue on the event's days / average daily revenue on days
-- with no event. A window function carries the non-event baseline to every row.
-- Revenue is excl. VAT. Events can overlap in the calendar: dim_date keeps one event per
-- day (lowest priority number), so each day belongs to at most one event.

WITH daily AS (
    SELECT d.date_key,
           d.event_name,
           COALESCE(SUM(f.net_ht), 0) AS revenue
    FROM dim_date AS d
    LEFT JOIN fact_order_line AS f
           ON f.date_key = d.date_key
          AND f.status = 'completed'
    WHERE d.date_key BETWEEN 20260501 AND 20261115
    GROUP BY d.date_key, d.event_name
),
with_baseline AS (
    SELECT daily.*,
           AVG(CASE WHEN event_name IS NULL THEN revenue END) OVER () AS baseline_daily_revenue
    FROM daily
)
SELECT event_name,
       COUNT(*)                                          AS event_days,
       ROUND(AVG(revenue), 2)                            AS avg_daily_revenue_eur,
       ROUND(MAX(baseline_daily_revenue), 2)             AS baseline_daily_revenue_eur,
       ROUND(AVG(revenue) / MAX(baseline_daily_revenue), 2) AS uplift_x,
       ROUND(100 * (AVG(revenue) / MAX(baseline_daily_revenue) - 1), 1) AS uplift_pct
FROM with_baseline
WHERE event_name IS NOT NULL
GROUP BY event_name
ORDER BY uplift_x DESC;
