from pathlib import Path
from typing import Optional

import pandas as pd


def load_csv_or_excel(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(p)
    return pd.read_csv(p)


def save_csv(df: pd.DataFrame, path: str | Path, index: bool = False) -> None:
    df.to_csv(Path(path), index=index)


def save_excel(df: pd.DataFrame, path: str | Path, index: bool = False) -> None:
    df.to_excel(Path(path), index=index)
