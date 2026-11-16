# SQL analysis queries

Eight MySQL 8.4 queries against the `lumi_dw` star schema (see [../docs/erd.md](../docs/erd.md) and [../docs/data-dictionary.md](../docs/data-dictionary.md)). Each file starts with a comment stating the business question and its definitions. They only read data (`SELECT`).

Common scope: orders with `status = 'completed'` and `date_key <= 20261115`. Revenue is excl. VAT (`net_ht`). All data is synthetic.

Run one file:

```bash
mysql -u lumi -h 127.0.0.1 lumi_dw < sql/01_kpi_summary.sql
```

(set `MYSQL_PWD` in your environment first.)

| File | Question it answers | Techniques |
|---|---|---|
| `01_kpi_summary.sql` | Revenue, orders, gross profit, ad spend, CIR and blended ROAS for the whole period | CTEs |
| `02_sku_profit.sql` | Which SKUs and categories make or lose money after fees and cost of goods? | CTEs, `RANK()`, window `SUM()` |
| `03_campaign_roas.sql` | Platform-reported ROAS, CPC, CTR and conversion rate per ad campaign | CTE, `RANK()`, window `SUM()` |
| `04_event_uplift.sql` | How much more revenue per day do sale events bring than ordinary days? | Calendar join, window `AVG()` baseline |
| `05_cohort_retention.sql` | Share of each monthly cohort that buys again in months 0 to 6 | Cohort CTEs, conditional pivot |
| `06_rfm_segments.sql` | RFM quintile scores and customer segments (reference date 2026-11-15) | `NTILE(5)`, `CASE` segmentation |
| `07_repeat_rate.sql` | Repeat-customer rate by the channel of the first order | `ROW_NUMBER()`, `WITH ROLLUP` |
| `08_returns_by_channel.sql` | Return rate by channel and category | `ROLLUP`, `GROUPING()`, `RANK()` |

## Reconciliation

Query 01 matches the numbers checked in the dashboard exactly: 1,186,856.31 EUR revenue, 32,110 orders, 371,116.18 EUR gross profit, 160,467.68 EUR ad spend, 26,994 customers. Query 07 totals 26,994 customers and 4,312 with two or more orders.

## Sample results

Real output from a run on the warehouse (first rows only).

**01_kpi_summary**

| orders | customers | revenue_ht_eur | gross_profit_eur | gross_margin_pct | ad_spend_eur | net_profit_eur | cir_pct | blended_roas |
|---|---|---|---|---|---|---|---|---|
| 32110 | 26994 | 1186856.31 | 371116.18 | 31.3 | 160467.68 | 210648.50 | 13.5 | 7.40 |

**02_sku_profit** (top 3 of 96; five SKUs lose money, the worst is LM064 Sunglasses 08 at -8,492.78 EUR)

| profit_rank | sku | category | units | revenue_ht_eur | profit_before_ads_eur | margin_pct |
|---|---|---|---|---|---|---|
| 1 | LM072 | Jewelry | 4695 | 138206.43 | 53590.53 | 38.8 |
| 2 | LM056 | Hats | 12220 | 108154.88 | 40646.86 | 37.6 |
| 3 | LM017 | Handbags | 2833 | 130282.28 | 40628.24 | 31.2 |

**03_campaign_roas** (top 3 of 9; the lowest is TT_Live_Ceintures at 0.91)

| roas_rank | channel | campaign | spend_eur | platform_roas | cpc_eur | conversion_rate_pct |
|---|---|---|---|---|---|---|
| 1 | google | GG_Search_Marque | 9112.48 | 11.48 | 0.232 | 5.99 |
| 2 | google | GG_Shopping_Portefeuilles | 22987.14 | 4.07 | 0.387 | 3.45 |
| 3 | meta | META_Retarget_Sacs | 24299.71 | 3.22 | 0.514 | 3.69 |

**04_event_uplift**

| event_name | event_days | avg_daily_revenue_eur | baseline_daily_revenue_eur | uplift_x |
|---|---|---|---|---|
| Jours Flash Prime | 2 | 8834.80 | 5644.47 | 1.57 |
| Singles Day 11.11 | 2 | 8866.22 | 5644.47 | 1.57 |
| Prime Day | 4 | 8558.90 | 5644.47 | 1.52 |

**05_cohort_retention** (first rows)

| cohort_month | cohort_size | m0_pct | m1_pct | m2_pct | m3_pct |
|---|---|---|---|---|---|
| 2026-05 | 3744 | 100.0 | 12.4 | 8.4 | 4.8 |
| 2026-06 | 3826 | 100.0 | 9.1 | 5.1 | 4.0 |
| 2026-07 | 4881 | 100.0 | 4.8 | 5.0 | 4.1 |

**06_rfm_segments** (top 3 segments by revenue)

| segment | customers | customers_pct | avg_recency_days | avg_orders | total_revenue_eur | revenue_pct |
|---|---|---|---|---|---|---|
| At risk | 6096 | 22.6 | 145.6 | 1.33 | 372730.87 | 31.4 |
| Champions | 4532 | 16.8 | 32.0 | 1.46 | 349377.61 | 29.4 |
| Loyal | 5568 | 20.6 | 64.1 | 1.18 | 292086.21 | 24.6 |

**07_repeat_rate**

| first_channel | customers | repeat_customers | repeat_rate_pct |
|---|---|---|---|
| Amazon.fr | 8804 | 1428 | 16.2 |
| Shein | 3134 | 508 | 16.2 |
| TikTok Shop | 3682 | 589 | 16.0 |
| All channels | 26994 | 4312 | 16.0 |

**08_returns_by_channel** (first rows)

| channel | category | lines_shipped | lines_returned | return_rate_pct | return_value_pct |
|---|---|---|---|---|---|
| Amazon.fr | Belts | 998 | 145 | 14.5 | 14.2 |
| Amazon.fr | Hats | 5074 | 617 | 12.2 | 11.9 |
| Amazon.fr | Jewelry | 2711 | 267 | 9.8 | 9.3 |

## Notes and caveats

- Return rates, repeat rates and event uplifts come from a synthetic generator with deliberately planted patterns (assumptions A12, A13). They illustrate the method; they are not market findings.
- In query 06 most customers have a single order, so frequency has many ties. Ties are broken by monetary value to keep the quintiles deterministic, which means the F score also reflects spend. Segment thresholds are listed in the file header and are a judgment call.
- Platform ROAS in query 03 is self-reported by the ad platforms and includes VAT; do not compare it directly with blended ROAS from query 01.
