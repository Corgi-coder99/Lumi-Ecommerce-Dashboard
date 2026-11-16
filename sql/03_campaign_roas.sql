-- 03_campaign_roas.sql
-- Business question: which ad campaigns return the most per euro, and where do the
-- ad platforms' own numbers look too good?
-- Scope: date_key <= 20261115. Spend is excl. VAT; platform_conv_value is the value each
-- ad platform attributes to itself and includes VAT (see assumption A7), so
-- platform ROAS is overstated by about 20% against an excl.-VAT basis.
-- Orders are not linked to campaigns, so this is platform-reported performance only.
-- Metrics: platform ROAS = conv value / spend; CPC = spend / clicks;
--          CTR = clicks / impressions; conversion rate = conversions / clicks.

WITH campaign AS (
    SELECT c.channel,
           a.campaign,
           SUM(a.spend)                 AS spend,
           SUM(a.impressions)           AS impressions,
           SUM(a.clicks)                AS clicks,
           SUM(a.platform_conversions)  AS conversions,
           SUM(a.platform_conv_value)   AS conv_value
    FROM fact_ads_daily AS a
    JOIN dim_campaign   AS c ON c.campaign = a.campaign
    WHERE a.date_key <= 20261115
    GROUP BY c.channel, a.campaign
)
SELECT RANK() OVER (ORDER BY conv_value / spend DESC)   AS roas_rank,
       channel,
       campaign,
       ROUND(spend, 2)                                  AS spend_eur,
       ROUND(100 * spend / SUM(spend) OVER (), 1)       AS spend_share_pct,
       clicks,
       conversions,
       ROUND(conv_value, 2)                             AS platform_conv_value_eur,
       ROUND(conv_value / spend, 2)                     AS platform_roas,
       ROUND(spend / clicks, 3)                         AS cpc_eur,
       ROUND(100 * clicks / impressions, 2)             AS ctr_pct,
       ROUND(100 * conversions / clicks, 2)             AS conversion_rate_pct
FROM campaign
ORDER BY roas_rank;
