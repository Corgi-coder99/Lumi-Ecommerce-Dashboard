"""Phien ban DuckDB cua build_dw.py: khong can MySQL.

Nap CSV tho vao DuckDB (staging), lam sach, dung star schema (cung ten bang, cot, view) va chay kiem tra chat luong.
Chay: python -I build_dw_duckdb.py --raw data/raw_fr [--db data/lumi.duckdb]
Chay lai nhieu lan an toan: moi lan xoa file .duckdb cu va dung lai tu dau.
"""
import argparse
import json
import re
import time
from pathlib import Path

import duckdb

SOURCES = {
    "stg_orders_amazon_fr": "orders_amazon_fr.csv",
    "stg_orders_temu": "orders_temu.csv",
    "stg_orders_shein": "orders_shein.csv",
    "stg_orders_tiktokshop": "orders_tiktokshop.csv",
    "stg_orders_cdiscount": "orders_cdiscount.csv",
    "stg_orders_web": "orders_web.csv",
    "stg_ads_meta": "ads_meta.csv",
    "stg_ads_tiktok": "ads_tiktok.csv",
    "stg_ads_google": "ads_google.csv",
    "stg_products": "products.csv",
    "stg_platform_fees": "platform_fees.csv",
    "stg_calendar_events": "calendar_events.csv",
}


def colname(h):
    return re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_")


def load_staging(con, raw):
    for table, fname in SOURCES.items():
        path = (raw / fname).resolve().as_posix().replace("'", "''")
        src = f"read_csv('{path}', header=true, all_varchar=true, nullstr='<<NULL>>'"
        header = con.execute(f"SELECT * FROM {src}) LIMIT 0").description
        cols = [colname(d[0]) for d in header]
        names = "[" + ", ".join(f"'{c}'" for c in cols) + "]"
        con.execute(f"DROP TABLE IF EXISTS {table}")
        # toan bo cot la VARCHAR, giong staging MySQL; chuoi rong giu nguyen la ''
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM {src}, names={names})")
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n} dong")


DDL = """
CREATE TABLE dim_date (
  date_key INTEGER PRIMARY KEY, full_date DATE NOT NULL, year SMALLINT, month TINYINT, month_name VARCHAR,
  day TINYINT, weekday TINYINT, is_weekend TINYINT, event_name VARCHAR
);
CREATE TABLE dim_product (
  sku VARCHAR PRIMARY KEY, product_name VARCHAR, category VARCHAR, color VARCHAR,
  list_price_ttc DECIMAL(14,2), unit_cost_ht DECIMAL(14,2)
);
CREATE TABLE dim_platform (
  platform VARCHAR PRIMARY KEY, display_name VARCHAR, channel_type VARCHAR
);
CREATE TABLE dim_platform_fee (
  platform VARCHAR, category VARCHAR, commission_rate DECIMAL(5,4),
  PRIMARY KEY (platform, category)
);
CREATE TABLE dim_campaign (campaign VARCHAR PRIMARY KEY, channel VARCHAR);
CREATE TABLE dim_customer (
  customer_key VARCHAR PRIMARY KEY, region VARCHAR, first_order_date DATE, first_platform VARCHAR
);
CREATE SEQUENCE seq_line_id START 1;
CREATE SEQUENCE seq_ad_id START 1;
CREATE TABLE fact_order_line (
  line_id BIGINT DEFAULT nextval('seq_line_id') PRIMARY KEY,
  order_id VARCHAR NOT NULL, platform VARCHAR NOT NULL,
  order_ts_utc TIMESTAMP NOT NULL, order_ts_local TIMESTAMP NOT NULL, date_key INTEGER NOT NULL,
  sku VARCHAR NOT NULL, customer_key VARCHAR NOT NULL,
  qty INTEGER NOT NULL, gross_ttc DECIMAL(14,2) NOT NULL, discount_ttc DECIMAL(14,2) NOT NULL,
  net_ttc DECIMAL(14,2) NOT NULL, vat_amount DECIMAL(14,2) NOT NULL, net_ht DECIMAL(14,2) NOT NULL,
  platform_fee DECIMAL(14,2) NOT NULL, cogs DECIMAL(14,2) NOT NULL,
  status VARCHAR NOT NULL
);
CREATE TABLE fact_ads_daily (
  ad_id BIGINT DEFAULT nextval('seq_ad_id') PRIMARY KEY,
  date_key INTEGER NOT NULL, channel VARCHAR NOT NULL, campaign VARCHAR NOT NULL,
  spend DECIMAL(14,2) NOT NULL, impressions INTEGER NOT NULL, clicks INTEGER NOT NULL,
  platform_conversions INTEGER NOT NULL, platform_conv_value DECIMAL(14,2) NOT NULL,
  UNIQUE (date_key, campaign)
);
"""

