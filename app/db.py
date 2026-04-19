from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
import json
from datetime import datetime, timedelta

import pandas as pd

from app.config import DB_DIR, DB_PATH, DEFAULT_DATA_FILE
from app.data.loader import clean_sales_dataframe, merge_sales_frames, parse_uploaded_file


def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def initialize_database(sample_csv: str | Path = DEFAULT_DATA_FILE) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            shop_id TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            shop_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            units_sold REAL NOT NULL,
            unit_price REAL,
            stock_available REAL NOT NULL,
            is_holiday INTEGER DEFAULT 0,
            festival_season INTEGER DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shops (
            shop_id TEXT PRIMARY KEY,
            shop_name TEXT NOT NULL,
            shop_type TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            prep_time_min INTEGER DEFAULT 15,
            is_featured INTEGER DEFAULT 0,
            is_available INTEGER DEFAULT 1
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            offer_code TEXT NOT NULL,
            discount_percent REAL NOT NULL,
            min_order_amount REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            start_date TEXT,
            end_date TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            shop_id TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT,
            channel TEXT NOT NULL,
            order_source TEXT DEFAULT 'app',
            table_ref TEXT,
            items_json TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount_amount REAL DEFAULT 0,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            payment_status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    users = [
        ("admin", _hash_password("admin123"), "admin", None),
        ("kathmandu_manager", _hash_password("shop123"), "shop", "kathmandu-mart-01"),
        ("pokhara_manager", _hash_password("shop123"), "shop", "pokhara-cafe-02"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO users (username, password_hash, role, shop_id) VALUES (?, ?, ?, ?)",
        users,
    )

    sales_count = cursor.execute("SELECT COUNT(*) AS count FROM sales").fetchone()["count"]
    if sales_count == 0:
        sales_df = pd.read_csv(sample_csv)
        sales_df.to_sql("sales", connection, if_exists="append", index=False)

    shops_count = cursor.execute("SELECT COUNT(*) AS count FROM shops").fetchone()["count"]
    if shops_count == 0:
        shops_df = pd.read_sql_query(
            """
            SELECT DISTINCT
                shop_id,
                CASE
                    WHEN shop_id LIKE '%mart%' THEN 'Retail Mart'
                    WHEN shop_id LIKE '%cafe%' THEN 'Cafe / Restaurant'
                    ELSE 'Local Shop'
                END AS shop_type
            FROM sales
            """,
            connection,
        )
        shops_df["shop_name"] = shops_df["shop_id"].str.replace("-", " ").str.title()
        shops_df = shops_df[["shop_id", "shop_name", "shop_type"]]
        shops_df.to_sql("shops", connection, if_exists="append", index=False)

    menu_count = cursor.execute("SELECT COUNT(*) AS count FROM menu_items").fetchone()["count"]
    if menu_count == 0:
        _seed_menu_items(connection)

    offers_count = cursor.execute("SELECT COUNT(*) AS count FROM offers").fetchone()["count"]
    if offers_count == 0:
        _seed_offers(connection)

    orders_count = cursor.execute("SELECT COUNT(*) AS count FROM orders").fetchone()["count"]
    if orders_count == 0:
        _seed_orders(connection)

    connection.commit()
    connection.close()


def _seed_menu_items(connection: sqlite3.Connection) -> None:
    sales_df = pd.read_sql_query(
        """
        SELECT shop_id, product_name, category, AVG(COALESCE(unit_price, 0)) AS avg_price
        FROM sales
        GROUP BY shop_id, product_name, category
        ORDER BY shop_id, product_name
        """,
        connection,
    )
    if sales_df.empty:
        return

    seed_rows = []
    for shop_id, group in sales_df.groupby("shop_id"):
        featured_names = set(group.sort_values("avg_price", ascending=False)["product_name"].head(3))
        for _, row in group.head(10).iterrows():
            price = float(row["avg_price"]) if float(row["avg_price"]) > 0 else 120.0
            seed_rows.append(
                {
                    "shop_id": shop_id,
                    "item_name": row["product_name"],
                    "category": row["category"],
                    "price": round(price, 2),
                    "description": f"Fresh {str(row['product_name']).lower()} prepared for fast-moving neighborhood demand.",
                    "prep_time_min": 10 if "drink" in str(row["category"]).lower() else 18,
                    "is_featured": 1 if row["product_name"] in featured_names else 0,
                    "is_available": 1,
                }
            )

    pd.DataFrame(seed_rows).to_sql("menu_items", connection, if_exists="append", index=False)


def _seed_offers(connection: sqlite3.Connection) -> None:
    shops = pd.read_sql_query("SELECT shop_id, shop_type FROM shops ORDER BY shop_id", connection)
    if shops.empty:
        return

    today = datetime.now().date()
    offers = []
    for _, row in shops.iterrows():
        base_discount = 12 if "Cafe" in row["shop_type"] else 10
        offers.extend(
            [
                {
                    "shop_id": row["shop_id"],
                    "title": "Loyalty Push",
                    "description": "Designed to increase repeat purchases during non-peak hours.",
                    "offer_code": f"{row['shop_id'].split('-')[0].upper()}10",
                    "discount_percent": base_discount,
                    "min_order_amount": 500,
                    "is_active": 1,
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=45)).isoformat(),
                },
                {
                    "shop_id": row["shop_id"],
                    "title": "Bundle Boost",
                    "description": "Lift average order value with a bundled basket offer.",
                    "offer_code": f"{row['shop_id'].split('-')[0].upper()}15",
                    "discount_percent": base_discount + 5,
                    "min_order_amount": 900,
                    "is_active": 1,
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=30)).isoformat(),
                },
            ]
        )

    pd.DataFrame(offers).to_sql("offers", connection, if_exists="append", index=False)


