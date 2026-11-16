"""Xuat du lieu TONG HOP tu MySQL lumi_dw ra dashboard/data.json cho dashboard HTML.

Chi xuat so tong hop (theo ngay, kenh, SKU, thang, vung, cohort). KHONG xuat ma khach hang, khong xuat dong don le.
Ket noi: 127.0.0.1, user lumi, mat khau tu bien moi truong MYSQL_PWD.
Chay: python -I export_dashboard_data.py
Khong co MySQL: python -I export_dashboard_data.py --engine duckdb --db data/lumi.duckdb [--out duong_dan.json]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

LAST_DAY = 20261115  # quang cao dung o 15/11; ngay 16/11 chi co vai gio cuoi do doi gio UTC sang Paris
OUT = Path(__file__).parent / "data.json"


def connect():
    import pymysql
    pwd = os.environ.get("MYSQL_PWD")
    if not pwd:
        sys.exit("Thieu bien moi truong MYSQL_PWD")
    return pymysql.connect(host="127.0.0.1", user="lumi", password=pwd, database="lumi_dw", charset="utf8mb4")


class DuckCursor:
    """Boc ket noi DuckDB thanh giao dien giong cursor pymysql; doi cu phap MySQL sang DuckDB."""

    def __init__(self, con):
        self.con = con
        self.res = None

    @staticmethod
    def translate(sql):
        sql = sql.replace("%%", "%").replace("%s", "?")
        sql = re.sub(r"FIELD\((\w+),((?:'[^']*',?)+)\)", lambda m: f"list_position([{m.group(2)}], {m.group(1)})", sql)
        sql = sql.replace("DATE_FORMAT(", "strftime(")
        sql = re.sub(r"SUM\(([\w.]+)='(\w+)'\)", lambda m: "SUM(CASE WHEN " + m.group(1) + "='" + m.group(2) + "' THEN 1 ELSE 0 END)", sql)
        return sql

    def execute(self, sql, args=None):
        self.res = self.con.execute(self.translate(sql), list(args) if args else [])

    def fetchall(self):
        return self.res.fetchall()


def q(cur, sql, args=None):
    cur.execute(sql, args)
    return cur.fetchall()


def f2(x):
    return round(float(x), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["mysql", "duckdb"], default="mysql")
    ap.add_argument("--db", default="data/lumi.duckdb", help="file DuckDB (chi dung voi --engine duckdb)")
    ap.add_argument("--out", default=str(OUT), help="file json dau ra (mac dinh dashboard/data.json)")
    args = ap.parse_args()
    out_path = Path(args.out)
    if args.engine == "duckdb":
        import duckdb
        conn = duckdb.connect(args.db, read_only=True)
        cur = DuckCursor(conn)
    else:
        conn = connect()
        cur = conn.cursor()

    platforms = q(cur, "SELECT platform, display_name, channel_type FROM dim_platform ORDER BY FIELD(platform,'amazon_fr','temu','shein','tiktokshop','cdiscount','web')")
    plat_idx = {p[0]: i for i, p in enumerate(platforms)}
    products = q(cur, "SELECT sku, product_name, category, list_price_ttc, unit_cost_ht FROM dim_product ORDER BY sku")
    sku_idx = {p[0]: i for i, p in enumerate(products)}
    campaigns = q(cur, "SELECT campaign, channel FROM dim_campaign ORDER BY FIELD(channel,'meta','tiktok','google'), campaign")
    camp_idx = {c[0]: i for i, c in enumerate(campaigns)}
    channels = ["meta", "tiktok", "google"]
    events = q(cur, "SELECT event_name, start_date, end_date, priority FROM stg_calendar_events ORDER BY start_date")

    months = [m[0] for m in q(cur, "SELECT DISTINCT DATE_FORMAT(full_date,'%%Y-%%m') FROM dim_date WHERE date_key >= 20260501 AND date_key <= %s ORDER BY 1", (LAST_DAY,))]
    month_idx = {m: i for i, m in enumerate(months)}

    # ---- ngay x kenh (don completed cho doanh thu; dem dong theo trang thai cho ti le hoan) ----
    rows = q(cur, """
        SELECT d.full_date, f.platform,
               COUNT(DISTINCT CASE WHEN f.status='completed' THEN f.order_id END),
               COALESCE(SUM(CASE WHEN f.status='completed' THEN f.qty END),0),
               COALESCE(SUM(CASE WHEN f.status='completed' THEN f.net_ht END),0),
               COALESCE(SUM(CASE WHEN f.status='completed' THEN f.net_ttc END),0),
               COALESCE(SUM(CASE WHEN f.status='completed' THEN f.platform_fee END),0),
               COALESCE(SUM(CASE WHEN f.status='completed' THEN f.cogs END),0),
               SUM(f.status='completed'), SUM(f.status='returned'), SUM(f.status='cancelled')
        FROM fact_order_line f JOIN dim_date d USING (date_key)
        WHERE f.date_key <= %s GROUP BY d.full_date, f.platform ORDER BY d.full_date, f.platform""", (LAST_DAY,))
    daily = [[r[0].isoformat(), plat_idx[r[1]], int(r[2]), int(r[3]), f2(r[4]), f2(r[5]), f2(r[6]), f2(r[7]), int(r[8]), int(r[9]), int(r[10])] for r in rows]

    # ---- SKU x kenh x thang (completed) ----
    rows = q(cur, """
        SELECT f.sku, f.platform, DATE_FORMAT(d.full_date,'%%Y-%%m'), SUM(f.qty), SUM(f.net_ht), SUM(f.platform_fee), SUM(f.cogs)
        FROM fact_order_line f JOIN dim_date d USING (date_key)
        WHERE f.status='completed' AND f.date_key <= %s GROUP BY f.sku, f.platform, 3""", (LAST_DAY,))
    sku_month = [[sku_idx[r[0]], plat_idx[r[1]], month_idx[r[2]], int(r[3]), f2(r[4]), f2(r[5]), f2(r[6])] for r in rows]

    # ---- hoan tra theo SKU x kenh (dong completed va returned) ----
    rows = q(cur, """
        SELECT sku, platform, SUM(status='completed'), SUM(status='returned')
        FROM fact_order_line WHERE date_key <= %s GROUP BY sku, platform""", (LAST_DAY,))
    sku_ret = [[sku_idx[r[0]], plat_idx[r[1]], int(r[2]), int(r[3])] for r in rows]

    # ---- quang cao theo ngay x chien dich ----
    rows = q(cur, """
        SELECT d.full_date, a.campaign, a.spend, a.impressions, a.clicks, a.platform_conversions, a.platform_conv_value
        FROM fact_ads_daily a JOIN dim_date d USING (date_key) WHERE a.date_key <= %s ORDER BY d.full_date, a.campaign""", (LAST_DAY,))
    ads = [[r[0].isoformat(), camp_idx[r[1]], f2(r[2]), int(r[3]), int(r[4]), int(r[5]), f2(r[6])] for r in rows]

    # ---- vung x kenh x thang (completed, doanh thu HT) ----
    rows = q(cur, """
        SELECT c.region, f.platform, DATE_FORMAT(d.full_date,'%%Y-%%m'), SUM(f.net_ht), COUNT(DISTINCT f.order_id)
        FROM fact_order_line f JOIN dim_date d USING (date_key) JOIN dim_customer c USING (customer_key)
        WHERE f.status='completed' AND f.date_key <= %s GROUP BY c.region, f.platform, 3""", (LAST_DAY,))
    regions = sorted({r[0] or "Khong ro" for r in rows})
    reg_idx = {r: i for i, r in enumerate(regions)}
    region = [[reg_idx[r[0] or "Khong ro"], plat_idx[r[1]], month_idx[r[2]], f2(r[3]), int(r[4])] for r in rows]

    # ---- khach hang: cohort, khach moi, ti le quay lai (tinh trong Python, chi xuat so tong hop) ----
    rows = q(cur, """
        SELECT f.customer_key, f.order_id, f.platform, f.order_ts_local
        FROM fact_order_line f WHERE f.status='completed' AND f.date_key <= %s
        GROUP BY f.customer_key, f.order_id, f.platform, f.order_ts_local ORDER BY f.customer_key, f.order_ts_local""", (LAST_DAY,))
    by_cust = defaultdict(list)
    for cust, oid, plat, ts in rows:
        by_cust[cust].append((ts, oid, plat))
    first_month, new_by = {}, defaultdict(int)
    active = defaultdict(set)  # (cohort, k) -> customers
    orders_per_cust = {}
    for cust, lst in by_cust.items():
        lst.sort()
        m0 = lst[0][0].strftime("%Y-%m")
        first_month[cust] = m0
        new_by[(month_idx[m0], plat_idx[lst[0][2]])] += 1
        orders_per_cust[cust] = len({o for _, o, _ in lst})
        y0, mm0 = int(m0[:4]), int(m0[5:])
        for ts, _o, _p in lst:
            k = (ts.year - y0) * 12 + (ts.month - mm0)
            active[(month_idx[m0], k)].add(cust)
    n_months = len(months)
    cohort = []
    for ci in range(n_months):
        size = len(active.get((ci, 0), ()))
        counts = [len(active.get((ci, k), ())) for k in range(0, n_months - ci)]
        cohort.append({"month": months[ci], "size": size, "active": counts})
    new_customers = [[mi, pi, n] for (mi, pi), n in sorted(new_by.items())]
    total_cust = len(by_cust)
    repeat_cust = sum(1 for n in orders_per_cust.values() if n >= 2)

    data = {
        "meta": {
            "title": "Lumi Accessories - tableau de bord e-commerce (donnees simulees)",
            "currency": "EUR",
            "period": [months[0] + "-01", "2026-11-15"],
            "note": "Donnees 100% synthetiques generees par script. Aucun client reel, aucun chiffre d'une vraie entreprise.",
        },
        "months": months,
        "platforms": [{"key": p[0], "name": p[1], "type": p[2]} for p in platforms],
        "channels": channels,
        "campaigns": [{"name": c[0], "channel": c[1]} for c in campaigns],
        "products": [{"sku": p[0], "name": p[1], "category": p[2], "price_ttc": f2(p[3]), "cost_ht": f2(p[4])} for p in products],
        "regions": regions,
        "events": [{"name": e[0], "start": e[1], "end": e[2], "priority": int(e[3])} for e in events],
        "cols": {
            "daily": ["date", "platform", "orders", "units", "revenue_ht", "revenue_ttc", "platform_fee", "cogs", "lines_completed", "lines_returned", "lines_cancelled"],
            "sku_month": ["sku", "platform", "month", "units", "revenue_ht", "platform_fee", "cogs"],
            "sku_ret": ["sku", "platform", "lines_completed", "lines_returned"],
            "ads": ["date", "campaign", "spend", "impressions", "clicks", "conversions", "conv_value"],
            "region": ["region", "platform", "month", "revenue_ht", "orders"],
            "new_customers": ["month", "platform", "customers"],
        },
        "daily": daily,
        "sku_month": sku_month,
        "sku_ret": sku_ret,
        "ads": ads,
        "region": region,
        "new_customers": new_customers,
        "cohort": cohort,
        "customers": {"total": total_cust, "repeat": repeat_cust},
    }
    for e in data["events"]:
        e["start"] = e["start"].isoformat() if hasattr(e["start"], "isoformat") else str(e["start"])
        e["end"] = e["end"].isoformat() if hasattr(e["end"], "isoformat") else str(e["end"])
    out_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{out_path.name}: {out_path.stat().st_size/1024:.0f} KB; daily={len(daily)} sku_month={len(sku_month)} ads={len(ads)} "
          f"region={len(region)} customers={total_cust} repeat={repeat_cust}")


if __name__ == "__main__":
    main()