DIMS = """
INSERT INTO dim_product SELECT sku, product_name, category, color, CAST(list_price_ttc AS DOUBLE), CAST(unit_cost_ht AS DOUBLE) FROM stg_products;
INSERT INTO dim_platform VALUES
('amazon_fr', 'Amazon.fr', 'marketplace'), ('temu', 'Temu', 'marketplace'),
('shein', 'Shein', 'marketplace'), ('tiktokshop', 'TikTok Shop', 'marketplace'),
('cdiscount', 'Cdiscount', 'marketplace'), ('web', 'Boutique web', 'own_store');
INSERT INTO dim_platform_fee SELECT platform, category, CAST(commission_rate AS DOUBLE) FROM stg_platform_fees;
INSERT INTO dim_campaign SELECT DISTINCT campaign_name, 'meta' FROM stg_ads_meta;
INSERT INTO dim_campaign SELECT DISTINCT campaign_name, 'tiktok' FROM stg_ads_tiktok;
INSERT INTO dim_campaign SELECT DISTINCT campaign, 'google' FROM stg_ads_google;
"""

# MySQL WEEKDAY (Mon=0) -> isodow-1; MONTHNAME -> strftime %B; su kien uu tien theo priority roi event_name
DATE_DIM = """
INSERT INTO dim_date
WITH RECURSIVE d(dt) AS (SELECT DATE '2026-04-30' UNION ALL SELECT CAST(dt + INTERVAL 1 DAY AS DATE) FROM d WHERE dt < DATE '2026-11-16'),
ev AS (
  SELECT d.dt, arg_min(e.event_name, struct_pack(p := CAST(e.priority AS DOUBLE), n := e.event_name)) AS event_name
  FROM d JOIN stg_calendar_events e
    ON d.dt BETWEEN CAST(e.start_date AS DATE) AND CAST(e.end_date AS DATE)
  GROUP BY d.dt
)
SELECT year(d.dt)*10000+month(d.dt)*100+day(d.dt), d.dt, year(d.dt), month(d.dt), strftime(d.dt, '%B'), day(d.dt),
       isodow(d.dt) - 1, CASE WHEN isodow(d.dt) - 1 >= 5 THEN 1 ELSE 0 END, ev.event_name
FROM d LEFT JOIN ev ON ev.dt = d.dt;
"""

