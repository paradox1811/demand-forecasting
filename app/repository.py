from __future__ import annotations

import hashlib

import pandas as pd

from app.db import get_connection


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate_user(username: str, password: str) -> dict | None:
    connection = get_connection()
    user_df = pd.read_sql_query(
        "SELECT id, username, password_hash, role, shop_id FROM users WHERE username = ?",
        connection,
        params=(username,),
    )
    connection.close()
    if user_df.empty:
        return None
    record = user_df.iloc[0].to_dict()
    if record["password_hash"] != _hash_password(password):
        return None
    return {
        "id": int(record["id"]),
        "username": record["username"],
        "role": record["role"],
        "shop_id": record["shop_id"],
    }


def list_shops() -> pd.DataFrame:
    connection = get_connection()
    df = pd.read_sql_query("SELECT shop_id, shop_name, shop_type FROM shops ORDER BY shop_name", connection)
    connection.close()
    return df


def load_sales(shop_id: str | None = None) -> pd.DataFrame:
    connection = get_connection()
    if shop_id:
        df = pd.read_sql_query(
            "SELECT * FROM sales WHERE shop_id = ? ORDER BY date",
            connection,
            params=(shop_id,),
        )
    else:
        df = pd.read_sql_query("SELECT * FROM sales ORDER BY date", connection)
    connection.close()
    return df


def sales_summary_by_shop() -> pd.DataFrame:
    connection = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            shop_id,
            COUNT(DISTINCT product_name) AS total_products,
            SUM(units_sold) AS total_units_sold,
            SUM(units_sold * COALESCE(unit_price, 0)) AS total_revenue,
            AVG(stock_available) AS avg_stock
        FROM sales
        GROUP BY shop_id
        ORDER BY total_revenue DESC
        """,
        connection,
    )
    connection.close()
    return df
