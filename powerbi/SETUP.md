# Build the Lumi report in Power BI Desktop (from MySQL)

Result: a 4-page report (Overview, Advertising, Products, Customers) on the `lumi_dw` warehouse. All numbers are simulated data for a fictional store (Lumi Accessories, France, EUR). Reference spec: `docs/10-dashboard-spec.md`. DAX: `powerbi/measures.dax`.

Prerequisite: `lumi_dw` is built and MySQL is running (`python generate_data.py`, then `python build_dw.py`).

## 1. Install the MySQL driver

1. Close Power BI Desktop.
2. Install **MySQL Connector/NET** (64-bit, the 8.0.x series; check the Power BI documentation "Connect to MySQL database" for the currently supported version) from the official MySQL downloads page. Choose the "Typical" or "Complete" setup so the assembly is registered in the GAC.
3. Restart Power BI Desktop.

## 2. Connect and load the tables

1. Home > Get data > More... > Database > **MySQL database** > Connect.
2. Server `127.0.0.1`, Database `lumi_dw`. Data Connectivity mode: **Import**. OK.
3. Credentials dialog: choose the **Database** tab (not Windows). User name `lumi`, password = the `lumi` account password (type it in the dialog; never save it in the repo or in the .pbix you publish). Connect. If you get an encryption warning for a local connection, accept it.
4. In the Navigator tick these 8 tables, then **Load**:
   `dim_date`, `dim_product`, `dim_platform`, `dim_platform_fee`, `dim_campaign`, `dim_customer`, `fact_order_line`, `fact_ads_daily`.
   (Do not load the `stg_*` tables or the `v_*` views; the report uses the model, the views are only for reconciliation.)
5. Check types in Table view (Power BI usually gets them right): `dim_date[full_date]` = Date; `dim_customer[first_order_date]` = Date; `fact_order_line[order_ts_*]` = Date/Time; money columns = Fixed decimal number or Decimal number; `date_key` = Whole number.

## 3. Relationships (Model view)

Create each as **Many to one (*:1)**, cross-filter direction **Single** (dimension filters fact), active, except the last one.

| From (many) | To (one) | Active |
|---|---|---|
| `fact_order_line[date_key]` | `dim_date[date_key]` | yes |
| `fact_order_line[sku]` | `dim_product[sku]` | yes |
| `fact_order_line[platform]` | `dim_platform[platform]` | yes |
| `fact_order_line[customer_key]` | `dim_customer[customer_key]` | yes |
| `fact_ads_daily[date_key]` | `dim_date[date_key]` | yes |
| `fact_ads_daily[campaign]` | `dim_campaign[campaign]` | yes |
| `dim_customer[first_date_key]` | `dim_date[date_key]` | **NO (inactive)** |

The inactive one is created after you add the calculated column `first_date_key` (step 5); in the edit-relationship dialog untick "Make this relationship active". It is used only through `USERELATIONSHIP` in `New Customers` and `CAC`.
`dim_platform_fee` stays unrelated (reference only). Power BI may auto-detect some relationships on load: delete any it creates that are not in this table.

## 4. Date table and model hygiene

1. Select `dim_date` > Table tools > **Mark as date table** > date column `full_date`.
2. Select `dim_date[month_name]` > Column tools > Sort by column > `month`.
3. Hide key columns in the fact tables (Model view > right-click > Hide in report view): `fact_order_line[date_key, sku, platform, customer_key, line_id]`, `fact_ads_daily[date_key, campaign, channel, ad_id]`, `dim_date[date_key, month]`, `dim_customer[customer_key]`. Use `dim_campaign[channel]` (not `fact_ads_daily[channel]`) in visuals.
4. Set "Summarize: Don't summarize" on `dim_date` year/day/weekday and on `fact_order_line[months_since_first]` (so it is used as a plain axis value).
5. Optionally in File > Options > Current file > Data load/Model, nothing else is required.

## 5. Calculated columns

