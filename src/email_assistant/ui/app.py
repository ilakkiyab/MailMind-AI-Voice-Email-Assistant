"""Application shell and navigation for the Streamlit interface."""

import sqlite3
import streamlit as st

from .pages import PAGE_RENDERERS
from .theme import apply_theme
from .scheduled import start_scheduler
from .reminders import render_reminder_notifications


NAV_ITEMS = {
    "Dashboard": "⌂",
    "Compose Email": "✎",
    "Inbox": "▣",
    "Follow-ups": "↩",
    "Voice Email Search": "⌕",
    "AI Assistant": "✦",
    "Scheduled Emails": "◷",
    "Reminders": "♢",
    "Settings": "⚙",
}


def _select_page(page: str) -> None:
    st.session_state.current_page = page


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="brand">
                <div class="brand-mark">✦</div>
                <div><strong>MailMind</strong><small>VOICE EMAIL ASSISTANT</small></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("WORKSPACE")
        for label, icon in NAV_ITEMS.items():
            button_type = "primary" if st.session_state.current_page == label else "secondary"
            st.button(
                f"{icon}  {label}", key=f"nav_{label}", use_container_width=True,
                type=button_type, on_click=_select_page, args=(label,),
            )

        st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="status-card">
                <strong>Built around your workflow</strong>
                <p>Voice capture · AI assistance · Gmail<br>Review your drafts before sending.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def run_app():
    """Render the complete application."""

    st.set_page_config(
        page_title="MailMind | AI Voice Email Assistant",
        page_icon="📧",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Google account connection
    if st.user.is_logged_in:
        with st.sidebar:
            st.success(f"Connected: {st.user.email}")

            if st.button("Logout from Google"):
                st.logout()

    else:
        with st.sidebar:
            st.info("Connect Google to use Gmail and Calendar.")

            if st.button("Connect Google"):
                st.login()

    apply_theme()

    start_scheduler()

    try:
        initialize_database()
    except sqlite3.Error:
        st.warning(
            "Local database could not start. "
            "Check local data folder permissions and restart MailMind."
        )

    if "current_page" not in st.session_state:
        st.session_state.current_page = "Dashboard"

    _render_sidebar()

    current_page = st.session_state.current_page
    page_renderer = PAGE_RENDERERS[current_page]
    page_renderer()
