"""Build practice/bank.json: real market moves for every event in practice/events.yaml.

Runs in GitHub Actions (which can reach Yahoo Finance and FRED). Each move is
measured from the previous trading day's close to the close on the event date.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from journal.core import ROOT, load_yaml, parse_date  # noqa: E402
from journal.data import MarketData, day_move  # noqa: E402

MARKETS = {
    "SPY": ("S&P 500 (SPY)", "yahoo", "pct"),
    "QQQ": ("Nasdaq 100", "yahoo", "pct"),
    "IWM": ("Small caps (Russell 2000)", "yahoo", "pct"),
    "DGS2": ("2-year Treasury yield", "fred", "bp"),
    "DGS10": ("10-year Treasury yield", "fred", "bp"),
    "DX-Y.NYB": ("US dollar (DXY)", "yahoo", "pct"),
    "GLD": ("Gold", "yahoo", "pct"),
    "USO": ("Oil", "yahoo", "pct"),
    "^VIX": ("VIX (fear gauge)", "yahoo", "pct"),
}
SECTORS = {
    "XLK": "Technology", "SMH": "Semiconductors", "XLF": "Financials",
    "KRE": "Regional banks", "XLE": "Energy", "XLV": "Health care",
    "XLY": "Consumer discretionary", "XLP": "Consumer staples",
    "XLI": "Industrials", "XLU": "Utilities", "XLRE": "Real estate",
    "XHB": "Homebuilders", "XLC": "Communication services",
    "IWM": "Small caps (Russell 2000)",
}


def main() -> None:
    events = load_yaml(ROOT / "practice" / "events.yaml")["events"]
    md = MarketData()
    out, problems = [], []

    # Fetch each series once for the whole span, so every event reads from cache.
    days = [parse_date(e["date"]) for e in events]
    span = (min(days) - dt.timedelta(days=14), max(days) + dt.timedelta(days=5))
    wanted = {t: (src, unit) for t, (_, src, unit) in MARKETS.items()}
    for e in events:
        for t in e.get("sectors", []) + ([e["stock"]] if e.get("stock") else []):
            wanted.setdefault(t, ("yahoo", "pct"))
    import time
    for t, (src, _) in wanted.items():
        t0 = time.time()
        try:
            n = len(md.series(src, t, *span))
        except Exception as ex:
            n = f"error {ex}"
            problems.append(f"prefetch {t}: {ex}")
        print(f"fetched {t:10s} {src:5s} rows={n} in {time.time() - t0:.1f}s", flush=True)

    for e in events:
        day = parse_date(e["date"])
        start, end = day - dt.timedelta(days=14), day + dt.timedelta(days=5)
        moves = {}
        tickers = dict(MARKETS)
        for t in e.get("sectors", []):
            tickers.setdefault(t, (SECTORS.get(t, t), "yahoo", "pct"))
        if e.get("stock"):
            tickers.setdefault(e["stock"], (e["stock"], "yahoo", "pct"))
        for t, (label, source, unit) in tickers.items():
            try:
                move, status = day_move(md.series(source, t, start, end), day, unit)
            except Exception as ex:  # keep going; report at the end
                move, status = None, f"error: {ex}"
            if status != "ok":
                problems.append(f"{e['id']} {t}: {status}")
                continue
            moves[t] = {"label": label, "move": move, "unit": unit}
        out.append({**{k: e[k] for k in e if k != "date"}, "date": day.isoformat(), "moves": moves})

    (ROOT / "practice").mkdir(exist_ok=True)
    payload = {"generated": dt.date.today().isoformat(), "events": out,
               "sector_names": SECTORS}
    (ROOT / "practice" / "bank.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"{len(out)} events written")
    if problems:
        print("Missing data:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    main()