# Chuan hoa sau nen tang ban hang ve UTC va tong dong theo EUR TTC (so thuc double nhu MySQL '+0').
UNION = """
CREATE TEMP TABLE tmp_orders AS
SELECT 'amazon_fr' AS platform, amazon_order_id AS order_id,
       strptime(substr(purchase_date,1,19), '%Y-%m-%dT%H:%M:%S') AS ts,
       sku, CAST(quantity_purchased AS INTEGER) AS qty,
       CAST(replace(item_price,',','.') AS DOUBLE) AS gross_ttc,
       CAST(replace(promotion_discount,',','.') AS DOUBLE) AS discount_ttc,
       CASE order_status WHEN 'Shipped' THEN 'completed' WHEN 'Returned' THEN 'returned' ELSE 'cancelled' END AS status,
       buyer_key AS cust, NULLIF(ship_state,'') AS region
FROM stg_orders_amazon_fr
UNION ALL
SELECT 'temu', order_sn, TIMESTAMP '1970-01-01 00:00:00' + to_seconds(CAST(order_time_epoch AS BIGINT)), sku_id, CAST(qty AS INTEGER),
       CAST(unit_price_eur AS DOUBLE)*CAST(qty AS DOUBLE), CAST(discount_eur AS DOUBLE),
       CASE status WHEN 'delivered' THEN 'completed' WHEN 'refunded' THEN 'returned' ELSE 'cancelled' END,
       user_hash, NULLIF(region_code,'')
FROM stg_orders_temu
UNION ALL
SELECT 'shein', orderno, strptime(createdate, '%d/%m/%Y %H:%M:%S'), sellersku, CAST(number AS INTEGER),
       CAST(sellingprice AS DOUBLE)*CAST(number AS DOUBLE), CAST(couponamount AS DOUBLE),
       CASE orderstate WHEN 'Completed' THEN 'completed' WHEN 'Return' THEN 'returned' ELSE 'cancelled' END,
       memberhash, NULLIF(province,'')
FROM stg_orders_shein
UNION ALL
SELECT 'tiktokshop', order_id, TIMESTAMP '1970-01-01 00:00:00' + to_seconds(CAST(create_time_ms AS BIGINT) // 1000), seller_sku, CAST(quantity AS INTEGER),
       CAST(sku_subtotal_before_discount AS DOUBLE), CAST(seller_discount AS DOUBLE),
       CASE order_state WHEN 'COMPLETED' THEN 'completed' WHEN 'RETURNED' THEN 'returned' ELSE 'cancelled' END,
       buyer_id, NULLIF(region,'')
FROM (SELECT DISTINCT * FROM stg_orders_tiktokshop) t
UNION ALL
SELECT 'cdiscount', ordernumber, strptime(creationdate, '%Y-%m-%d %H:%M'), sellerproductid, CAST(quantity AS INTEGER),
       CAST(saleprice AS DOUBLE)*CAST(quantity AS DOUBLE), CAST(discount AS DOUBLE),
       CASE state WHEN 'Delivered' THEN 'completed' WHEN 'Returned' THEN 'returned' ELSE 'cancelled' END,
       customerkey, NULLIF(deliveryregion,'')
FROM stg_orders_cdiscount
UNION ALL
SELECT 'web', id, strptime(created_at_utc, '%Y-%m-%dT%H:%M:%SZ'), sku, CAST(quantity AS INTEGER),
       CAST(price AS DOUBLE)*CAST(quantity AS DOUBLE), CAST(coupon_discount AS DOUBLE),
       CASE fulfillment_status WHEN 'completed' THEN 'completed' WHEN 'returned' THEN 'returned' ELSE 'cancelled' END,
       customer_key, NULLIF(region,'')
FROM stg_orders_web;
"""

