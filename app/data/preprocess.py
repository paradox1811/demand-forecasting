from __future__ import annotations

import pandas as pd


def preprocess_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
    cleaned = cleaned.dropna(subset=["date"]).copy()
    cleaned["product_name"] = cleaned["product_name"].astype(str).str.strip()
    cleaned["category"] = cleaned["category"].astype(str).str.strip()
    cleaned["shop_id"] = cleaned["shop_id"].astype(str).str.strip()
    cleaned["day_of_week"] = cleaned["date"].dt.day_name()
    cleaned["week_number"] = cleaned["date"].dt.isocalendar().week.astype(int)
    cleaned["month"] = cleaned["date"].dt.month
    cleaned["is_weekend"] = cleaned["date"].dt.dayofweek >= 5
    return cleaned
