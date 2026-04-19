# Smart Demand Forecasting for Local Shops

A practical data science MVP for Nepali retailers, groceries, and restaurants.

## What it does

- Loads historical sales data from CSV
- Seeds a SQLite database for a more realistic app workflow
- Provides login-based access for admin and shop users
- Supports separate admin and shop dashboards
- Forecasts next 7 or 30 days of demand for a selected product
- Estimates reorder quantity using safety stock
- Highlights fast-moving products and stockout risk
- Exports planning reports to CSV and PDF
- Runs as a multi-view Streamlit dashboard

## Project structure

- `streamlit_app.py`: Streamlit entry point
- `app/data/`: loading and preprocessing
- `app/models/`: forecasting logic
- `app/services/`: business logic and recommendations
- `data/raw/`: source CSV files
- `data/processed/`: cleaned outputs

## Quick start

```bash
cd smart-demand-forecasting-nepal
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Demo login accounts

- Admin: `admin / admin123`
- Kathmandu shop: `kathmandu_manager / shop123`
- Pokhara shop: `pokhara_manager / shop123`

## Importing a new CSV

1. Sign in as `admin`
2. Open the sidebar `Dataset Manager`
3. Download the CSV template if needed
4. Upload your new sales CSV
5. Click `Import Dataset`

After import, the new shop dataset will appear in the dashboard automatically.

Bundled files:

- `data/raw/template_sales.csv`
- `data/raw/quick_commerce_bharatpur.csv`

## Forecasting models

- `baseline`: moving-average + weekly pattern blend
- `prophet`: used when Prophet is installed
- `xgboost`: used when XGBoost is installed

If Prophet or XGBoost is unavailable, the app falls back to the baseline model gracefully.

## CSV columns

Required:

- `date`
- `shop_id`
- `product_name`
- `category`
- `units_sold`
- `stock_available`

Optional but useful:

- `unit_price`
- `is_holiday`
- `festival_season`

## Sample use cases

- Grocery restock planning
- Restaurant ingredient demand planning
- Local retailer fast-moving item tracking
- District/shop-level demand analysis
