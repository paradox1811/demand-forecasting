from __future__ import annotations

import math

import pandas as pd


def latest_stock_level(df: pd.DataFrame, shop_id: str, product_name: str) -> int:
    filtered = df[(df["shop_id"] == shop_id) & (df["product_name"] == product_name)].sort_values("date")
    if filtered.empty:
        return 0
    return int(filtered.iloc[-1]["stock_available"])


def restock_recommendation(
    forecast_df: pd.DataFrame,
    current_stock: int,
    safety_stock_days: int = 3,
) -> dict:
    total_forecast = float(forecast_df["predicted_units_sold"].sum())
    avg_daily = float(forecast_df["predicted_units_sold"].mean()) if not forecast_df.empty else 0.0
    safety_stock = math.ceil(avg_daily * safety_stock_days)
    recommended = max(0, math.ceil(total_forecast + safety_stock - current_stock))
    stockout_risk = "High" if current_stock < avg_daily * 3 else "Medium" if current_stock < avg_daily * 7 else "Low"

    return {
        "forecast_total_units": round(total_forecast, 2),
        "avg_daily_units": round(avg_daily, 2),
        "current_stock": current_stock,
        "safety_stock": safety_stock,
        "recommended_restock": recommended,
        "stockout_risk": stockout_risk,
    }


def top_fast_moving_products(df: pd.DataFrame, shop_id: str, limit: int = 5) -> pd.DataFrame:
    filtered = df[df["shop_id"] == shop_id]
    return (
        filtered.groupby("product_name", as_index=False)["units_sold"]
        .sum()
        .sort_values("units_sold", ascending=False)
        .head(limit)
    )


def build_restock_table(
    df: pd.DataFrame, shop_id: str, safety_stock_days: int = 3, forecast_days: int = 7
) -> pd.DataFrame:
    from app.services.forecast_service import forecast_product_demand

    products = sorted(df[df["shop_id"] == shop_id]["product_name"].unique())
    records = []

    for product_name in products:
        forecast_df, _ = forecast_product_demand(df, shop_id, product_name, forecast_days)
        current_stock = latest_stock_level(df, shop_id, product_name)
        recommendation = restock_recommendation(forecast_df, current_stock, safety_stock_days)
        records.append(
            {
                "product_name": product_name,
                "current_stock": recommendation["current_stock"],
                "forecast_units": recommendation["forecast_total_units"],
                "avg_daily_units": recommendation["avg_daily_units"],
                "recommended_restock": recommendation["recommended_restock"],
                "stockout_risk": recommendation["stockout_risk"],
            }
        )

    return pd.DataFrame(records).sort_values(
        by=["stockout_risk", "recommended_restock"],
        ascending=[True, False],
    )
