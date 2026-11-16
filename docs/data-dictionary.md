# Data dictionary: `lumi_dw`

All data is synthetic (fictional shop, seed 42). Period: 2026-05-01 to 2026-11-15. Currency: EUR. `HT` = excl. VAT, `TTC` = incl. VAT (France, 20% on everything, assumption A4). Assumption IDs refer to [assumptions-log.md](assumptions-log.md). Relationships are in [erd.md](erd.md).

Conventions:
- Revenue means `net_ht` of orders with `status = 'completed'`. Returned and cancelled orders carry no revenue.
- Timestamps in the source files are UTC; the warehouse keeps both UTC and Paris time (CEST UTC+2 from 2026-03-29 01:00 UTC to 2026-10-25 01:00 UTC, else CET UTC+1; assumption A2).
- Source data is loaded into `stg_*` tables (raw CSV text, one table per export). They are staging only and not documented here.

## fact_order_line

One row per SKU per order. Grain: `line_id`.

| Column | Type | Meaning | Unit / basis | Notes |
|---|---|---|---|---|
| line_id | BIGINT | Surrogate key | | Auto-increment |
| order_id | VARCHAR(20) | Order number from the sales channel | | Not unique: several lines share an order. Count orders with `COUNT(DISTINCT order_id)` |
| platform | VARCHAR(20) | Sales channel code | | `amazon_fr`, `temu`, `shein`, `tiktokshop`, `cdiscount`, `web`. Joins to `dim_platform` |
| order_ts_utc | DATETIME | Order time | UTC | As exported (assumption A2) |
| order_ts_local | DATETIME | Order time in France | Paris time | Derived from UTC with the fixed summer/winter rule |
| date_key | INT | Calendar day of the order, YYYYMMDD | Paris time | Joins to `dim_date`. Use `date_key <= 20261115` to stay within the data |
| sku | VARCHAR(10) | Product code | | Joins to `dim_product` |
| customer_key | VARCHAR(16) | Pseudonymous customer hash | | Matches across channels (A8). No personal data |
| qty | INT | Units on the line | units | |
| gross_ttc | DECIMAL(14,2) | List value of the line before discount | EUR TTC | unit price x qty |
| discount_ttc | DECIMAL(14,2) | Discount or coupon on the line | EUR TTC | |
| net_ttc | DECIMAL(14,2) | `gross_ttc - discount_ttc` | EUR TTC | What the customer pays |
| vat_amount | DECIMAL(14,2) | VAT contained in `net_ttc` | EUR | `net_ttc - net_ht` |
| net_ht | DECIMAL(14,2) | `ROUND(net_ttc / 1.2, 2)` | EUR HT | Revenue basis for all analysis (A4) |
| platform_fee | DECIMAL(14,2) | Marketplace commission | EUR HT | `net_ttc` x rate from `dim_platform_fee` (A5), treated as excl. VAT |
| cogs | DECIMAL(14,2) | Cost of goods sold | EUR HT | `qty x dim_product.unit_cost_ht` (A6) |
| status | VARCHAR(12) | Normalised order status | | `completed`, `returned`, `cancelled`. Source vocabularies differ per channel and are mapped in the loader |

Derived measure used throughout: gross profit (profit before ads) = `net_ht - platform_fee - cogs`.

## fact_ads_daily

One row per campaign per day. Grain: (`date_key`, `campaign`), unique.

| Column | Type | Meaning | Unit / basis | Notes |
|---|---|---|---|---|
| ad_id | BIGINT | Surrogate key | | |
| date_key | INT | Day of the ad stats, YYYYMMDD | As reported by the platform | Joins to `dim_date` |
| channel | VARCHAR(12) | Ad platform | | `meta`, `tiktok`, `google` |
| campaign | VARCHAR(40) | Campaign name | | Joins to `dim_campaign` |
| spend | DECIMAL(14,2) | Ad cost | EUR HT | Google costs are converted from micros |
| impressions | INT | Ad impressions | count | |
| clicks | INT | Link clicks | count | |
| platform_conversions | INT | Purchases attributed by the ad platform | count | Not linked to real orders (A7) |
| platform_conv_value | DECIMAL(14,2) | Value of those purchases, self-reported | EUR TTC | Meta over-reports by about 30% in this data (A7) |

## dim_date

One row per calendar day from 2026-04-30 to 2026-11-16 (one padding day on each side, A2). Grain: `date_key`.

| Column | Type | Meaning | Notes |
|---|---|---|---|
| date_key | INT | Day as YYYYMMDD | Primary key |
| full_date | DATE | Calendar date | |
| year | SMALLINT | Year | |
| month | TINYINT | Month number 1 to 12 | |
| month_name | VARCHAR(10) | English month name | |
| day | TINYINT | Day of month | |
| weekday | TINYINT | Day of week | 0 = Monday ... 6 = Sunday (MySQL `WEEKDAY`) |
| is_weekend | TINYINT | 1 for Saturday and Sunday | |
| event_name | VARCHAR(30) | Sale event running that day | NULL on ordinary days. One event per day (lowest priority number wins). Dates and confidence levels: A13 and `docs/market-fr/sources.md`. Values: Fete des meres, French Days printemps, Prime Day, Jours Flash Prime, Soldes ete, French Days rentree, Singles Day 11.11 |

