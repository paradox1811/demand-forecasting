from __future__ import annotations

from pathlib import Path
import io

import pandas as pd
import streamlit as st

from app.config import DEFAULT_SAFETY_STOCK_DAYS
from app.data.loader import clean_sales_dataframe, merge_sales_frames, parse_uploaded_file
from app.data.preprocess import preprocess_sales_data
from app.db import import_multiple_sales_files, initialize_database
from app.repository import (
    add_menu_item,
    authenticate_user,
    create_offer,
    create_order,
    finance_timeseries,
    get_shop_details,
    list_active_offers,
    list_shop_menu,
    list_shops,
    load_order_items,
    load_orders,
    load_sales,
    order_summary,
    sales_summary_by_shop,
    set_offer_active,
    setup_scorecard,
    shop_type_overview,
    update_order_status,
)
from app.services.export_service import create_share_bundle, export_dataframe_csv, export_summary_pdf, generate_invoice_pdf
from app.services.media_service import list_dashboard_images, save_dashboard_images
from app.services.forecast_service import forecast_product_demand, predict_best_selling_products
from app.services.inventory_service import (
    build_restock_table,
    latest_stock_level,
    restock_recommendation,
    top_fast_moving_products,
)
from app.utils.plot_utils import (
    best_selling_prediction_chart,
    category_share_chart,
    daily_sales_chart,
    finance_overview_chart,
    order_status_chart,
    performance_worm_chart,
    revenue_trend_chart,
    sales_and_forecast_chart,
    stock_risk_chart,
    top_products_chart,
)


st.set_page_config(page_title="RetailOS Nepal", page_icon="🛍️", layout="wide")


