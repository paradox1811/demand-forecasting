from __future__ import annotations

import numpy as np
import pandas as pd


def xgboost_forecast(series: pd.Series, horizon: int) -> pd.DataFrame:
    from xgboost import XGBRegressor

    ordered = series.sort_index()
    if len(ordered) < 10:
        raise ValueError("XGBoost forecast needs at least 10 observations.")

    df = ordered.reset_index()
    df.columns = ["date", "units_sold"]
    df["lag_1"] = df["units_sold"].shift(1)
    df["lag_7"] = df["units_sold"].shift(7)
    df["rolling_3"] = df["units_sold"].rolling(3).mean().shift(1)
    df["day_of_week"] = pd.to_datetime(df["date"]).dt.dayofweek
    df = df.dropna().reset_index(drop=True)

    features = ["lag_1", "lag_7", "rolling_3", "day_of_week"]
    model = XGBRegressor(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(df[features], df["units_sold"])

    history_values = ordered.tolist()
    last_date = ordered.index.max()
    predictions: list[float] = []

    for step in range(1, horizon + 1):
        current_date = last_date + pd.Timedelta(days=step)
        lag_1 = predictions[-1] if predictions else history_values[-1]
        lag_7_source = history_values + predictions
        lag_7 = lag_7_source[-7] if len(lag_7_source) >= 7 else np.mean(lag_7_source)
        rolling_3 = float(np.mean((history_values + predictions)[-3:]))
        feature_row = pd.DataFrame(
            [{"lag_1": lag_1, "lag_7": lag_7, "rolling_3": rolling_3, "day_of_week": current_date.dayofweek}]
        )
        predicted = float(model.predict(feature_row)[0])
        predictions.append(max(0.0, predicted))

    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
    return pd.DataFrame(
        {"date": future_dates, "predicted_units_sold": np.round(predictions, 2)}
    )
