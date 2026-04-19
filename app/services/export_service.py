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
