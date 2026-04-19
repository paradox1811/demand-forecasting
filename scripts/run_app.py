from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent


if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(PROJECT_ROOT / "streamlit_app.py")],
        check=True,
    )
