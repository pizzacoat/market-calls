"""Market data: daily closes from Yahoo Finance; Treasury yields from FRED,
falling back to Yahoo's yield tickers when FRED can't be reached (FRED often
times out from GitHub's servers)."""
from __future__ import annotations

import datetime as dt
import io
import sys
import urllib.request

import pandas as pd

# Yahoo equivalents of the FRED yield series, quoted in percent.
YAHOO_YIELDS = {"DGS10": "^TNX", "DGS2": "2YY=F", "DGS5": "^FVX", "DGS30": "^TYX"}


class MarketData:
    """Fetches daily closing levels. Results are cached per run."""

    def __init__(self):
        self._cache: dict[tuple[str, str], pd.Series] = {}
        self._fred_down = False

    def series(self, source: str, ticker: str, start: dt.date, end: dt.date) -> pd.Series:
        key = (source, ticker)
        s = self._cache.get(key)
        if s is not None and s.empty:
            return s  # already tried; don't hammer the source again
        if s is None or s.index.min().date() > start or s.index.max().date() < end:
            try:
                s = self._fetch(source, ticker, start, end)
            except Exception as e:
                print(f"warning: no data for {ticker}: {e}", file=sys.stderr)
                s = pd.Series(dtype=float)
            self._cache[key] = s
        return s

    def _fetch(self, source: str, ticker: str, start: dt.date, end: dt.date) -> pd.Series:
        if source == "fred":
            if not self._fred_down:
                try:
                    s = _fred(ticker, start, end)
                    if not s.empty and s.index.max().date() >= min(end, dt.date.today() - dt.timedelta(days=3)):
                        return s
                except Exception as e:
                    print(f"warning: FRED unavailable ({e}); using Yahoo yields", file=sys.stderr)
                    self._fred_down = True
            alt = YAHOO_YIELDS.get(ticker)
            if not alt:
                return pd.Series(dtype=float)
            s = _yahoo(alt, start, end)
            if not s.empty and s.median() > 20:  # some feeds quote yield x10
                s = s / 10
            return s
        return _yahoo(ticker, start, end)


def _yahoo(ticker: str, start: dt.date, end: dt.date) -> pd.Series:
    import yfinance as yf

    df = yf.download(ticker, start=start.isoformat(),
                     end=(end + dt.timedelta(days=1)).isoformat(),
                     auto_adjust=False, progress=False, threads=False, timeout=30)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):  # newer yfinance returns one column per ticker
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close.dropna().astype(float)


def _fred(series_id: str, start: dt.date, end: dt.date) -> pd.Series:
    url = ("https://fred.stlouisfed.org/graph/fredgraph.csv"
           f"?id={series_id}&cosd={start.isoformat()}&coed={end.isoformat()}")
    req = urllib.request.Request(url, headers={"User-Agent": "market-calls-journal"})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read().decode()
    df = pd.read_csv(io.StringIO(raw))
    date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
    s = pd.to_numeric(df[series_id], errors="coerce")
    s.index = pd.to_datetime(df[date_col]).dt.normalize()
    return s.dropna().astype(float)


def day_move(s: pd.Series, day: dt.date, unit: str):
    """Move on `day` vs the previous available close.

    Returns (move, status): status is 'ok', 'pending' (no data yet) or
    'closed' (later data exists but nothing for that day, e.g. a holiday).
    """
    if s.empty:
        return None, "pending"
    ts = pd.Timestamp(day)
    if ts not in s.index:
        return None, ("closed" if s.index.max() > ts else "pending")
    prev = s[s.index < ts]
    if prev.empty:
        return None, "pending"
    today, before = float(s[ts]), float(prev.iloc[-1])
    if unit == "bp":
        return round((today - before) * 100, 1), "ok"
    return round((today / before - 1) * 100, 2), "ok"
