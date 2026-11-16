"""Draft the monthly review for the month that just ended (posted as an issue)."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from journal.core import now_et  # noqa: E402
from scorecard import rows  # noqa: E402


def build(today: dt.date | None = None) -> str:
    today = today or now_et().date()
    last_month_end = today.replace(day=1) - dt.timedelta(days=1)
    start = last_month_end.replace(day=1)
    title = f"{start:%B %Y}"

    df = rows()
    if not df.empty:
        df = df[(df["date"] >= start.isoformat()) & (df["date"] <= last_month_end.isoformat())]
        df = df[df["on_time"] != False]  # noqa: E712
    lines = [f"# Monthly review: {title}", ""]
    if df.empty:
        lines.append("_No graded calls this month._")
        return "\n".join(lines) + "\n"

    calls = (df.groupby("file").agg(event=("event", "first"), date=("date", "first"),
                                    score=("score", "mean")).sort_values("score"))
    lines += [f"- **Calls graded:** {len(calls)}",
              f"- **Direction right:** {100 * df['direction_right'].mean():.0f}%",
              f"- **Average call score:** {100 * calls['score'].mean():.0f}/100", "",
              "**Best calls**", ""]
    for f, r in calls.tail(3)[::-1].iterrows():
        lines.append(f"- [{r['event']}]({f}) ({r['date']}): {100 * r['score']:.0f}")
    lines += ["", "**Worst calls**", ""]
    for f, r in calls.head(3).iterrows():
        lines.append(f"- [{r['event']}]({f}) ({r['date']}): {100 * r['score']:.0f}")
    by = df.groupby("group")["direction_right"].mean().sort_values()
    lines += ["", f"**Weakest asset:** {by.index[0]} ({100 * by.iloc[0]:.0f}% direction right)",
              f"**Strongest asset:** {by.index[-1]} ({100 * by.iloc[-1]:.0f}% direction right)", "",
              "## Your write-up (fill in, then post the short version on LinkedIn)", "",
              "1. **Biggest lesson:** what pattern did the misses share? Wrong data guess, "
              "right data but wrong reaction (already priced in?), or noise?",
              "2. **One call I'd make differently, and why:**",
              "3. **What I'll focus on next month:**"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(build())