Paste from `powerbi/measures.dax` section A (Table view > New column, one block each):
`dim_customer[first_date_key]`, `dim_customer[first_month]`, `dim_customer[region_label]`, `fact_order_line[order_date]`, `fact_order_line[months_since_first]`, `dim_date[month_start]`.
Order: create `first_month` before `months_since_first`; create `first_date_key` before the inactive relationship. Set the formats listed in each header (`first_month` = `mmm yyyy`). Hide `first_date_key` and `order_date`.

## 6. Measures

1. Home > Enter data > create an empty table named `_Measures` (one blank column), Load. Hide the blank column.
2. For each block in section B of `measures.dax`: select `_Measures` > New measure > paste the DAX (comment lines are fine) > set **Format** and **Display folder** from the header line (`//@ measure | folder=... | format=...`). Folders: Sales, Profit, Advertising, Customers, Time and events, Helpers.
3. Waterfall helper (section C): New table, paste `waterfall_steps`; then paste the `Waterfall Value` measure. Select `waterfall_steps[Step]` > Sort by column > `StepOrder`.

Definition notes (also write them in a "Definitions" page or tooltips):
- Revenue is excl. VAT (HT) of `completed` lines; returned and cancelled lines are excluded but counted in Return Rate / Cancel Rate (line-based).
- Platform ROAS uses conversion value reported by the ad platforms, **TTC**, self-reported and inflated; Blended ROAS uses real Revenue HT. Show both side by side.
- Ads cannot be linked to orders. Compare ads and revenue only by day. `Blended ROAS`, `CPO` and `CAC` are meaningful only with no campaign/ads-channel filter (use them on cards, not split by ads channel).
- Add a footer text box on every page: "Simulated data, not real business figures."

## 7. Page filter (all pages)

`dim_date` also contains 2026-11-16, which is outside the reporting period. In the Filters pane > **Filters on all pages**: drag `dim_date[full_date]` > Advanced filtering > "is on or before" > 2026-11-15 > Apply filter. (Or set the same filter in "Filters on this page" on each of the 4 pages.)

## 8. Pages

Canvas 16:9. Slicers use `dim_date`/`dim_platform` fields (Dropdown style). "Card" = Card or KPI visual.

### Page 1: Overview

| Visual | Fields | Chart type |
|---|---|---|
| 6 KPI cards | Revenue, Gross Profit, Net Profit, Blended ROAS, CIR, Orders (each with `Revenue MoM %` for Revenue as tooltip/subtitle; others use a small text box or a KPI visual with trend axis `dim_date[month_start]`) | Card / KPI |
| Daily trend | X: `dim_date[full_date]`; Y (line): `Revenue`, `Net Profit`; Y (column, secondary): `Event Revenue Marker` to mark event days; tooltip: `dim_date[event_name]` | Line and clustered column |
| Revenue by month and channel | X: `dim_date[month_start]` (format `mmm yyyy`); Legend: `dim_platform[display_name]`; Y: `Revenue` | Stacked column |
| Marketplace vs own store | Category: `dim_platform[channel_type]`; Values: `Revenue`, `Gross Margin %`, `Return Rate` (percentages on a second small chart) | Clustered column (or donut for Revenue) |
| Top 3 alerts | Three small tables, each with a visual-level filter: (a) `dim_campaign[campaign]`, `Platform ROAS` filtered `Platform ROAS < 1`; (b) `dim_product[sku]`, `Gross Profit` filtered `Gross Profit < 0`; (c) `dim_product[category]`, `Return Rate` filtered `Return Rate > 0.10` | Table |
| Slicers | `dim_date[month_name]` (or `month_start`), `dim_platform[display_name]` | Slicer |

### Page 2: Advertising

