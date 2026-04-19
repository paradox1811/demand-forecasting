from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.config import ASSETS_DIR


def save_dashboard_images(shop_key: str, files: list[tuple[str, bytes]]) -> list[Path]:
    target_dir = ASSETS_DIR / shop_key
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for index, (filename, content) in enumerate(files, start=1):
        suffix = Path(filename).suffix or ".png"
        safe_name = Path(filename).stem.replace(" ", "_").lower()
        output_path = target_dir / f"{timestamp}_{index}_{safe_name}{suffix}"
        output_path.write_bytes(content)
        saved_paths.append(output_path)
    return saved_paths


def list_dashboard_images(shop_key: str) -> list[Path]:
    target_dir = ASSETS_DIR / shop_key
    if not target_dir.exists():
        return []
    return sorted(target_dir.iterdir())
