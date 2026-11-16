"""Nap CSV tho vao MySQL (staging), lam sach, dung star schema trong lumi_dw va chay kiem tra chat luong.

Chay: python -I build_dw.py [--raw data/raw]
Ket noi: 127.0.0.1, user lumi, database lumi_dw, mat khau lay tu bien moi truong MYSQL_PWD (khong ghi vao file).
Chay lai nhieu lan an toan: moi lan xoa va dung lai toan bo bang stg_*, dim_*, fact_*.
"""
import argparse
import csv
import os
import re
import sys
from pathlib import Path

import pymysql

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


def connect():
    pwd = os.environ.get("MYSQL_PWD")
    if not pwd:
        sys.exit("Thieu bien moi truong MYSQL_PWD")
    return pymysql.connect(host="127.0.0.1", user="lumi", password=pwd, database="lumi_dw",
                           charset="utf8mb4", autocommit=False)


def load_staging(cur, raw):
    for table, fname in SOURCES.items():
        with open(raw / fname, encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            cols = [colname(h) for h in next(r)]
            rows = list(r)
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        cur.execute(f"CREATE TABLE {table} (" + ", ".join(f"`{c}` VARCHAR(120)" for c in cols) + ") CHARACTER SET utf8mb4")
        ph = ", ".join(["%s"] * len(cols))
        for i in range(0, len(rows), 5000):
            cur.executemany(f"INSERT INTO {table} VALUES ({ph})", rows[i:i + 5000])
        print(f"  {table}: {len(rows)} dong")


DDL = """
DROP TABLE IF EXISTS fact_order_line, fact_ads_daily, dim_date, dim_product, dim_platform, dim_customer, dim_campaign, dim_platform_fee;
DROP VIEW IF EXISTS v_sales_daily, v_campaign_perf, v_sku_profit;

CREATE TABLE dim_date (
  date_key INT PRIMARY KEY, full_date DATE NOT NULL, year SMALLINT, month TINYINT, month_name VARCHAR(10),
  day TINYINT, weekday TINYINT, is_weekend TINYINT, event_name VARCHAR(30)
);
CREATE TABLE dim_product (
  sku VARCHAR(10) PRIMARY KEY, product_name VARCHAR(60), category VARCHAR(30), color VARCHAR(20),
  list_price_ttc DECIMAL(14,2), unit_cost_ht DECIMAL(14,2)
);
CREATE TABLE dim_platform (
  platform VARCHAR(20) PRIMARY KEY, display_name VARCHAR(30), channel_type VARCHAR(12)
);
CREATE TABLE dim_platform_fee (
  platform VARCHAR(20), category VARCHAR(30), commission_rate DECIMAL(5,4),
  PRIMARY KEY (platform, category)
);
CREATE TABLE dim_campaign (campaign VARCHAR(40) PRIMARY KEY, channel VARCHAR(12));
CREATE TABLE dim_customer (
  customer_key VARCHAR(16) PRIMARY KEY, region VARCHAR(40), first_order_date DATE, first_platform VARCHAR(20)
);
CREATE TABLE fact_order_line (
  line_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id VARCHAR(20) NOT NULL, platform VARCHAR(20) NOT NULL,
  order_ts_utc DATETIME NOT NULL, order_ts_local DATETIME NOT NULL, date_key INT NOT NULL,
  sku VARCHAR(10) NOT NULL, customer_key VARCHAR(16) NOT NULL,
  qty INT NOT NULL, gross_ttc DECIMAL(14,2) NOT NULL, discount_ttc DECIMAL(14,2) NOT NULL,
  net_ttc DECIMAL(14,2) NOT NULL, vat_amount DECIMAL(14,2) NOT NULL, net_ht DECIMAL(14,2) NOT NULL,
  platform_fee DECIMAL(14,2) NOT NULL, cogs DECIMAL(14,2) NOT NULL,
  status VARCHAR(12) NOT NULL,
  KEY ix_date (date_key), KEY ix_sku (sku), KEY ix_cust (customer_key), KEY ix_order (order_id),
  KEY ix_platform (platform)
);
CREATE TABLE fact_ads_daily (
  ad_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  date_key INT NOT NULL, channel VARCHAR(12) NOT NULL, campaign VARCHAR(40) NOT NULL,
  spend DECIMAL(14,2) NOT NULL, impressions INT NOT NULL, clicks INT NOT NULL,
  platform_conversions INT NOT NULL, platform_conv_value DECIMAL(14,2) NOT NULL,
  UNIQUE KEY uq_ad (date_key, campaign)
);
"""

DIMS = """
INSERT INTO dim_product SELECT sku, product_name, category, color, list_price_ttc+0, unit_cost_ht+0 FROM stg_products;
INSERT INTO dim_platform VALUES
('amazon_fr', 'Amazon.fr', 'marketplace'), ('temu', 'Temu', 'marketplace'),
('shein', 'Shein', 'marketplace'), ('tiktokshop', 'TikTok Shop', 'marketplace'),
('cdiscount', 'Cdiscount', 'marketplace'), ('web', 'Boutique web', 'own_store');
INSERT INTO dim_platform_fee SELECT platform, category, commission_rate+0 FROM stg_platform_fees;
INSERT INTO dim_campaign SELECT DISTINCT campaign_name, 'meta' FROM stg_ads_meta;
INSERT INTO dim_campaign SELECT DISTINCT campaign_name, 'tiktok' FROM stg_ads_tiktok;
INSERT INTO dim_campaign SELECT DISTINCT campaign, 'google' FROM stg_ads_google;
"""

DATE_DIM = """
INSERT INTO dim_date
WITH RECURSIVE d AS (SELECT DATE('2026-04-30') AS dt UNION ALL SELECT dt + INTERVAL 1 DAY FROM d WHERE dt < '2026-11-16')
SELECT YEAR(dt)*10000+MONTH(dt)*100+DAY(dt), dt, YEAR(dt), MONTH(dt), MONTHNAME(dt), DAY(dt), WEEKDAY(dt),
       WEEKDAY(dt) >= 5,
       (SELECT e.event_name FROM stg_calendar_events e
        WHERE dt BETWEEN CAST(e.start_date AS DATE) AND CAST(e.end_date AS DATE)
        ORDER BY e.priority+0, e.event_name LIMIT 1)
FROM d;
"""

# Normalize six sales platforms to UTC timestamps and line totals in EUR TTC.
UNION = """
DROP TEMPORARY TABLE IF EXISTS tmp_orders;
CREATE TEMPORARY TABLE tmp_orders AS
SELECT 'amazon_fr' AS platform, amazon_order_id AS order_id,
       STR_TO_DATE(LEFT(purchase_date,19), '%Y-%m-%dT%H:%i:%s') AS ts,
       sku, quantity_purchased+0 AS qty,
       REPLACE(item_price,',','.')+0 AS gross_ttc,
       REPLACE(promotion_discount,',','.')+0 AS discount_ttc,
       CASE order_status WHEN 'Shipped' THEN 'completed' WHEN 'Returned' THEN 'returned' ELSE 'cancelled' END AS status,
       buyer_key AS cust, NULLIF(ship_state,'') AS region
FROM stg_orders_amazon_fr
UNION ALL
SELECT 'temu', order_sn, FROM_UNIXTIME(order_time_epoch+0), sku_id, qty+0,
       (unit_price_eur+0)*(qty+0), discount_eur+0,
       CASE status WHEN 'delivered' THEN 'completed' WHEN 'refunded' THEN 'returned' ELSE 'cancelled' END,
       user_hash, NULLIF(region_code,'')
FROM stg_orders_temu
UNION ALL
SELECT 'shein', orderno, STR_TO_DATE(createdate, '%d/%m/%Y %H:%i:%s'), sellersku, number+0,
       (sellingprice+0)*(number+0), couponamount+0,
       CASE orderstate WHEN 'Completed' THEN 'completed' WHEN 'Return' THEN 'returned' ELSE 'cancelled' END,
       memberhash, NULLIF(province,'')
FROM stg_orders_shein
UNION ALL
SELECT 'tiktokshop', order_id, FROM_UNIXTIME(create_time_ms/1000), seller_sku, quantity+0,
       sku_subtotal_before_discount+0, seller_discount+0,
       CASE order_state WHEN 'COMPLETED' THEN 'completed' WHEN 'RETURNED' THEN 'returned' ELSE 'cancelled' END,
       buyer_id, NULLIF(region,'')
FROM (SELECT DISTINCT * FROM stg_orders_tiktokshop) t
UNION ALL
SELECT 'cdiscount', ordernumber, STR_TO_DATE(creationdate, '%Y-%m-%d %H:%i'), sellerproductid, quantity+0,
       (saleprice+0)*(quantity+0), discount+0,
       CASE state WHEN 'Delivered' THEN 'completed' WHEN 'Returned' THEN 'returned' ELSE 'cancelled' END,
       customerkey, NULLIF(deliveryregion,'')
FROM stg_orders_cdiscount
UNION ALL
SELECT 'web', id, STR_TO_DATE(created_at_utc, '%Y-%m-%dT%H:%i:%sZ'), sku, quantity+0,
       (price+0)*(quantity+0), coupon_discount+0,
       CASE fulfillment_status WHEN 'completed' THEN 'completed' WHEN 'returned' THEN 'returned' ELSE 'cancelled' END,
       customer_key, NULLIF(region,'')
FROM stg_orders_web;
"""

# Paris uses CEST (UTC+2) between the 2026 UTC transitions, otherwise CET (UTC+1).
FACTS = """
INSERT INTO fact_order_line (order_id, platform, order_ts_utc, order_ts_local, date_key, sku, customer_key, qty,
                             gross_ttc, discount_ttc, net_ttc, vat_amount, net_ht, platform_fee, cogs, status)
SELECT o.order_id, o.platform, o.ts, o.local_ts,
       YEAR(o.local_ts)*10000 + MONTH(o.local_ts)*100 + DAY(o.local_ts),
       o.sku, o.cust, o.qty, o.gross_ttc, o.discount_ttc, o.net_ttc,
       o.net_ttc - ROUND(o.net_ttc / 1.2, 2), ROUND(o.net_ttc / 1.2, 2),
       ROUND(o.net_ttc * COALESCE(fc.commission_rate, fd.commission_rate), 2),
       o.qty * p.unit_cost_ht, o.status
FROM (
  SELECT t.*, t.gross_ttc - t.discount_ttc AS net_ttc,
         t.ts + INTERVAL (CASE WHEN t.ts >= '2026-03-29 01:00:00' AND t.ts < '2026-10-25 01:00:00'
                              THEN 2 ELSE 1 END) HOUR AS local_ts
  FROM tmp_orders t
) o
JOIN dim_product p ON p.sku = o.sku
LEFT JOIN dim_platform_fee fc ON fc.platform = o.platform AND fc.category = p.category
LEFT JOIN dim_platform_fee fd ON fd.platform = o.platform AND fd.category = '*';

INSERT INTO dim_customer
SELECT c.customer_key, r.region,
       DATE(MIN(c.order_ts_local)),
       SUBSTRING_INDEX(GROUP_CONCAT(c.platform ORDER BY c.order_ts_local), ',', 1)
FROM fact_order_line c
LEFT JOIN (SELECT cust, MIN(region) AS region FROM tmp_orders GROUP BY cust) r ON r.cust = c.customer_key
GROUP BY c.customer_key, r.region;

INSERT INTO fact_ads_daily (date_key, channel, campaign, spend, impressions, clicks, platform_conversions, platform_conv_value)
SELECT CAST(REPLACE(day,'-','') AS UNSIGNED), 'meta', campaign_name, amount_spent_eur+0, impressions+0, link_clicks+0, purchases+0, purchase_conversion_value+0
FROM stg_ads_meta
UNION ALL
SELECT CAST(REPLACE(stat_time_day,'/','') AS UNSIGNED), 'tiktok', campaign_name, cost+0, impressions+0, clicks+0, complete_payment+0, complete_payment_value+0
FROM stg_ads_tiktok
UNION ALL
SELECT CAST(REPLACE(date,'-','') AS UNSIGNED), 'google', campaign, ROUND((cost_micros+0)/1000000,2), impressions+0, clicks+0, conversions+0, conversions_value+0
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


def run_script(cur, sql):
    for stmt in [s.strip() for s in sql.split(";\n") if s.strip().rstrip(";")]:
        cur.execute(stmt.rstrip(";"))


def q(cur, sql):
    cur.execute(sql)
    return cur.fetchall()


def checks(cur, truth_skus):
    print("\n=== KIEM TRA CHAT LUONG ===")
    platforms = ("amazon_fr", "temu", "shein", "tiktokshop", "cdiscount", "web")
    raw_lines = {p: q(cur, f"SELECT COUNT(*) FROM stg_orders_{p}")[0][0] for p in platforms}
    fact_lines = dict(q(cur, "SELECT platform, COUNT(*) FROM fact_order_line GROUP BY platform"))
    print("Dong staging:", raw_lines)
    print("Dong fact:   ", fact_lines)
    for p in platforms:
        print(f"  {p}: staging={raw_lines[p]}, fact={fact_lines.get(p, 0)}")
    tt_distinct = q(cur, "SELECT COUNT(*) FROM (SELECT DISTINCT * FROM stg_orders_tiktokshop) t")[0][0]
    print(f"Dong TikTok bi loai (trung hoan toan): {raw_lines['tiktokshop'] - tt_distinct}")
    print(f"Mat dong TikTok sau loai trung (phai = 0): {tt_distinct - fact_lines.get('tiktokshop', 0)}")
    for p in platforms:
        if p != "tiktokshop":
            print(f"Mat dong o {p} (phai = 0): {raw_lines[p] - fact_lines.get(p, 0)}")
    print("Dong fact khong co khach:", q(cur, "SELECT COUNT(*) FROM fact_order_line WHERE customer_key IS NULL OR customer_key=''")[0][0])
    print("Vung thieu o dim_customer:", q(cur, "SELECT COUNT(*) FROM dim_customer WHERE region IS NULL")[0][0],
          "/", q(cur, "SELECT COUNT(*) FROM dim_customer")[0][0])
    print("Khoang ngay (gio Paris):", q(cur, "SELECT MIN(DATE(order_ts_local)), MAX(DATE(order_ts_local)) FROM fact_order_line")[0])
    print("Doi chieu gross_ttc - discount_ttc - net_ttc (phai = 0):",
          q(cur, "SELECT SUM(gross_ttc-discount_ttc-net_ttc) FROM fact_order_line")[0][0])
    print("Doi chieu net_ttc - net_ht - vat_amount (phai = 0):",
          q(cur, "SELECT SUM(net_ttc-net_ht-vat_amount) FROM fact_order_line")[0][0])
    print("Don bi am hoac 0:", q(cur, "SELECT COUNT(*) FROM fact_order_line WHERE net_ttc <= 0")[0][0])
    print("\nDoanh thu / loi nhuan truoc ads theo san (chi don completed), nghin EUR:")
    for r in q(cur, "SELECT platform, ROUND(SUM(revenue)/1000,2), ROUND(SUM(profit_before_ads)/1000,2) FROM v_sales_daily GROUP BY platform"):
        print("  ", r)
    print("\n5 SKU lo nhat (v_sku_profit), nghin EUR:")
    worst = q(cur, "SELECT sku, ROUND(profit_before_ads/1000,2) FROM v_sku_profit ORDER BY profit_before_ads LIMIT 5")
    for r in worst:
        print("  ", r)
    print("Khop voi SKU lo da nhung:", sorted(x[0] for x in worst) == sorted(truth_skus))
    print("\nROAS theo chien dich (do nen tang tu bao cao), spend nghin EUR:")
    for r in q(cur, "SELECT channel, campaign, ROUND(spend/1000,2), ROUND(platform_roas,2) FROM v_campaign_perf ORDER BY platform_roas"):
        print("  ", r)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    args = ap.parse_args()
    raw = Path(args.raw)
    import json
    truth = json.loads((raw / "truth_summary.json").read_text(encoding="utf-8"))
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET time_zone = '+00:00'")
    print("1) Nap staging")
    load_staging(cur, raw)
    print("2) Tao schema")
    run_script(cur, DDL)
    print("3) Dim va fact")
    run_script(cur, DIMS)
    run_script(cur, DATE_DIM)
    run_script(cur, UNION)
    run_script(cur, FACTS)
    run_script(cur, VIEWS)
    conn.commit()
    checks(cur, truth["loss_making_skus_after_discount_and_fees"])
    conn.close()


if __name__ == "__main__":
    main()
