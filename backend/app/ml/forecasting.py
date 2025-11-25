from typing import List, Dict, Tuple

import logging
import numpy as np
import pandas as pd
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA
from xgboost import XGBRegressor

from ..models.forecast import (
    ForecastRequest,
    ForecastPoint,
    ForecastMetadata,
)
from ..feature_store.registry import load_sales_with_signals


logger = logging.getLogger(__name__)


def _generate_stub_forecast(base: float, horizon: int) -> np.ndarray:
    if horizon <= 0:
        return np.asarray([], dtype="float64")

    steps = np.linspace(0.0, 2.5 * np.pi, horizon, endpoint=False, dtype="float64")
    seasonal = 0.12 * np.sin(steps)
    trend = np.linspace(-0.08, 0.08, horizon, dtype="float64")
    raw = base * (1.0 + seasonal + trend)
    noise = 0.05 * base * np.sin(steps * 1.7)
    values = raw + noise

    return np.maximum(values, 0.0)


def _compute_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true > 0
    if not np.any(mask):
        return np.inf
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])))


def _compute_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if y_true.size == 0 or y_pred.size == 0:
        return float("inf")
    return float(np.mean(np.abs(y_true - y_pred)))


def _prepare_history(
    sku: str,
    location: str | None,
) -> pd.Series:
    df = load_sales_with_signals()
    logger.info("load_sales_with_signals returned %d rows, columns=%s", len(df), list(df.columns))
    logger.info("Available SKUs: %s", df["sku"].unique().tolist() if "sku" in df.columns else "NO SKU COLUMN")
    
    df = df[df["sku"] == sku]
    logger.info("After filtering sku=%s: %d rows", sku, len(df))
    
    if location is not None:
        # Only filter by location if that value actually appears; otherwise
        # fall back to using all locations for this SKU so forecasting still
        # has a non-empty history.
        if "location" in df.columns and (df["location"] == location).any():
            df = df[df["location"] == location]

    if df.empty:
        logger.warning("No data found for sku=%s, location=%s", sku, location)
        return pd.Series(dtype="float64")

    daily = (
        df.groupby("date")["quantity"]
        .sum()
        .sort_index()
    )
    logger.info("Prepared history for sku=%s: %d daily points", sku, len(daily))
    return daily


def _forecast_arima(series: pd.Series, horizon: int) -> np.ndarray | None:
    if len(series) < 4 or horizon <= 0:
        logger.warning("ARIMA skipped: len=%d < 4 or horizon=%d <= 0", len(series), horizon)
        return None
    try:
        model = ARIMA(series.values.astype("float64"), order=(1, 1, 1))
        res = model.fit()
        fc = res.forecast(steps=horizon)
        logger.info("ARIMA success: len=%d, horizon=%d, fc_mean=%.2f", len(series), horizon, float(np.mean(fc)))
        return np.maximum(fc, 0.0)
    except Exception as exc:
        logger.warning("ARIMA forecast failed (len=%d, horizon=%d): %s", len(series), horizon, exc)
        return None


def _forecast_prophet(series: pd.Series, horizon_dates: pd.DatetimeIndex) -> np.ndarray | None:
    if len(series) < 4 or len(horizon_dates) == 0:
        logger.warning("Prophet skipped: len=%d < 4 or horizon=%d == 0", len(series), len(horizon_dates))
        return None
    try:
        df = pd.DataFrame({"ds": series.index, "y": series.values})
        m = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
        m.fit(df)
        future = pd.DataFrame({"ds": horizon_dates})
        fc = m.predict(future)["yhat"].values
        logger.info("Prophet success: len=%d, horizon=%d, fc_mean=%.2f", len(series), len(horizon_dates), float(np.mean(fc)))
        return np.maximum(fc, 0.0)
    except Exception as exc:
        logger.warning("Prophet forecast failed (len=%d, horizon=%d): %s", len(series), len(horizon_dates), exc)
        return None