# MySQL ROUND(double, 2) = rint(x*100)/100 (lam tron chan theo gia tri nhi phan), nen dung macro my_round2 de ra cung so le.
# Paris dung CEST (UTC+2) giua hai moc doi gio 2026 (tinh theo UTC), con lai CET (UTC+1). Viet cung.
FACTS = """
CREATE OR REPLACE TEMP MACRO my_round2(x) AS round_even(x * 100.0, 0) / 100.0;
INSERT INTO fact_order_line (order_id, platform, order_ts_utc, order_ts_local, date_key, sku, customer_key, qty,
                             gross_ttc, discount_ttc, net_ttc, vat_amount, net_ht, platform_fee, cogs, status)
SELECT o.order_id, o.platform, o.ts, o.local_ts,
       year(o.local_ts)*10000 + month(o.local_ts)*100 + day(o.local_ts),
       o.sku, o.cust, o.qty, o.gross_ttc, o.discount_ttc, o.net_ttc,
       o.net_ttc - my_round2(o.net_ttc / 1.2), my_round2(o.net_ttc / 1.2),
       my_round2(o.net_ttc * CAST(COALESCE(fc.commission_rate, fd.commission_rate) AS DOUBLE)),
       o.qty * p.unit_cost_ht, o.status
FROM (
  SELECT t.*, t.gross_ttc - t.discount_ttc AS net_ttc,
         t.ts + to_hours(CASE WHEN t.ts >= TIMESTAMP '2026-03-29 01:00:00' AND t.ts < TIMESTAMP '2026-10-25 01:00:00'
                              THEN 2 ELSE 1 END) AS local_ts
  FROM tmp_orders t
) o
JOIN dim_product p ON p.sku = o.sku
LEFT JOIN dim_platform_fee fc ON fc.platform = o.platform AND fc.category = p.category
LEFT JOIN dim_platform_fee fd ON fd.platform = o.platform AND fd.category = '*';

INSERT INTO dim_customer
SELECT c.customer_key, r.region,
       CAST(MIN(c.order_ts_local) AS DATE),
       arg_min(c.platform, c.order_ts_local)
FROM fact_order_line c
LEFT JOIN (SELECT cust, MIN(region) AS region FROM tmp_orders GROUP BY cust) r ON r.cust = c.customer_key
GROUP BY c.customer_key, r.region;

INSERT INTO fact_ads_daily (date_key, channel, campaign, spend, impressions, clicks, platform_conversions, platform_conv_value)
SELECT CAST(replace(day,'-','') AS INTEGER), 'meta', campaign_name, CAST(amount_spent_eur AS DOUBLE), CAST(impressions AS INTEGER), CAST(link_clicks AS INTEGER), CAST(purchases AS INTEGER), CAST(purchase_conversion_value AS DOUBLE)
FROM stg_ads_meta
UNION ALL
SELECT CAST(replace(stat_time_day,'/','') AS INTEGER), 'tiktok', campaign_name, CAST(cost AS DOUBLE), CAST(impressions AS INTEGER), CAST(clicks AS INTEGER), CAST(complete_payment AS INTEGER), CAST(complete_payment_value AS DOUBLE)
FROM stg_ads_tiktok
UNION ALL
SELECT CAST(replace(date,'-','') AS INTEGER), 'google', campaign, ROUND(CAST(cost_micros AS DOUBLE)/1000000,2), CAST(impressions AS INTEGER), CAST(clicks AS INTEGER), CAST(CAST(conversions AS DOUBLE) AS INTEGER), CAST(conversions_value AS DOUBLE)
FROM stg_ads_google;
"""

VIEWS = """
CREATE VIEW v_sales_daily AS
SELECT d.full_date, d.event_name, f.platform,
       COUNT(DISTINCT f.order_id) AS orders,
       SUM(f.net_ht) AS revenue,
       SUM(f.platform_fee) AS platform_fee,
       SUM(f.cogs) AS cogs,
       SUM(f.net_ht - f.platform_fee - f.cogs) AS profit_before_ads
FROM fact_order_line f JOIN dim_date d USING (date_key)
WHERE f.status = 'completed'
GROUP BY d.full_date, d.event_name, f.platform;

CREATE VIEW v_sku_profit AS
SELECT p.sku, p.category, SUM(f.qty) AS units, SUM(f.net_ht) AS revenue,
       SUM(f.net_ht - f.platform_fee - f.cogs) AS profit_before_ads
FROM fact_order_line f JOIN dim_product p USING (sku)
WHERE f.status = 'completed'
GROUP BY p.sku, p.category;

CREATE VIEW v_campaign_perf AS
SELECT a.channel, a.campaign, SUM(a.spend) AS spend, SUM(a.clicks) AS clicks,
       SUM(a.platform_conversions) AS platform_conversions, SUM(a.platform_conv_value) AS platform_value,
       SUM(a.platform_conv_value) / SUM(a.spend) AS platform_roas
FROM fact_ads_daily a GROUP BY a.channel, a.campaign;
"""


def run_script(con, sql):
    for stmt in [s.strip() for s in sql.split(";\n") if s.strip().rstrip(";")]:
        con.execute(stmt.rstrip(";"))


def q(con, sql):
    return con.execute(sql).fetchall()