| Visual | Fields | Chart type |
|---|---|---|
| KPI cards | Ad Spend, Platform ROAS, Blended ROAS, CPO, CAC, CTR | Card |
| Campaign table | Rows: `dim_campaign[channel]`, `dim_campaign[campaign]`; Values: `Ad Spend`, `Clicks`, `CPC`, `Ads CVR`, `Platform ROAS`; conditional formatting on `Platform ROAS`: rule "< 1" red font/background | Table |
| ROAS by ads channel | Axis: `dim_campaign[channel]`; Values: `Platform ROAS` (note "TTC, self-reported"). Blended ROAS is not attributable per channel: show it as a constant line (Analytics pane > Constant line, or a card) | Clustered column |
| Spend vs revenue by day | X: `dim_date[full_date]`; Y (stacked column): `Ad Spend`; Legend: `dim_campaign[channel]`; Y2 (line): `Revenue` | Line and stacked column |
| Spend vs ROAS scatter | Details: `dim_campaign[campaign]`; X: `Ad Spend`; Y: `Platform ROAS`; Size: `Clicks`; Legend: `dim_campaign[channel]` | Scatter |

### Page 3: Products

| Visual | Fields | Chart type |
|---|---|---|
| Gross profit by category | Axis: `dim_product[category]`; Values: `Gross Profit` | Clustered bar |
| SKU table | Rows: `dim_product[sku]`, `dim_product[product_name]`; Values: `Units`, `Revenue`, `Gross Profit`, `Gross Margin %`, `Return Rate` | Table |
| Loss-making SKUs | Rows: `dim_product[sku]`; Values: `Gross Profit`; visual-level filter on measure `Gross Profit` < 0. Must show exactly 5 SKUs: LM064 (about -8.5 k EUR), LM002, LM013, LM060, LM081 (see `data/raw_fr/truth_summary.json`) | Table |
| Return rate heatmap | Rows: `dim_product[category]`; Columns: `dim_platform[display_name]`; Values: `Return Rate`; Cell elements > Background color > Gradient (or rules) on `Return Rate` | Matrix |
| Profit waterfall | Category: `waterfall_steps[Step]`; Y: `Waterfall Value`; Power BI appends a Total bar = Net Profit (Revenue - fees - COGS - ads). The Gross Profit subtotal is not a separate bar | Waterfall |

### Page 4: Customers

| Visual | Fields | Chart type |
|---|---|---|
| KPI cards | Customers, New Customers, AOV, Repeat Rate, Return Rate | Card |
| Cohort matrix | Rows: `dim_customer[first_month]`; Columns: `fact_order_line[months_since_first]`; Values: `Retention %`; Background color gradient | Matrix |
| New customers by month | X: `dim_date[month_start]`; Y: `New Customers`; Legend: `dim_customer[first_platform]` (the measure uses the inactive relationship, so the month is the first-order month) | Stacked column |
| Revenue by region | Axis: `dim_customer[region_label]`; Values: `Revenue`; sort descending | Clustered bar |
| AOV trend | X: `dim_date[month_start]`; Y: `AOV`; Legend: `dim_platform[display_name]` | Line |

## 9. Reconciliation table (check yourself)

With the page filter `full_date <= 2026-11-15` and no other filter:

| Measure | Expected value |
|---|---|
| Revenue (HT) | 1,186,856.31 EUR |
| Orders | 32,110 |
| Gross Profit | 371,116.18 EUR (31.3% of revenue) |
| Ad Spend | 160,467.68 EUR |
| CIR | 13.5% |
| Blended ROAS | 7.40 |
| Net Profit | about 210,648 EUR (17.7%) |
| Units | 50,374 |
| Customers | 26,994 (4,312 with 2+ orders = Repeat Rate 16.0%) |
| Return Rate by channel | Temu 12.3%, TikTok Shop 12.3%, Shein 12.0%, Amazon.fr 9.0%, Cdiscount 8.9%, Boutique web 7.1% |
| Platform ROAS | `TT_Live_Ceintures` 0.91 (lowest), `GG_Search_Marque` 11.48 (highest) |

Also compare with MySQL: `SELECT SUM(revenue) FROM v_sales_daily WHERE full_date <= '2026-11-15';` must equal Revenue exactly. If a number is off: check the page filter, the relationship list (step 3), and that `status = "completed"` is spelled in lower case in the data.
