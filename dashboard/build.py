"""Bundle dashboard/template.html, dashboard/theme.css and dashboard/data.json into one standalone file, site/index.html.

The output needs no network, no external fonts and no external libraries.
Run: python -I dashboard/build.py
"""
import json
from pathlib import Path

here = Path(__file__).parent
data = json.loads((here / "data.json").read_text(encoding="utf-8"))
theme = (here / "theme.css").read_text(encoding="utf-8")
tpl = (here / "template.html").read_text(encoding="utf-8")
assert "/*__THEME__*/" in tpl and "/*__DATA__*/" in tpl
# '</' inside the JSON could close the script tag early, so escape it
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = tpl.replace("/*__THEME__*/", theme).replace("/*__DATA__*/", payload)
out = here.parent / "site" / "index.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8")
print(f"{out} {out.stat().st_size / 1024:.0f} KB")
