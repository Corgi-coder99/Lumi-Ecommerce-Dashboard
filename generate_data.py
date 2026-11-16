"""Bo sinh du lieu gia lap cho cua hang phu kien thoi trang hu cau "Lumi Accessories" ban thi truong Phap.

Du lieu 100% tong hop (synthetic), khong co khach hang that, khong co thong tin dinh danh.
Tien EUR. Gia ban le la gia TTC (da gom VAT 20%). Gia von va chi phi quang cao la HT.
6 kenh ban: Amazon.fr, Temu, Shein, TikTok Shop, Cdiscount, cua hang web rieng. 3 nen tang ads: Meta, TikTok, Google.
Moi nguon xuat CSV voi luoc do khac nhau co chu dich (de lam buoc lam sach). Luoc do chi tiet: SPEC-T-047.md.
Phi hoa hong va lich sale: market-fr/sources.md (tra cuu cong khai).
Chay: python -I generate_data.py [--out data/raw] [--seed 42]
Cac bat thuong nhung san ghi trong truth_summary.json (chi dung de QA, khong dua vao dashboard).
"""
import argparse
import csv
import hashlib
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

START = date(2026, 5, 1)
END = date(2026, 11, 15)

# (ten, bat dau, ket thuc, uu tien (nho = hon), he so nhu cau)
EVENTS = [
    ("French Days printemps", date(2026, 4, 29), date(2026, 5, 5), 3, 1.5),
    ("Fete des meres", date(2026, 5, 25), date(2026, 5, 31), 4, 1.35),
    ("Prime Day", date(2026, 6, 23), date(2026, 6, 26), 1, 2.2),
    ("Soldes ete", date(2026, 6, 24), date(2026, 7, 28), 5, 1.45),
    ("French Days rentree", date(2026, 9, 7), date(2026, 9, 14), 2, 1.7),
    ("Jours Flash Prime", date(2026, 10, 6), date(2026, 10, 7), 1, 2.0),
    ("Singles Day 11.11", date(2026, 11, 10), date(2026, 11, 11), 2, 1.6),
]

CATEGORIES = {
    # ten: (so SKU, khoang gia TTC EUR, ti le gia von HT so voi gia HT, ti le hoan tra co so)
    "Handbags": (18, (25, 95), 0.50, 0.05),
    "Wallets": (14, (15, 55), 0.46, 0.04),
    "Belts": (12, (15, 45), 0.44, 0.14),
    "Hats": (12, (10, 35), 0.46, 0.12),
    "Sunglasses": (14, (15, 80), 0.52, 0.07),
    "Jewelry": (16, (8, 60), 0.40, 0.09),
    "Scarves": (10, (10, 40), 0.44, 0.04),
}
SINGULAR = {"Handbags": "Handbag", "Wallets": "Wallet", "Belts": "Belt", "Hats": "Hat", "Sunglasses": "Sunglasses", "Jewelry": "Jewelry piece", "Scarves": "Scarf"}
COLORS = ["noir", "marron", "creme", "rouge", "bleu", "argent", "or"]
REGIONS = ["Ile-de-France", "Auvergne-Rhone-Alpes", "Provence-Alpes-Cote d'Azur", "Occitanie", "Nouvelle-Aquitaine",
           "Hauts-de-France", "Grand Est", "Bretagne", "Pays de la Loire", "Normandie"]
REGION_W = [19, 12, 8, 9, 9, 9, 8, 5, 6, 5]
VAT = 1.2

PLATFORMS = {
    # ten: (ti trong don, hoa hong mac dinh, he so hoan tra, them giam gia co so)
    "amazon_fr": (0.32, 0.15, 1.0, 0.00),
    "temu": (0.15, 0.10, 1.3, 0.05),
    "shein": (0.12, 0.10, 1.4, 0.03),
    "tiktokshop": (0.14, 0.09, 1.4, 0.00),
    "cdiscount": (0.09, 0.15, 1.0, 0.02),
    "web": (0.18, 0.025, 0.8, 0.00),
}
FEE_OVERRIDES = [("cdiscount", "Jewelry", 0.20)]
PREFIX = {"amazon_fr": "AF", "temu": "TE", "shein": "SH", "tiktokshop": "TT", "cdiscount": "CD", "web": "WB"}


def money(x):
    return f"{x:.2f}"