def _forecast_xgb(series: pd.Series, horizon: int) -> np.ndarray | None:
    if len(series) < 6 or horizon <= 0:
        logger.warning("XGBoost skipped: len=%d < 6 or horizon=%d <= 0", len(series), horizon)
        return None
    try:
        values = series.values.astype("float64")
        X: list[list[float]] = []
        y: list[float] = []
        for i in range(1, len(values)):
            X.append([values[i - 1]])
            y.append(values[i])

        X_arr = np.asarray(X)
        y_arr = np.asarray(y)

        model = XGBRegressor(
            n_estimators=50,
            max_depth=2,
            learning_rate=0.1,
            objective="reg:squarederror",
            subsample=0.9,
            colsample_bytree=1.0,
        )
        model.fit(X_arr, y_arr)

        history = float(values[-1])
        forecasts: list[float] = []
        for _ in range(horizon):
            pred = float(model.predict(np.array([[history]], dtype="float64"))[0])
            pred = max(pred, 0.0)
            forecasts.append(pred)
            history = pred
        logger.info("XGBoost success: len=%d, horizon=%d, fc_mean=%.2f", len(series), horizon, float(np.mean(forecasts)))
        return np.asarray(forecasts, dtype="float64")
    except Exception as exc:
        logger.warning("XGBoost forecast failed (len=%d, horizon=%d): %s", len(series), horizon, exc)
        return None


