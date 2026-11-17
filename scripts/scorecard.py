"""Rebuild results/scorecard.csv, results/scorecard.png and the README scorecard."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd  # noqa: E402

from journal.core import RESULTS_DIR, ROOT, all_calls  # noqa: E402

START, END = "<!-- SCORECARD:START -->", "<!-- SCORECARD:END -->"


def rows() -> pd.DataFrame:
    out = []
    for path, meta, _ in all_calls():
        if meta.get("status") != "graded":
            continue
        for key, r in (meta.get("results") or {}).items():
            group = ("Sector vs S&P" if key.startswith("sector_")
                     else "Single stock" if key.startswith("stock_") else r["label"])
            out.append({
                "date": meta["reaction_date"], "event": meta["event"],
                "event_type": meta.get("event_type"), "confidence": meta.get("confidence"),
                "on_time": meta.get("on_time"), "asset": r["label"], "group": group,
                "call": r["call"], "actual": r["actual"], "move": r["move"], "unit": r["unit"],
                "score": r["score"], "direction_right": r["direction_right"],
                "file": f"calls/{path.name}",
            })
    return pd.DataFrame(out)


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def summary_md(df: pd.DataFrame) -> str:
    if df.empty:
        return ("_No graded calls yet. Log your first call from the "
                "**Issues → New issue → New call** form._")
    df = df[df["on_time"] != False]  # noqa: E712  late calls don't count
    if df.empty:
        return "_Only late calls so far. Calls logged after the release don't count._"
    calls = df.groupby("file").agg(score=("score", "mean"), date=("date", "first"),
                                   event=("event", "first"), conf=("confidence", "first"))
    lines = [
        f"**{len(calls)} graded calls · {len(df)} asset predictions**",
        "",
        "| Metric | Value |", "|---|---|",
        f"| Direction right | {pct(df['direction_right'].mean())} |",
        f"| Direction and size right | {pct((df['score'] == 1).mean())} |",
        f"| Average call score (0–100) | {100 * calls['score'].mean():.0f} |",
        "", "**By asset**", "", "| Asset | Calls | Direction right | Avg score |", "|---|---|---|---|",
    ]
    for g, d in df.groupby("group"):
        lines.append(f"| {g} | {len(d)} | {pct(d['direction_right'].mean())} | {100 * d['score'].mean():.0f} |")

    lines += ["", "**By event type**", "", "| Event | Calls | Avg score |", "|---|---|---|"]
    for g, d in calls.join(df.groupby("file")["event_type"].first()).groupby("event_type"):
        lines.append(f"| {g} | {len(d)} | {100 * d['score'].mean():.0f} |")

    lines += ["", "**Calibration** (are high-confidence calls actually better?)", "",
              "| Confidence | Calls | Avg score |", "|---|---|---|"]
    for c, d in calls.groupby("conf"):
        lines.append(f"| {int(c)} | {len(d)} | {100 * d['score'].mean():.0f} |")

    lines += ["", "**Last 10 calls**", "", "| Date | Event | Score |", "|---|---|---|"]
    for f, r in calls.sort_values("date", ascending=False).head(10).iterrows():
        lines.append(f"| {r['date']} | [{r['event']}]({f}) | {100 * r['score']:.0f} |")
    lines += ["", "![Scorecard chart](results/scorecard.png)"]
    return "\n".join(lines)


def chart(df: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if df.empty:
        return
    df = df[df["on_time"] != False]  # noqa: E712
    if df.empty:
        return
    calls = (df.groupby("file").agg(date=("date", "first"), score=("score", "mean"),
                                    dir=("direction_right", "mean"))
             .sort_values("date").reset_index(drop=True))
    calls["avg_score"] = calls["score"].expanding().mean() * 100
    calls["avg_dir"] = calls["dir"].expanding().mean() * 100

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [3, 2]})
    x = range(1, len(calls) + 1)
    a1.plot(x, calls["avg_dir"], color="#185FA5", lw=2, label="Direction right (running)")
    a1.plot(x, calls["avg_score"], color="#1D9E75", lw=2, label="Avg call score (running)")
    a1.axhline(50, color="#888780", lw=0.8, ls="--")
    a1.set_ylim(0, 100), a1.set_xlabel("Call number"), a1.set_ylabel("%")
    a1.set_title("Track record over time", loc="left", fontsize=11)
    a1.legend(frameon=False, fontsize=9)

    by = df.groupby("group")["direction_right"].mean().sort_values() * 100
    a2.barh(by.index, by.values, color="#7F77DD")
    a2.axvline(50, color="#888780", lw=0.8, ls="--")
    a2.set_xlim(0, 100), a2.set_xlabel("Direction right (%)")
    a2.set_title("By asset", loc="left", fontsize=11)
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "scorecard.png", dpi=150)
    plt.close(fig)


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    df = rows()
    df.to_csv(RESULTS_DIR / "scorecard.csv", index=False)
    chart(df)
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if START in text and END in text:
        head, rest = text.split(START, 1)
        _, tail = rest.split(END, 1)
        readme.write_text(f"{head}{START}\n{summary_md(df)}\n{END}{tail}", encoding="utf-8")
    print(f"scorecard: {df['file'].nunique() if not df.empty else 0} graded calls")


if __name__ == "__main__":
    main()