def build_products(rng):
    rows, n = [], 0
    for cat, (cnt, (lo, hi), cost_ratio, _ret) in CATEGORIES.items():
        for i in range(1, cnt + 1):
            n += 1
            price = round(rng.uniform(lo, hi)) - 0.01  # gia le kieu 34,99
            ratio = min(0.7, max(0.25, rng.gauss(cost_ratio, 0.04)))
            rows.append({
                "sku": f"LM{n:03d}",
                "product_name": f"{SINGULAR[cat]} {i:02d}",
                "category": cat,
                "color": rng.choice(COLORS),
                "list_price": price,
                "unit_cost": round(price / VAT * ratio, 2),
                "popularity": rng.paretovariate(1.6),
            })
    # SKU lo chu dich: gia von HT bang gia ban HT, sau giam gia va hoa hong se lo
    loss = rng.sample([r for r in rows if r["category"] in ("Handbags", "Sunglasses", "Jewelry")], 5)
    for r in loss:
        r["unit_cost"] = round(r["list_price"] / VAT * 1.0, 2)
    return rows, [r["sku"] for r in loss]


def new_customer(rng, i):
    return {"customer_key": hashlib.sha256(f"cust-{i}-lumi-fr".encode()).hexdigest()[:12],
            "region": rng.choices(REGIONS, REGION_W)[0]}


def event_for(d):
    cands = [e for e in EVENTS if e[1] <= d <= e[2]]
    return min(cands, key=lambda e: e[3]) if cands else None


