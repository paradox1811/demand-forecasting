from __future__ import annotations

import hashlib
import io
import sqlite3
from pathlib import Path

import pandas as pd

from app.config import DB_DIR, DB_PATH, DEFAULT_DATA_FILE
from app.data.loader import clean_sales_dataframe, merge_sales_frames


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

    connection.commit()
    connection.close()


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
    csv_df = pd.read_csv(io.BytesIO(file_bytes))
    sales_df, clean_report = clean_sales_dataframe(csv_df)
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
    for file_bytes in files:
        csv_df = pd.read_csv(io.BytesIO(file_bytes))
        cleaned_df, report = clean_sales_dataframe(csv_df)
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
