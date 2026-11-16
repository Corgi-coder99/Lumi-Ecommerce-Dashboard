"""Kiem tra DuckDB cho ra cung ket qua voi ban MySQL.

Chay: python -I tests/test_duckdb_parity.py   (khong can pytest, khong can MySQL)
Buoc: build DuckDB tu data/raw_fr trong thu muc tam -> kiem tra cac so da biet -> xuat data.json bang
--engine duckdb -> so voi tests/reference_data_mysql.json (sai so 0.01 voi tien, thu tu dong co the khac).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_fr"
REF = ROOT / "tests" / "reference_data_mysql.json"
LAST_DAY = 20261115

fails = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'LECH'}] {name}: {got}" + ("" if ok else f" (mong doi {want})"))
    if not ok:
        fails.append(f"{name}: {got} != {want}")


def run(args):
    r = subprocess.run([sys.executable, "-I", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-1500:])
        fails.append(f"lenh loi: {' '.join(args)}")
        return False
    return True


# so sanh co sai so, bo qua thu tu dong cua cac mang khong co ORDER BY
KEYLEN = {"daily": 2, "sku_month": 3, "sku_ret": 2, "ads": 2, "region": 3, "new_customers": 2}


def compare(a, b, path, diffs):
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            diffs.append(f"{path}: khac khoa {sorted(a.keys() ^ b.keys())}")
            return
        for k in a:
            if path == "" and k in KEYLEN and isinstance(a[k], list) and len(a[k]) == len(b[k]):
                ka = sorted(a[k], key=lambda r: [str(x) for x in r[:KEYLEN[k]]])
                kb = sorted(b[k], key=lambda r: [str(x) for x in r[:KEYLEN[k]]])
                compare(ka, kb, k, diffs)
            else:
                compare(a[k], b[k], f"{path}/{k}" if path else k, diffs)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append(f"{path}: do dai {len(a)} != {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            if len(diffs) < 10:
                compare(x, y, f"{path}[{i}]", diffs)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if abs(a - b) > 0.0100001:
            diffs.append(f"{path}: {a} != {b}")
    elif a != b:
        diffs.append(f"{path}: {a!r} != {b!r}")


def main():
    truth = json.loads((RAW / "truth_summary.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "t.duckdb"
        out = Path(tmp) / "data.json"
        print("1) Build DuckDB tu", RAW)
        if not run(["build_dw_duckdb.py", "--raw", str(RAW), "--db", str(db)]):
            print("FAIL (build loi)")
            return 1
        con = duckdb.connect(str(db), read_only=True)
        one = lambda sql: con.execute(sql).fetchone()[0]
        print("2) So da biet")
        comp = f"status='completed' AND date_key <= {LAST_DAY}"
        check("doanh thu HT completed", float(one(f"SELECT SUM(net_ht) FROM fact_order_line WHERE {comp}")), 1186856.31)
        check("don completed", one(f"SELECT COUNT(DISTINCT order_id) FROM fact_order_line WHERE {comp}"), 32110)
        check("loi nhuan gop", float(one(f"SELECT SUM(net_ht - platform_fee - cogs) FROM fact_order_line WHERE {comp}")), 371116.18)
        check("so san pham ban (units)", one(f"SELECT SUM(qty) FROM fact_order_line WHERE {comp}"), 50374)
        check("chi phi ads", float(one(f"SELECT SUM(spend) FROM fact_ads_daily WHERE date_key <= {LAST_DAY}")), 160467.68)
        check("khach co don completed", one(f"SELECT COUNT(DISTINCT customer_key) FROM fact_order_line WHERE {comp}"), 26994)
        dup = one("SELECT COUNT(*) FROM stg_orders_tiktokshop") - one("SELECT COUNT(*) FROM (SELECT DISTINCT * FROM stg_orders_tiktokshop) t")
        check("dong TikTok bi loai", dup, truth["tiktok_duplicate_rows_injected"])
        worst = [r[0] for r in con.execute("SELECT sku FROM v_sku_profit ORDER BY profit_before_ads LIMIT 5").fetchall()]
        check("5 SKU lo nhat", sorted(worst), sorted(truth["loss_making_skus_after_discount_and_fees"]))
        con.close()
        print("3) Xuat data.json bang --engine duckdb va so voi ban MySQL")
        if run(["dashboard/export_dashboard_data.py", "--engine", "duckdb", "--db", str(db), "--out", str(out)]):
            diffs = []
            compare(json.loads(REF.read_text(encoding="utf-8")), json.loads(out.read_text(encoding="utf-8")), "", diffs)
            check("data.json == tham chieu MySQL (so dong khac)", len(diffs), 0)
            for d in diffs:
                print("    ", d)
    print("PASS" if not fails else "FAIL: " + "; ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