def demand_for(d, day_idx, total_days):
    weekday = [1.0, 0.95, 0.95, 1.0, 1.1, 1.25, 1.2][d.weekday()]
    trend = 1.0 + 0.40 * day_idx / total_days
    ev = event_for(d)
    mult = max([e[4] for e in EVENTS if e[1] <= d <= e[2]], default=1.0)
    if mult == 1.0:
        # veille d'un grand evenement (priorite 1 ou 2): leger regain
        if any(e[3] <= 2 and e[1] - timedelta(days=1) == d for e in EVENTS):
            mult = 1.15
    return 125 * weekday * trend * mult, ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    products, loss_skus = build_products(rng)
    customers = []  # khach hang tao dan theo don: ~82% don la khach moi, ~18% la khach cu quay lai
    cat_ret = {c: v[3] for c, v in CATEGORIES.items()}
    weights = [p["popularity"] for p in products]

    days = (END - START).days + 1
    order_seq = 0
    lines = []
    for k in range(days):
        d = START + timedelta(days=k)
        total, ev = demand_for(d, k, days)
        n_orders = max(1, int(rng.gauss(total, total * 0.08)))
        ev_name = ev[0] if ev else ""
        in_soldes = date(2026, 6, 24) <= d <= date(2026, 7, 28)
        for _ in range(n_orders):
            order_seq += 1
            plat = rng.choices(list(PLATFORMS), [v[0] for v in PLATFORMS.values()])[0]
            ret_mult, extra_disc = PLATFORMS[plat][2], PLATFORMS[plat][3]
            if customers and rng.random() < 0.18:
                cust = rng.choice(customers)
            else:
                cust = new_customer(rng, len(customers))
                customers.append(cust)
            ts = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(
                seconds=int(rng.triangular(0, 86399, 72000)))
            n_lines = rng.choices([1, 2, 3], [0.72, 0.22, 0.06])[0]
            oid = f"{PREFIX[plat]}{order_seq:07d}"
            status_roll = rng.random()
            used = set()
            for _l in range(n_lines):
                p = rng.choices(products, weights)[0]
                while p["sku"] in used:  # un SKU par ligne et par commande (le panier fusionne les quantites)
                    p = rng.choices(products, weights)[0]
                used.add(p["sku"])
                qty = rng.choices([1, 2, 3], [0.85, 0.12, 0.03])[0]
                disc = rng.choice([0, 0, 0.05, 0.10])
                if ev_name:
                    disc = rng.choice([0.10, 0.15, 0.20, 0.25])
                if in_soldes:
                    disc += 0.05
                disc += extra_disc
                if p["sku"] in loss_skus and (ev_name or in_soldes):
                    disc += 0.10
                gross = round(p["list_price"] * qty, 2)
                discount = round(gross * disc, 2)
                ret_p = min(0.45, cat_ret[p["category"]] * ret_mult)
                if status_roll < 0.04:
                    status = "cancelled"
                elif status_roll < 0.04 + ret_p:
                    status = "returned"
                else:
                    status = "completed"
                lines.append({
                    "order_id": oid, "ts": ts, "platform": plat, "sku": p["sku"], "qty": qty,
                    "unit_price": p["list_price"], "gross": gross, "discount": discount,
                    "status": status, "cust": cust["customer_key"], "region": cust["region"],
                })

    def write(name, header, rows):
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    by = {p: [l for l in lines if l["platform"] == p] for p in PLATFORMS}
    comma = lambda x: f"{x:.2f}".replace(".", ",")

    # amazon.fr: ISO +00:00, tong dong TTC, dau phay thap phan
    st = {"completed": "Shipped", "returned": "Returned", "cancelled": "Cancelled"}
    write("orders_amazon_fr.csv",
          ["amazon-order-id", "purchase-date", "sku", "quantity-purchased", "item-price", "promotion-discount", "order-status", "buyer-key", "ship-state"],
          [[l["order_id"], l["ts"].strftime("%Y-%m-%dT%H:%M:%S+00:00"), l["sku"], l["qty"], comma(l["gross"]), comma(l["discount"]),
            st[l["status"]], l["cust"], l["region"]] for l in by["amazon_fr"]])

    # temu: epoch giay, don gia TTC
    st = {"completed": "delivered", "returned": "refunded", "cancelled": "cancelled"}
    write("orders_temu.csv",
          ["order_sn", "order_time_epoch", "sku_id", "qty", "unit_price_eur", "discount_eur", "status", "user_hash", "region_code"],
          [[l["order_id"], int(l["ts"].timestamp()), l["sku"], l["qty"], money(l["unit_price"]), money(l["discount"]),
            st[l["status"]], l["cust"], l["region"]] for l in by["temu"]])

    # shein: dd/mm/YYYY HH:MM:SS
    st = {"completed": "Completed", "returned": "Return", "cancelled": "Cancel"}
    write("orders_shein.csv",
          ["orderNo", "createDate", "sellerSku", "number", "sellingPrice", "couponAmount", "orderState", "memberHash", "province"],
          [[l["order_id"], l["ts"].strftime("%d/%m/%Y %H:%M:%S"), l["sku"], l["qty"], money(l["unit_price"]), money(l["discount"]),
            st[l["status"]], l["cust"], l["region"]] for l in by["shein"]])

    # tiktok shop: epoch ms, ~0.6% dong trung (loi xuat file)
    tt_rows = [[l["order_id"], int(l["ts"].timestamp() * 1000), l["sku"], l["qty"], money(l["gross"]), money(l["discount"]),
                l["status"].upper(), l["cust"], l["region"]] for l in by["tiktokshop"]]
    dups = rng.sample(tt_rows, int(len(tt_rows) * 0.006))
    tt_rows.extend(dups)
    rng.shuffle(tt_rows)
    write("orders_tiktokshop.csv",
          ["order_id", "create_time_ms", "seller_sku", "quantity", "sku_subtotal_before_discount", "seller_discount", "order_state", "buyer_id", "region"], tt_rows)

    # cdiscount: ~1% thieu vung giao hang
    st = {"completed": "Delivered", "returned": "Returned", "cancelled": "Cancelled"}
    cd_rows = []
    for l in by["cdiscount"]:
        reg = "" if rng.random() < 0.01 else l["region"]
        cd_rows.append([l["order_id"], l["ts"].strftime("%Y-%m-%d %H:%M"), l["sku"], l["qty"], money(l["unit_price"]), money(l["discount"]),
                        st[l["status"]], l["cust"], reg])
    write("orders_cdiscount.csv",
          ["OrderNumber", "CreationDate", "SellerProductId", "Quantity", "SalePrice", "Discount", "State", "CustomerKey", "DeliveryRegion"], cd_rows)

    # web: UTC ISO 'T'
    write("orders_web.csv",
          ["id", "created_at_utc", "sku", "quantity", "price", "coupon_discount", "fulfillment_status", "customer_key", "region"],
          [[l["order_id"], l["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), l["sku"], l["qty"], money(l["unit_price"]), money(l["discount"]),
            l["status"], l["cust"], l["region"]] for l in by["web"]])

    # san pham, phi, lich
    write("products.csv", ["sku", "product_name", "category", "color", "list_price_ttc", "unit_cost_ht"],
          [[p["sku"], p["product_name"], p["category"], p["color"], money(p["list_price"]), money(p["unit_cost"])] for p in products])
    fee_rows = [[k, "*", v[1]] for k, v in PLATFORMS.items()] + [[a, b, c] for a, b, c in FEE_OVERRIDES]
    write("platform_fees.csv", ["platform", "category", "commission_rate"], fee_rows)
    write("calendar_events.csv", ["event_name", "start_date", "end_date", "priority", "demand_multiplier"],
          [[e[0], e[1].isoformat(), e[2].isoformat(), e[3], e[4]] for e in EVENTS])

    # ---------- quang cao (EUR, HT) ----------
    # (ten chien dich, ngan sach moi ngay EUR, ti le chuyen doi, CPC EUR)
    campaigns = {
        "meta": [("META_Retarget_Sacs", 91, 0.030, 0.51), ("META_Prospect_Bijoux", 51, 0.016, 0.40), ("META_Cadeau_Foulards", 43, 0.020, 0.44)],
        "tiktok": [("TT_Spark_Chapeaux", 60, 0.022, 0.32), ("TT_Live_Ceintures", 77, 0.007, 0.29), ("TT_Video_Lunettes", 55, 0.018, 0.34)],
        "google": [("GG_Shopping_Portefeuilles", 85, 0.034, 0.38), ("GG_Search_Marque", 34, 0.060, 0.23), ("GG_PMax_Tout", 102, 0.019, 0.41)],
    }
    aov = sum(p["list_price"] for p in products) / len(products) * 1.25
    ad_rows = {k: [] for k in campaigns}
    for k in range(days):
        d = START + timedelta(days=k)
        boost = max([e[4] for e in EVENTS if e[1] <= d <= e[2]], default=1.0)
        trend = 1.0 + 0.40 * k / days
        for chan, camps in campaigns.items():
            for name, daily, cvr, cpc in camps:
                spend = round(daily * boost ** 0.8 * trend * rng.uniform(0.85, 1.15), 2)
                clicks = max(1, int(spend / (cpc * rng.uniform(0.85, 1.2))))
                impressions = int(clicks / rng.uniform(0.008, 0.02))
                conv = int(clicks * cvr * rng.uniform(0.8, 1.2) * (1.15 if boost > 1 else 1))
                if chan == "meta":  # Meta s'attribue plus de conversions que reel (attribution large) ~1.3x
                    conv = int(conv * 1.3)
                value = round(conv * aov * rng.uniform(0.8, 1.1), 2)
                ad_rows[chan].append((d, name, spend, impressions, clicks, conv, value))
    write("ads_meta.csv", ["Day", "Campaign name", "Amount spent (EUR)", "Impressions", "Link clicks", "Purchases", "Purchase conversion value"],
          [[r[0].isoformat(), r[1], money(r[2]), *r[3:6], money(r[6])] for r in ad_rows["meta"]])
    write("ads_tiktok.csv", ["stat_time_day", "campaign_name", "cost", "impressions", "clicks", "complete_payment", "complete_payment_value"],
          [[r[0].strftime("%Y/%m/%d"), r[1], money(r[2]), *r[3:6], money(r[6])] for r in ad_rows["tiktok"]])
    write("ads_google.csv", ["date", "campaign", "cost_micros", "impressions", "clicks", "conversions", "conversions_value"],
          [[r[0].isoformat(), r[1], int(round(r[2] * 1_000_000)), *r[3:6], money(r[6])] for r in ad_rows["google"]])

    truth = {
        "seed": args.seed,
        "market": "France, EUR, prix TTC, VAT 20%",
        "period": [START.isoformat(), END.isoformat()],
        "events": {e[0]: [e[1].isoformat(), e[2].isoformat()] for e in EVENTS},
        "loss_making_skus_after_discount_and_fees": loss_skus,
        "loss_making_campaign": "TT_Live_Ceintures (CVR tres faible, ROAS faible)",
        "meta_conversions_overreported_factor": 1.3,
        "tiktok_duplicate_rows_injected": len(dups),
        "cdiscount_missing_region_rate": 0.01,
        "high_return_categories": ["Belts", "Hats"],
        "high_return_platforms": ["temu", "shein", "tiktokshop"],
        "notes": "Donnees synthetiques. Aucune donnee personnelle. Clients identifies par un hash.",
    }
    (out / "truth_summary.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"order lines={len(lines)} unique_orders={order_seq} products={len(products)} days={days} out={out}")


if __name__ == "__main__":
    main()
