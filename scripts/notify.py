"""Format grading results as a GitHub comment. Reads grade.py's JSON on stdin,
writes one comment file per graded call into the folder given as argv[1]."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ICON = {1.0: "✅", 0.5: "🟡", 0.0: "❌"}


def comment(item: dict) -> str:
    if item["status"] == "market-closed":
        return ("The market was closed on this reaction date, so this call can't be graded. "
                "Log it again with the next trading day.")
    if item["status"] == "no-data":
        return "No market data came through for this date, so this call couldn't be graded."
    lines = [f"### Graded: {item['event']} — score {item.get('score', '–')}/100", "",
             "| | Asset | Your call | What happened | Move |", "|---|---|---|---|---|"]
    for r in item["results"].values():
        unit = r["unit"]
        move = f"{r['move']:+.1f} bp" if unit == "bp" else f"{r['move']:+.2f} {unit}"
        lines.append(f"| {ICON.get(r['score'], '')} | {r['label']} | {r['call']} | {r['actual']} | {move} |")
    lines += ["", "✅ direction and size right · 🟡 direction right or one step off · ❌ wrong"]
    if item.get("on_time") is False:
        lines += ["", "⚠️ This call was logged after the release, so it doesn't count toward your scorecard."]
    lines += ["", f"Next: open [{item['file']}](../blob/main/{item['file']}) and fill in **Review notes** "
              "— what did the market do, and what did you miss?"]
    return "\n".join(lines)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for item in json.load(sys.stdin):
        if item.get("issue"):
            (out / f"{item['issue']}.md").write_text(comment(item), encoding="utf-8")


if __name__ == "__main__":
    main()
