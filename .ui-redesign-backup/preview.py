import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import streamlit as st
import importlib
import email_assistant.ui.theme as theme
importlib.reload(theme)
from email_assistant.ui.theme import apply_theme
from email_assistant.ui.app import _render_sidebar
from email_assistant.ui.pages import render_dashboard, render_compose, render_ai_assistant, render_settings
from email_assistant.ui.search import render_search
st.set_page_config(page_title="MailMind preview", layout="wide")
apply_theme()
if "current_page" not in st.session_state: st.session_state.current_page = "Dashboard"
_render_sidebar()
renderers = {"Dashboard": render_dashboard, "Compose Email": render_compose, "AI Assistant": render_ai_assistant, "Settings": render_settings, "Voice Email Search": render_search}
if st.session_state.current_page in renderers:
    renderers[st.session_state.current_page]()
else:
    st.info("Data-connected pages are verified through mocked regression tests.")
