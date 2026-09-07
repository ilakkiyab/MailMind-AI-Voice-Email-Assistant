"""Visual theme shared by all Streamlit pages."""

import streamlit as st


def apply_theme() -> None:
    """Inject the application CSS."""
    st.markdown(
        """
        <style>
        :root { --ink:#14213d; --muted:#526078; }
        .stApp { font-family:Inter,Segoe UI,Arial,sans-serif; }
        .stApp { background:#f8faff; }
        .block-container { max-width:1200px; padding:4.5rem 2.5rem 3rem; }
        [data-testid="stSidebar"] { background:#10172a; border-right:1px solid #202a42; }
        [data-testid="stSidebar"] { color:#e5eaf5; }
        [data-testid="stSidebar"] .stCaption { color:#aebbd4; font-size:.69rem; letter-spacing:.14em; margin:2rem 0 .5rem; }
        .brand { display:flex; gap:.75rem; align-items:center; padding:.25rem 0 1rem; }
        .brand-mark { width:38px; height:38px; display:grid; place-items:center; border-radius:11px; background:#4f46c8; font-size:1.2rem; }
        .brand strong { color:white; font-size:1.15rem; }
        .brand small { display:block; color:#aebbd4; font-size:.62rem; letter-spacing:.11em; margin-top:.1rem; }
        .sidebar-spacer { height:1rem; }
        .status-card { padding:.9rem; border:1px solid #293650; background:#172138; border-radius:12px; font-size:.82rem; }
        .status-card p { color:#aebbd4!important; margin:.35rem 0 0; font-size:.72rem; line-height:1.4; }
        .status-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:#5ee3a1; margin-right:.45rem;  }
        .eyebrow { color:#4b5eb6; font-weight:700; font-size:.72rem; letter-spacing:.13em; text-transform:uppercase; margin-bottom:.4rem; }
        [data-testid="stMain"] h1 { color:var(--ink)!important; letter-spacing:-.04em!important; font-size:2rem!important; margin:0!important; }
        .page-subtitle { color:var(--muted); font-size:1rem; margin:.4rem 0 1.25rem; }
        .hero { padding:1.7rem 2rem; border-radius:16px; background:#17264a; color:white; margin:.25rem 0 1.25rem; border:1px solid #273e7f; }
        .hero h2 { color:#fff!important; font-size:1.75rem; margin:0 0 .55rem; letter-spacing:-.025em; }
        .hero p { color:#cdd7f4; max-width:610px; margin:0; line-height:1.6; }
        .feature-card { min-height:185px; padding:1.15rem; background:#fff; border:1px solid #dce3ef; border-radius:12px; }
        .feature-icon { width:32px; height:32px; display:grid; place-items:center; background:#eef1ff; border-radius:12px; font-size:1.15rem; margin-bottom:.75rem; }
        .feature-card h3 { color:#1b2948; font-size:1.02rem; margin:0 0 .4rem; }
        .feature-card p { color:#526078; font-size:.82rem; line-height:1.5; margin:0; }
        .section-title { color:#253352; font-size:1rem; font-weight:700; margin:0 0 .8rem; }
        [data-testid="stForm"] { border:1px solid #e5e9f2; border-radius:12px; padding:1.25rem; background:#fff; }
        .voice-panel { padding:1.15rem 1.25rem; border-radius:14px; border:1px dashed #bdc7e7; background:#f7f8ff; margin:.35rem 0 1rem; }
        .voice-panel strong { color:#26375d; }
        .voice-panel p { color:#526078; font-size:.8rem; margin:.25rem 0 0; }
        .placeholder { padding:1.5rem; text-align:left; border:1px solid #e6eaf2; background:white; border-radius:18px; color:#526078; margin-top:1.5rem; }
        .placeholder span { font-size:2rem; display:block; margin-bottom:.65rem; }
        /* Explicit surfaces prevent an inherited dark theme from mixing palettes. */
        [data-testid="stMain"] { color:#14213d; color-scheme:light; }
        [data-testid="stHeader"] { background:#f8faff; color:#14213d; }
        [data-testid="stMain"] :is(h2,h3,h4,h5,h6) { color:#14213d; }
        [data-testid="stMain"] :is([data-testid="stText"], [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"]) { color:#14213d; }
        [data-testid="stMain"] [data-testid="stCaptionContainer"] { color:#526078; }
        [data-testid="stSidebar"] :is([data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"]) { color:#dce3f5; }
        [data-testid="stMain"] [data-testid="stMarkdownContainer"] a { color:#4338ca; }

        /* Widget buttons only: do not recolor toolbar, expander or audio icons. */
        :is([data-testid="stMain"], [data-testid="stSidebar"]) :is(.stButton, .stFormSubmitButton, .stDownloadButton, [data-testid="stFileUploader"]) button {
            --button-bg:#eef2ff; --button-hover:#dfe5ff; --button-active:#cdd7ff;
            --button-ink:#283b86; --button-border:#9caedc;
            background:var(--button-bg)!important; color:var(--button-ink)!important;
            border:1px solid var(--button-border)!important; border-radius:10px; font-weight:600;
            opacity:1!important;
        }
        :is([data-testid="stMain"], [data-testid="stSidebar"]) :is(.stButton, .stFormSubmitButton, .stDownloadButton) button[kind="primary"] {
            --button-bg:#4f46c8; --button-hover:#4338ad; --button-active:#37308d;
            --button-ink:#fff; --button-border:#4f46c8;
        }
        [data-testid="stSidebar"] .stButton button[kind="secondary"] {
            --button-bg:#10172a; --button-hover:#243251; --button-active:#304165;
            --button-ink:#e5eaf5; --button-border:transparent;
        }
        [data-testid="stSidebar"] .stButton button { text-align:left; justify-content:flex-start; padding:.62rem .85rem; }
        [data-testid="stSidebar"] .stButton button > div { justify-content:flex-start; }
        [data-testid="stSidebar"] .stButton button [data-testid="stMarkdownContainer"] { width:100%; text-align:left; }
        :is([data-testid="stMain"], [data-testid="stSidebar"]) :is(.stButton, .stFormSubmitButton, .stDownloadButton, [data-testid="stFileUploader"]) button:is(:hover,:focus) {
            background:var(--button-hover)!important; color:var(--button-ink)!important;
        }
        :is([data-testid="stMain"], [data-testid="stSidebar"]) :is(.stButton, .stFormSubmitButton, .stDownloadButton, [data-testid="stFileUploader"]) button:active {
            background:var(--button-active)!important; color:var(--button-ink)!important;
        }
        :is([data-testid="stMain"], [data-testid="stSidebar"]) :is(.stButton, .stFormSubmitButton, .stDownloadButton, [data-testid="stFileUploader"]) button:disabled {
            background:#e2e8f0!important; color:#475569!important; border-color:#94a3b8!important; opacity:1!important;
        }
        /* Markdown wrappers, paragraphs and spans must inherit the button state. */
        :is([data-testid="stMain"], [data-testid="stSidebar"]) :is(.stButton, .stFormSubmitButton, .stDownloadButton, [data-testid="stFileUploader"]) button :is(div,p,span,strong,em,small) { color:inherit!important; }
        :is([data-testid="stMain"], [data-testid="stSidebar"]) button:focus-visible,
        [data-testid="stMain"] summary:focus-visible { outline:3px solid #818cf8!important; outline-offset:3px; }

        [data-testid="stMain"] :is([data-testid="stTextInput"], [data-testid="stTextArea"], [data-testid="stSelectbox"], [data-testid="stDateInput"], [data-testid="stTimeInput"]) :is(input,textarea,[data-baseweb="select"] > div) {
            background:#fff!important; color:#14213d!important; -webkit-text-fill-color:#14213d;
            border-radius:10px; caret-color:#4338ca;
        }
        [data-testid="stMain"] :is([data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div) { background:#fff; border:1px solid #94a3b8; }
        [data-testid="stMain"] :is(input,textarea)::placeholder { color:#59677d!important; -webkit-text-fill-color:#59677d; opacity:1; }
        [data-testid="stMain"] :is([data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"]):focus-within { outline:2px solid #6366f1; outline-offset:2px; }
        [data-baseweb="popover"] [role="listbox"] { background:#fff; color:#14213d; }
        [data-baseweb="popover"] [role="option"] { background:#fff; color:#14213d; }
        [data-baseweb="popover"] [role="option"]:is(:hover,[aria-selected="true"]) { background:#e0e7ff; color:#283b86; }

        [data-testid="stMain"] [data-testid="stExpander"] details { background:#fff; border:1px solid #cbd5e1; border-radius:10px; }
        [data-testid="stMain"] [data-testid="stExpander"] summary { background:#f1f4fc!important; color:#14213d!important; border-radius:9px; }
        [data-testid="stMain"] [data-testid="stExpander"] summary:is(:hover,:focus,:active),
        [data-testid="stMain"] [data-testid="stExpander"] details[open] > summary { background:#e0e7ff!important; color:#283b86!important; }
        [data-testid="stMain"] [data-testid="stExpander"] summary :is(div,p,span) { color:inherit!important; }
        [data-testid="stMain"] :is([data-testid="stAudioInput"], [data-testid="stFileUploaderDropzone"]) { background:#f1f4fc; color:#14213d; border-radius:10px; color-scheme:light; }
        [data-testid="stMain"] [data-testid="stAudioInput"] button { background:#e0e7ff!important; color:#283b86!important; opacity:1; }
        [data-testid="stMain"] [data-testid="stAudioInput"] button:is(:hover,:focus,:active,[aria-pressed="true"]) { background:#cdd7ff!important; color:#14213d!important; }
        [data-testid="stMain"] [data-testid="stAudioInput"] button:disabled { background:#e2e8f0!important; color:#475569!important; }
        [data-testid="stMain"] [data-testid="stAudioInput"] button :is(div,p,span) { color:inherit!important; }

        /* Shared surfaces, semantic states and content hierarchy. */
        [data-testid="stMain"] :is(h2,h3) { letter-spacing:-.02em; }
        [data-testid="stMain"] h2 { font-size:1.4rem; }
        [data-testid="stMain"] h3 { font-size:1.1rem; }
        [data-testid="stMain"] [data-testid="stText"] { font-family:inherit; line-height:1.6; overflow-wrap:anywhere; white-space:pre-wrap; }
        [data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] > div { border-color:#dce3ef!important; border-radius:12px!important; background:#fff; }
        [data-testid="stMain"] [data-testid="stAlert"] { border-radius:10px; padding:.7rem 1rem; font-size:.9rem; }
        [data-testid="stMain"] [data-testid="stAlert"][data-baseweb="notification"] { box-shadow:none; }
        [data-testid="stMain"] [data-testid="stAlertContainer"] :is(p,li) { color:inherit; }
        [data-testid="stMain"] [data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) { background:#ecfdf5; color:#166534; border:1px solid #a7d9bd; }
        [data-testid="stMain"] [data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) { background:#fffbeb; color:#854d0e; border:1px solid #e8cd83; }
        [data-testid="stMain"] [data-testid="stAlert"]:has([data-testid="stAlertContentError"]) { background:#fff1f2; color:#9f1239; border:1px solid #f0b5bf; }
        [data-testid="stMain"] [data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) { background:#eef2ff; color:#283b86; border:1px solid #c7d2fe; }
        .hero .hero-kicker { color:#cdd7f4; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; margin-bottom:.6rem; }
        [data-testid="stMain"] [class*="st-key-priority_badge_"] [data-testid="stText"] { display:inline-block; padding:.2rem .7rem; border-radius:999px; font-size:.78rem; font-weight:650; }
        [data-testid="stMain"] [class*="st-key-priority_badge_HIGH"] [data-testid="stText"] { background:#fff1f2; color:#9f1239; }
        [data-testid="stMain"] [class*="st-key-priority_badge_MEDIUM"] [data-testid="stText"] { background:#fffbeb; color:#854d0e; }
        [data-testid="stMain"] [class*="st-key-priority_badge_LOW"] [data-testid="stText"] { background:#ecfdf5; color:#166534; }
        .status-badge { display:inline-block; padding:.2rem .7rem; border-radius:999px; font-size:.78rem; font-weight:650; margin-bottom:.5rem; }
        .status-warning { background:#fffbeb; color:#854d0e; }
        .status-info { background:#eef2ff; color:#283b86; }
        .status-success { background:#ecfdf5; color:#166534; }
        [data-testid="stMain"] :is([class*="st-key-email_card_"], [class*="st-key-search_card_"]) > [data-testid="stElementContainer"]:first-child [data-testid="stText"] { font-weight:600; font-size:1rem; line-height:1.7; }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.65rem; }
        [data-testid="stMain"] hr { margin:1rem 0; border-color:#dce3ef; }
        @media (max-width:1100px) { .block-container { padding:4.5rem 1.5rem 2.5rem; } .feature-card { min-height:230px; } }
        @media (max-width:850px) { [data-testid="stMain"] [data-testid="stHorizontalBlock"] { flex-wrap:wrap; } [data-testid="stMain"] [data-testid="stColumn"] { min-width:min(100%,240px); flex:1 1 240px; } .feature-card { min-height:0; } }
        @media (max-width:700px) { .block-container { padding:4.5rem 1rem 3rem; } h1 { font-size:2rem!important; } .hero { padding:1.5rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    """Render a consistent heading with escaped display copy."""
    from html import escape
    st.markdown(f'<div class="eyebrow">{escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="page-subtitle">{escape(subtitle)}</p>', unsafe_allow_html=True)


def followup_badge(status: str) -> None:
    """Only trusted status vocabulary is rendered as markup."""
    styles = {"Follow-up Needed": "warning", "Waiting": "info", "Replied": "success"}
    if status in styles:
        st.markdown(f'<span class="status-badge status-{styles[status]}">{status}</span>', unsafe_allow_html=True)
