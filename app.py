"""Streamlit entry point for the AI Voice-Powered Email Assistant."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from email_assistant.ui.app import run_app


if __name__ == "__main__":
    run_app()