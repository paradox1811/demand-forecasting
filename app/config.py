from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_DATA_FILE = RAW_DATA_DIR / "sample_sales.csv"
DB_DIR = PROJECT_ROOT / "data" / "db"
DB_PATH = DB_DIR / "forecasting.db"
REPORTS_DIR = PROJECT_ROOT / "reports" / "forecast_exports"
ASSETS_DIR = REPORTS_DIR / "dashboard_assets"
DEFAULT_FORECAST_DAYS = 7
DEFAULT_SAFETY_STOCK_DAYS = 3
