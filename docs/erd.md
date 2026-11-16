# Entity-relationship diagram: `lumi_dw`

Star schema in MySQL 8.4, built by `build_dw.py`. Two fact tables (`fact_order_line`, `fact_ads_daily`) share the date dimension. Column types are those of the DDL in `build_dw.py`. Column meanings are in [data-dictionary.md](data-dictionary.md).

MySQL does not declare foreign keys in this warehouse (the loader guarantees integrity and checks it), so the relationships below are logical joins. The join key is shown on each line.

```mermaid
erDiagram
    dim_date ||--o{ fact_order_line : "date_key"
    dim_date ||--o{ fact_ads_daily : "date_key"
    dim_product ||--o{ fact_order_line : "sku"
    dim_platform ||--o{ fact_order_line : "platform"
    dim_customer ||--o{ fact_order_line : "customer_key"
    dim_campaign ||--o{ fact_ads_daily : "campaign"
    dim_platform ||--o{ dim_platform_fee : "platform"
    dim_product }o--o{ dim_platform_fee : "category (or '*' default)"

    dim_date {
        INT date_key PK "YYYYMMDD"
        DATE full_date
        SMALLINT year
        TINYINT month
        VARCHAR month_name
        TINYINT day
        TINYINT weekday "0 = Monday"
        TINYINT is_weekend
        VARCHAR event_name "NULL on ordinary days"
    }
    dim_product {
        VARCHAR sku PK
        VARCHAR product_name
        VARCHAR category
        VARCHAR color
        DECIMAL list_price_ttc
        DECIMAL unit_cost_ht
    }
    dim_platform {
        VARCHAR platform PK
        VARCHAR display_name
        VARCHAR channel_type "marketplace or own_store"
    }
    dim_platform_fee {
        VARCHAR platform PK
        VARCHAR category PK "'*' = default rate"
        DECIMAL commission_rate
    }
    dim_campaign {
        VARCHAR campaign PK
        VARCHAR channel "meta, tiktok, google"
    }
    dim_customer {
        VARCHAR customer_key PK
        VARCHAR region
        DATE first_order_date
        VARCHAR first_platform
    }
    fact_order_line {
        BIGINT line_id PK
        VARCHAR order_id
        VARCHAR platform FK
        DATETIME order_ts_utc
        DATETIME order_ts_local
        INT date_key FK
        VARCHAR sku FK
        VARCHAR customer_key FK
        INT qty
        DECIMAL gross_ttc
        DECIMAL discount_ttc
        DECIMAL net_ttc
        DECIMAL vat_amount
        DECIMAL net_ht
        DECIMAL platform_fee
        DECIMAL cogs
        VARCHAR status "completed, returned, cancelled"
    }
    fact_ads_daily {
        BIGINT ad_id PK
        INT date_key FK
        VARCHAR channel
        VARCHAR campaign FK
        DECIMAL spend
        INT impressions
        INT clicks
        INT platform_conversions
        DECIMAL platform_conv_value
    }
```

## Relationships

| From (many) | To (one) | Join key | Notes |
|---|---|---|---|
| `fact_order_line` | `dim_date` | `date_key` | Local (Paris) calendar day of the order |
| `fact_order_line` | `dim_product` | `sku` | |
| `fact_order_line` | `dim_platform` | `platform` | Sales channel |
| `fact_order_line` | `dim_customer` | `customer_key` | Hash that matches across channels |
| `fact_ads_daily` | `dim_date` | `date_key` | |
| `fact_ads_daily` | `dim_campaign` | `campaign` | `fact_ads_daily.channel` repeats `dim_campaign.channel` |
| `dim_platform_fee` | `dim_platform` | `platform` | One row per platform and category |
| `dim_platform_fee` | `dim_product` | `category` | Category-specific rate if present, else the `'*'` row. Used only while loading `fact_order_line` |

There is no join between `fact_order_line` and `fact_ads_daily`: orders are not attributed to campaigns (assumption A7). Compare them only through shared dimensions such as `dim_date`.

Views built on top: `v_sales_daily`, `v_sku_profit`, `v_campaign_perf` (see the data dictionary).
