"""Grade every pending call whose reaction day has closed.

For each asset the actual move (previous close -> reaction-day close) is
turned into a size level and compared with the call. Writes results back into
each call file and prints a JSON list of newly graded calls for the workflow.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from journal.core import (all_calls, label_to_level, level_to_words, load_assets,  # noqa: E402
                          move_to_level, now_et, parse_date, score_call, write_call)
from journal.data import MarketData, day_move  # noqa: E402

GIVE_UP_AFTER_DAYS = 10  # stop waiting for data after this long


def ready_to_grade(day: dt.date, now: dt.datetime) -> bool:
    today = now.date()
    if day < today:
        return True
    return day == today and now.time() >= dt.time(16, 30)


def grade_one(meta: dict, md: MarketData, assets: dict) -> tuple[str, dict]:
    day = parse_date(meta["reaction_date"])
    start, end = day - dt.timedelta(days=14), day + dt.timedelta(days=5)
    results: dict[str, dict] = {}
    waiting = False

    def record(key, label, pred_label, move, unit, thresholds, relative=False):
        pred = label_to_level(pred_label)
        actual = move_to_level(move, thresholds)
        results[key] = {
            "label": label,
            "call": pred_label,
            "actual": level_to_words(actual, relative),
            "move": move,
            "unit": "bp" if unit == "bp" else ("pp vs S&P" if relative else "%"),
            "score": score_call(pred, actual),
            "direction_right": (pred > 0) - (pred < 0) == (actual > 0) - (actual < 0),
        }

    for key, pred_label in (meta.get("calls") or {}).items():
        a = assets["core"][key]
        move, status = day_move(md.series(a["source"], a["ticker"], start, end), day, a["unit"])
        if status == "closed":
            return "market-closed", {}
        if status == "pending":
            waiting = True
            continue
        record(key, a["label"], pred_label, move, a["unit"], a["thresholds"])

    sec_cfg = assets["sectors"]
    for sec in meta.get("sectors") or []:
        t = sec["ticker"]
        m_sec, st1 = day_move(md.series("yahoo", t, start, end), day, "pct")
        m_bench, st2 = day_move(md.series("yahoo", sec_cfg["benchmark"], start, end), day, "pct")
        if "closed" in (st1, st2):
            return "market-closed", {}
        if "pending" in (st1, st2):
            waiting = True
            continue
        label = f"{sec_cfg['tickers'][t]} ({t})"
        record(f"sector_{t}", label, sec["call"], round(m_sec - m_bench, 2), "pct",
               sec_cfg["thresholds"], relative=True)

    stock = meta.get("stock")
    if stock:
        t = stock["ticker"]
        move, status = day_move(md.series("yahoo", t, start, end), day, "pct")
        if status == "closed":
            return "market-closed", {}
        if status == "pending":
            waiting = True
        else:
            record(f"stock_{t}", t, stock["call"], move, "pct", assets["stock"]["thresholds"])

    if waiting:
        return "pending", results
    return "graded", results


def main() -> None:
    assets = load_assets()
    md = MarketData()
    now = now_et()
    newly = []

    for path, meta, body in all_calls():
        if meta.get("status") != "pending" or not meta.get("reaction_date"):
            continue
        day = parse_date(meta["reaction_date"])
        if not ready_to_grade(day, now):
            continue
        try:
            status, results = grade_one(meta, md, assets)
        except Exception as e:  # network hiccup etc. -> try again next run
            print(f"warning: could not grade {path.name}: {e}", file=sys.stderr)
            continue

        if status == "pending" and (now.date() - day).days > GIVE_UP_AFTER_DAYS:
            status = "graded" if results else "no-data"
        if status == "pending":
            continue

        meta["status"] = status
        meta["results"] = results
        if results:
            meta["score"] = round(100 * sum(r["score"] for r in results.values()) / len(results))
        meta["graded_at"] = now.isoformat(timespec="minutes")
        write_call(path, meta, body)
        newly.append({"file": f"calls/{path.name}", "issue": meta.get("issue"),
                      "event": meta.get("event"), "status": status,
                      "score": meta.get("score"), "results": results,
                      "on_time": meta.get("on_time")})

    print(json.dumps(newly))


if __name__ == "__main__":
    main()