def checks(con, truth_skus):
    print("\n=== KIEM TRA CHAT LUONG ===")
    platforms = ("amazon_fr", "temu", "shein", "tiktokshop", "cdiscount", "web")
    raw_lines = {p: q(con, f"SELECT COUNT(*) FROM stg_orders_{p}")[0][0] for p in platforms}
    fact_lines = dict(q(con, "SELECT platform, COUNT(*) FROM fact_order_line GROUP BY platform"))
    print("Dong staging:", raw_lines)
    print("Dong fact:   ", fact_lines)
    for p in platforms:
        print(f"  {p}: staging={raw_lines[p]}, fact={fact_lines.get(p, 0)}")
    tt_distinct = q(con, "SELECT COUNT(*) FROM (SELECT DISTINCT * FROM stg_orders_tiktokshop) t")[0][0]
    print(f"Dong TikTok bi loai (trung hoan toan): {raw_lines['tiktokshop'] - tt_distinct}")
    print(f"Mat dong TikTok sau loai trung (phai = 0): {tt_distinct - fact_lines.get('tiktokshop', 0)}")
    for p in platforms:
        if p != "tiktokshop":
            print(f"Mat dong o {p} (phai = 0): {raw_lines[p] - fact_lines.get(p, 0)}")
    print("Dong fact khong co khach:", q(con, "SELECT COUNT(*) FROM fact_order_line WHERE customer_key IS NULL OR customer_key=''")[0][0])
    print("Vung thieu o dim_customer:", q(con, "SELECT COUNT(*) FROM dim_customer WHERE region IS NULL")[0][0],
          "/", q(con, "SELECT COUNT(*) FROM dim_customer")[0][0])
    print("Khoang ngay (gio Paris):", q(con, "SELECT MIN(CAST(order_ts_local AS DATE)), MAX(CAST(order_ts_local AS DATE)) FROM fact_order_line")[0])
    print("Doi chieu gross_ttc - discount_ttc - net_ttc (phai = 0):",
          q(con, "SELECT SUM(gross_ttc-discount_ttc-net_ttc) FROM fact_order_line")[0][0])
    print("Doi chieu net_ttc - net_ht - vat_amount (phai = 0):",
          q(con, "SELECT SUM(net_ttc-net_ht-vat_amount) FROM fact_order_line")[0][0])
    print("Don bi am hoac 0:", q(con, "SELECT COUNT(*) FROM fact_order_line WHERE net_ttc <= 0")[0][0])
    print("\nDoanh thu / loi nhuan truoc ads theo san (chi don completed), nghin EUR:")
    for r in q(con, "SELECT platform, ROUND(SUM(revenue)/1000,2), ROUND(SUM(profit_before_ads)/1000,2) FROM v_sales_daily GROUP BY platform"):
        print("  ", r)
    print("\n5 SKU lo nhat (v_sku_profit), nghin EUR:")
    worst = q(con, "SELECT sku, ROUND(profit_before_ads/1000,2) FROM v_sku_profit ORDER BY profit_before_ads LIMIT 5")
    for r in worst:
        print("  ", r)
    print("Khop voi SKU lo da nhung:", sorted(x[0] for x in worst) == sorted(truth_skus))
    print("\nROAS theo chien dich (do nen tang tu bao cao), spend nghin EUR:")
    for r in q(con, "SELECT channel, campaign, ROUND(spend/1000,2), ROUND(platform_roas,2) FROM v_campaign_perf ORDER BY platform_roas"):
        print("  ", r)


def build(raw, db):
    raw = Path(raw)
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    for p in (db, Path(str(db) + ".wal")):
        if p.exists():
            p.unlink()
    truth = json.loads((raw / "truth_summary.json").read_text(encoding="utf-8"))
    con = duckdb.connect(str(db))
    t0 = time.time()
    print("1) Nap staging")
    load_staging(con, raw)
    print("2) Tao schema")
    run_script(con, DDL)
    print("3) Dim va fact")
    run_script(con, DIMS)
    run_script(con, DATE_DIM)
    run_script(con, UNION)
    run_script(con, FACTS)
    run_script(con, VIEWS)
    checks(con, truth["loss_making_skus_after_discount_and_fees"])
    con.close()
    print(f"\nXong trong {time.time() - t0:.1f} giay -> {db}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw_fr")
    ap.add_argument("--db", default="data/lumi.duckdb")
    args = ap.parse_args()
    build(args.raw, args.db)


if __name__ == "__main__":
    main()
