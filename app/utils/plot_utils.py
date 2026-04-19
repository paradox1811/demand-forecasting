from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def apply_professional_layout(figure: go.Figure, height: int, theme: str = "light") -> go.Figure:
    is_dark = theme == "dark"
    figure.update_layout(
        template="plotly_dark" if is_dark else "plotly_white",
        height=height,
        margin=dict(l=20, r=20, t=30, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#081327" if is_dark else "#f8fbff",
        font=dict(color="#dbeafe" if is_dark else "#16324f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    grid = "rgba(148,163,184,0.18)" if not is_dark else "rgba(148,163,184,0.12)"
    figure.update_xaxes(showgrid=True, gridcolor=grid, zeroline=False)
    figure.update_yaxes(showgrid=True, gridcolor=grid, zeroline=False)
    return figure


def sales_and_forecast_chart(history_df: pd.DataFrame, forecast_df: pd.DataFrame, theme: str = "light") -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=history_df["date"],
            y=history_df["units_sold"],
            mode="lines+markers",
            name="Historical Sales",
            line=dict(color="#2563eb", width=3),
            marker=dict(size=7, color="#2563eb"),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["predicted_units_sold"],
            mode="lines+markers",
            name="Forecast",
            line=dict(color="#38bdf8", width=3, dash="dot"),
            marker=dict(size=7, color="#38bdf8"),
        )
    )
    return apply_professional_layout(figure, 420, theme)


def category_share_chart(df: pd.DataFrame, theme: str = "light") -> go.Figure:
    category_data = df.groupby("category", as_index=False)["units_sold"].sum()
    figure = px.pie(
        category_data,
        names="category",
        values="units_sold",
        hole=0.6,
        color_discrete_sequence=["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#7dd3fc", "#93c5fd", "#38bdf8"],
    )
    figure.update_traces(textfont_color="#dbeafe" if theme == "dark" else "#16324f")
    return apply_professional_layout(figure, 360, theme)


def daily_sales_chart(df: pd.DataFrame, theme: str = "light") -> go.Figure:
    daily_data = df.groupby("date", as_index=False)["units_sold"].sum()
    figure = px.line(
        daily_data,
        x="date",
        y="units_sold",
        markers=True,
        color_discrete_sequence=["#2563eb"],
    )
    return apply_professional_layout(figure, 360, theme)


def top_products_chart(df: pd.DataFrame, limit: int = 8, theme: str = "light") -> go.Figure:
    product_data = (
        df.groupby("product_name", as_index=False)["units_sold"]
        .sum()
        .sort_values("units_sold", ascending=False)
        .head(limit)
    )
    figure = px.bar(
        product_data,
        x="units_sold",
        y="product_name",
        orientation="h",
        color="units_sold",
        color_continuous_scale=["#dbeafe", "#93c5fd", "#60a5fa", "#2563eb"],
    )
    figure = apply_professional_layout(figure, 360, theme)
    figure.update_layout(coloraxis_showscale=False, yaxis=dict(categoryorder="total ascending"))
    return figure


def stock_risk_chart(restock_df: pd.DataFrame, theme: str = "light") -> go.Figure:
    risk_data = restock_df.groupby("stockout_risk", as_index=False)["product_name"].count()
    risk_data = risk_data.rename(columns={"product_name": "product_count"})
    color_map = {"Low": "#22c55e", "Medium": "#f59e0b", "High": "#ef4444"}
    figure = px.bar(
        risk_data,
        x="stockout_risk",
        y="product_count",
        color="stockout_risk",
        color_discrete_map=color_map,
    )
    figure = apply_professional_layout(figure, 320, theme)
    figure.update_layout(showlegend=False)
    return figure


def revenue_trend_chart(df: pd.DataFrame, theme: str = "light") -> go.Figure:
    revenue_df = df.copy()
    revenue_df["revenue"] = revenue_df["units_sold"] * revenue_df.get("unit_price", 0)
    trend = revenue_df.groupby("date", as_index=False)["revenue"].sum()
    figure = px.area(
        trend,
        x="date",
        y="revenue",
        color_discrete_sequence=["#38bdf8"],
    )
    return apply_professional_layout(figure, 360, theme)


def best_selling_prediction_chart(prediction_df: pd.DataFrame, theme: str = "light") -> go.Figure:
    figure = px.bar(
        prediction_df.sort_values("predicted_units_next_period", ascending=True),
        x="predicted_units_next_period",
        y="product_name",
        orientation="h",
        color="predicted_units_next_period",
        color_continuous_scale=["#dbeafe", "#93c5fd", "#60a5fa", "#2563eb"],
    )
    figure = apply_professional_layout(figure, 360, theme)
    figure.update_layout(coloraxis_showscale=False, yaxis=dict(categoryorder="total ascending"))
    return figure


def performance_worm_chart(df: pd.DataFrame, theme: str = "light") -> go.Figure:
    trend = (
        df.assign(revenue=df["units_sold"] * df.get("unit_price", 0))
        .groupby("date", as_index=False)
        .agg(units_sold=("units_sold", "sum"), revenue=("revenue", "sum"))
        .sort_values("date")
    )
    trend["units_ma"] = trend["units_sold"].rolling(7, min_periods=1).mean()
    trend["revenue_ma"] = trend["revenue"].rolling(7, min_periods=1).mean()

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=trend["date"],
            y=trend["units_ma"],
            name="7-Day Demand Signal",
            mode="lines",
            line=dict(color="#2563eb", width=4, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(37,99,235,0.14)",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=trend["date"],
            y=trend["revenue_ma"],
            name="7-Day Revenue Signal",
            mode="lines",
            line=dict(color="#38bdf8", width=3, shape="spline", dash="dot"),
        )
    )
    return apply_professional_layout(figure, 380, theme)


def order_status_chart(order_df: pd.DataFrame, theme: str = "light") -> go.Figure:
    if order_df.empty:
        empty = go.Figure()
        return apply_professional_layout(empty, 320, theme)
    summary = order_df.groupby("status", as_index=False)["order_number"].count().rename(columns={"order_number": "orders"})
    figure = px.pie(
        summary,
        names="status",
        values="orders",
        hole=0.6,
        color="status",
        color_discrete_map={
            "New": "#2563eb",
            "Preparing": "#f59e0b",
            "Ready": "#38bdf8",
            "Completed": "#22c55e",
            "Cancelled": "#ef4444",
        },
    )
    figure.update_traces(textfont_color="#dbeafe" if theme == "dark" else "#16324f")
    return apply_professional_layout(figure, 320, theme)


def finance_overview_chart(finance_df: pd.DataFrame, theme: str = "light") -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=finance_df["business_date"],
            y=finance_df["gross_sales"],
            name="Gross Sales",
            marker_color="#93c5fd",
        )
    )
    figure.add_trace(
        go.Bar(
            x=finance_df["business_date"],
            y=finance_df["discounts"],
            name="Discounts",
            marker_color="#f59e0b",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=finance_df["business_date"],
            y=finance_df["net_sales"],
            name="Net Sales",
            mode="lines+markers",
            line=dict(color="#1d4ed8", width=3),
        )
    )
    figure.update_layout(barmode="group")
    return apply_professional_layout(figure, 360, theme)
