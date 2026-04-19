from __future__ import annotations

import pandas as pd


def prophet_forecast(series: pd.Series, horizon: int) -> pd.DataFrame:
    from prophet import Prophet

    if series.empty:
        raise ValueError("Cannot forecast an empty series.")

    prophet_df = series.reset_index()
    prophet_df.columns = ["ds", "y"]
    model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=horizon, freq="D")
    forecast = model.predict(future)[["ds", "yhat"]].tail(horizon)
    forecast = forecast.rename(columns={"ds": "date", "yhat": "predicted_units_sold"})
    forecast["predicted_units_sold"] = forecast["predicted_units_sold"].clip(lower=0).round(2)
    return forecast
