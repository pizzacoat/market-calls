"""Shared helpers: config, call files, size buckets and scoring."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[2]
CALLS_DIR = ROOT / "calls"
RESULTS_DIR = ROOT / "results"
ET = ZoneInfo("America/New_York")

SIZES = ["flat", "small", "medium", "large"]
NO_CALL = "No call"

# Dropdown labels used in the issue form. Order matters (shown top to bottom).
MOVE_OPTIONS = ["Up - large", "Up - medium", "Up - small", "Flat",
                "Down - small", "Down - medium", "Down - large"]
REL_OPTIONS = ["Outperform - large", "Outperform - medium", "Outperform - small",
               "In line", "Underperform - small", "Underperform - medium",
               "Underperform - large"]
EVENT_TYPES = ["CPI", "Jobs", "FOMC", "PCE", "GDP", "PPI", "JOLTS",
               "Fed speaker", "Earnings", "Geopolitics / news", "Other"]


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_assets() -> dict:
    return load_yaml(ROOT / "config" / "assets.yaml")


# ---------- size buckets ----------

def label_to_level(label: str | None) -> int | None:
    """'Down - medium' -> -2, 'Flat'/'In line' -> 0, 'No call'/blank -> None."""
    if not label:
        return None
    label = label.strip()
    if label in (NO_CALL, "", "_No response_"):
        return None
    if label in ("Flat", "In line"):
        return 0
    m = re.match(r"(Up|Down|Outperform|Underperform)\s*-\s*(small|medium|large)$", label, re.I)
    if not m:
        raise ValueError(f"Unrecognised call: {label!r}")
    sign = 1 if m.group(1).lower() in ("up", "outperform") else -1
    return sign * SIZES.index(m.group(2).lower())


def move_to_level(move: float, thresholds: list[float]) -> int:
    """Turn an actual move into a signed size level using [small, medium, large] cut-offs."""
    a = abs(move)
    size = 0
    for i, t in enumerate(thresholds, start=1):
        if a >= t:
            size = i
    return 0 if size == 0 else (size if move > 0 else -size)


def level_to_words(level: int, relative: bool = False) -> str:
    if level == 0:
        return "In line" if relative else "Flat"
    up, down = ("Outperform", "Underperform") if relative else ("Up", "Down")
    return f"{up if level > 0 else down} - {SIZES[abs(level)]}"


def sign(x: int) -> int:
    return (x > 0) - (x < 0)


def score_call(pred: int, actual: int) -> float:
    """1.0 = right direction and size; 0.5 = right direction or one step away; 0 = wrong."""
    if pred == actual:
        return 1.0
    if sign(pred) == sign(actual) or abs(pred - actual) == 1:
        return 0.5
    return 0.0


# ---------- call files ----------

FRONT = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def read_call(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = FRONT.match(text)
    if not m:
        raise ValueError(f"{path} has no front matter")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def write_call(path: Path, meta: dict, body: str) -> None:
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000)
    path.write_text(f"---\n{front}---\n{body}", encoding="utf-8")


def all_calls() -> list[tuple[Path, dict, str]]:
    out = []
    for p in sorted(CALLS_DIR.glob("*.md")):
        meta, body = read_call(p)
        out.append((p, meta, body))
    return out


def parse_date(value) -> dt.date:
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value).strip())


def now_et() -> dt.datetime:
    return dt.datetime.now(tz=ET)
