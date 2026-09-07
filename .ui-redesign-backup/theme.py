"""Visual theme shared by all Streamlit pages."""

import streamlit as st


def apply_theme() -> None:
    """Inject the application CSS."""
    st.markdown(
        """
        <style>
        :root { --ink:#14213d; --muted:#526078; }
        .stApp { font-family:Inter,Segoe UI,Arial,sans-serif; }
        .stApp { background:linear-gradient(135deg,#f8faff 0%,#fff 48%,#f8f6ff 100%); }
        .block-container { max-width:1200px; padding:2.6rem 3rem 4rem; }
        [data-testid="stSidebar"] { background:#10172a; border-right:1px solid #202a42; }
        [data-testid="stSidebar"] { color:#e5eaf5; }
        [data-testid="stSidebar"] .stCaption { color:#aebbd4; font-size:.69rem; letter-spacing:.14em; margin:2rem 0 .5rem; }
        .brand { display:flex; gap:.75rem; align-items:center; padding:.25rem 0 1rem; }
        .brand-mark { width:38px; height:38px; display:grid; place-items:center; border-radius:11px; background:linear-gradient(135deg,#657cff,#945cff); font-size:1.2rem; }
        .brand strong { color:white; font-size:1.15rem; }
        .brand small { display:block; color:#aebbd4; font-size:.56rem; letter-spacing:.11em; margin-top:.1rem; }
        .sidebar-spacer { height:3rem; }
        .status-card { padding:.9rem; border:1px solid #293650; background:#172138; border-radius:12px; font-size:.82rem; }
        .status-card p { color:#aebbd4!important; margin:.35rem 0 0; font-size:.72rem; line-height:1.4; }
        .status-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:#5ee3a1; margin-right:.45rem; box-shadow:0 0 8px #5ee3a1; }
        .eyebrow { color:#4b5eb6; font-weight:700; font-size:.72rem; letter-spacing:.13em; text-transform:uppercase; margin-bottom:.4rem; }
        [data-testid="stMain"] h1 { color:var(--ink)!important; letter-spacing:-.04em!important; font-size:2.5rem!important; margin:0!important; }
        .page-subtitle { color:var(--muted); font-size:1rem; margin:.45rem 0 2rem; }
        .hero { padding:2.2rem 2.4rem; border-radius:22px; background:linear-gradient(120deg,#17264a,#273e7f 68%,#6b55c8); color:white; margin:1.6rem 0 2rem; box-shadow:0 20px 50px rgba(40,57,110,.16); }
        .hero h2 { color:#fff!important; font-size:1.75rem; margin:0 0 .55rem; letter-spacing:-.025em; }
        .hero p { color:#cdd7f4; max-width:610px; margin:0; line-height:1.6; }
        .feature-card { min-height:168px; padding:1.35rem; background:rgba(255,255,255,.9); border:1px solid #e7ebf4; border-radius:16px; box-shadow:0 7px 24px rgba(31,45,88,.05); }
        .feature-icon { width:42px; height:42px; display:grid; place-items:center; background:#eef1ff; border-radius:12px; font-size:1.15rem; margin-bottom:1rem; }
        .feature-card h3 { color:#1b2948; font-size:1.02rem; margin:0 0 .4rem; }
        .feature-card p { color:#526078; font-size:.82rem; line-height:1.5; margin:0; }
        .section-title { color:#253352; font-size:1rem; font-weight:700; margin:0 0 .8rem; }
        [data-testid="stForm"] { border:1px solid #e5e9f2; border-radius:18px; padding:1.5rem 1.6rem 1.2rem; background:rgba(255,255,255,.88); box-shadow:0 9px 30px rgba(31,45,88,.05); }
        .voice-panel { padding:1.15rem 1.25rem; border-radius:14px; border:1px dashed #bdc7e7; background:#f7f8ff; margin:.35rem 0 1rem; }
        .voice-panel strong { color:#26375d; }
        .voice-panel p { color:#526078; font-size:.8rem; margin:.25rem 0 0; }
        .placeholder { padding:2rem; text-align:center; border:1px solid #e6eaf2; background:white; border-radius:18px; color:#526078; margin-top:1.5rem; }
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

        @media (max-width:700px) { .block-container { padding:1.5rem 1rem 3rem; } h1 { font-size:2rem!important; } .hero { padding:1.5rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )
