from __future__ import annotations

from pathlib import Path
import io

import pandas as pd
import streamlit as st

from app.config import DEFAULT_SAFETY_STOCK_DAYS
from app.data.loader import clean_sales_dataframe, merge_sales_frames
from app.data.preprocess import preprocess_sales_data
from app.db import import_multiple_sales_files, import_sales_csv_bytes, initialize_database
from app.repository import authenticate_user, list_shops, load_sales, sales_summary_by_shop
from app.services.export_service import create_share_bundle, export_dataframe_csv, export_summary_pdf
from app.services.media_service import list_dashboard_images, save_dashboard_images
from app.services.forecast_service import forecast_product_demand
from app.services.inventory_service import (
    build_restock_table,
    latest_stock_level,
    restock_recommendation,
    top_fast_moving_products,
)
from app.utils.plot_utils import (
    category_share_chart,
    daily_sales_chart,
    revenue_trend_chart,
    sales_and_forecast_chart,
    stock_risk_chart,
    top_products_chart,
)


st.set_page_config(page_title="Retail Forecasting Platform", page_icon="📈", layout="wide")

def inject_theme_css(theme: str) -> None:
    is_dark = theme == "dark"
    bg = (
        "radial-gradient(circle at top left, rgba(37, 99, 235, 0.18), transparent 24%),"
        "radial-gradient(circle at top right, rgba(56, 189, 248, 0.14), transparent 22%),"
        "linear-gradient(180deg, #071427 0%, #0b1730 48%, #09121f 100%)"
        if is_dark
        else "radial-gradient(circle at top left, rgba(125, 211, 252, 0.45), transparent 24%),"
        "radial-gradient(circle at top right, rgba(147, 197, 253, 0.35), transparent 24%),"
        "linear-gradient(180deg, #dff4ff 0%, #eef8ff 44%, #f7fbff 100%)"
    )
    sidebar_bg = (
        "linear-gradient(180deg, #081327 0%, #10213d 100%)"
        if is_dark
        else "linear-gradient(180deg, #d8f0ff 0%, #eaf7ff 100%)"
    )
    text = "#e2e8f0" if is_dark else "#16324f"
    muted = "#94a3b8" if is_dark else "#4b6480"
    hero_bg = (
        "linear-gradient(135deg, rgba(15,23,42,0.92), rgba(17,24,39,0.82))"
        if is_dark
        else "linear-gradient(135deg, rgba(255,255,255,0.92), rgba(224,242,254,0.88))"
    )
    card_bg = (
        "linear-gradient(180deg, rgba(15,23,42,0.92), rgba(15,23,42,0.82))"
        if is_dark
        else "linear-gradient(180deg, rgba(255,255,255,0.95), rgba(246,250,255,0.95))"
    )
    metric_bg = (
        "linear-gradient(180deg, rgba(15,23,42,0.95), rgba(15,23,42,0.82))"
        if is_dark
        else "linear-gradient(180deg, rgba(255,255,255,0.94), rgba(239,246,255,0.95))"
    )
    input_bg = "rgba(15,23,42,0.95)" if is_dark else "rgba(255,255,255,0.92)"
    button_bg = (
        "linear-gradient(180deg, #1e40af 0%, #1d4ed8 100%)"
        if is_dark
        else "linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%)"
    )
    button_text = "#eff6ff" if is_dark else "#0f3a63"

    st.markdown(
        f"""
        <style>
          .stApp {{
            background: {bg};
            color: {text};
          }}
          .block-container {{padding-top: 1.4rem; padding-bottom: 2rem;}}
          [data-testid="stSidebar"] {{
            background: {sidebar_bg};
            border-right: 1px solid rgba(59,130,246,0.12);
          }}
          [data-testid="stHeader"] {{background: rgba(255,255,255,0.0);}}
          .app-shell {{
            display:flex; align-items:flex-start; justify-content:space-between; gap:1rem;
            margin-bottom: 0.9rem;
          }}
          .app-shell-left h1 {{
            margin:0; font-size:2rem; color:{text}; letter-spacing:-0.03em;
          }}
          .app-shell-left p {{
            margin:0.35rem 0 0; color:{muted}; max-width:760px;
          }}
          .hero {{
            padding: 1.5rem 1.7rem;
            border: 1px solid rgba(96,165,250,0.18);
            border-radius: 24px;
            background: {hero_bg};
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
            margin-bottom: 1rem;
          }}
          .hero h1 {{margin: 0; font-size: 2rem; color: {text};}}
          .hero p {{margin: 0.45rem 0 0; color: {muted};}}
          .top-badge {{
            display:inline-block; padding:0.42rem 0.75rem; border-radius:999px;
            background:rgba(59,130,246,0.12); color:{text}; border:1px solid rgba(59,130,246,0.16);
            font-size:0.86rem; font-weight:600;
          }}
          div[data-testid="stMetric"] {{
            background: {metric_bg};
            border: 1px solid rgba(96,165,250,0.16);
            padding: 0.9rem 1rem;
            border-radius: 18px;
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
          }}
          .section-card {{
            border: 1px solid rgba(96,165,250,0.14);
            border-radius: 20px;
            background: {card_bg};
            box-shadow: 0 18px 48px rgba(15, 23, 42, 0.06);
            padding: 0.7rem 1rem 0.85rem;
          }}
          .login-card {{
            max-width: 540px;
            margin: 6vh auto 0;
            padding: 1.65rem;
            border-radius: 24px;
            border: 1px solid rgba(96,165,250,0.16);
            background: {card_bg};
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
          }}
          .small-note {{color: {muted}; font-size: 0.92rem;}}
          .pill {{
            display:inline-block; padding:0.35rem 0.65rem; border-radius:999px;
            background:rgba(96,165,250,0.12); color:{text};
            border:1px solid rgba(96,165,250,0.2); margin-right:0.4rem; margin-bottom:0.4rem;
          }}
          .data-summary {{
            display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.8rem;
            margin-bottom: 1rem;
          }}
          .data-summary-card {{
            border:1px solid rgba(96,165,250,0.14); background:{card_bg}; border-radius:18px;
            padding:0.95rem 1rem;
          }}
          .data-summary-card .label {{font-size:0.82rem; color:{muted}; text-transform:uppercase; letter-spacing:0.08em;}}
          .data-summary-card .value {{font-size:1.45rem; font-weight:700; color:{text}; margin-top:0.2rem;}}
          h1, h2, h3, h4, h5, h6, label, p, li, span, div {{color: {text};}}
          .stTabs [data-baseweb="tab-list"] {{
            gap: 0.45rem;
            padding-bottom: 0.35rem;
          }}
          .stTabs [data-baseweb="tab"] {{
            height: 42px;
            padding: 0 1rem;
            border-radius: 999px;
            background: rgba(59,130,246,0.08);
            border: 1px solid rgba(59,130,246,0.12);
            color: {text};
            font-weight: 600;
          }}
          .stTabs [aria-selected="true"] {{
            background: rgba(59,130,246,0.18) !important;
          }}
          .stButton > button, .stDownloadButton > button {{
            border-radius: 14px;
            border: 1px solid rgba(59,130,246,0.18);
            background: {button_bg};
            color: {button_text};
            font-weight: 600;
          }}
          .stButton > button:hover, .stDownloadButton > button:hover {{
            border-color: rgba(37,99,235,0.28);
            filter: brightness(1.03);
          }}
          div[data-baseweb="select"] > div,
          .stTextInput input,
          .stTextArea textarea,
          .stNumberInput input,
          .stDateInput input {{
            background: {input_bg} !important;
            border: 1px solid rgba(96,165,250,0.18) !important;
            color: {text} !important;
          }}
          [data-testid="stDataFrame"] {{
            border-radius: 18px;
            overflow: hidden;
          }}
          @media (max-width: 900px) {{
            .data-summary {{grid-template-columns: repeat(2, minmax(0, 1fr));}}
            .app-shell {{display:block;}}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=60)
def get_sales_dataframe(shop_id: str | None = None) -> pd.DataFrame:
    return preprocess_sales_data(load_sales(shop_id))


@st.cache_data(ttl=60)
def get_shop_table() -> pd.DataFrame:
    return list_shops()


@st.cache_data(ttl=60)
def get_shop_summary() -> pd.DataFrame:
    return sales_summary_by_shop()


def ensure_defaults() -> None:
    initialize_database()
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("temp_dataset", None)
    st.session_state.setdefault("temp_report", None)
    st.session_state.setdefault("theme_mode", "light")


def logout() -> None:
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.cache_data.clear()


def refresh_data() -> None:
    st.cache_data.clear()


def login_view() -> None:
    st.markdown(
        """
        <div class="login-card">
          <span class="top-badge">Retail Analytics Platform</span>
          <h2 style="margin-top:0;">Retail Forecasting Platform</h2>
          <p class="small-note">Sign in to access the admin or shop dashboard.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    st.info("Demo accounts: `admin / admin123`, `kathmandu_manager / shop123`, `pokhara_manager / shop123`")

    if submitted:
        user = authenticate_user(username, password)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user"] = user
            st.rerun()
        st.error("Invalid username or password.")


def export_controls(
    prefix: str,
    dataframe: pd.DataFrame,
    pdf_title: str,
    pdf_lines: list[str],
) -> None:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export CSV", key=f"csv_{prefix}", use_container_width=True):
            path = export_dataframe_csv(dataframe, prefix)
            st.success(f"CSV exported: {path.name}")
    with col2:
        if st.button("Export PDF Summary", key=f"pdf_{prefix}", use_container_width=True):
            path = export_summary_pdf(pdf_title, pdf_lines, prefix)
            st.success(f"PDF exported: {path.name}")


def dataset_manager() -> None:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Dataset Manager")

    template_path = Path(__file__).resolve().parent / "data" / "raw" / "template_sales.csv"
    sample_path = Path(__file__).resolve().parent / "data" / "raw" / "quick_commerce_bharatpur.csv"

    if template_path.exists():
        st.sidebar.download_button(
            "Download CSV Template",
            data=template_path.read_bytes(),
            file_name="template_sales.csv",
            mime="text/csv",
            use_container_width=True,
        )
    if sample_path.exists():
        st.sidebar.download_button(
            "Download Sample Dataset",
            data=sample_path.read_bytes(),
            file_name="quick_commerce_bharatpur.csv",
            mime="text/csv",
            use_container_width=True,
        )

    upload_mode = st.sidebar.radio("Data mode", options=["Database", "Temporary Uploaded Dashboard"], index=0)
    if upload_mode == "Database":
        st.session_state["temp_dataset"] = None
        st.session_state["temp_report"] = None

    uploaded = st.sidebar.file_uploader(
        "Import sales CSV files",
        type=["csv"],
        key="admin_dataset_upload",
        accept_multiple_files=True,
    )
    replace_matching_shops = st.sidebar.checkbox("Replace matching shops", value=False)
    if uploaded and st.sidebar.button("Process Uploaded Files", use_container_width=True):
        try:
            cleaned_frames = []
            file_reports = []
            for uploaded_file in uploaded:
                cleaned_df, report = clean_sales_dataframe(pd.read_csv(io.BytesIO(uploaded_file.getvalue())))
                report["file_name"] = uploaded_file.name
                cleaned_frames.append(cleaned_df)
                file_reports.append(report)

            merged_df = merge_sales_frames(cleaned_frames)
            st.session_state["temp_dataset"] = merged_df
            st.session_state["temp_report"] = file_reports

            if upload_mode == "Database":
                result = import_multiple_sales_files(
                    [uploaded_file.getvalue() for uploaded_file in uploaded],
                    replace_matching_shops=replace_matching_shops,
                )
                refresh_data()
                st.sidebar.success(
                    f"Imported {result['rows_imported']} rows for {len(result['shops_imported'])} shop(s)."
                )
            else:
                st.sidebar.success(
                    f"Temporary dashboard ready with {len(merged_df)} cleaned rows from {len(uploaded)} file(s)."
                )
        except Exception as exc:
            st.sidebar.error(f"Import failed: {exc}")

    temp_report = st.session_state.get("temp_report")
    if temp_report:
        st.sidebar.markdown("**Cleaning Summary**")
        for report in temp_report:
            st.sidebar.caption(
                f"{report.get('file_name', 'file')}: {report['clean_rows']} rows, "
                f"{report['duplicates_removed']} duplicates removed, "
                f"{report['negative_values_fixed']} negatives fixed"
            )

    return upload_mode


def image_manager(shop_key: str) -> list[Path]:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Dashboard Images")
    image_files = st.sidebar.file_uploader(
        "Upload dashboard images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"images_{shop_key}",
    )
    if image_files and st.sidebar.button("Save Images", use_container_width=True, key=f"save_images_{shop_key}"):
        saved = save_dashboard_images(
            shop_key,
            [(image_file.name, image_file.getvalue()) for image_file in image_files],
        )
        st.sidebar.success(f"Saved {len(saved)} image(s).")
    return list_dashboard_images(shop_key)


def render_common_dashboard(
    df: pd.DataFrame,
    shop_name_label: str,
    shop_id: str,
    selected_category: str,
    selected_product: str,
    forecast_days: int,
    safety_stock_days: int,
    model_name: str,
) -> None:
    filtered_df = df.copy()
    if selected_category != "All":
        filtered_df = filtered_df[filtered_df["category"] == selected_category].copy()

    history = (
        filtered_df[filtered_df["product_name"] == selected_product]
        .groupby("date", as_index=False)["units_sold"]
        .sum()
    )
    forecast_df, model_used = forecast_product_demand(filtered_df, shop_id, selected_product, forecast_days, model_name)
    current_stock = latest_stock_level(filtered_df, shop_id, selected_product)
    recommendation = restock_recommendation(forecast_df, current_stock, safety_stock_days)
    fast_movers = top_fast_moving_products(filtered_df, shop_id)
    restock_df = build_restock_table(filtered_df, shop_id, safety_stock_days, forecast_days)
    theme_mode = st.session_state.get("theme_mode", "light")

    total_units = int(filtered_df["units_sold"].sum())
    total_products = int(filtered_df["product_name"].nunique())
    total_categories = int(filtered_df["category"].nunique())
    revenue = float((filtered_df["units_sold"] * filtered_df["unit_price"]).sum()) if "unit_price" in filtered_df.columns else 0.0
    image_paths = list_dashboard_images(shop_id)

    st.markdown(
        f"""
        <div class="hero">
          <span class="top-badge">{model_used} Forecasting</span>
          <h1>{shop_name_label}</h1>
          <p>Operational dashboard for forecasting demand, tracking stock risk, monitoring revenue, and generating restock recommendations. Forecast model: <strong>{model_used}</strong>.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metrics = st.columns(4)
    metrics[0].metric("Total Units Sold", total_units)
    metrics[1].metric("Products", total_products)
    metrics[2].metric("Categories", total_categories)
    metrics[3].metric("Revenue", f"Rs. {revenue:,.0f}")

    second_metrics = st.columns(4)
    second_metrics[0].metric("Current Stock", recommendation["current_stock"])
    second_metrics[1].metric("Forecast Units", recommendation["forecast_total_units"])
    second_metrics[2].metric("Recommended Restock", recommendation["recommended_restock"])
    second_metrics[3].metric("Stockout Risk", recommendation["stockout_risk"])

    overview_tab, forecasting_tab, operations_tab, media_tab = st.tabs(
        ["Overview", "Forecast & Restock", "Operations", "Media & Sharing"]
    )

    with overview_tab:
        row_one = st.columns([1.1, 1.1, 1.1])
        with row_one[0]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Category Mix")
            st.plotly_chart(category_share_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_one[1]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Daily Sales")
            st.plotly_chart(daily_sales_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_one[2]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Top Products")
            st.plotly_chart(top_products_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        row_three = st.columns([1.05, 1.05, 1.2])
        with row_three[0]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Fast Moving Products")
            st.dataframe(fast_movers, use_container_width=True, hide_index=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_three[1]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Stockout Risk Summary")
            st.plotly_chart(stock_risk_chart(restock_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_three[2]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Revenue Trend")
            st.plotly_chart(revenue_trend_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with forecasting_tab:
        row_two = st.columns([1.6, 1])
        with row_two[0]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader(f"Demand Forecast: {selected_product}")
            st.plotly_chart(sales_and_forecast_chart(history, forecast_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_two[1]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Restock Recommendation")
            st.write(
                {
                    "Shop": shop_id,
                    "Category": selected_category,
                    "Product": selected_product,
                    "Average Daily Units": recommendation["avg_daily_units"],
                    "Safety Stock": recommendation["safety_stock"],
                    "Suggested Restock": recommendation["recommended_restock"],
                }
            )
            export_controls(
                prefix=f"{shop_id}_forecast",
                dataframe=forecast_df,
                pdf_title="Demand Forecast Summary",
                pdf_lines=[
                    f"Shop: {shop_id}",
                    f"Category: {selected_category}",
                    f"Product: {selected_product}",
                    f"Forecast Model: {model_used}",
                    f"Current Stock: {recommendation['current_stock']}",
                    f"Forecast Units: {recommendation['forecast_total_units']}",
                    f"Suggested Restock: {recommendation['recommended_restock']}",
                    f"Stockout Risk: {recommendation['stockout_risk']}",
                ],
            )
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Forecast Table")
        st.dataframe(forecast_df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with operations_tab:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Inventory Planning Table")
        st.dataframe(restock_df, use_container_width=True, hide_index=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Export Inventory CSV", key=f"csv_{shop_id}", use_container_width=True):
                csv_path = export_dataframe_csv(restock_df, f"{shop_id}_inventory")
                st.success(f"CSV exported: {csv_path.name}")
        with col2:
            if st.button("Export Inventory PDF", key=f"pdf_{shop_id}", use_container_width=True):
                pdf_path = export_summary_pdf(
                    "Inventory Planning Summary",
                    [
                        f"Shop: {shop_id}",
                        f"Rows: {len(restock_df)}",
                        f"High Risk Products: {(restock_df['stockout_risk'] == 'High').sum()}",
                        f"Total Recommended Restock: {restock_df['recommended_restock'].sum()}",
                    ],
                    f"{shop_id}_inventory",
                )
                st.success(f"PDF exported: {pdf_path.name}")
        with col3:
            if st.button("Create Share Bundle", key=f"bundle_{shop_id}", use_container_width=True):
                files = [
                    export_dataframe_csv(restock_df, f"{shop_id}_inventory_bundle"),
                    export_summary_pdf(
                        "Inventory Planning Share Bundle",
                        [
                            f"Shop: {shop_id}",
                            f"Category: {selected_category}",
                            f"Products: {total_products}",
                            f"Revenue: Rs. {revenue:,.0f}",
                            f"Forecast Product: {selected_product}",
                            f"Suggested Restock: {recommendation['recommended_restock']}",
                        ],
                        f"{shop_id}_bundle_summary",
                    ),
                ] + image_paths
                bundle = create_share_bundle(f"{shop_id}_share_bundle", files)
                st.success(f"Share bundle created: {bundle.name}")
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("View Raw Data Preview"):
            st.dataframe(filtered_df.head(30), use_container_width=True, hide_index=True)

    with media_tab:
        if image_paths:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Dashboard Image Gallery")
            gallery_cols = st.columns(min(3, len(image_paths)))
            for idx, image_path in enumerate(image_paths):
                with gallery_cols[idx % len(gallery_cols)]:
                    st.image(str(image_path), caption=image_path.name, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No dashboard images uploaded yet. Use the sidebar to attach images for this shop.")


def admin_view() -> None:
    user = st.session_state["user"]
    upload_mode = dataset_manager()
    temp_df = st.session_state.get("temp_dataset")
    using_temp = upload_mode == "Temporary Uploaded Dashboard" and isinstance(temp_df, pd.DataFrame)
    shops_df = get_shop_table()
    summary_df = get_shop_summary()

    st.sidebar.success(f"Signed in as {user['username']} (Admin)")
    if using_temp:
        temp_shops = sorted(temp_df["shop_id"].unique())
        selected_shop_id = st.sidebar.selectbox("Temporary shop", options=temp_shops)
        selected_shop_name = selected_shop_id.replace("-", " ").title()
        shop_df = temp_df[temp_df["shop_id"] == selected_shop_id].copy()
    else:
        selected_shop_id = st.sidebar.selectbox("Shop", options=shops_df["shop_id"].tolist())
        selected_shop_name = shops_df.loc[shops_df["shop_id"] == selected_shop_id, "shop_name"].iloc[0]
        shop_df = get_sales_dataframe(selected_shop_id)

    image_manager(selected_shop_id)
    selected_model = st.sidebar.selectbox("Forecast model", options=["baseline", "prophet", "xgboost"])
    forecast_days = st.sidebar.selectbox("Forecast horizon", options=[7, 14, 30], index=0)
    safety_stock_days = st.sidebar.slider("Safety stock days", min_value=1, max_value=10, value=DEFAULT_SAFETY_STOCK_DAYS)
    category_options = ["All"] + sorted(shop_df["category"].unique())
    selected_category = st.sidebar.selectbox("Category", options=category_options)
    visible_df = shop_df if selected_category == "All" else shop_df[shop_df["category"] == selected_category]
    selected_product = st.sidebar.selectbox("Product", options=sorted(visible_df["product_name"].unique()))

    if not using_temp:
        top_row = st.columns(3)
        top_row[0].metric("Active Shops", int(shops_df["shop_id"].nunique()))
        top_row[1].metric("Platform Revenue", f"Rs. {summary_df['total_revenue'].sum():,.0f}")
        top_row[2].metric("Platform Units Sold", int(summary_df["total_units_sold"].sum()))

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Admin Shop Summary")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        export_controls(
            prefix="admin_shop_summary",
            dataframe=summary_df,
            pdf_title="Admin Shop Summary",
            pdf_lines=[
                f"Shops: {len(summary_df)}",
                f"Total Revenue: Rs. {summary_df['total_revenue'].sum():,.0f}",
                f"Total Units Sold: {int(summary_df['total_units_sold'].sum())}",
            ],
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Temporary Dataset Workspace")
        temp_report = st.session_state.get("temp_report") or []
        for report in temp_report:
            st.markdown(
                f"<span class='pill'>{report.get('file_name','file')}: {report['clean_rows']} clean rows</span>",
                unsafe_allow_html=True,
            )
        st.caption("This dashboard is generated from uploaded CSV files only and is not saved to the database.")
        st.markdown("</div>", unsafe_allow_html=True)

    render_common_dashboard(
        df=shop_df,
        shop_name_label=f"{selected_shop_name} Dashboard",
        shop_id=selected_shop_id,
        selected_category=selected_category,
        selected_product=selected_product,
        forecast_days=forecast_days,
        safety_stock_days=safety_stock_days,
        model_name=selected_model,
    )


def shop_view() -> None:
    user = st.session_state["user"]
    shop_id = user["shop_id"]
    shops_df = get_shop_table()
    shop_name = shops_df.loc[shops_df["shop_id"] == shop_id, "shop_name"].iloc[0]
    shop_df = get_sales_dataframe(shop_id)

    st.sidebar.success(f"Signed in as {user['username']} (Shop)")
    selected_model = st.sidebar.selectbox("Forecast model", options=["baseline", "prophet", "xgboost"])
    forecast_days = st.sidebar.selectbox("Forecast horizon", options=[7, 14, 30], index=0)
    safety_stock_days = st.sidebar.slider("Safety stock days", min_value=1, max_value=10, value=DEFAULT_SAFETY_STOCK_DAYS)
    category_options = ["All"] + sorted(shop_df["category"].unique())
    selected_category = st.sidebar.selectbox("Category", options=category_options)
    visible_df = shop_df if selected_category == "All" else shop_df[shop_df["category"] == selected_category]
    selected_product = st.sidebar.selectbox("Product", options=sorted(visible_df["product_name"].unique()))

    render_common_dashboard(
        df=shop_df,
        shop_name_label=f"{shop_name} Shop View",
        shop_id=shop_id,
        selected_category=selected_category,
        selected_product=selected_product,
        forecast_days=forecast_days,
        safety_stock_days=safety_stock_days,
        model_name=selected_model,
    )


def main() -> None:
    ensure_defaults()
    inject_theme_css(st.session_state.get("theme_mode", "light"))

    with st.sidebar:
        chosen_theme = st.selectbox("Appearance", options=["light", "dark"], index=0 if st.session_state.get("theme_mode", "light") == "light" else 1)
        if chosen_theme != st.session_state.get("theme_mode"):
            st.session_state["theme_mode"] = chosen_theme
            st.rerun()
        st.button("Logout", on_click=logout, use_container_width=True, disabled=not st.session_state["authenticated"])

    if not st.session_state["authenticated"]:
        login_view()
        return

    role = st.session_state["user"]["role"]
    if role == "admin":
        admin_view()
    else:
        shop_view()


if __name__ == "__main__":
    main()
