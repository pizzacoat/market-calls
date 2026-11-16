import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import grade  # noqa: E402
import issue_to_call  # noqa: E402
import scorecard  # noqa: E402
import week_ahead  # noqa: E402
from journal import core  # noqa: E402
from journal.data import day_move  # noqa: E402


# ---------- buckets and scoring ----------

def test_label_levels():
    assert core.label_to_level("Down - medium") == -2
    assert core.label_to_level("Outperform - large") == 3
    assert core.label_to_level("Flat") == 0
    assert core.label_to_level("No call") is None
    with pytest.raises(ValueError):
        core.label_to_level("Sideways")


def test_move_to_level():
    th = [0.2, 0.6, 1.2]
    assert core.move_to_level(0.1, th) == 0
    assert core.move_to_level(-0.25, th) == -1
    assert core.move_to_level(0.6, th) == 2
    assert core.move_to_level(-2.0, th) == -3


def test_scores():
    assert core.score_call(2, 2) == 1.0
    assert core.score_call(1, 3) == 0.5      # right direction, wrong size
    assert core.score_call(1, 0) == 0.5      # "up small" vs flat: one step off
    assert core.score_call(-1, 2) == 0.0


def test_day_move():
    s = pd.Series([100.0, 101.0, 99.99],
                  index=pd.to_datetime(["2026-12-08", "2026-12-09", "2026-12-11"]))
    assert day_move(s, dt.date(2026, 12, 9), "pct") == (1.0, "ok")
    assert day_move(s, dt.date(2026, 12, 10), "pct") == (None, "closed")
    assert day_move(s, dt.date(2026, 12, 14), "pct") == (None, "pending")
    y = pd.Series([4.10, 4.17], index=pd.to_datetime(["2026-12-09", "2026-12-10"]))
    assert day_move(y, dt.date(2026, 12, 10), "bp") == (7.0, "ok")


# ---------- issue form -> call file ----------

ISSUE_BODY = """### Event

November CPI

### Event type

CPI

### Reaction date

2026-12-10

### Release time (ET)

08:30

### Consensus expectation

Core +0.3% m/m

### Your view on the data

Hotter / stronger than consensus

### S&P 500

Down - medium

### 2-year yield

Up - large

### 10-year yield

Up - medium

### US dollar (DXY)

Up - small

### Gold

No call

### Oil

No call

### Sector 1

XLRE - Real estate

### Sector 1 vs the S&P 500

Underperform - medium

### Sector 2

None

### Sector 2 vs the S&P 500

No call

### Single stock (ticker)

_No response_

### Single stock call

No call

### Confidence

3 - fairly confident

### Reasoning

Shelter still sticky; a hot core print pushes out cuts.

### If it goes the other way

_No response_

### Source link

https://www.wsj.com/example
"""


def make_issue(created="2026-12-10T03:00:00Z", n=7):
    return {"number": n, "created_at": created, "url": f"https://github.com/x/y/issues/{n}"}


def test_issue_parsing_and_build():
    fields = issue_to_call.parse_issue_body(ISSUE_BODY)
    assert fields["event"] == "November CPI"
    assert fields["stock"] == ""
    meta, body, errors = issue_to_call.build_call(fields, make_issue())
    assert errors == []
    assert meta["calls"] == {"spx": "Down - medium", "us2y": "Up - large",
                             "us10y": "Up - medium", "dollar": "Up - small"}
    assert meta["sectors"] == [{"ticker": "XLRE", "call": "Underperform - medium"}]
    assert meta["stock"] is None and meta["confidence"] == 3
    assert meta["on_time"] is True          # 03:00Z = 22:00 ET the night before
    assert "## Reasoning" in body and "## Source" in body


def test_late_call_flagged():
    fields = issue_to_call.parse_issue_body(ISSUE_BODY)
    meta, _, _ = issue_to_call.build_call(fields, make_issue("2026-12-10T14:00:00Z"))
    assert meta["on_time"] is False         # 09:00 ET, after the 08:30 release