def _select_model_and_forecast(
    series: pd.Series,
    horizon_dates: pd.DatetimeIndex,
    forced_model: str | None = None,
) -> Tuple[np.ndarray, str, Dict[str, float]]:
    """Select and run a forecast model.

    If forced_model is provided ("arima", "prophet", "xgboost", "stub"), we try that
    first. Otherwise we compute validation metrics (MAPE/MAE) and pick the best model
    by MAPE.
    """

    horizon = len(horizon_dates)
    if len(series) < 4 or horizon <= 0:
        base = float(series.mean()) if len(series) > 0 else 100.0
        return _generate_stub_forecast(base, horizon), "stub", {}

    n_val = min(3, max(1, len(series) // 4))
    train = series.iloc[:-n_val]
    val_true = series.iloc[-n_val:].values.astype("float64")

    metrics: Dict[str, float] = {}

    logger.info("Computing validation metrics: train_len=%d, val_len=%d", len(train), n_val)
    
    arima_val = _forecast_arima(train, n_val)
    if arima_val is not None:
        metrics["arima_mape"] = _compute_mape(val_true, arima_val)
        metrics["arima_mae"] = _compute_mae(val_true, arima_val)
        logger.info("ARIMA validation: mape=%.2f%%, mae=%.2f", metrics["arima_mape"] * 100, metrics["arima_mae"])

    prophet_val = _forecast_prophet(train, pd.date_range(start=train.index[-n_val], periods=n_val, freq="D"))
    if prophet_val is not None:
        metrics["prophet_mape"] = _compute_mape(val_true, prophet_val)
        metrics["prophet_mae"] = _compute_mae(val_true, prophet_val)
        logger.info("Prophet validation: mape=%.2f%%, mae=%.2f", metrics["prophet_mape"] * 100, metrics["prophet_mae"])

    xgb_val = _forecast_xgb(train, n_val)
    if xgb_val is not None:
        metrics["xgb_mape"] = _compute_mape(val_true, xgb_val)
        metrics["xgb_mae"] = _compute_mae(val_true, xgb_val)
        logger.info("XGBoost validation: mape=%.2f%%, mae=%.2f", metrics["xgb_mape"] * 100, metrics["xgb_mae"])

    def _forecast_with_name(name: str) -> Tuple[np.ndarray | None, str]:
        if name == "arima":
            return _forecast_arima(series, horizon), "arima"
        if name == "prophet":
            return _forecast_prophet(series, horizon_dates), "prophet"
        if name == "xgboost":
            return _forecast_xgb(series, horizon), "xgboost"
        if name == "stub":
            base = float(series.mean()) if len(series) > 0 else 100.0
            return _generate_stub_forecast(base, horizon), "stub"
        return None, "stub"

    # If caller forced a model, honour that first
    if forced_model in {"arima", "prophet", "xgboost", "stub"}:
        final_fc, chosen = _forecast_with_name(forced_model)
        if final_fc is None:
            base = float(series.mean()) if len(series) > 0 else 100.0
            return _generate_stub_forecast(base, horizon), "stub", metrics
        return final_fc, chosen, metrics

    # Auto-selection based on MAPE
    if not metrics:
        base = float(series.mean()) if len(series) > 0 else 100.0
        return _generate_stub_forecast(base, horizon), "stub", {}

    score_candidates: Dict[str, float] = {}
    if "arima_mape" in metrics:
        score_candidates["arima"] = metrics["arima_mape"]
    if "prophet_mape" in metrics:
        score_candidates["prophet"] = metrics["prophet_mape"]
    if "xgb_mape" in metrics:
        score_candidates["xgboost"] = metrics["xgb_mape"]

    if not score_candidates:
        base = float(series.mean()) if len(series) > 0 else 100.0
        return _generate_stub_forecast(base, horizon), "stub", metrics

    best_model = min(score_candidates, key=score_candidates.get)
    final_fc, chosen = _forecast_with_name(best_model)
    if final_fc is None:
        base = float(series.mean()) if len(series) > 0 else 100.0
        return _generate_stub_forecast(base, horizon), "stub", metrics

    return final_fc, chosen, metrics


def generate_ensemble_forecast(
    request: ForecastRequest,
) -> Tuple[List[ForecastPoint], ForecastMetadata, Dict[str, float]]:
    date_index = pd.date_range(
        start=request.start_date,
        end=request.end_date,
        freq=request.granularity.value,
    )

    points: List[ForecastPoint] = []
    global_metrics: Dict[str, float] = {}
    per_sku_model: Dict[str, str] = {}

    for sku in request.sku_list:
        history = _prepare_history(sku=sku, location=request.location)

        if history.empty:
            base_level = 100.0
            mean_values = _generate_stub_forecast(base_level, len(date_index))
            chosen_model = "stub"
            metrics: Dict[str, float] = {}
        else:
            fc_values, chosen_model, metrics = _select_model_and_forecast(
                history,
                date_index,
                getattr(request, "forced_model", None),
            )
            mean_values = fc_values

        logger.info(
            "Forecast model for sku=%s: chosen=%s forced=%s metrics=%s history_len=%d horizon=%d",
            sku,
            chosen_model,
            getattr(request, "forced_model", None),
            metrics,
            len(history),
            len(date_index),
        )

        per_sku_model[sku] = chosen_model

        for key, value in metrics.items():
            global_metrics[f"{sku}.{key}"] = value

        for ts, mean in zip(date_index, mean_values):
            q50 = float(mean)
            q10 = float(mean * 0.8)
            q90 = float(mean * 1.2)

            points.append(
                ForecastPoint(
                    sku=sku,
                    date=ts.date(),
                    mean=float(mean),
                    q10=q10,
                    q50=q50,
                    q90=q90,
                )
            )

        global_metrics[f"{sku}.chosen_model"] = {
            "stub": 0.0,
            "arima": 1.0,
            "prophet": 2.0,
            "xgboost": 3.0,
        }.get(chosen_model, -1.0)

    metadata = ForecastMetadata(
        model_name="arima_prophet_xgb_ensemble",
        model_version="1.0.0",
        components=["arima", "prophet", "xgboost"],
        notes="Per-SKU model selection with ARIMA, Prophet, and XGBoost; quantiles approximated from mean.",
        per_sku_model=per_sku_model,
    )

    return points, metadata, global_metrics
