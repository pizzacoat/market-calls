# Market Calls

A public, timestamped journal of my predictions for how markets react to macro data, Fed decisions and earnings, graded automatically against what actually happened.

**The rule:** every call is logged *before* the release, and never edited afterwards. Losses stay in the record.

## How it works

1. **Sunday:** a [Week ahead](WEEK_AHEAD.md) issue lists the coming week's scheduled releases (CPI, jobs, Fed, PCE, GDP…) and watchlist earnings.
2. **Before the event:** I open a **New call** issue (Issues → New issue → New call). I predict the direction and size of the move in the S&P 500, 2- and 10-year Treasury yields, the dollar, gold, oil, up to two sectors (graded against the S&P 500), and optionally one stock, with my confidence and reasoning. The issue's timestamp proves the call came first.
3. **Logged automatically:** a GitHub Action turns the issue into a file in [`calls/`](calls/) and flags it as late if it was opened after the release time.
4. **Graded automatically:** after the close, an Action pulls the actual moves (Yahoo Finance prices, FRED Treasury yields), scores the call, posts the results on the issue and updates the scorecard below.
5. **Review:** I write what I missed in the call's *Review notes*. On the 1st of each month an issue drafts a review of the month.

## Scoring

Moves are measured from the previous trading day's close to the close on the reaction date.

| Asset | Measured with | Small | Medium | Large |
|---|---|---|---|---|
| S&P 500 | SPY | ≥0.20% | ≥0.60% | ≥1.20% |
| 2-year / 10-year yield | FRED DGS2 / DGS10 | ≥2 bp | ≥5 bp | ≥10 bp |
| US dollar | DXY index | ≥0.15% | ≥0.40% | ≥0.80% |
| Gold | GLD | ≥0.30% | ≥0.80% | ≥1.50% |
| Oil | USO | ≥0.50% | ≥1.50% | ≥3.00% |
| Sector (vs S&P 500) | sector ETF minus SPY | ≥0.20 pp | ≥0.60 pp | ≥1.20 pp |
| Single stock | the stock | ≥1% | ≥3% | ≥7% |

Anything smaller than "small" counts as **flat** (or **in line** for sectors).

Each prediction scores **1** if the direction and size are both right, **0.5** if the direction is right or it's one step off, and **0** otherwise. A call's score is the average across its assets, out of 100.

## Scorecard

<!-- SCORECARD:START -->
_No graded calls yet._
<!-- SCORECARD:END -->

## Repo layout

| Path | What's there |
|---|---|
| `calls/` | One file per call: predictions, reasoning, results, review notes |
| `results/` | `scorecard.csv` (every graded prediction) and the chart |
| `data/calendar.yaml` | Scheduled US releases (from BLS, BEA and Fed calendars) |
| `data/watchlist.yaml` | Companies whose earnings appear in the week ahead |
| `config/assets.yaml` | Tickers and size thresholds used for grading |
| `scripts/` | Logging, grading, scorecard, week-ahead and monthly review |

## Running it locally

```bash
pip install -r requirements.txt
python scripts/grade.py        # grade pending calls
python scripts/scorecard.py    # rebuild the scorecard
python scripts/week_ahead.py   # print next week's calendar
pytest                         # run the tests
```

If you add sectors to `config/assets.yaml`, run `python scripts/build_issue_form.py` to update the form.

*Market data from Yahoo Finance (via yfinance) and FRED. News context from my own reading; articles are linked, never copied. Not investment advice.*
