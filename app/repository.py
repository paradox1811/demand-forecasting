from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime

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


def _query_dataframe(query: str, params: tuple = ()) -> pd.DataFrame:
    connection = get_connection()
    df = pd.read_sql_query(query, connection, params=params)
    connection.close()
    return df


def list_shops() -> pd.DataFrame:
    return _query_dataframe("SELECT shop_id, shop_name, shop_type FROM shops ORDER BY shop_name")


def get_shop_details(shop_id: str) -> dict | None:
    df = _query_dataframe(
        "SELECT shop_id, shop_name, shop_type FROM shops WHERE shop_id = ?",
        params=(shop_id,),
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def load_sales(shop_id: str | None = None) -> pd.DataFrame:
    if shop_id:
        return _query_dataframe("SELECT * FROM sales WHERE shop_id = ? ORDER BY date", params=(shop_id,))
    return _query_dataframe("SELECT * FROM sales ORDER BY date")


def sales_summary_by_shop() -> pd.DataFrame:
    return _query_dataframe(
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
        """
    )


def list_shop_menu(shop_id: str, available_only: bool = False) -> pd.DataFrame:
    query = """
        SELECT id, shop_id, item_name, category, price, description, prep_time_min, is_featured, is_available
        FROM menu_items
        WHERE shop_id = ?
    """
    if available_only:
        query += " AND is_available = 1"
    query += " ORDER BY is_featured DESC, category ASC, item_name ASC"
    return _query_dataframe(query, params=(shop_id,))


def add_menu_item(
    shop_id: str,
    item_name: str,
    category: str,
    price: float,
    description: str,
    prep_time_min: int = 15,
    is_featured: bool = False,
    is_available: bool = True,
) -> None:
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO menu_items (
            shop_id, item_name, category, price, description, prep_time_min, is_featured, is_available
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            shop_id,
            item_name,
            category,
            float(price),
            description,
            int(prep_time_min),
            1 if is_featured else 0,
            1 if is_available else 0,
        ),
    )
    connection.commit()
    connection.close()


def list_active_offers(shop_id: str | None = None) -> pd.DataFrame:
    query = """
        SELECT id, shop_id, title, description, offer_code, discount_percent, min_order_amount, is_active, start_date, end_date
        FROM offers
        WHERE is_active = 1
    """
    params: tuple = ()
    if shop_id:
        query += " AND shop_id = ?"
        params = (shop_id,)
    query += " ORDER BY discount_percent DESC, end_date ASC"
    return _query_dataframe(query, params=params)


def create_offer(
    shop_id: str,
    title: str,
    description: str,
    offer_code: str,
    discount_percent: float,
    min_order_amount: float,
    start_date: str,
    end_date: str,
) -> None:
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO offers (
            shop_id, title, description, offer_code, discount_percent, min_order_amount, is_active, start_date, end_date
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            shop_id,
            title,
            description,
            offer_code.upper(),
            float(discount_percent),
            float(min_order_amount),
            start_date,
            end_date,
        ),
    )
    connection.commit()
    connection.close()


def set_offer_active(offer_id: int, is_active: bool) -> None:
    connection = get_connection()
    connection.execute("UPDATE offers SET is_active = ? WHERE id = ?", (1 if is_active else 0, int(offer_id)))
    connection.commit()
    connection.close()


def lookup_offer(shop_id: str, offer_code: str | None) -> dict | None:
    if not offer_code:
        return None
    df = _query_dataframe(
        """
        SELECT id, shop_id, title, description, offer_code, discount_percent, min_order_amount, is_active, start_date, end_date
        FROM offers
        WHERE shop_id = ? AND UPPER(offer_code) = ? AND is_active = 1
        ORDER BY end_date ASC
        LIMIT 1
        """,
        params=(shop_id, offer_code.upper()),
    )
    if df.empty:
        return None
    record = df.iloc[0].to_dict()
    now = datetime.now().date()
    if record.get("start_date") and datetime.fromisoformat(record["start_date"]).date() > now:
        return None
    if record.get("end_date") and datetime.fromisoformat(record["end_date"]).date() < now:
        return None
    return record


def load_orders(shop_id: str | None = None, status: str | None = None) -> pd.DataFrame:
    query = """
        SELECT
            id,
            order_number,
            shop_id,
            customer_name,
            customer_phone,
            channel,
            order_source,
            table_ref,
            subtotal,
            discount_amount,
            total_amount,
            status,
            payment_status,
            notes,
            created_at
        FROM orders
        WHERE 1 = 1
    """
    params: list = []
    if shop_id:
        query += " AND shop_id = ?"
        params.append(shop_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY datetime(created_at) DESC"
    return _query_dataframe(query, params=tuple(params))


def load_order_items(order_id: int) -> pd.DataFrame:
    df = _query_dataframe("SELECT items_json FROM orders WHERE id = ?", params=(int(order_id),))
    if df.empty:
        return pd.DataFrame(columns=["item_name", "quantity", "price", "item_total"])
    items = json.loads(df.iloc[0]["items_json"])
    return pd.DataFrame(items)


def create_order(
    shop_id: str,
    customer_name: str,
    customer_phone: str,
    channel: str,
    table_ref: str,
    items: list[dict],
    offer_code: str | None = None,
    notes: str = "",
    payment_status: str = "Pending",
) -> dict:
    subtotal = round(sum(float(item["price"]) * int(item["quantity"]) for item in items), 2)
    discount_amount = 0.0
    offer = lookup_offer(shop_id, offer_code)
    if offer and subtotal >= float(offer["min_order_amount"]):
        discount_amount = round(subtotal * (float(offer["discount_percent"]) / 100.0), 2)
    total_amount = round(subtotal - discount_amount, 2)

    payload = []
    for item in items:
        quantity = int(item["quantity"])
        price = float(item["price"])
        payload.append(
            {
                "item_name": item["item_name"],
                "category": item.get("category", "General"),
                "quantity": quantity,
                "price": round(price, 2),
                "item_total": round(price * quantity, 2),
            }
        )

    order_number = f"ORD-{int(datetime.now().timestamp())}"
    created_at = datetime.now().isoformat(timespec="seconds")

    connection = get_connection()
    connection.execute(
        """
        INSERT INTO orders (
            order_number, shop_id, customer_name, customer_phone, channel, order_source, table_ref,
            items_json, subtotal, discount_amount, total_amount, status, payment_status, notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, 'menu', ?, ?, ?, ?, ?, 'New', ?, ?, ?)
        """,
        (
            order_number,
            shop_id,
            customer_name,
            customer_phone,
            channel,
            table_ref,
            json.dumps(payload),
            subtotal,
            discount_amount,
            total_amount,
            payment_status,
            notes,
            created_at,
        ),
    )
    connection.commit()
    connection.close()

    return {
        "order_number": order_number,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total_amount": total_amount,
        "offer_applied": offer["offer_code"] if offer else None,
    }


def update_order_status(order_id: int, status: str) -> None:
    connection = get_connection()
    connection.execute("UPDATE orders SET status = ? WHERE id = ?", (status, int(order_id)))
    connection.commit()
    connection.close()


def order_summary(shop_id: str | None = None) -> dict:
    orders_df = load_orders(shop_id)
    if orders_df.empty:
        return {
            "total_orders": 0,
            "completed_orders": 0,
            "avg_order_value": 0.0,
            "gross_sales": 0.0,
            "discounts": 0.0,
            "net_sales": 0.0,
        }

    completed = orders_df[orders_df["status"] == "Completed"]
    return {
        "total_orders": int(len(orders_df)),
        "completed_orders": int(len(completed)),
        "avg_order_value": round(float(orders_df["total_amount"].mean()), 2),
        "gross_sales": round(float(orders_df["subtotal"].sum()), 2),
        "discounts": round(float(orders_df["discount_amount"].sum()), 2),
        "net_sales": round(float(orders_df["total_amount"].sum()), 2),
    }


def finance_timeseries(shop_id: str | None = None) -> pd.DataFrame:
    query = """
        SELECT
            date(created_at) AS business_date,
            COUNT(*) AS order_count,
            SUM(subtotal) AS gross_sales,
            SUM(discount_amount) AS discounts,
            SUM(total_amount) AS net_sales
        FROM orders
        WHERE 1 = 1
    """
    params: list = []
    if shop_id:
        query += " AND shop_id = ?"
        params.append(shop_id)
    query += " GROUP BY date(created_at) ORDER BY business_date"
    return _query_dataframe(query, params=tuple(params))


def shop_type_overview() -> pd.DataFrame:
    return _query_dataframe(
        """
        SELECT
            s.shop_type,
            COUNT(DISTINCT s.shop_id) AS shops,
            COUNT(DISTINCT mi.id) AS menu_items,
            COUNT(DISTINCT o.id) AS active_offers,
            COALESCE(SUM(ord.total_amount), 0) AS order_revenue
        FROM shops s
        LEFT JOIN menu_items mi ON mi.shop_id = s.shop_id AND mi.is_available = 1
        LEFT JOIN offers o ON o.shop_id = s.shop_id AND o.is_active = 1
        LEFT JOIN orders ord ON ord.shop_id = s.shop_id
        GROUP BY s.shop_type
        ORDER BY order_revenue DESC, shops DESC
        """
    )


def setup_scorecard(shop_id: str) -> dict:
    menu_df = list_shop_menu(shop_id)
    offers_df = list_active_offers(shop_id)
    orders_df = load_orders(shop_id)
    order_count = len(orders_df)
    return {
        "menu_ready": len(menu_df) >= 6,
        "offers_ready": len(offers_df) >= 1,
        "qr_ready": True,
        "orders_live": order_count >= 1,
        "analytics_ready": True,
        "setup_score": int(
            sum(
                [
                    len(menu_df) >= 6,
                    len(offers_df) >= 1,
                    True,
                    order_count >= 1,
                    True,
                ]
            )
            / 5
            * 100
        ),
    }
