"""Generate .github/ISSUE_TEMPLATE/new-call.yml from config/assets.yaml.

Run this after adding sectors to config/assets.yaml so the form stays in sync.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml  # noqa: E402

from journal.core import (EVENT_TYPES, MOVE_OPTIONS, NO_CALL, REL_OPTIONS, ROOT,  # noqa: E402
                          load_assets)


def dropdown(id_, label, options, desc="", required=False, default=None):
    item = {"type": "dropdown", "id": id_,
            "attributes": {"label": label, "options": options}}
    if desc:
        item["attributes"]["description"] = desc
    if default is not None:
        item["attributes"]["default"] = default
    item["validations"] = {"required": required}
    return item


def text(id_, label, desc="", placeholder="", required=False, area=False):
    item = {"type": "textarea" if area else "input", "id": id_,
            "attributes": {"label": label}}
    if desc:
        item["attributes"]["description"] = desc
    if placeholder:
        item["attributes"]["placeholder"] = placeholder
    item["validations"] = {"required": required}
    return item


def build() -> dict:
    a = load_assets()
    moves = [NO_CALL] + MOVE_OPTIONS
    rels = [NO_CALL] + REL_OPTIONS
    sector_opts = ["None"] + [f"{t} - {n}" for t, n in a["sectors"]["tickers"].items()]

    body = [
        {"type": "markdown", "attributes": {"value": (
            "**Make your call before the release, and before you ask Claude.** "
            "The time you open this issue is your proof.\n\n"
            "Moves are graded from the previous close to the close on the reaction date. "
            "Sizes: S&P 500 small ≥0.2%, medium ≥0.6%, large ≥1.2%; yields small ≥2bp, "
            "medium ≥5bp, large ≥10bp. Full table in the README.")}},
        text("event", "Event", placeholder="November CPI", required=True),
        dropdown("event_type", "Event type", EVENT_TYPES, required=True),
        text("reaction_date", "Reaction date",
             "Trading day the market reacts (YYYY-MM-DD). Data before 9:30 ET = same day; "
             "earnings after the close = next trading day.", "2026-12-10", required=True),
        text("release_time", "Release time (ET)",
             "Optional, 24-hour. Calls opened after this time are marked late.", "08:30"),
        text("consensus", "Consensus expectation", placeholder="Core CPI +0.3% m/m, headline +0.2%"),
        dropdown("data_view", "Your view on the data",
                 ["Hotter / stronger than consensus", "In line", "Cooler / weaker than consensus",
                  "Not a data release"]),
        {"type": "markdown", "attributes": {"value": "### Your calls\nLeave anything you have no view on as **No call**."}},
    ]
    for key, cfg in a["core"].items():
        body.append(dropdown(key, cfg["label"], moves, default=0))
    body += [
        dropdown("sector1", "Sector 1", sector_opts, default=0),
        dropdown("sector1_call", "Sector 1 vs the S&P 500", rels,
                 "Graded on the sector's move minus the S&P 500's move.", default=0),
        dropdown("sector2", "Sector 2", sector_opts, default=0),
        dropdown("sector2_call", "Sector 2 vs the S&P 500", rels, default=0),
        text("stock", "Single stock (ticker)", "Mainly for earnings calls.", "NVDA"),
        dropdown("stock_call", "Single stock call", moves,
                 "Stock sizes: small ≥1%, medium ≥3%, large ≥7%.", default=0),
        dropdown("confidence", "Confidence",
                 ["1 - coin flip", "2 - slight lean", "3 - fairly confident",
                  "4 - confident", "5 - very confident"], required=True),
        text("reasoning", "Reasoning",
             "2–3 lines on WHY. What's priced in? What would surprise the market?",
             required=True, area=True),
        text("scenarios", "If it goes the other way",
             "Optional: what you'd expect if the data surprises the other way.", area=True),
        text("source", "Source link", "Optional: the WSJ article (link only, don't paste text)."),
    ]
    return {"name": "New call", "description": "Log a market call before the event",
            "title": "[Call] ", "body": body}


def main() -> None:
    out = ROOT / ".github" / "ISSUE_TEMPLATE" / "new-call.yml"
    out.write_text(yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=1000),
                   encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