def format_currency(value: float) -> str:
    return f"Rs. {value:,.0f}"


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
          .stApp {{ background: {bg}; color: {text}; }}
          .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}
          [data-testid="stSidebar"] {{ background: {sidebar_bg}; border-right: 1px solid rgba(59,130,246,0.12); }}
          [data-testid="stHeader"] {{ background: rgba(255,255,255,0.0); }}
          .hero {{
            padding: 1.5rem 1.7rem; border: 1px solid rgba(96,165,250,0.18); border-radius: 24px;
            background: {hero_bg}; box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08); margin-bottom: 1rem;
          }}
          .hero h1 {{ margin: 0; font-size: 2rem; color: {text}; letter-spacing: -0.03em; }}
          .hero p {{ margin: 0.45rem 0 0; color: {muted}; }}
          .top-badge {{
            display:inline-block; padding:0.42rem 0.75rem; border-radius:999px; margin-right:0.35rem;
            background:rgba(59,130,246,0.12); color:{text}; border:1px solid rgba(59,130,246,0.16);
            font-size:0.86rem; font-weight:600;
          }}
          .section-card, div[data-testid="stMetric"], .login-card, .menu-card, .insight-card {{
            border: 1px solid rgba(96,165,250,0.14); border-radius: 20px; background: {card_bg};
            box-shadow: 0 18px 48px rgba(15, 23, 42, 0.06);
          }}
          .section-card {{ padding: 0.8rem 1rem 1rem; }}
          div[data-testid="stMetric"] {{ padding: 0.9rem 1rem; }}
          .login-card {{
            max-width: 560px; margin: 5vh auto 0; padding: 1.7rem;
          }}
          .small-note {{ color: {muted}; font-size: 0.92rem; }}
          .menu-card {{ padding: 1rem; min-height: 170px; }}
          .menu-card h4 {{ margin: 0 0 0.35rem; }}
          .menu-meta {{ color: {muted}; font-size: 0.9rem; }}
          .insight-grid {{
            display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.8rem; margin-bottom: 1rem;
          }}
          .insight-card {{ padding: 1rem; }}
          .insight-card .label {{ color:{muted}; font-size:0.82rem; text-transform:uppercase; letter-spacing:0.08em; }}
          .insight-card .value {{ font-size:1.4rem; font-weight:700; margin-top:0.2rem; }}
          .pill {{
            display:inline-block; padding:0.35rem 0.65rem; border-radius:999px;
            background:rgba(96,165,250,0.12); color:{text}; border:1px solid rgba(96,165,250,0.2);
            margin-right:0.4rem; margin-bottom:0.4rem;
          }}
          h1, h2, h3, h4, h5, h6, label, p, li, span, div {{ color: {text}; }}
          .stTabs [data-baseweb="tab"] {{
            height: 42px; padding: 0 1rem; border-radius: 999px; background: rgba(59,130,246,0.08);
            border: 1px solid rgba(59,130,246,0.12); color: {text}; font-weight: 600;
          }}
          .stTabs [aria-selected="true"] {{ background: rgba(59,130,246,0.18) !important; }}
          .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
            border-radius: 14px; border: 1px solid rgba(59,130,246,0.18); background: {button_bg}; color: {button_text}; font-weight: 600;
          }}
          div[data-baseweb="select"] > div, .stTextInput input, .stTextArea textarea,
          .stNumberInput input, .stDateInput input {{
            background: {input_bg} !important; border: 1px solid rgba(96,165,250,0.18) !important; color: {text} !important;
          }}
          @media (max-width: 900px) {{
            .insight-grid {{ grid-template-columns: repeat(1, minmax(0, 1fr)); }}
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


@st.cache_data(ttl=60)
def get_menu_dataframe(shop_id: str) -> pd.DataFrame:
    return list_shop_menu(shop_id)


@st.cache_data(ttl=60)
def get_offer_dataframe(shop_id: str | None = None) -> pd.DataFrame:
    return list_active_offers(shop_id)


@st.cache_data(ttl=60)
def get_orders_dataframe(shop_id: str | None = None) -> pd.DataFrame:
    return load_orders(shop_id)


@st.cache_data(ttl=60)
def get_finance_dataframe(shop_id: str | None = None) -> pd.DataFrame:
    return finance_timeseries(shop_id)


@st.cache_data(ttl=60)
def get_shop_type_overview() -> pd.DataFrame:
    return shop_type_overview()


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


def build_menu_url(shop_id: str) -> str:
    return f"?menu_shop={shop_id}"


def maybe_render_qr(menu_url: str) -> None:
    try:
        import qrcode
    except Exception:
        st.info("Install `qrcode` to render QR images automatically. The share link below already works.")
        return

    qr_image = qrcode.make(menu_url)
    buffer = io.BytesIO()
    qr_image.save(buffer, format="PNG")
    buffer.seek(0)
    st.image(buffer.getvalue(), caption="Menu QR", width=180)


def export_controls(prefix: str, dataframe: pd.DataFrame, pdf_title: str, pdf_lines: list[str]) -> None:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export CSV", key=f"csv_{prefix}", use_container_width=True):
            path = export_dataframe_csv(dataframe, prefix)
            st.success(f"CSV exported: {path.name}")
    with col2:
        if st.button("Export PDF Summary", key=f"pdf_{prefix}", use_container_width=True):
            path = export_summary_pdf(pdf_title, pdf_lines, prefix)
            st.success(f"PDF exported: {path.name}")


def dataset_manager() -> str:
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
        "Import structured data files",
        type=None,
        key="admin_dataset_upload",
        accept_multiple_files=True,
        help="Supported: CSV, Excel, JSON, Parquet, TXT/TSV, and ZIP bundles containing those files.",
    )
    replace_matching_shops = st.sidebar.checkbox("Replace matching shops", value=False)
    if uploaded and st.sidebar.button("Process Uploaded Files", use_container_width=True):
        try:
            cleaned_frames = []
            file_reports = []
            for uploaded_file in uploaded:
                for parsed_name, raw_df in parse_uploaded_file(uploaded_file.name, uploaded_file.getvalue()):
                    cleaned_df, report = clean_sales_dataframe(raw_df)
                    report["file_name"] = parsed_name
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
        saved = save_dashboard_images(shop_key, [(image_file.name, image_file.getvalue()) for image_file in image_files])
        st.sidebar.success(f"Saved {len(saved)} image(s).")
    return list_dashboard_images(shop_key)


def render_setup_strip(scorecard: dict) -> None:
    states = [
        ("Menu Ready", scorecard["menu_ready"]),
        ("Offers Ready", scorecard["offers_ready"]),
        ("QR Ready", scorecard["qr_ready"]),
        ("Orders Live", scorecard["orders_live"]),
        ("Analytics Ready", scorecard["analytics_ready"]),
    ]
    st.markdown('<div class="insight-grid">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="insight-card">
          <div class="label">Startup Readiness</div>
          <div class="value">{scorecard['setup_score']}%</div>
          <div class="small-note">How close this shop is to a live, self-serve retail operation.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for label, state in states[:2]:
        st.markdown(
            f"""
            <div class="insight-card">
              <div class="label">{label}</div>
              <div class="value">{"Live" if state else "Pending"}</div>
              <div class="small-note">{"Configured and ready to use." if state else "Needs setup to unlock growth."}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("Setup focus: good retail apps work best when menu, offers, QR ordering, and analytics are all connected.")


def render_menu_management(shop_id: str, menu_df: pd.DataFrame) -> None:
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Live Menu")
        menu_cols = st.columns(3)
        for idx, (_, row) in enumerate(menu_df.head(9).iterrows()):
            with menu_cols[idx % 3]:
                st.markdown(
                    f"""
                    <div class="menu-card">
                      <span class="top-badge">{row['category']}</span>
                      <h4>{row['item_name']}</h4>
                      <div class="menu-meta">{row['description']}</div>
                      <div style="margin-top:0.9rem; font-weight:700;">{format_currency(float(row['price']))}</div>
                      <div class="small-note">Prep {int(row['prep_time_min'])} min · {"Featured" if int(row['is_featured']) else "Standard"}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    with right:
        st.subheader("Add Menu Item")
        with st.form(f"menu_form_{shop_id}"):
            item_name = st.text_input("Item name")
            category = st.text_input("Category", value="Fast Moving")
            price = st.number_input("Price", min_value=0.0, value=150.0, step=10.0)
            description = st.text_area("Description", value="Fresh, high-demand item prepared for quick ordering.")
            prep_time = st.number_input("Prep time (minutes)", min_value=5, value=15, step=5)
            is_featured = st.checkbox("Feature this item")
            submitted = st.form_submit_button("Add to menu", use_container_width=True)
        if submitted and item_name.strip():
            add_menu_item(shop_id, item_name.strip(), category.strip(), price, description.strip(), prep_time, is_featured)
            refresh_data()
            st.success("Menu item added.")
            st.rerun()


def render_offer_management(shop_id: str, offers_df: pd.DataFrame) -> None:
    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.subheader("Offer Engine")
        if offers_df.empty:
            st.info("No active offers yet.")
        else:
            offer_view = offers_df.copy()
            offer_view["discount_percent"] = offer_view["discount_percent"].map(lambda value: f"{value:.0f}%")
            offer_view["min_order_amount"] = offer_view["min_order_amount"].map(format_currency)
            st.dataframe(
                offer_view[["title", "offer_code", "discount_percent", "min_order_amount", "end_date"]],
                use_container_width=True,
                hide_index=True,
            )
            selected_offer = st.selectbox(
                "Pause an active offer",
                options=["None"] + offers_df["offer_code"].tolist(),
                key=f"offer_pause_{shop_id}",
            )
            if selected_offer != "None" and st.button("Pause offer", use_container_width=True, key=f"pause_offer_{shop_id}"):
                offer_id = int(offers_df.loc[offers_df["offer_code"] == selected_offer, "id"].iloc[0])
                set_offer_active(offer_id, False)
                refresh_data()
                st.success(f"{selected_offer} paused.")
                st.rerun()
    with col2:
        st.subheader("Create Offer")
        with st.form(f"offer_form_{shop_id}"):
            title = st.text_input("Campaign title")
            code = st.text_input("Offer code")
            discount = st.slider("Discount %", min_value=5, max_value=40, value=15)
            minimum = st.number_input("Minimum order amount", min_value=0.0, value=500.0, step=100.0)
            start_date = st.date_input("Start date")
            end_date = st.date_input("End date")
            description = st.text_area("Description", value="Use this to increase AOV and repeat purchase behavior.")
            submitted = st.form_submit_button("Create offer", use_container_width=True)
        if submitted and title.strip() and code.strip():
            create_offer(shop_id, title.strip(), description.strip(), code.strip(), discount, minimum, start_date.isoformat(), end_date.isoformat())
            refresh_data()
            st.success("Offer created.")
            st.rerun()


def render_orders_management(shop_id: str, orders_df: pd.DataFrame, finance_df: pd.DataFrame, theme_mode: str) -> None:
    top = order_summary(shop_id)
    metrics = st.columns(4)
    metrics[0].metric("Orders", top["total_orders"])
    metrics[1].metric("Completed", top["completed_orders"])
    metrics[2].metric("Average Order Value", format_currency(top["avg_order_value"]))
    metrics[3].metric("Net Sales", format_currency(top["net_sales"]))

    row = st.columns([1, 1.4])
    with row[0]:
        st.subheader("Order Pipeline")
        st.plotly_chart(order_status_chart(orders_df, theme=theme_mode), use_container_width=True)
    with row[1]:
        st.subheader("Finance Snapshot")
        if finance_df.empty:
            st.info("No finance activity yet.")
        else:
            st.plotly_chart(finance_overview_chart(finance_df, theme=theme_mode), use_container_width=True)

    st.subheader("Incoming Orders")
    st.dataframe(
        orders_df[["order_number", "customer_name", "channel", "status", "payment_status", "total_amount", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )
    if not orders_df.empty:
        order_col, status_col = st.columns([1.4, 1])
        with order_col:
            selected_order_number = st.selectbox("Order to update", options=orders_df["order_number"].tolist(), key=f"order_select_{shop_id}")
        with status_col:
            next_status = st.selectbox("New status", options=["New", "Preparing", "Ready", "Completed", "Cancelled"], key=f"order_status_{shop_id}")
        if st.button("Update order status", key=f"update_order_{shop_id}", use_container_width=True):
            order_id = int(orders_df.loc[orders_df["order_number"] == selected_order_number, "id"].iloc[0])
            update_order_status(order_id, next_status)
            refresh_data()
            st.success(f"{selected_order_number} updated to {next_status}.")
            st.rerun()

        preview_order = orders_df.iloc[0].to_dict()
        preview_id = int(preview_order["id"])
        st.caption(f"Latest order items: {preview_order['order_number']}")
        items_df = load_order_items(preview_id)
        st.dataframe(items_df, use_container_width=True, hide_index=True)

        shop_info = get_shop_details(shop_id)
        invoice_path = generate_invoice_pdf(preview_order, items_df, shop_info)
        with open(invoice_path, "rb") as f:
            st.download_button(
                label=f"Download Invoice PDF ({preview_order['order_number']})",
                data=f,
                file_name=invoice_path.name,
                mime="application/pdf",
                key=f"dl_inv_{shop_id}",
                use_container_width=True
            )


def render_customer_menu(shop_id: str) -> None:
    shop = get_shop_details(shop_id)
    if not shop:
        st.error("Shop not found.")
        return
    theme_mode = st.session_state.get("theme_mode", "light")
    menu_df = get_menu_dataframe(shop_id)
    offers_df = get_offer_dataframe(shop_id)
    inject_theme_css(theme_mode)

    st.markdown(
        f"""
        <div class="hero" style="background: linear-gradient(135deg, rgba(30,58,138,0.95), rgba(37,99,235,0.85));">
          <span class="top-badge" style="background: rgba(255,255,255,0.2); border:none; color:white;">QR Ordering</span>
          <span class="top-badge" style="background: rgba(255,255,255,0.2); border:none; color:white;">{shop['shop_type']}</span>
          <h1 style="color: white; font-size: 2.2rem; margin-top: 1rem;">{shop['shop_name']}</h1>
          <p style="color: rgba(255,255,255,0.9); font-size: 1.1rem;">Browse our premium selection, apply offers, and order with seamless digital payments.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not offers_df.empty:
        st.markdown("### 🎁 Live Offers")
        for _, offer in offers_df.head(3).iterrows():
            st.markdown(
                f"<span class='pill' style='background:rgba(245,158,11,0.15); border-color:rgba(245,158,11,0.4); color:#b45309; font-weight:600;'>{offer['offer_code']} · {int(offer['discount_percent'])}% off above {format_currency(float(offer['min_order_amount']))}</span>",
                unsafe_allow_html=True,
            )

    with st.form(f"customer_menu_{shop_id}"):
        st.markdown("### 📝 Your Details")
        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input("Name")
        with col2:
            customer_phone = st.text_input("Mobile Number")
        
        col3, col4 = st.columns(2)
        with col3:
            table_ref = st.text_input("Table / Delivery Reference", value="Walk-in")
        with col4:
            offer_code = st.text_input("Offer Code")
            
        st.markdown("### 🍔 Select Items")
        chosen_items = []
        for _, row in menu_df.iterrows():
            st.markdown(
                f"""
                <div style="padding: 12px 16px; margin-bottom: 8px; border-radius: 12px; border: 1px solid rgba(59,130,246,0.15); background: var(--card-bg, rgba(255,255,255,0.02)); display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 700; font-size: 1.15rem;">{row['item_name']}</div>
                        <div style="font-size: 0.9rem; color: #888;">{row['category']} · Prep {int(row['prep_time_min'])}m</div>
                    </div>
                    <div style="font-weight: 700; color: #3b82f6; font-size: 1.1rem;">{format_currency(float(row['price']))}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            quantity = st.number_input(
                f"Qty for {row['item_name']}",
                min_value=0, max_value=20, value=0, step=1,
            )
            if quantity > 0:
                chosen_items.append({{
                    "item_name": row["item_name"],
                    "category": row["category"],
                    "quantity": int(quantity),
                    "price": float(row["price"])
                }})
        
        st.markdown("### 💳 Payment Method")
        payment_method = st.radio("Pay via", options=["Cash on Delivery", "eSewa", "Khalti", "FonePay"], horizontal=True)

        st.markdown("<br/>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Complete Checkout", use_container_width=True)

    if submitted:
        if not customer_name.strip():
            st.error("Please enter your name.")
        elif not chosen_items:
            st.error("Please select at least one menu item.")
        else:
            payment_status = f"Paid ({payment_method})" if payment_method != "Cash on Delivery" else "Pending"
            result = create_order(
                shop_id=shop_id,
                customer_name=customer_name.strip(),
                customer_phone=customer_phone.strip(),
                channel="QR Menu",
                table_ref=table_ref.strip(),
                items=chosen_items,
                offer_code=offer_code.strip() or None,
                payment_status=payment_status,
            )
            refresh_data()
            st.success(
                f"✅ **Order {result['order_number']} placed successfully.** Total: {format_currency(result['total_amount'])}"
                + (f" · Offer applied: {result['offer_applied']}" if result["offer_applied"] else "")
            )
            if payment_method != "Cash on Delivery":
                st.info(f"🔒 **Mock Gateway**: Redirecting to {payment_method}... Payment simulated successfully! Status updated to `{payment_status}`.")

    if st.button("Back to login", use_container_width=True):
        st.query_params.clear()
        st.rerun()


def login_view() -> None:
    st.markdown(
        """
        <div class="login-card">
          <span class="top-badge">RetailOS Nepal</span>
          <span class="top-badge">Forecasting + Orders + Finance</span>
          <h2 style="margin-top:0;">Retail Operating System</h2>
          <p class="small-note">A startup-style retail platform for forecasting demand, running QR ordering, managing offers, and monitoring financial growth from one dashboard.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    st.info("Demo accounts: `admin / admin123`, `kathmandu_manager / shop123`, `pokhara_manager / shop123`")

    shops_df = get_shop_table()
    if not shops_df.empty:
        menu_shop = st.selectbox("Try public menu / QR mode", options=shops_df["shop_id"].tolist(), format_func=lambda shop_id: shops_df.loc[shops_df["shop_id"] == shop_id, "shop_name"].iloc[0])
        if st.button("Open customer menu", use_container_width=True):
            st.query_params["menu_shop"] = menu_shop
            st.rerun()

    if submitted:
        user = authenticate_user(username, password)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user"] = user
            st.rerun()
        st.error("Invalid username or password.")


def render_common_dashboard(
    df: pd.DataFrame,
    shop_name_label: str,
    shop_id: str,
    selected_category: str,
    selected_product: str,
    forecast_days: int,
    safety_stock_days: int,
    model_name: str,
    admin_mode: bool = False,
) -> None:
    filtered_df = df.copy()
    if selected_category != "All":
        filtered_df = filtered_df[filtered_df["category"] == selected_category].copy()

    history = filtered_df[filtered_df["product_name"] == selected_product].groupby("date", as_index=False)["units_sold"].sum()
    forecast_df, model_used = forecast_product_demand(filtered_df, shop_id, selected_product, forecast_days, model_name)
    current_stock = latest_stock_level(filtered_df, shop_id, selected_product)
    recommendation = restock_recommendation(forecast_df, current_stock, safety_stock_days)
    fast_movers = top_fast_moving_products(filtered_df, shop_id)
    restock_df = build_restock_table(filtered_df, shop_id, safety_stock_days, forecast_days)
    best_selling_df = predict_best_selling_products(filtered_df, shop_id, forecast_days, model_name)
    theme_mode = st.session_state.get("theme_mode", "light")
    image_paths = list_dashboard_images(shop_id)
    menu_df = get_menu_dataframe(shop_id)
    offers_df = get_offer_dataframe(shop_id)
    orders_df = get_orders_dataframe(shop_id)
    finance_df = get_finance_dataframe(shop_id)
    scorecard = setup_scorecard(shop_id)
    order_metrics = order_summary(shop_id)

    total_units = int(filtered_df["units_sold"].sum())
    total_products = int(filtered_df["product_name"].nunique())
    total_categories = int(filtered_df["category"].nunique())
    revenue = float((filtered_df["units_sold"] * filtered_df["unit_price"]).sum()) if "unit_price" in filtered_df.columns else 0.0

    st.markdown(
        f"""
        <div class="hero">
          <span class="top-badge">{model_used} Forecasting</span>
          <span class="top-badge">{len(menu_df)} Menu Items</span>
          <span class="top-badge">{order_metrics['total_orders']} Orders</span>
          <h1>{shop_name_label}</h1>
          <p>Startup-ready retail workspace for demand forecasting, QR ordering, offer management, and financial operations. The experience is designed to be fast to set up for marts, cafes, restaurants, and neighborhood stores.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_setup_strip(scorecard)

    metrics = st.columns(4)
    metrics[0].metric("Total Units Sold", total_units)
    metrics[1].metric("Products", total_products)
    metrics[2].metric("Revenue", format_currency(revenue))
    metrics[3].metric("Average Order Value", format_currency(order_metrics["avg_order_value"]))

    second_metrics = st.columns(4)
    second_metrics[0].metric("Current Stock", recommendation["current_stock"])
    second_metrics[1].metric("Forecast Units", recommendation["forecast_total_units"])
    second_metrics[2].metric("Recommended Restock", recommendation["recommended_restock"])
    second_metrics[3].metric("Active Offers", int(len(offers_df)))

    tabs = st.tabs(["Overview", "Forecast & Restock", "Orders", "Menu & QR", "Offers & Finance", "Media & Sharing"])
    overview_tab, forecasting_tab, orders_tab, menu_tab, finance_tab, media_tab = tabs

    with overview_tab:
        row_one = st.columns([1.05, 1.05, 1.2])
        with row_one[0]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Category Mix")
            st.plotly_chart(category_share_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_one[1]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Demand Worm Chart")
            st.plotly_chart(performance_worm_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_one[2]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Revenue Trend")
            st.plotly_chart(revenue_trend_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        row_two = st.columns([1, 1, 1])
        with row_two[0]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Daily Sales")
            st.plotly_chart(daily_sales_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_two[1]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Top Products")
            st.plotly_chart(top_products_chart(filtered_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row_two[2]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Stockout Risk")
            st.plotly_chart(stock_risk_chart(restock_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Best-Selling Product Prediction")
        st.plotly_chart(best_selling_prediction_chart(best_selling_df, theme=theme_mode), use_container_width=True)
        st.dataframe(best_selling_df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Growth Signals")
        growth_cols = st.columns(3)
        growth_cols[0].info(f"Fastest demand is coming from **{fast_movers.iloc[0]['product_name']}**" if not fast_movers.empty else "Add more sales history to unlock growth signals.")
        growth_cols[1].info(f"Discounts contributed **{format_currency(order_metrics['discounts'])}** in promotional spend.")
        growth_cols[2].info(f"Current order completion rate is **{(order_metrics['completed_orders'] / order_metrics['total_orders'] * 100):.0f}%**." if order_metrics["total_orders"] else "Completion rate will appear once orders start coming in.")
        st.markdown("</div>", unsafe_allow_html=True)

    with forecasting_tab:
        row = st.columns([1.65, 1])
        with row[0]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader(f"Demand Forecast: {selected_product}")
            st.plotly_chart(sales_and_forecast_chart(history, forecast_df, theme=theme_mode), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with row[1]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Restock Recommendation")
            st.write(
                {
                    "Shop": shop_id,
                    "Product": selected_product,
                    "Forecast model": model_used,
                    "Average Daily Units": recommendation["avg_daily_units"],
                    "Safety Stock": recommendation["safety_stock"],
                    "Suggested Restock": recommendation["recommended_restock"],
                    "Risk": recommendation["stockout_risk"],
                }
            )
            export_controls(
                prefix=f"{shop_id}_forecast",
                dataframe=forecast_df,
                pdf_title="Demand Forecast Summary",
                pdf_lines=[
                    f"Shop: {shop_id}",
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
        st.subheader("Inventory Planning Table")
        st.dataframe(restock_df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with orders_tab:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        render_orders_management(shop_id, orders_df, finance_df, theme_mode)
        st.markdown("</div>", unsafe_allow_html=True)

    with menu_tab:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        menu_url = build_menu_url(shop_id)
        qr_col, link_col = st.columns([1, 1.5])
        with qr_col:
            st.subheader("Menu QR")
            maybe_render_qr(menu_url)
        with link_col:
            st.subheader("Shareable Menu Link")
            st.code(menu_url, language="text")
            if st.button("Open customer menu", key=f"open_menu_{shop_id}", use_container_width=True):
                st.query_params["menu_shop"] = shop_id
                st.rerun()
            st.caption("Use this link or QR to let customers browse the menu and place orders directly.")
        render_menu_management(shop_id, menu_df)
        st.markdown("</div>", unsafe_allow_html=True)

    with finance_tab:
        row = st.columns([1.1, 1])
        with row[0]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            render_offer_management(shop_id, offers_df)
            st.markdown("</div>", unsafe_allow_html=True)
        with row[1]:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Financial Statistics")
            st.metric("Gross Sales", format_currency(order_metrics["gross_sales"]))
            st.metric("Discount Spend", format_currency(order_metrics["discounts"]))
            st.metric("Net Sales", format_currency(order_metrics["net_sales"]))
            st.metric("Completed Orders", order_metrics["completed_orders"])
            st.markdown("</div>", unsafe_allow_html=True)
        if admin_mode:
            platform_mix = get_shop_type_overview()
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Shop Type Analytics")
            st.dataframe(platform_mix, use_container_width=True, hide_index=True)
            st.caption("This helps position the product for marts, cafes, restaurants, and local stores with different menu and revenue behavior.")
            st.markdown("</div>", unsafe_allow_html=True)

    with media_tab:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        if image_paths:
            st.subheader("Dashboard Image Gallery")
            gallery_cols = st.columns(min(3, len(image_paths)))
            for idx, image_path in enumerate(image_paths):
                with gallery_cols[idx % len(gallery_cols)]:
                    st.image(str(image_path), caption=image_path.name, use_container_width=True)
        else:
            st.info("No dashboard images uploaded yet. Use the sidebar to attach images for this shop.")

        if st.button("Create Investor Share Bundle", key=f"bundle_{shop_id}", use_container_width=True):
            files = [
                export_dataframe_csv(restock_df, f"{shop_id}_inventory_bundle"),
                export_summary_pdf(
                    "RetailOS Business Summary",
                    [
                        f"Shop: {shop_id}",
                        f"Products: {total_products}",
                        f"Revenue: {format_currency(revenue)}",
                        f"Orders: {order_metrics['total_orders']}",
                        f"Net Sales: {format_currency(order_metrics['net_sales'])}",
                        f"Forecast Product: {selected_product}",
                    ],
                    f"{shop_id}_bundle_summary",
                ),
            ] + image_paths
            bundle = create_share_bundle(f"{shop_id}_share_bundle", files)
            st.success(f"Share bundle created: {bundle.name}")
        st.markdown("</div>", unsafe_allow_html=True)


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

    top_row = st.columns(4)
    top_row[0].metric("Active Shops", int(shops_df["shop_id"].nunique()))
    top_row[1].metric("Platform Revenue", format_currency(summary_df["total_revenue"].sum()))
    top_row[2].metric("Platform Units Sold", int(summary_df["total_units_sold"].sum()))
    top_row[3].metric("Shop Types", int(shops_df["shop_type"].nunique()))

    if not using_temp:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Executive Shop Summary")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        export_controls(
            prefix="admin_shop_summary",
            dataframe=summary_df,
            pdf_title="Admin Shop Summary",
            pdf_lines=[
                f"Shops: {len(summary_df)}",
                f"Total Revenue: {format_currency(summary_df['total_revenue'].sum())}",
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
        st.caption("This dashboard is generated from uploaded files only and is not saved to the database.")
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
        admin_mode=True,
    )


def shop_view() -> None:
    user = st.session_state["user"]
    shop_id = user["shop_id"]
    shops_df = get_shop_table()
    shop_name = shops_df.loc[shops_df["shop_id"] == shop_id, "shop_name"].iloc[0]
    shop_df = get_sales_dataframe(shop_id)

    st.sidebar.success(f"Signed in as {user['username']} (Shop)")
    image_manager(shop_id)
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

    if st.query_params.get("menu_shop"):
        render_customer_menu(str(st.query_params.get("menu_shop")))
        return

    with st.sidebar:
        chosen_theme = st.selectbox(
            "Appearance",
            options=["light", "dark"],
            index=0 if st.session_state.get("theme_mode", "light") == "light" else 1,
        )
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
