from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"


def _normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "").replace("_", "")


def _guess_column(columns: list[str], candidates: list[str]) -> str | None:
    norm_to_original = {_normalize(c): c for c in columns}
    for cand in candidates:
        key = _normalize(cand)
        for norm, original in norm_to_original.items():
            if norm == key:
                return original
    # fallback: try substring matching
    for cand in candidates:
        key = _normalize(cand)
        for norm, original in norm_to_original.items():
            if key in norm:
                return original
    return None


def load_sales_with_signals() -> pd.DataFrame:
    sales_path = UPLOAD_DIR / "sales.csv"
    if not sales_path.exists():
        sales_path = DATA_DIR / "sample_sales.csv"

    signals_path = UPLOAD_DIR / "external_signals.csv"
    if not signals_path.exists():
        signals_path = DATA_DIR / "sample_external_signals.csv"

    sales = pd.read_csv(sales_path)

    # Heuristic mapping so slightly different schemas (e.g. Product/Region/Date/Quantity)
    # can still be used for forecasting.
    cols = list(sales.columns)
    date_col = _guess_column(cols, ["date", "order_date", "orderdate"])
    sku_col = _guess_column(cols, ["sku", "product", "item", "product_id", "productid"])
    location_col = _guess_column(cols, ["location", "region", "store", "warehouse", "country"])
    qty_col = _guess_column(cols, ["quantity", "qty", "units", "orderquantity", "order_qty"])

    if date_col is None or qty_col is None:
        raise ValueError("Sales dataset is missing a usable date or quantity column.")

    sales[date_col] = pd.to_datetime(sales[date_col])
    sales = sales.rename(columns={date_col: "date"})

    rename_map: dict[str, str] = {}
    if sku_col is not None and sku_col != "sku":
        rename_map[sku_col] = "sku"
    if location_col is not None and location_col != "location":
        rename_map[location_col] = "location"
    if qty_col is not None and qty_col != "quantity":
        rename_map[qty_col] = "quantity"

    if rename_map:
        sales = sales.rename(columns=rename_map)

    # If sku/location still missing, fall back to single pseudo group so forecasting still works.
    if "sku" not in sales.columns:
        sales["sku"] = "ALL-SKU"
    if "location" not in sales.columns:
        sales["location"] = "ALL-LOC"

    signals = pd.read_csv(signals_path, parse_dates=["date"])

    # Use LEFT merge to keep all sales rows, filling missing signal values with NaN
    merged = sales.merge(
        signals,
        on=["date", "location"],
        how="left",
    )
    
    # Fill NaN values in signal columns with reasonable defaults
    signal_cols = ["is_holiday", "temperature", "google_trends_index", "promotion", "price"]
    for col in signal_cols:
        if col in merged.columns:
            if col == "is_holiday":
                merged[col] = merged[col].fillna(0)
            elif col in ["temperature", "google_trends_index", "promotion", "price"]:
                merged[col] = merged[col].fillna(merged[col].mean())

    return merged
