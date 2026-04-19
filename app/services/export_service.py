from __future__ import annotations

from datetime import datetime
from pathlib import Path
import zipfile

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.config import REPORTS_DIR


def export_dataframe_csv(df: pd.DataFrame, prefix: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = REPORTS_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(file_path, index=False)
    return file_path


def export_summary_pdf(title: str, lines: list[str], prefix: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = REPORTS_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf = canvas.Canvas(str(file_path), pagesize=A4)
    width, height = A4
    y = height - 60
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, title)
    y -= 28
    pdf.setFont("Helvetica", 11)
    for line in lines:
        pdf.drawString(40, y, line)
        y -= 20
        if y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 11)
            y = height - 60
    pdf.save()
    return file_path


def create_share_bundle(prefix: str, files: list[Path]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    bundle_path = REPORTS_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in files:
            if file_path.exists():
                zip_file.write(file_path, arcname=file_path.name)
    return bundle_path


def generate_invoice_pdf(order: dict, items: pd.DataFrame, shop_details: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    invoice_num = order.get("order_number", "INV")
    file_path = REPORTS_DIR / f"Invoice_{invoice_num}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    pdf = canvas.Canvas(str(file_path), pagesize=A4)
    width, height = A4
    
    # Header
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(40, height - 60, "INVOICE")
    
    # Shop Details
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, height - 100, shop_details.get("shop_name", "RetailOS Store"))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, height - 115, f"{shop_details.get('shop_type', 'Retail')} · Nepal")
    
    # Order Details (Right aligned)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(width - 40, height - 100, f"Invoice #: {invoice_num}")
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(width - 40, height - 115, f"Date: {order.get('created_at', datetime.now().strftime('%Y-%m-%d'))}")
    pdf.drawRightString(width - 40, height - 130, f"Payment: {order.get('payment_status', 'Pending')}")
    pdf.drawRightString(width - 40, height - 145, f"Customer: {order.get('customer_name', 'Walk-in')}")
    pdf.drawRightString(width - 40, height - 160, f"Phone: {order.get('customer_phone', '')}")
    
    # Line Items Header
    y = height - 210
    pdf.setStrokeColorRGB(0.8, 0.8, 0.8)
    pdf.line(40, y + 15, width - 40, y + 15)
    
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(45, y, "Item Description")
    pdf.drawString(320, y, "Qty")
    pdf.drawString(380, y, "Unit Price")
    pdf.drawRightString(width - 45, y, "Total")
    
    pdf.line(40, y - 10, width - 40, y - 10)
    y -= 30
    
    # Line Items
    pdf.setFont("Helvetica", 11)
    for _, row in items.iterrows():
        item_name = str(row.get("item_name", "Item"))
        qty = int(row.get("quantity", 0))
        price = float(row.get("unit_price", row.get("price", 0.0)))
        total = float(row.get("total_price", qty * price))
        
        pdf.drawString(45, y, item_name)
        pdf.drawString(320, y, str(qty))
        pdf.drawString(380, y, f"Rs. {price:,.2f}")
        pdf.drawRightString(width - 45, y, f"Rs. {total:,.2f}")
        
        y -= 25
        if y < 100:
            pdf.showPage()
            pdf.setFont("Helvetica", 11)
            y = height - 60
            
    # Totals
    pdf.line(40, y, width - 40, y)
    y -= 25
    
    total_amount = float(order.get("total_amount", items["total_price"].sum() if "total_price" in items.columns else 0.0))
    discount_applied = float(order.get("discount_applied", 0.0))
    
    if discount_applied > 0:
        pdf.setFont("Helvetica", 11)
        pdf.drawRightString(width - 150, y, "Subtotal:")
        pdf.drawRightString(width - 45, y, f"Rs. {(total_amount + discount_applied):,.2f}")
        y -= 20
        pdf.drawRightString(width - 150, y, f"Discount ({order.get('offer_applied', '')}):")
        pdf.drawRightString(width - 45, y, f"- Rs. {discount_applied:,.2f}")
        y -= 20
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(width - 150, y, "Total Amount:")
    pdf.drawRightString(width - 45, y, f"Rs. {total_amount:,.2f}")
    
    # Footer
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawCentredString(width / 2, 50, "Thank you for your business!")
    pdf.drawCentredString(width / 2, 35, "Generated by RetailOS Nepal")
    
    pdf.save()
    return file_path
