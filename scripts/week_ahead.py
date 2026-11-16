"""Write WEEK_AHEAD.md: next week's scheduled macro releases + watchlist earnings."""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from journal.core import ROOT, load_yaml, now_et, parse_date  # noqa: E402

DAY_FMT = "%a %b %-d"


def week_bounds(today: dt.date) -> tuple[dt.date, dt.date]:
    """Monday–Friday of the coming week (or this week if run Mon–Thu)."""
    monday = today - dt.timedelta(days=today.weekday())
    if today.weekday() >= 4:  # Fri/Sat/Sun -> next week
        monday += dt.timedelta(days=7)
    return monday, monday + dt.timedelta(days=4)


def macro_events(start: dt.date, end: dt.date) -> tuple[list[dict], dt.date]:
    events = load_yaml(ROOT / "data" / "calendar.yaml").get("events", [])
    last = max(parse_date(e["date"]) for e in events)
    week = [e for e in events if start <= parse_date(e["date"]) <= end]
    return sorted(week, key=lambda e: (str(e["date"]), e["time"])), last


def earnings(start: dt.date, end: dt.date) -> tuple[list[dict], list[str]]:
    tickers = load_yaml(ROOT / "data" / "watchlist.yaml").get("tickers", [])
    found, failed = [], []
    try:
        import yfinance as yf
    except ImportError:
        return [], tickers
    for t in tickers:
        try:
            df = yf.Ticker(t).get_earnings_dates(limit=8)
            if df is None or df.empty:
                continue
            for ts in df.index:
                d = ts.tz_convert("America/New_York") if ts.tzinfo else ts
                if start <= d.date() <= end:
                    timing = "before the open" if d.hour < 12 else "after the close"
                    found.append({"ticker": t, "date": d.date(), "timing": timing})
                    break
        except Exception:
            failed.append(t)
    return sorted(found, key=lambda x: (x["date"], x["ticker"])), failed


def build(today: dt.date | None = None, with_earnings: bool = True) -> str:
    today = today or now_et().date()
    start, end = week_bounds(today)
    repo = os.environ.get("GITHUB_REPOSITORY", "pizzacoat/market-calls")
    form = f"https://github.com/{repo}/issues/new?template=new-call.yml"

    events, last = macro_events(start, end)
    lines = [f"# Week ahead: {start:%b %-d} – {end:%b %-d, %Y}", "",
             f"Pick 1–2 events, make your call **before** the release, and log it here: "
             f"[**New call**]({form})", "", "## Scheduled data and Fed events (Eastern time)", ""]
    if events:
        lines += ["| Day | Time (ET) | Event | Type |", "|---|---|---|---|"]
        for e in events:
            d = parse_date(e["date"])
            lines.append(f"| {d:{DAY_FMT}} | {e['time']} | {e['event']} | {e['type']} |")
    else:
        lines.append("_No major scheduled US releases this week. A good week for an earnings call._")

    if with_earnings:
        found, failed = earnings(start, end)
        lines += ["", "## Earnings on your watchlist", ""]
        if found:
            lines += ["| Day | Company | Timing | Market reacts |", "|---|---|---|---|"]
            for f in found:
                reacts = "same day" if f["timing"] == "before the open" else "next trading day"
                lines.append(f"| {f['date']:{DAY_FMT}} | {f['ticker']} | {f['timing']} | {reacts} |")
        else:
            lines.append("_None of your watchlist companies report this week._")
        if failed:
            lines += ["", f"_Couldn't check: {', '.join(failed)}._"]

    if (last - today).days < 28:
        lines += ["", f"⚠️ The event calendar runs out on {last}. Add the next months to "
                      "`data/calendar.yaml` from the BLS, BEA and Fed calendars."]
    lines += ["", "**Reminder:** the reaction date is the trading day the market reacts. For data "
                  "released before 9:30 ET it's the same day; for earnings after the close it's "
                  "the next trading day."]
    return "\n".join(lines) + "\n"


def main() -> None:
    text = build()
    (ROOT / "WEEK_AHEAD.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
