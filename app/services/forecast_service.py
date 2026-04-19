from __future__ import annotations

import pandas as pd

from app.models.baseline import moving_average_forecast
from app.models.prophet_model import prophet_forecast
from app.models.xgboost_model import xgboost_forecast


def build_product_series(df: pd.DataFrame, shop_id: str, product_name: str) -> pd.Series:
    filtered = df[(df["shop_id"] == shop_id) & (df["product_name"] == product_name)].copy()
    daily = filtered.groupby("date", as_index=True)["units_sold"].sum().sort_index()
    return daily


def forecast_product_demand(
    df: pd.DataFrame,
    shop_id: str,
    product_name: str,
    forecast_days: int,
    model_name: str = "baseline",
) -> tuple[pd.DataFrame, str]:
    series = build_product_series(df, shop_id, product_name)
    normalized = model_name.lower()
    if series.empty:
        future_dates = pd.date_range(start=pd.Timestamp.today().normalize() + pd.Timedelta(days=1), periods=forecast_days, freq="D")
        empty_forecast = pd.DataFrame({"date": future_dates, "predicted_units_sold": [0.0] * forecast_days})
        return empty_forecast, "No history fallback"

    if normalized == "prophet":
        try:
            return prophet_forecast(series, forecast_days), "Prophet"
        except Exception:
            return moving_average_forecast(series, forecast_days), "Baseline fallback"

    if normalized == "xgboost":
        try:
            return xgboost_forecast(series, forecast_days), "XGBoost"
        except Exception:
            return moving_average_forecast(series, forecast_days), "Baseline fallback"

    return moving_average_forecast(series, forecast_days), "Baseline"


def predict_best_selling_products(
    df: pd.DataFrame,
    shop_id: str,
    forecast_days: int,
    model_name: str = "baseline",
    top_n: int = 8,
) -> pd.DataFrame:
    products = sorted(df[df["shop_id"] == shop_id]["product_name"].unique())
    rows = []
    for product_name in products:
        forecast_df, model_used = forecast_product_demand(df, shop_id, product_name, forecast_days, model_name)
        rows.append(
            {
                "product_name": product_name,
                "predicted_units_next_period": round(float(forecast_df["predicted_units_sold"].sum()), 2),
                "avg_daily_forecast": round(float(forecast_df["predicted_units_sold"].mean()), 2),
                "model_used": model_used,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["predicted_units_next_period", "avg_daily_forecast"],
        ascending=[False, False],
    ).head(top_n)
