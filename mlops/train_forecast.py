from pathlib import Path

import mlflow
import pandas as pd

from backend.app.feature_store.registry import load_sales_with_signals


def train_naive_mean_model() -> None:
    df = load_sales_with_signals()

    daily = df.groupby("date")["quantity"].sum().sort_index()

    baseline = daily.mean()

    mape = (daily.sub(baseline).abs() / daily.clip(lower=1)).mean()

    mlflow.set_experiment("forecast_naive_baseline")

    with mlflow.start_run():
        mlflow.log_param("model_type", "naive_mean")
        mlflow.log_metric("mape", float(mape))

        model_info_path = Path("mlruns_artifacts") / "naive_mean_model.txt"
        model_info_path.parent.mkdir(parents=True, exist_ok=True)
        model_info_path.write_text(f"baseline_mean={baseline}")

        mlflow.log_artifact(str(model_info_path))


if __name__ == "__main__":
    train_naive_mean_model()
