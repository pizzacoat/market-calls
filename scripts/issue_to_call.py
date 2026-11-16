"""Turn a 'New call' GitHub issue into a timestamped call file in calls/.

Run by .github/workflows/log-call.yml. Reads the issue from environment variables
and prints a JSON result that the workflow uses to comment on the issue.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from journal.core import (CALLS_DIR, ET, EVENT_TYPES, NO_CALL, label_to_level,  # noqa: E402
                          load_assets, parse_date, write_call)

FIELD_KEYS = {
    "Event": "event",
    "Event type": "event_type",
    "Reaction date": "reaction_date",
    "Release time (ET)": "release_time",
    "Consensus expectation": "consensus",
    "Your view on the data": "data_view",
    "S&P 500": "spx",
    "2-year yield": "us2y",
    "10-year yield": "us10y",
    "US dollar (DXY)": "dollar",
    "Gold": "gold",
    "Oil": "oil",
    "Sector 1": "sector1",
    "Sector 1 vs the S&P 500": "sector1_call",
    "Sector 2": "sector2",
    "Sector 2 vs the S&P 500": "sector2_call",
    "Single stock (ticker)": "stock",
    "Single stock call": "stock_call",
    "Confidence": "confidence",
    "Reasoning": "reasoning",
    "If it goes the other way": "scenarios",
    "Source link": "source",
}


def parse_issue_body(body: str) -> dict:
    """GitHub issue forms render as '### Label\\n\\nvalue' blocks."""
    fields = {}
    for block in re.split(r"^### ", body or "", flags=re.M)[1:]:
        label, _, value = block.partition("\n")
        value = value.strip()
        if value == "_No response_":
            value = ""
        key = FIELD_KEYS.get(label.strip())
        if key:
            fields[key] = value
    return fields


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "call"


def build_call(fields: dict, issue: dict) -> tuple[dict, str, list[str]]:
    errors: list[str] = []
    assets = load_assets()

    event = fields.get("event", "").strip()
    if not event:
        errors.append("**Event** is empty.")

    try:
        reaction = parse_date(fields.get("reaction_date", ""))
        if reaction.weekday() >= 5:
            errors.append(f"**Reaction date** {reaction} is a weekend; markets are closed.")
    except ValueError:
        reaction = None
        errors.append("**Reaction date** must look like 2026-11-18 (YYYY-MM-DD).")

    release = fields.get("release_time", "").strip()
    if release and not re.fullmatch(r"\d{1,2}:\d{2}", release):
        errors.append("**Release time** must look like 08:30 (24-hour, Eastern time).")
        release = ""

    calls: dict[str, str] = {}
    for key in assets["core"]:
        val = fields.get(key, "").strip() or NO_CALL
        try:
            if label_to_level(val) is not None:
                calls[key] = val
        except ValueError as e:
            errors.append(str(e))

    sectors = []
    for n in (1, 2):
        raw = fields.get(f"sector{n}", "").strip()
        call = fields.get(f"sector{n}_call", "").strip()
        if not raw or raw == "None" or not call or call == NO_CALL:
            continue
        ticker = raw.split()[0].upper()
        if ticker not in assets["sectors"]["tickers"]:
            errors.append(f"Unknown sector {raw!r}.")
            continue
        sectors.append({"ticker": ticker, "call": call})

    stock = None
    stock_t = fields.get("stock", "").strip().upper().lstrip("$")
    stock_call = fields.get("stock_call", "").strip()
    if stock_t and stock_call and stock_call != NO_CALL:
        if not re.fullmatch(r"[A-Z.\-]{1,10}", stock_t):
            errors.append(f"**Single stock** {stock_t!r} doesn't look like a ticker.")
        else:
            stock = {"ticker": stock_t, "call": stock_call}

    if not calls and not sectors and not stock:
        errors.append("You didn't make a call on any asset. Pick at least one.")

    reasoning = fields.get("reasoning", "").strip()
    if not reasoning:
        errors.append("**Reasoning** is empty. Write 2-3 lines on *why*.")

    conf_raw = fields.get("confidence", "")
    m = re.match(r"(\d)", conf_raw)
    confidence = int(m.group(1)) if m else None

    created = dt.datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
    on_time = None
    deadline_txt = ""
    if reaction:
        hh, mm = (release or "09:30").split(":")
        deadline = dt.datetime.combine(reaction, dt.time(int(hh), int(mm)), tzinfo=ET)
        on_time = created < deadline
        deadline_txt = deadline.isoformat()

    event_type = fields.get("event_type", "Other")
    if event_type not in EVENT_TYPES:
        event_type = "Other"

    meta = {
        "event": event,
        "event_type": event_type,
        "reaction_date": reaction.isoformat() if reaction else None,
        "release_time_et": release or None,
        "consensus": fields.get("consensus") or None,
        "data_view": fields.get("data_view") or None,
        "confidence": confidence,
        "calls": calls,
        "sectors": sectors,
        "stock": stock,
        "logged_at": created.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "deadline_et": deadline_txt or None,
        "on_time": on_time,
        "issue": issue["number"],
        "issue_url": issue["url"],
        "status": "pending",
    }

    body = f"\n## Reasoning\n\n{reasoning}\n"
    if fields.get("scenarios"):
        body += f"\n## If it goes the other way\n\n{fields['scenarios']}\n"
    if fields.get("source"):
        body += f"\n## Source\n\n{fields['source']}\n"
    body += ("\n## Review notes\n\n_Fill this in after grading: what did the market do, "
             "and what did you miss?_\n")
    return meta, body, errors


def main() -> None:
    issue = {
        "number": int(os.environ["ISSUE_NUMBER"]),
        "created_at": os.environ["ISSUE_CREATED_AT"],
        "url": os.environ["ISSUE_URL"],
    }
    existing = list(CALLS_DIR.glob(f"*-issue{issue['number']}.md"))
    if existing:
        print(json.dumps({"status": "exists", "path": str(existing[0].relative_to(CALLS_DIR.parent))}))
        return

    fields = parse_issue_body(os.environ.get("ISSUE_BODY", ""))
    meta, body, errors = build_call(fields, issue)
    if errors:
        print(json.dumps({"status": "invalid", "errors": errors}))
        return

    name = f"{meta['reaction_date']}-{slugify(meta['event'])}-issue{issue['number']}.md"
    path = CALLS_DIR / name
    write_call(path, meta, body)
    print(json.dumps({"status": "logged", "path": f"calls/{name}",
                      "on_time": meta["on_time"], "deadline_et": meta["deadline_et"]}))


if __name__ == "__main__":
    main()
