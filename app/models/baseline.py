from __future__ import annotations

import numpy as np
import pandas as pd


def moving_average_forecast(series: pd.Series, horizon: int) -> pd.DataFrame:
    ordered = series.sort_index()
    if ordered.empty:
        raise ValueError("Cannot forecast an empty series.")

    recent_window = min(7, len(ordered))
    recent_mean = max(0.0, ordered.tail(recent_window).mean())

    weekly_pattern = ordered.groupby(ordered.index.dayofweek).mean().to_dict()
    start_date = ordered.index.max() + pd.Timedelta(days=1)
    future_dates = pd.date_range(start=start_date, periods=horizon, freq="D")

    forecast_values = []
    for date in future_dates:
      day_value = weekly_pattern.get(date.dayofweek, recent_mean)
      blended = (0.65 * recent_mean) + (0.35 * day_value)
      forecast_values.append(max(0.0, float(blended)))

    return pd.DataFrame(
        {
            "date": future_dates,
            "predicted_units_sold": np.round(forecast_values, 2),
        }
    )
