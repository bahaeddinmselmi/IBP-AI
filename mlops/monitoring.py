import pandas as pd

from backend.app.feature_store.registry import load_sales_with_signals


def compute_simple_mape() -> float:
    df = load_sales_with_signals()
    daily = df.groupby("date")["quantity"].sum().sort_index()
    baseline = daily.mean()
    mape = (daily.sub(baseline).abs() / daily.clip(lower=1)).mean()
    return float(mape)


def main() -> None:
    mape = compute_simple_mape()
    print({"metric": "naive_mape", "value": mape})


if __name__ == "__main__":
    main()
