import streamlit as st

def apply_custom_css():
    st.markdown("""
    <style>
    /* =====================================================
       DESIGN TOKENS — Central color system (WCAG AA)
       ===================================================== */
    :root {
        /* Backgrounds */
        --bg-base:           #0d1117;
        --bg-surface:        #161b27;
        --bg-surface-2:      #1e2736;
        --bg-surface-3:      #252f42;

        /* Text — all meet ≥4.5:1 on dark backgrounds */
        --text-primary:      #f0f4f8;   /* near-white, 15:1 on --bg-base */
        --text-secondary:    #c8d3e0;   /* soft-blue-grey, 8:1 */
        --text-muted:        #8fa3bc;   /* readable muted, 4.6:1 */
        --text-disabled:     #52687a;   /* truly disabled, intentionally lower */

        /* Inputs */
        --input-bg:          #1a2236;
        --input-bg-hover:    #1e2a42;
        --input-text:        #edf2f7;   /* 13:1 on --input-bg */
        --input-border:      #3a4d66;
        --input-border-focus:#4d82c8;
        --placeholder:       #7a93ad;   /* 4.6:1 on --input-bg */

        /* Brand / Accent */
        --accent:            #4d9ef7;   /* blue, 5.2:1 on dark bg */
        --accent-hover:      #6aafff;
        --accent-muted:      rgba(77, 158, 247, 0.15);

        /* Semantic */
        --success:           #4ade80;
        --success-bg:        rgba(34, 197, 94, 0.12);
        --warning:           #fbbf24;
        --warning-bg:        rgba(245, 158, 11, 0.12);
        --error:             #f87171;
        --error-bg:          rgba(239, 68, 68, 0.12);
        --info:              #38bdf8;
        --info-bg:           rgba(56, 189, 248, 0.12);

        /* Borders */
        --border:            #2d3f55;
        --border-strong:     #3a4d66;

        /* Sidebar */
        --sidebar-bg:        #111827;
        --sidebar-border:    #1f2d3d;
    }

    /* =====================================================
       BASE & BODY
       ===================================================== */
    .stApp, .stApp > div {
        background-color: var(--bg-base) !important;
        color: var(--text-primary) !important;
    }

    /* =====================================================
       STREAMLIT GLOBAL TEXT
       ===================================================== */
    .stApp p, .stApp span, .stApp div,
    .stApp li, .stApp label {
        color: var(--text-primary);
    }

    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
    }

    /* =====================================================
       SIDEBAR
       ===================================================== */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }
    [data-testid="stSidebar"] * {
        color: var(--text-primary) !important;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown span {
        color: var(--text-secondary) !important;
    }
    [data-testid="stSidebar"] h3 {
        color: var(--accent) !important;
    }
    /* Sidebar radio options */
    [data-testid="stSidebar"] .stRadio label {
        color: var(--text-secondary) !important;
        font-size: 14px;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        color: var(--text-primary) !important;
    }
    /* Sidebar horizontal dividers */
    [data-testid="stSidebar"] hr {
        border-color: var(--border) !important;
    }

    /* =====================================================
       FORM LABELS — fix the #1 reported issue
       ===================================================== */
    /* Every widget label Streamlit renders */
    .stTextInput > label,
    .stTextArea > label,
    .stSelectbox > label,
    .stMultiSelect > label,
    .stSlider > label,
    .stNumberInput > label,
    .stFileUploader > label,
    .stCheckbox > label,
    .stRadio > label,
    .stDateInput > label,
    .stTimeInput > label,
    .stColorPicker > label {
        color: var(--text-secondary) !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        margin-bottom: 4px !important;
    }

    /* Subheader labels inside expanders etc */
    .stMarkdown h4, .stMarkdown h5 {
        color: var(--text-secondary) !important;
    }

    /* =====================================================
       TEXT INPUTS & NUMBER INPUTS
       ===================================================== */
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stTimeInput input {
        background-color: var(--input-bg) !important;
        color: var(--input-text) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 6px !important;
        caret-color: var(--accent) !important;
    }
    .stTextInput input:focus,
    .stNumberInput input:focus {
        border-color: var(--input-border-focus) !important;
        box-shadow: 0 0 0 2px rgba(77, 158, 247, 0.2) !important;
    }
    .stTextInput input::placeholder,
    .stNumberInput input::placeholder {
        color: var(--placeholder) !important;
        opacity: 1 !important;
    }
    .stTextInput input:hover,
    .stNumberInput input:hover {
        background-color: var(--input-bg-hover) !important;
        border-color: var(--border-strong) !important;
    }

    /* =====================================================
       TEXTAREA
       ===================================================== */
    .stTextArea textarea {
        background-color: var(--input-bg) !important;
        color: var(--input-text) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 6px !important;
        caret-color: var(--accent) !important;
    }
    .stTextArea textarea:focus {
        border-color: var(--input-border-focus) !important;
        box-shadow: 0 0 0 2px rgba(77, 158, 247, 0.2) !important;
    }
    .stTextArea textarea::placeholder {
        color: var(--placeholder) !important;
        opacity: 1 !important;
    }
    .stTextArea textarea:hover {
        background-color: var(--input-bg-hover) !important;
        border-color: var(--border-strong) !important;
    }

    /* =====================================================
       SELECT / DROPDOWN
       ===================================================== */
    /* Outer container */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background-color: var(--input-bg) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 6px !important;
    }
    .stSelectbox > div > div:hover,
    .stMultiSelect > div > div:hover {
        border-color: var(--border-strong) !important;
        background-color: var(--input-bg-hover) !important;
    }
    /* Selected value text */
    .stSelectbox [data-baseweb="select"] span,
    .stSelectbox [data-baseweb="select"] div,
    .stMultiSelect [data-baseweb="select"] span,
    .stMultiSelect [data-baseweb="select"] div {
        color: var(--input-text) !important;
    }
    /* Placeholder text in select */
    .stSelectbox [data-baseweb="select"] [data-testid="stSelectboxValue"],
    .stSelectbox input {
        color: var(--input-text) !important;
    }
    /* Dropdown arrow / chevron */
    .stSelectbox svg, .stMultiSelect svg {
        fill: var(--text-muted) !important;
    }
    /* Dropdown menu */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [role="listbox"] {
        background-color: var(--bg-surface-2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
    }
    /* Dropdown options */
    [role="option"] {
        color: var(--text-primary) !important;
        background-color: transparent !important;
    }
    [role="option"]:hover,
    [aria-selected="true"][role="option"] {
        background-color: var(--accent-muted) !important;
        color: var(--accent) !important;
    }

    /* =====================================================
       SLIDER
       ===================================================== */
    .stSlider [data-baseweb="slider"] [data-testid="stTickBar"] {
        color: var(--text-muted) !important;
    }
    .stSlider .stMarkdown p {
        color: var(--text-muted) !important;
    }

    /* =====================================================
       FILE UPLOADER
       ===================================================== */
    [data-testid="stFileUploader"] {
        background-color: var(--input-bg) !important;
        border: 1px dashed var(--input-border) !important;
        border-radius: 6px !important;
    }
    [data-testid="stFileUploader"] * {
        color: var(--text-secondary) !important;
    }

    /* =====================================================
       BUTTONS
       ===================================================== */
    /* Primary */
    .stButton > button[kind="primary"] {
        background-color: var(--accent) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        transition: background-color 0.18s, transform 0.1s;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--accent-hover) !important;
        transform: translateY(-1px);
    }
    /* Secondary / Default */
    .stButton > button,
    .stButton > button[kind="secondary"] {
        background-color: var(--bg-surface-2) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        transition: background-color 0.18s, border-color 0.18s;
    }
    .stButton > button:hover,
    .stButton > button[kind="secondary"]:hover {
        background-color: var(--bg-surface-3) !important;
        border-color: var(--accent) !important;
        color: var(--text-primary) !important;
    }
    /* Download button */
    .stDownloadButton > button {
        background-color: var(--success-bg) !important;
        color: var(--success) !important;
        border: 1px solid var(--success) !important;
        border-radius: 6px !important;
    }

    /* =====================================================
       TABS
       ===================================================== */
    [data-baseweb="tab-list"] {
        background-color: var(--bg-surface) !important;
        border-bottom: 1px solid var(--border) !important;
        gap: 4px;
    }
    [data-baseweb="tab"] {
        background-color: transparent !important;
        color: var(--text-muted) !important;
        border-bottom: 2px solid transparent !important;
        font-weight: 500 !important;
        padding: 10px 16px !important;
    }
    [data-baseweb="tab"]:hover {
        color: var(--text-primary) !important;
        background-color: var(--bg-surface-2) !important;
    }
    [aria-selected="true"][data-baseweb="tab"] {
        color: var(--accent) !important;
        border-bottom-color: var(--accent) !important;
        background-color: transparent !important;
    }

    /* =====================================================
       EXPANDERS
       ===================================================== */
    [data-testid="stExpander"] {
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        margin-bottom: 8px !important;
    }
    [data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }
    [data-testid="stExpander"] summary:hover {
        color: var(--accent) !important;
    }
    [data-testid="stExpander"] svg {
        fill: var(--text-muted) !important;
    }
    [data-testid="stExpander"] > div {
        border-top: 1px solid var(--border) !important;
        padding-top: 12px !important;
    }

    /* =====================================================
       DATAFRAMES / TABLES (Glide Data Grid container)
       ===================================================== */
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
    }

    /* =====================================================
       ALERTS & MESSAGES
       ===================================================== */
    /* st.success */
    [data-testid="stAlert"][data-type="success"],
    div[class*="AlertSuccess"] {
        background-color: var(--success-bg) !important;
        border-left: 4px solid var(--success) !important;
        border-radius: 6px !important;
        color: var(--success) !important;
    }
    /* st.error */
    [data-testid="stAlert"][data-type="error"],
    div[class*="AlertError"] {
        background-color: var(--error-bg) !important;
        border-left: 4px solid var(--error) !important;
        border-radius: 6px !important;
        color: var(--error) !important;
    }
    /* st.warning */
    [data-testid="stAlert"][data-type="warning"],
    div[class*="AlertWarning"] {
        background-color: var(--warning-bg) !important;
        border-left: 4px solid var(--warning) !important;
        border-radius: 6px !important;
        color: var(--warning) !important;
    }
    /* st.info */
    [data-testid="stAlert"][data-type="info"],
    div[class*="AlertInfo"] {
        background-color: var(--info-bg) !important;
        border-left: 4px solid var(--info) !important;
        border-radius: 6px !important;
        color: var(--info) !important;
    }
    /* Generic Streamlit notification elements */
    .element-container [data-testid="stNotification"] {
        color: var(--text-primary) !important;
    }

    /* =====================================================
       CHECKBOX & RADIO
       ===================================================== */
    .stCheckbox label,
    .stRadio label span {
        color: var(--text-secondary) !important;
        font-size: 14px !important;
    }
    .stCheckbox label:hover span,
    .stRadio label:hover span {
        color: var(--text-primary) !important;
    }

    /* =====================================================
       SPINNER / PROGRESS
       ===================================================== */
    [data-testid="stSpinner"] {
        color: var(--accent) !important;
    }

    /* =====================================================
       CAPTION & SMALL TEXT
       ===================================================== */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--text-muted) !important;
        font-size: 12px !important;
    }

    /* st.code blocks */
    .stCodeBlock {
        background-color: var(--bg-surface-2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
    }
    .stCodeBlock code {
        color: var(--text-primary) !important;
    }

    /* =====================================================
       HORIZONTAL RULES
       ===================================================== */
    hr {
        border-color: var(--border) !important;
        margin: 16px 0 !important;
    }

    /* =====================================================
       STREAMLIT MAIN CONTENT AREA PADDING
       ===================================================== */
    .block-container {
        padding-top: 1rem !important;
    }

    /* =====================================================
       TOP BAR HEADER (existing class, updated to use tokens)
       ===================================================== */
    .main-header {
        background: linear-gradient(90deg, var(--bg-surface-2) 0%, var(--bg-surface) 100%);
        border-bottom: 2px solid var(--accent);
        padding: 18px 24px;
        border-radius: 8px;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .brand-title {
        font-size: 24px;
        font-weight: 700;
        color: var(--accent);
        letter-spacing: 0.5px;
    }
    .brand-subtitle {
        font-size: 13px;
        color: var(--text-secondary);
    }

    /* =====================================================
       SAFETY WARNING BANNER
       ===================================================== */
    .safety-banner {
        background: rgba(249, 115, 22, 0.12);
        border-left: 4px solid #f97316;
        padding: 12px 18px;
        border-radius: 4px;
        margin-bottom: 20px;
        color: #fed7aa;      /* warmer, higher contrast amber */
        font-size: 14px;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    /* =====================================================
       METRIC CARDS
       ===================================================== */
    .metric-card {
        background-color: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 18px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        color: var(--info);
    }
    .metric-label {
        font-size: 13px;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }

    /* =====================================================
       STATUS BADGES
       ===================================================== */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .badge-approved { background-color: rgba(34,197,94,0.18); color: #6ee7a0; border: 1px solid #22c55e; }
    .badge-rejected { background-color: rgba(239,68,68,0.18); color: #fca5a5; border: 1px solid #ef4444; }
    .badge-ai       { background-color: rgba(77,158,247,0.18); color: #7bbffa; border: 1px solid #4d9ef7; }
    .badge-review   { background-color: rgba(245,158,11,0.18); color: #fcd34d; border: 1px solid #f59e0b; }
    .badge-draft    { background-color: rgba(148,163,184,0.18); color: #cbd5e1; border: 1px solid #64748b; }

    /* =====================================================
       ASIL BADGES
       ===================================================== */
    .badge-asild { background-color: #dc2626; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
    .badge-asilc { background-color: #ea580c; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
    .badge-asilb { background-color: #ca8a04; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
    .badge-asila { background-color: #2563eb; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
    .badge-qm    { background-color: #374151; color: #d1d5db; padding: 4px 10px; border-radius: 4px; font-weight: 600; }

    /* =====================================================
       CITATION BOX
       ===================================================== */
    .citation-box {
        background-color: var(--bg-surface-2);
        border-left: 3px solid var(--accent);
        padding: 12px 16px;
        margin: 10px 0;
        border-radius: 0 6px 6px 0;
        color: var(--text-secondary);
    }
    .citation-box strong {
        color: var(--text-primary) !important;
    }
    .citation-box span {
        color: var(--text-secondary) !important;
    }

    /* =====================================================
       DOCUMENT CARDS (inline in app.py)
       ===================================================== */
    .doc-card {
        background-color: var(--bg-surface);
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 8px;
        border: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* =====================================================
       SCROLLBARS
       ===================================================== */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-base); }
    ::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

    /* =====================================================
       DISABLED STATE (intentional)
       ===================================================== */
    button:disabled,
    input:disabled,
    textarea:disabled,
    select:disabled {
        opacity: 0.4 !important;
        cursor: not-allowed !important;
    }

    /* =====================================================
       FOCUS RINGS (accessibility)
       ===================================================== */
    *:focus-visible {
        outline: 2px solid var(--accent) !important;
        outline-offset: 2px !important;
    }

    /* =====================================================
       TOOLTIP
       ===================================================== */
    [data-baseweb="tooltip"] {
        background-color: var(--bg-surface-3) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
        font-size: 13px !important;
    }

    </style>
    """, unsafe_allow_html=True)