## dim_product

One row per SKU (96 SKUs, 7 categories). Grain: `sku`.

| Column | Type | Meaning | Unit / basis | Notes |
|---|---|---|---|---|
| sku | VARCHAR(10) | Product code, e.g. LM001 | | Primary key |
| product_name | VARCHAR(60) | Product name | | |
| category | VARCHAR(30) | Product category | | Handbags, Wallets, Belts, Hats, Sunglasses, Jewelry, Scarves |
| color | VARCHAR(20) | Colour | | French colour names as in the source |
| list_price_ttc | DECIMAL(14,2) | Shelf price | EUR TTC | Actual sale prices can differ by channel and discount |
| unit_cost_ht | DECIMAL(14,2) | Cost per unit | EUR HT | Fixed over time (A6) |

## dim_platform

One row per sales channel. Grain: `platform`.

| Column | Type | Meaning | Notes |
|---|---|---|---|
| platform | VARCHAR(20) | Channel code | Primary key |
| display_name | VARCHAR(30) | Label for reports | Amazon.fr, Temu, Shein, TikTok Shop, Cdiscount, Boutique web. Labels only, no affiliation implied |
| channel_type | VARCHAR(12) | `marketplace` or `own_store` | |

## dim_platform_fee

Commission schedule. Grain: (`platform`, `category`).

| Column | Type | Meaning | Unit / basis | Notes |
|---|---|---|---|---|
| platform | VARCHAR(20) | Channel code | | |
| category | VARCHAR(30) | Product category, or `*` for the platform default | | A category row overrides the `*` row (for example Cdiscount Jewelry) |
| commission_rate | DECIMAL(5,4) | Commission as a share of `net_ttc` | ratio, e.g. 0.1500 = 15% | Simplified fixed rates (A5) |

## dim_campaign

One row per ad campaign (9 campaigns). Grain: `campaign`.

| Column | Type | Meaning | Notes |
|---|---|---|---|
| campaign | VARCHAR(40) | Campaign name | Primary key |
| channel | VARCHAR(12) | Ad platform | `meta`, `tiktok`, `google` |

## dim_customer

One row per pseudonymous customer. Grain: `customer_key`.

| Column | Type | Meaning | Notes |
|---|---|---|---|
| customer_key | VARCHAR(16) | Customer hash | Primary key. Matches across channels (A8) |
| region | VARCHAR(40) | French region | NULL for some customers (Cdiscount exports miss regions) |
| first_order_date | DATE | Date of the first order of any status | Paris time. For cohort work on completed orders, derive the first date from `fact_order_line` instead (see `sql/05_cohort_retention.sql`) |
| first_platform | VARCHAR(20) | Channel of the first order of any status | Same remark as above |

## Views

### v_sales_daily

Daily sales per channel, completed orders only. Grain: (`full_date`, `event_name`, `platform`).

| Column | Type | Meaning | Unit / basis |
|---|---|---|---|
| full_date | DATE | Day (Paris time) | |
| event_name | VARCHAR(30) | Sale event that day, NULL if none | |
| platform | VARCHAR(20) | Channel code | |
| orders | BIGINT | Distinct orders | count |
| revenue | DECIMAL | `SUM(net_ht)` | EUR HT |
| platform_fee | DECIMAL | `SUM(platform_fee)` | EUR HT |
| cogs | DECIMAL | `SUM(cogs)` | EUR HT |
| profit_before_ads | DECIMAL | `revenue - platform_fee - cogs` | EUR HT |

### v_sku_profit

Profit per SKU, completed orders only. Grain: `sku`.

| Column | Type | Meaning | Unit / basis |
|---|---|---|---|
| sku | VARCHAR(10) | Product code | |
| category | VARCHAR(30) | Category | |
| units | DECIMAL | Units sold | units |
| revenue | DECIMAL | `SUM(net_ht)` | EUR HT |
| profit_before_ads | DECIMAL | `SUM(net_ht - platform_fee - cogs)` | EUR HT. Ads are not attributable to a SKU |

### v_campaign_perf

Platform-reported performance per campaign over the whole period. Grain: (`channel`, `campaign`).

| Column | Type | Meaning | Unit / basis |
|---|---|---|---|
| channel | VARCHAR(12) | Ad platform | |
| campaign | VARCHAR(40) | Campaign name | |
| spend | DECIMAL | Total cost | EUR HT |
| clicks | DECIMAL | Total clicks | count |
| platform_conversions | DECIMAL | Purchases attributed by the platform | count |
| platform_value | DECIMAL | Value attributed by the platform | EUR TTC, self-reported |
| platform_roas | DECIMAL | `platform_value / spend` | ratio. Mixes TTC and HT and is inflated by platform over-reporting; compare with blended ROAS (revenue HT / total spend) |

## Key metric definitions

| Metric | Definition |
|---|---|
| Revenue | `SUM(net_ht)` of completed lines, EUR HT |
| Gross profit | Revenue - platform fees - COGS |
| Net profit | Gross profit - ad spend |
| CIR | Ad spend / revenue |
| Blended ROAS | Revenue HT / ad spend HT |
| Return rate | Returned lines / (completed + returned lines) |
| CAC | Ad spend / new customers (blended, A9) |
