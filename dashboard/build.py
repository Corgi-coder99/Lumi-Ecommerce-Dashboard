"""Gop dashboard/template.html va dashboard/data.json thanh mot file doc lap site/index.html (khong can mang, khong thu vien ngoai).

Chay: python -I dashboard/build.py
"""
import json
from pathlib import Path

here = Path(__file__).parent
data = json.loads((here / "data.json").read_text(encoding="utf-8"))
tpl = (here / "template.html").read_text(encoding="utf-8")
assert "/*__DATA__*/" in tpl
# '</' trong JSON co the dong the script som, nen thoat no
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
out = here.parent / "site" / "index.html"
out.parent.mkdir(exist_ok=True)
out.write_text(tpl.replace("/*__DATA__*/", payload), encoding="utf-8")
print(f"{out} {out.stat().st_size / 1024:.0f} KB")
