from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS_ORDER = [
    "date",
    "shop_id",
    "product_name",
    "category",
    "units_sold",
    "stock_available",
    "unit_price",
    "is_holiday",
    "festival_season",
]

REQUIRED_COLUMNS = {
    "date",
    "shop_id",
    "product_name",
    "category",
    "units_sold",
    "stock_available",
}

COLUMN_ALIASES = {
    "date": {"date", "day", "sales_date", "order_date", "transaction_date"},
    "shop_id": {"shop_id", "shop", "store_id", "store", "branch", "branch_id", "outlet"},
    "product_name": {"product_name", "product", "item", "item_name", "sku_name"},
    "category": {"category", "product_category", "dept", "department", "segment"},
    "units_sold": {"units_sold", "qty", "quantity", "sold_units", "sales_qty", "units"},
    "stock_available": {"stock_available", "stock", "inventory", "stock_left", "available_stock"},
    "unit_price": {"unit_price", "price", "selling_price", "mrp", "rate"},
    "is_holiday": {"is_holiday", "holiday", "public_holiday"},
    "festival_season": {"festival_season", "festival", "season_flag", "festive"},
}


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def detect_column_mapping(df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    available = {_normalize_name(column): column for column in df.columns}

    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized = _normalize_name(alias)
            if normalized in available:
                mapping[available[normalized]] = canonical
                break
    return mapping


def standardize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    mapping = detect_column_mapping(df)
    standardized = df.rename(columns=mapping).copy()
    return standardized, mapping


def validate_sales_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    df = df.copy()
    df["shop_id"] = df["shop_id"].astype(str).str.strip().str.lower().str.replace(" ", "-", regex=False)
    df["product_name"] = df["product_name"].astype(str).str.strip().str.title()
    df["category"] = df["category"].astype(str).str.strip().str.title()
    df["date"] = pd.to_datetime(df["date"])
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce").fillna(0)
    df["stock_available"] = pd.to_numeric(df["stock_available"], errors="coerce").fillna(0)
    if "unit_price" in df.columns:
        df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0)
    if "is_holiday" in df.columns:
        df["is_holiday"] = pd.to_numeric(df["is_holiday"], errors="coerce").fillna(0).astype(int)
    if "festival_season" in df.columns:
        df["festival_season"] = pd.to_numeric(df["festival_season"], errors="coerce").fillna(0).astype(int)
    return df.sort_values("date").reset_index(drop=True)


def clean_sales_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    standardized, mapping = standardize_columns(df)
    report = {
        "original_rows": int(len(standardized)),
        "mapped_columns": mapping,
        "duplicates_removed": 0,
        "negative_values_fixed": 0,
        "missing_category_filled": 0,
        "future_dates_removed": 0,
    }

    standardized = standardized.copy()
    if "category" in standardized.columns:
        missing_category_mask = standardized["category"].isna() | (standardized["category"].astype(str).str.strip() == "")
        report["missing_category_filled"] = int(missing_category_mask.sum())
        standardized.loc[missing_category_mask, "category"] = "Unknown"

    for numeric_col in ["units_sold", "stock_available", "unit_price"]:
        if numeric_col in standardized.columns:
            standardized[numeric_col] = pd.to_numeric(standardized[numeric_col], errors="coerce")
            negative_mask = standardized[numeric_col] < 0
            report["negative_values_fixed"] += int(negative_mask.fillna(False).sum())
            standardized.loc[negative_mask, numeric_col] = abs(standardized.loc[negative_mask, numeric_col])

    if "date" in standardized.columns:
        standardized["date"] = pd.to_datetime(standardized["date"], errors="coerce")
        future_mask = standardized["date"] > pd.Timestamp.today().normalize() + pd.Timedelta(days=365)
        report["future_dates_removed"] = int(future_mask.fillna(False).sum())
        standardized = standardized.loc[~future_mask].copy()

    before_dedup = len(standardized)
    standardized = standardized.drop_duplicates()
    report["duplicates_removed"] = int(before_dedup - len(standardized))

    cleaned = validate_sales_dataframe(standardized)
    for column in REQUIRED_COLUMNS_ORDER:
        if column not in cleaned.columns:
            if column in {"unit_price", "is_holiday", "festival_season"}:
                cleaned[column] = 0
    cleaned = cleaned[REQUIRED_COLUMNS_ORDER]
    report["clean_rows"] = int(len(cleaned))
    report["shops_found"] = int(cleaned["shop_id"].nunique())
    report["products_found"] = int(cleaned["product_name"].nunique())
    return cleaned, report


def merge_sales_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        raise ValueError("No dataframes provided for merge.")
    merged = pd.concat(frames, ignore_index=True)
    cleaned, _ = clean_sales_dataframe(merged)
    return cleaned


def load_sales_data(source: str | Path) -> pd.DataFrame:
    source_path = Path(source)
    suffix = source_path.suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(source_path)
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(source_path)
    elif suffix == ".json":
        df = pd.read_json(source_path)
    elif suffix == ".parquet":
        df = pd.read_parquet(source_path)
    elif suffix in {".txt", ".tsv"}:
        df = pd.read_csv(source_path, sep=None, engine="python")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    cleaned, _ = clean_sales_dataframe(df)
    return cleaned


def parse_uploaded_file(filename: str, file_bytes: bytes) -> list[tuple[str, pd.DataFrame]]:
    suffix = Path(filename).suffix.lower()

    if suffix == ".zip":
        extracted: list[tuple[str, pd.DataFrame]] = []
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            for member in archive.namelist():
                member_suffix = Path(member).suffix.lower()
                if member_suffix not in {".csv", ".xlsx", ".xls", ".json", ".parquet", ".txt", ".tsv"}:
                    continue
                extracted.extend(parse_uploaded_file(member, archive.read(member)))
        if not extracted:
            raise ValueError("ZIP file did not contain any supported structured data files.")
        return extracted

    if suffix == ".csv":
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(io.BytesIO(file_bytes))
    elif suffix == ".json":
        df = pd.read_json(io.BytesIO(file_bytes))
    elif suffix == ".parquet":
        df = pd.read_parquet(io.BytesIO(file_bytes))
    elif suffix in {".txt", ".tsv"}:
        df = pd.read_csv(io.BytesIO(file_bytes), sep=None, engine="python")
    else:
        raise ValueError(
            f"Unsupported file type '{suffix}'. Supported formats: CSV, Excel, JSON, Parquet, TXT/TSV, ZIP."
        )

    return [(filename, df)]
