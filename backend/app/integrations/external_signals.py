from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"


def load_external_signals() -> pd.DataFrame:
    sample_path = DATA_DIR / "sample_external_signals.csv"
    upload_path = UPLOAD_DIR / "external_signals.csv"

    if upload_path.exists():
        path = upload_path
    else:
        path = sample_path

    if not path.exists():
        raise FileNotFoundError(f"External signals file not found at {path}")

    df = pd.read_csv(path, parse_dates=["date"])
    return df


def summarize_signals(location: Optional[str] = None, days: int = 14) -> str:
    try:
        df = load_external_signals()
    except FileNotFoundError:
        return ""

    if location is not None and "location" in df.columns:
        df = df[df["location"] == location]

    if df.empty or "date" not in df.columns:
        return ""

    df = df.sort_values("date")
    recent = df[df["date"] >= df["date"].max() - pd.Timedelta(days=days)]
    if recent.empty:
        recent = df

    parts: list[str] = []

    if "google_trends_index" in recent.columns:
        start_val = float(recent["google_trends_index"].iloc[0])
        end_val = float(recent["google_trends_index"].iloc[-1])
        if start_val > 0:
            change_pct = (end_val - start_val) / start_val * 100.0
        else:
            change_pct = 0.0
        parts.append(
            f"Google search interest moved from {start_val:.0f} to {end_val:.0f} "
            f"over the last {days} days ({change_pct:+.1f}% change)."
        )

    if "temperature" in recent.columns:
        temp_min = float(recent["temperature"].min())
        temp_max = float(recent["temperature"].max())
        parts.append(
            f"Observed temperature range in the same window: {temp_min:.1f}–{temp_max:.1f}°C."
        )

    if "is_holiday" in recent.columns and recent["is_holiday"].sum() > 0:
        parts.append("Recent days include holidays, which may drive demand peaks.")

    return " ".join(parts)
