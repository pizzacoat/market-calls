"""Inject practice/bank.json into practice/app_template.html -> practice/app.html."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    bank = json.loads((ROOT / "practice" / "bank.json").read_text(encoding="utf-8"))
    data = json.dumps(bank, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    html = (ROOT / "practice" / "app_template.html").read_text(encoding="utf-8")
    if "/*BANK*/" not in html:
        sys.exit("template is missing the /*BANK*/ placeholder")
    out = ROOT / "practice" / "app.html"
    out.write_text(html.replace("/*BANK*/", data), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} with {len(bank['events'])} events")


if __name__ == "__main__":
    main()