def test_invalid_issue():
    bad = ISSUE_BODY.replace("2026-12-10", "next thursday").replace(
        "Shelter still sticky; a hot core print pushes out cuts.", "_No response_")
    _, _, errors = issue_to_call.build_call(issue_to_call.parse_issue_body(bad), make_issue())
    assert any("Reaction date" in e for e in errors)
    assert any("Reasoning" in e for e in errors)


# ---------- grading end to end with fake data ----------

class FakeData:
    """SPY -0.8%, XLRE -2.0% (=-1.2pp vs SPY), 2Y +12bp, 10Y +4bp, DXY +0.5%."""
    levels = {
        "SPY": (500.0, 496.0), "XLRE": (40.0, 39.2), "DX-Y.NYB": (100.0, 100.5),
        "DGS2": (4.00, 4.12), "DGS10": (4.20, 4.24),
    }

    def series(self, source, ticker, start, end):
        before, on = self.levels[ticker]
        return pd.Series([before, on], index=pd.to_datetime(["2026-12-09", "2026-12-10"]))


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    calls = tmp_path / "calls"
    results = tmp_path / "results"
    calls.mkdir(), results.mkdir()
    import shutil
    shutil.copytree(core.ROOT / "config", tmp_path / "config")
    (tmp_path / "README.md").write_text(
        f"# x\n{scorecard.START}\nold\n{scorecard.END}\nfooter\n", encoding="utf-8")
    for mod in (core, grade, scorecard):
        monkeypatch.setattr(mod, "CALLS_DIR", calls, raising=False)
        monkeypatch.setattr(mod, "RESULTS_DIR", results, raising=False)
        monkeypatch.setattr(mod, "ROOT", tmp_path, raising=False)
    monkeypatch.setattr(issue_to_call, "CALLS_DIR", calls)
    monkeypatch.setattr(grade, "MarketData", FakeData)
    monkeypatch.setattr(grade, "now_et",
                        lambda: dt.datetime(2026, 12, 10, 17, 0, tzinfo=core.ET))
    return tmp_path


def test_end_to_end(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("ISSUE_NUMBER", "7")
    monkeypatch.setenv("ISSUE_CREATED_AT", "2026-12-10T03:00:00Z")
    monkeypatch.setenv("ISSUE_URL", "https://github.com/x/y/issues/7")
    monkeypatch.setenv("ISSUE_BODY", ISSUE_BODY)
    issue_to_call.main()
    logged = json.loads(capsys.readouterr().out)
    assert logged["status"] == "logged"

    issue_to_call.main()                         # second run is a no-op
    assert json.loads(capsys.readouterr().out)["status"] == "exists"

    grade.main()
    graded = json.loads(capsys.readouterr().out)
    assert len(graded) == 1
    res = graded[0]["results"]
    assert res["spx"]["actual"] == "Down - medium" and res["spx"]["score"] == 1.0
    assert res["us2y"]["move"] == 12.0 and res["us2y"]["score"] == 1.0
    assert res["us10y"]["actual"] == "Up - small" and res["us10y"]["score"] == 0.5
    assert res["dollar"]["actual"] == "Up - medium" and res["dollar"]["score"] == 0.5
    assert res["sector_XLRE"]["move"] == -1.2 and res["sector_XLRE"]["actual"] == "Underperform - large"
    assert graded[0]["score"] == 70              # (1 + 1 + .5 + .5 + .5) / 5

    grade.main()                                 # already graded -> nothing new
    assert json.loads(capsys.readouterr().out) == []

    scorecard.main()
    capsys.readouterr()
    readme = (sandbox / "README.md").read_text()
    assert "1 graded calls" in readme and "footer" in readme and "old" not in readme
    assert (sandbox / "results" / "scorecard.png").exists()
    assert len(pd.read_csv(sandbox / "results" / "scorecard.csv")) == 5


def test_week_ahead_lists_cpi_week():
    text = week_ahead.build(dt.date(2026, 12, 6), with_earnings=False)
    assert "Dec 7 – Dec 11" in text
    assert "CPI inflation, November" in text and "Fed rate decision" in text


def test_issue_form_matches_parser():
    import build_issue_form
    form = build_issue_form.build()
    labels = {item["attributes"]["label"] for item in form["body"] if item["type"] != "markdown"}
    assert labels == set(issue_to_call.FIELD_KEYS)