def render_safety_banner():
    st.markdown("""
    <div class="safety-banner">
        <div><strong>⚠️ MANDATORY ENGINEERING NOTICE:</strong> AI outputs are advisory recommendations. 
        Autonomous safety approvals are disabled. Consequential engineering decisions require formal review & sign-off by a certified engineer.</div>
    </div>
    """, unsafe_allow_html=True)

def render_status_badge(status: str) -> str:
    s = str(status).upper()
    if s == "APPROVED":
        return f'<span class="badge badge-approved">APPROVED</span>'
    elif s == "REJECTED":
        return f'<span class="badge badge-rejected">REJECTED</span>'
    elif s == "ENGINEER_REVIEW":
        return f'<span class="badge badge-review">ENGINEER REVIEW</span>'
    elif s == "AI_GENERATED":
        return f'<span class="badge badge-ai">AI GENERATED</span>'
    else:
        return f'<span class="badge badge-draft">{s}</span>'

def render_asil_badge(asil: str) -> str:
    a = str(asil).upper().strip()
    if "ASIL D" in a:
        return f'<span class="badge-asild">ASIL D</span>'
    elif "ASIL C" in a:
        return f'<span class="badge-asilc">ASIL C</span>'
    elif "ASIL B" in a:
        return f'<span class="badge-asilb">ASIL B</span>'
    elif "ASIL A" in a:
        return f'<span class="badge-asila">ASIL A</span>'
    else:
        return f'<span class="badge-qm">QM</span>'