def _seed_orders(connection: sqlite3.Connection) -> None:
    menu_df = pd.read_sql_query(
        "SELECT id, shop_id, item_name, category, price FROM menu_items ORDER BY shop_id, is_featured DESC, id ASC",
        connection,
    )
    if menu_df.empty:
        return

    statuses = [
        ("New", "Pending"),
        ("Preparing", "Paid"),
        ("Ready", "Paid"),
        ("Completed", "Paid"),
    ]
    orders = []
    counter = 1001
    now = datetime.now()
    for shop_id, group in menu_df.groupby("shop_id"):
        top_items = group.head(4).to_dict("records")
        for idx, (status, payment_status) in enumerate(statuses):
            chosen = top_items[: 2 + (idx % 2)]
            items = []
            subtotal = 0.0
            for item in chosen:
                quantity = 1 + (idx % 3)
                item_total = float(item["price"]) * quantity
                items.append(
                    {
                        "item_name": item["item_name"],
                        "category": item["category"],
                        "quantity": quantity,
                        "price": float(item["price"]),
                        "item_total": round(item_total, 2),
                    }
                )
                subtotal += item_total

            discount = round(subtotal * (0.1 if idx in (1, 3) else 0.0), 2)
            created_at = (now - timedelta(hours=idx * 7 + len(orders))).isoformat(timespec="seconds")
            orders.append(
                {
                    "order_number": f"ORD-{counter}",
                    "shop_id": shop_id,
                    "customer_name": ["Aarav", "Sanjana", "Pratik", "Nisha"][idx % 4],
                    "customer_phone": f"+9779800000{idx + 11}",
                    "channel": "QR Menu" if idx % 2 == 0 else "Counter",
                    "order_source": "menu",
                    "table_ref": f"T-{idx + 1}" if "cafe" in shop_id else "Pickup",
                    "items_json": json.dumps(items),
                    "subtotal": round(subtotal, 2),
                    "discount_amount": discount,
                    "total_amount": round(subtotal - discount, 2),
                    "status": status,
                    "payment_status": payment_status,
                    "notes": "Seeded demo order",
                    "created_at": created_at,
                }
            )
            counter += 1

    pd.DataFrame(orders).to_sql("orders", connection, if_exists="append", index=False)


def sync_shops(connection: sqlite3.Connection) -> None:
    shops_df = pd.read_sql_query(
        """
        SELECT DISTINCT
            shop_id,
            CASE
                WHEN shop_id LIKE '%mart%' THEN 'Retail Mart'
                WHEN shop_id LIKE '%cafe%' THEN 'Cafe / Restaurant'
                WHEN shop_id LIKE '%express%' THEN 'Quick Commerce'
                ELSE 'Local Shop'
            END AS shop_type
        FROM sales
        """,
        connection,
    )
    if shops_df.empty:
        return
    shops_df["shop_name"] = shops_df["shop_id"].str.replace("-", " ").str.title()
    shops_df = shops_df[["shop_id", "shop_name", "shop_type"]]
    shops_df.to_sql("shops", connection, if_exists="replace", index=False)


def import_sales_csv_bytes(file_bytes: bytes, replace_matching_shops: bool = False) -> dict:
    connection = get_connection()
    parsed = parse_uploaded_file("uploaded.csv", file_bytes)
    if len(parsed) != 1:
        raise ValueError("Single-file import expected one structured dataset.")
    _, raw_df = parsed[0]
    sales_df, clean_report = clean_sales_dataframe(raw_df)
    shop_ids = sorted(sales_df["shop_id"].astype(str).unique().tolist())

    if replace_matching_shops:
        placeholders = ",".join(["?"] * len(shop_ids))
        connection.execute(f"DELETE FROM sales WHERE shop_id IN ({placeholders})", shop_ids)

    sales_df.to_sql("sales", connection, if_exists="append", index=False)
    sync_shops(connection)
    connection.commit()
    connection.close()

    return {
        "rows_imported": int(len(sales_df)),
        "shops_imported": shop_ids,
        "products_imported": int(sales_df["product_name"].nunique()),
        "cleaning_report": clean_report,
    }


def import_multiple_sales_files(files: list[bytes], replace_matching_shops: bool = False) -> dict:
    cleaned_frames = []
    reports = []
    for index, file_bytes in enumerate(files, start=1):
        for parsed_name, raw_df in parse_uploaded_file(f"uploaded_{index}.csv", file_bytes):
            cleaned_df, report = clean_sales_dataframe(raw_df)
            report["file_name"] = parsed_name
            cleaned_frames.append(cleaned_df)
            reports.append(report)

    merged_df = merge_sales_frames(cleaned_frames)
    shop_ids = sorted(merged_df["shop_id"].astype(str).unique().tolist())

    connection = get_connection()
    if replace_matching_shops and shop_ids:
        placeholders = ",".join(["?"] * len(shop_ids))
        connection.execute(f"DELETE FROM sales WHERE shop_id IN ({placeholders})", shop_ids)

    merged_df.to_sql("sales", connection, if_exists="append", index=False)
    sync_shops(connection)
    connection.commit()
    connection.close()

    return {
        "rows_imported": int(len(merged_df)),
        "shops_imported": shop_ids,
        "products_imported": int(merged_df["product_name"].nunique()),
        "file_reports": reports,
    }
