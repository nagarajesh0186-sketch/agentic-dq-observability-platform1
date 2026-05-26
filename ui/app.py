"""
Enterprise Data Quality Observability Platform
Run: streamlit run ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import httpx
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="DQ Observability",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design System ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ══════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ══════════════════════════════════════════════════════════════
   --primary:        #4f46e5  (indigo 600)
   --primary-hover:  #4338ca  (indigo 700)
   --primary-soft:   #eef2ff  (indigo 50)
   --bg-page:        #f7f8fa
   --bg-card:        #ffffff
   --bg-muted:       #f9fafb
   --bg-elevated:    #f3f4f6
   --border-1:       #e5e7eb
   --border-2:       #d1d5db
   --text-1:         #111827
   --text-2:         #4b5563
   --text-3:         #6b7280
   --text-4:         #9ca3af
   --success:        #059669 / bg #ecfdf5
   --warning:        #d97706 / bg #fef3c7
   --danger:         #dc2626 / bg #fef2f2
   --info:           #2563eb / bg #eff6ff
   --shadow-xs:      0 1px 2px rgba(16,24,40,0.05)
   --shadow-sm:      0 1px 3px rgba(16,24,40,0.06), 0 1px 2px rgba(16,24,40,0.04)
   --shadow-md:      0 4px 8px -2px rgba(16,24,40,0.06), 0 2px 4px -2px rgba(16,24,40,0.04)
   --shadow-lg:      0 12px 24px -6px rgba(16,24,40,0.08), 0 4px 8px -4px rgba(16,24,40,0.04)
   --radius-sm:      6px / --radius-md: 8px / --radius-lg: 12px
   ══════════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ─── Base typography ─── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif !important;
    font-size: 15px !important;
    line-height: 1.6 !important;
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
    color: #111827 !important;
    font-feature-settings: 'cv02','cv03','cv04','cv11' !important;
    text-rendering: optimizeLegibility !important;
}

/* Body copy — comfortable reading rhythm */
p, li, span { line-height: 1.65 !important; letter-spacing: -0.003em !important; }

/* Headings — tighter tracking for large sizes */
h1, h2, h3, h4 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
    line-height: 1.25 !important;
    color: #0f172a !important;
}

/* Streamlit native label text */
label, .stTextInput label, .stTextArea label,
.stSelectbox label, .stCheckbox label,
.stRadio label, .stNumberInput label {
    font-size: 0.835rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
    letter-spacing: 0.005em !important;
    line-height: 1.4 !important;
}

/* Input placeholder text */
input::placeholder, textarea::placeholder {
    color: #9ca3af !important;
    font-style: normal !important;
}

/* Monospace — code, session IDs, SQL */
code, pre, .stCode, [data-testid="stCode"],
[data-testid="stMarkdownContainer"] code {
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace !important;
    font-size: 0.82rem !important;
    letter-spacing: -0.02em !important;
}

/* Captions / helper text */
.stCaption, small, [data-testid="stCaptionContainer"] * {
    font-size: 0.8rem !important;
    line-height: 1.5 !important;
    color: #6b7280 !important;
    letter-spacing: 0.005em !important;
}

/* Native Streamlit metric */
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    color: #6b7280 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.03em !important;
    color: #0f172a !important;
    line-height: 1.1 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; font-weight: 600 !important; }

/* ─── Page background & container ─── */
.stApp { background: #f7f8fa !important; }
.main .block-container {
    padding: 2rem 2.25rem 3rem !important;
    max-width: 1480px !important;
}
/* Subtle hr divider */
hr { border: none !important; border-top: 1px solid #e5e7eb !important; margin: 1.5rem 0 !important; }

/* ══════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: #0a0e1a !important;
    border-right: 1px solid #1f2937 !important;
    min-width: 248px !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem !important; }
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
[data-testid="stSidebar"] hr { border-top: 1px solid #1f2937 !important; margin: 0.85rem 0 !important; }
[data-testid="stSidebar"] code {
    background: #141925 !important;
    color: #9ca3af !important;
    border: 1px solid #1f2937 !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
}

/* Sidebar nav buttons */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #94a3b8 !important;
    text-align: left !important;
    padding: 0.55rem 1rem !important;
    font-size: 0.94rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    border-radius: 8px !important;
    justify-content: flex-start !important;
    transition: all 0.15s ease !important;
    margin: 1px 0 !important;
    letter-spacing: 0.005em !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #141925 !important;
    color: #f1f5f9 !important;
    border: none !important;
    box-shadow: none !important;
    transform: none !important;
}
[data-testid="stSidebar"] .nav-active + div .stButton > button,
[data-testid="stSidebar"] .nav-active .stButton > button {
    background: linear-gradient(90deg, rgba(79,70,229,0.22), rgba(79,70,229,0.08)) !important;
    color: #ffffff !important;
    border-left: 3px solid #6366f1 !important;
    border-radius: 0 8px 8px 0 !important;
    font-weight: 600 !important;
    padding-left: calc(1rem - 3px) !important;
}

/* ══════════════════════════════════════════
   CARDS
   NOTE: When `<div class="dq-card">` is emitted via st.markdown in isolation,
   Streamlit auto-closes it, leaving an empty styled div (visible white box).
   Hide those orphans via :empty. The proper way to group content is
   st.container(border=True), styled below.
══════════════════════════════════════════ */
.dq-card, .dq-card-sm, .dq-card-elevated {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}
.dq-card-elevated {
    box-shadow: 0 4px 8px -2px rgba(16,24,40,0.06), 0 2px 4px -2px rgba(16,24,40,0.04);
}
/* Hide orphan empty card divs created by isolated st.markdown wrappers */
.dq-card:empty, .dq-card-sm:empty, .dq-card-elevated:empty { display: none !important; }

/* Style st.container(border=True) as a card */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 12px !important;
    padding: 1.4rem 1.6rem !important;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04) !important;
}

/* ══════════════════════════════════════════
   TABLES — modern enterprise look
══════════════════════════════════════════ */
.stDataFrame {
    border-radius: 10px !important;
    overflow: hidden !important;
    border: 1px solid #e5e7eb !important;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04) !important;
}
[data-testid="stDataFrame"] > div { border-radius: 10px !important; }
.stDataFrame thead th {
    background: #fafbfc !important;
    color: #6b7280 !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    padding: 0.85rem 1.15rem !important;
    border-bottom: 1px solid #e5e7eb !important;
}
.stDataFrame tbody td {
    font-size: 0.875rem !important;
    color: #1f2937 !important;
    padding: 0.7rem 1.15rem !important;
    border-bottom: 1px solid #f3f4f6 !important;
}
.stDataFrame tbody tr:hover { background: #fafbfc !important; }
.stDataFrame tbody tr:last-child td { border-bottom: none !important; }

/* ══════════════════════════════════════════
   BUTTONS
══════════════════════════════════════════ */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    border: 1px solid #d1d5db !important;
    color: #374151 !important;
    background: #ffffff !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.15s ease !important;
    box-shadow: 0 1px 2px rgba(16,24,40,0.05) !important;
    letter-spacing: 0.005em !important;
}
.stButton > button:hover:not([kind="primary"]) {
    border-color: #4f46e5 !important;
    color: #4f46e5 !important;
    background: #eef2ff !important;
    box-shadow: 0 1px 2px rgba(79,70,229,0.08) !important;
    transform: none !important;
}
.stButton > button[kind="primary"] {
    background: #4f46e5 !important;
    border-color: #4f46e5 !important;
    color: #ffffff !important;
    box-shadow: 0 1px 2px rgba(79,70,229,0.18), inset 0 1px 0 rgba(255,255,255,0.12) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #4338ca !important;
    border-color: #4338ca !important;
    color: #ffffff !important;
    box-shadow: 0 4px 10px rgba(79,70,229,0.28), inset 0 1px 0 rgba(255,255,255,0.12) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* Download button matches primary look */
.stDownloadButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
}

/* ══════════════════════════════════════════
   FORM INPUTS
══════════════════════════════════════════ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input {
    border-radius: 8px !important;
    border: 1px solid #d1d5db !important;
    font-size: 0.9rem !important;
    background: #ffffff !important;
    padding: 0.55rem 0.85rem !important;
    color: #111827 !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stTextInput > div > div > input:hover,
.stTextArea > div > div > textarea:hover { border-color: #9ca3af !important; }
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stNumberInput > div > div > input:focus {
    border-color: #4f46e5 !important;
    box-shadow: 0 0 0 4px rgba(79,70,229,0.10) !important;
    outline: none !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
    margin-bottom: 0.3rem !important;
}
.stSelectbox > div > div { border-radius: 8px !important; border: 1px solid #d1d5db !important; }

/* ══════════════════════════════════════════
   TABS — segmented control style
══════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    background: #f3f4f6 !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: 1px solid #e5e7eb !important;
    width: fit-content !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px !important;
    color: #6b7280 !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 1.1rem !important;
    background: transparent !important;
    border: none !important;
    transition: all 0.15s ease !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #111827 !important; }
.stTabs [aria-selected="true"][data-baseweb="tab"] {
    background: #ffffff !important;
    color: #111827 !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(16,24,40,0.08) !important;
}

/* ══════════════════════════════════════════
   METRICS (native st.metric)
══════════════════════════════════════════ */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}
[data-testid="stMetricValue"] {
    font-size: 1.85rem !important;
    font-weight: 700 !important;
    color: #111827 !important;
    letter-spacing: -0.03em !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: #6b7280 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; font-weight: 600 !important; }

/* ══════════════════════════════════════════
   ALERTS — softer enterprise look
══════════════════════════════════════════ */
.stAlert {
    border-radius: 10px !important;
    border: 1px solid transparent !important;
    font-size: 0.9rem !important;
    padding: 0.85rem 1.1rem !important;
    box-shadow: 0 1px 2px rgba(16,24,40,0.03) !important;
}
.stAlert[data-baseweb="notification"][kind="success"] { background: #ecfdf5 !important; border-color: #a7f3d0 !important; color: #047857 !important; }
.stAlert[data-baseweb="notification"][kind="warning"] { background: #fef3c7 !important; border-color: #fcd34d !important; color: #b45309 !important; }
.stAlert[data-baseweb="notification"][kind="error"]   { background: #fef2f2 !important; border-color: #fecaca !important; color: #b91c1c !important; }
.stAlert[data-baseweb="notification"][kind="info"]    { background: #eff6ff !important; border-color: #bfdbfe !important; color: #1d4ed8 !important; }

/* ══════════════════════════════════════════
   EXPANDERS
══════════════════════════════════════════ */
.stExpander {
    border-radius: 10px !important;
    border: 1px solid #e5e7eb !important;
    background: #ffffff !important;
    box-shadow: 0 1px 2px rgba(16,24,40,0.03) !important;
}
.stExpander summary {
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    color: #374151 !important;
    padding: 0.85rem 1.1rem !important;
}
.stExpander summary:hover { color: #4f46e5 !important; }

/* ══════════════════════════════════════════
   FORM, CHECKBOX, CAPTION, MISC
══════════════════════════════════════════ */
.stCheckbox label, .stRadio label > div { font-size: 0.9rem !important; color: #374151 !important; }
.stCode { border-radius: 8px !important; border: 1px solid #e5e7eb !important; }
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: 0.825rem !important;
    color: #6b7280 !important;
    line-height: 1.5 !important;
}
[data-testid="stMarkdownContainer"] p { line-height: 1.6 !important; }
[data-testid="stMarkdownContainer"] strong { color: #111827 !important; font-weight: 600 !important; }

/* Hide Streamlit branding chrome */
#MainMenu, footer { visibility: hidden; }
[data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }

/* Loading spinner */
.stSpinner > div { border-color: #4f46e5 transparent transparent transparent !important; }

/* Smooth page transitions */
.main > div { animation: fadeIn 0.28s ease-out; }
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
API_URL = os.getenv("DQ_API_URL", "http://localhost:8002")
API_KEY = os.getenv("API_KEY", "rickytokens")
_HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


# ── Design helpers ─────────────────────────────────────────────────────────────

def badge(text: str, kind: str = "") -> str:
    """Status pill. Empty text returns empty string (no chip rendered)."""
    if not text or not str(text).strip():
        return ""
    # (bg, text, dot, has_dot)
    cfg = {
        "PASS":     ("#ecfdf5", "#047857", "#10b981", True),
        "FAIL":     ("#fef2f2", "#b91c1c", "#ef4444", True),
        "WARN":     ("#fffbeb", "#b45309", "#f59e0b", True),
        "ERROR":    ("#fef2f2", "#b91c1c", "#ef4444", True),
        "INFO":     ("#eff6ff", "#1d4ed8", "#3b82f6", True),
        "APPROVED": ("#ecfdf5", "#047857", "#10b981", True),
        "REJECTED": ("#fef2f2", "#b91c1c", "#ef4444", True),
        "PENDING":  ("#f3f4f6", "#4b5563", "#9ca3af", True),
        "MODIFIED": ("#eff6ff", "#1d4ed8", "#3b82f6", True),
        "TECHNICAL":("#eff6ff", "#1d4ed8", "",        False),
        "BUSINESS": ("#faf5ff", "#7e22ce", "",        False),
    }
    key = text.upper() if text.upper() in cfg else kind.upper()
    bg, fg, dot, has_dot = cfg.get(key, ("#f3f4f6", "#4b5563", "#9ca3af", False))
    dot_html = (f'<span style="width:6px;height:6px;border-radius:50%;'
                f'background:{dot};display:inline-block;flex-shrink:0"></span>'
                if has_dot else "")
    return (f'<span style="background:{bg};color:{fg};'
            f'padding:3px 10px;border-radius:9999px;font-size:0.74rem;font-weight:600;'
            f'white-space:nowrap;display:inline-flex;align-items:center;gap:5px;'
            f'line-height:1.4">{dot_html}{text}</span>')


def kpi_tile(label: str, value: str, delta: str = "", accent: str = "#4f46e5",
             icon: str = "", help_text: str = "", trend: str = "") -> str:
    """Enterprise KPI tile. `trend` ∈ {"up","down","flat"} renders a small arrow."""
    arrows = {"up": "↑", "down": "↓", "flat": "→"}
    arrow = arrows.get(trend, "")
    arrow_span = f'<span>{arrow}</span>' if arrow else ''
    delta_html = (
        f'<div style="display:flex;align-items:center;gap:4px;margin-top:0.55rem;'
        f'font-size:0.825rem;color:{accent};font-weight:600">{arrow_span}'
        f'<span>{delta}</span></div>'
    ) if delta else ""
    help_html = (
        f'<div style="font-size:0.78rem;color:#9ca3af;margin-top:0.3rem">{help_text}</div>'
    ) if help_text else ""
    icon_html = (
        f'<div style="width:32px;height:32px;border-radius:8px;background:{accent}14;'
        f'color:{accent};display:flex;align-items:center;justify-content:center;'
        f'font-size:0.95rem;flex-shrink:0">{icon}</div>'
    ) if icon else ""
    return (
        f'<div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;'
        f'padding:1.25rem 1.4rem;box-shadow:0 1px 2px rgba(16,24,40,0.04);'
        f'position:relative;overflow:hidden">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:3px;background:{accent}"></div>'
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:0.75rem">'
        f'<div style="flex:1;min-width:0">'
        f'<div style="font-size:0.72rem;font-weight:600;color:#6b7280;'
        f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.55rem;'
        f'margin-top:0.1rem">{label}</div>'
        f'<div style="font-size:1.95rem;font-weight:700;color:#111827;'
        f'letter-spacing:-0.03em;line-height:1.1">{value}</div>'
        f'{delta_html}{help_html}'
        f'</div>{icon_html}</div></div>'
    )


def page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;'
        f'margin-bottom:1.75rem;padding-bottom:1.5rem;border-bottom:1px solid #e5e7eb">'
        f'<div>'
        f'<div style="font-size:1.6rem;font-weight:700;color:#111827;'
        f'letter-spacing:-0.025em;line-height:1.2">{title}</div>'
        f'<div style="font-size:0.92rem;color:#6b7280;margin-top:0.4rem;'
        f'font-weight:400">{subtitle}</div>'
        f'</div>'
        f'<div style="text-align:right;flex-shrink:0;padding-left:1.5rem">'
        f'<div style="font-size:0.68rem;font-weight:600;color:#9ca3af;'
        f'text-transform:uppercase;letter-spacing:0.08em">Last refreshed</div>'
        f'<div style="font-size:0.88rem;font-weight:500;color:#4b5563;'
        f'margin-top:0.2rem;font-feature-settings:&apos;tnum&apos;">{ts}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def section_heading(title: str, subtitle: str = "", action: str = "",
                    border_color: str = "") -> None:
    """Section heading with optional right-aligned action HTML.
    If `border_color` is set, renders a colored accent bar on the left."""
    sub_html = (
        f'<div style="font-size:0.85rem;color:#6b7280;margin-top:0.2rem;'
        f'font-weight:400">{subtitle}</div>'
    ) if subtitle else ""
    action_html = f'<div>{action}</div>' if action else ""
    bar_html = (
        f'<div style="width:3px;height:2rem;background:{border_color};'
        f'border-radius:2px;flex-shrink:0;margin-right:0.85rem"></div>'
    ) if border_color else ""
    st.markdown(
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;'
        f'margin-bottom:1.1rem;margin-top:0.15rem;gap:1rem">'
        f'<div style="display:flex;align-items:flex-start;flex:1;min-width:0">'
        f'{bar_html}'
        f'<div>'
        f'<div style="font-size:1.05rem;font-weight:700;color:#111827;'
        f'letter-spacing:-0.015em">{title}</div>'
        f'{sub_html}'
        f'</div></div>{action_html}</div>',
        unsafe_allow_html=True,
    )


def empty_state(message: str, sub: str = "", icon: str = "○", success: bool = False) -> None:
    """Centered empty/success state."""
    bg, border, color = (
        ("#ecfdf5", "#a7f3d0", "#047857") if success
        else ("#f9fafb", "#e5e7eb", "#6b7280")
    )
    sub_html = (
        f'<div style="font-size:0.86rem;opacity:0.75;margin-top:0.3rem">{sub}</div>'
    ) if sub else ""
    st.markdown(
        f'<div style="background:{bg};border:1px solid {border};border-radius:10px;'
        f'padding:1.75rem 1.5rem;text-align:center;color:{color}">'
        f'<div style="font-size:1.4rem;margin-bottom:0.55rem;opacity:0.85">{icon}</div>'
        f'<div style="font-weight:600;font-size:0.95rem">{message}</div>'
        f'{sub_html}</div>',
        unsafe_allow_html=True,
    )


def stepper(stages: list[tuple[str, bool, bool]]) -> None:
    """Modern stepper with connector lines. stages = [(label, done, active), ...]"""
    n = len(stages)
    parts = ['<div style="display:flex;align-items:center;justify-content:space-between;padding:0.5rem 0;width:100%">']
    for i, (label, done, active) in enumerate(stages):
        if done:
            circle_bg, circle_color, label_color, label_weight = "#10b981", "#fff", "#059669", "600"
            symbol = "✓"
        elif active:
            circle_bg, circle_color, label_color, label_weight = "#4f46e5", "#fff", "#4f46e5", "600"
            symbol = str(i + 1)
        else:
            circle_bg, circle_color, label_color, label_weight = "#ffffff", "#9ca3af", "#9ca3af", "500"
            symbol = str(i + 1)
        circle_border = "2px solid #e5e7eb" if not (done or active) else "none"
        glow = "0 0 0 4px rgba(79,70,229,0.10)" if active else "none"
        parts.append(
            f'<div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;gap:0.5rem">'
            f'<div style="width:30px;height:30px;border-radius:50%;background:{circle_bg};'
            f'border:{circle_border};display:inline-flex;align-items:center;justify-content:center;'
            f'font-size:0.78rem;font-weight:700;color:{circle_color};box-shadow:{glow}">{symbol}</div>'
            f'<div style="font-size:0.74rem;font-weight:{label_weight};color:{label_color};'
            f'white-space:nowrap;letter-spacing:0.01em">{label}</div>'
            f'</div>'
        )
        if i < n - 1:
            line_color = "#10b981" if done else "#e5e7eb"
            parts.append(
                f'<div style="flex:1;height:2px;background:{line_color};'
                f'margin:0 0.5rem;margin-top:-1.5rem;border-radius:1px"></div>'
            )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def rule_row_badge(source: str) -> str:
    return badge(source, kind=source)


# ── API helpers ────────────────────────────────────────────────────────────────
def _extract_error(exc: Exception) -> str:
    if hasattr(exc, "response"):
        try:
            body = exc.response.json()
            return body.get("detail") or body.get("error") or str(exc)
        except Exception:
            pass
    return str(exc)


def api_get(path: str, timeout: int = 60) -> dict:
    try:
        r = httpx.get(f"{API_URL}{path}", headers=_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"success": False, "error": _extract_error(exc)}


def api_post(path: str, body: dict, timeout: int = 300) -> dict:
    try:
        r = httpx.post(f"{API_URL}{path}", json=body, headers=_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"success": False, "error": _extract_error(exc)}


def api_put(path: str, body: dict, timeout: int = 30) -> dict:
    try:
        r = httpx.put(f"{API_URL}{path}", json=body, headers=_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"success": False, "error": _extract_error(exc)}


def api_delete(path: str, params: dict | None = None, timeout: int = 10) -> dict:
    try:
        r = httpx.delete(f"{API_URL}{path}", headers=_HEADERS, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"success": False, "error": _extract_error(exc)}


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="padding:1.4rem 1rem 1.1rem">
  <div style="display:flex;align-items:center;gap:0.7rem">
    <div style="width:36px;height:36px;
                background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);
                border-radius:9px;display:flex;align-items:center;justify-content:center;
                font-size:0.82rem;font-weight:800;color:#fff;flex-shrink:0;
                box-shadow:0 4px 12px -2px rgba(79,70,229,0.4)">DQ</div>
    <div>
      <div style="font-size:0.98rem;font-weight:700;color:#f9fafb;line-height:1.2;
                  letter-spacing:-0.01em">DataQuality</div>
      <div style="font-size:0.62rem;font-weight:600;color:#6b7280;
                  letter-spacing:0.14em;text-transform:uppercase;margin-top:0.15rem">
          Observability Platform
      </div>
    </div>
  </div>
</div>
<hr>""", unsafe_allow_html=True)

    _NAV = ["New Workflow", "Rules Manager", "Approvals", "Observability", "Settings"]

    if "page" not in st.session_state:
        st.session_state.page = "New Workflow"

    for _name in _NAV:
        _active = st.session_state.page == _name
        if _active:
            st.markdown('<div class="nav-active">', unsafe_allow_html=True)
        if st.button(_name, key=f"_nav_{_name}", use_container_width=True):
            st.session_state.page = _name
            st.rerun()
        if _active:
            st.markdown('</div>', unsafe_allow_html=True)

    page = st.session_state.page

    st.markdown("<hr>", unsafe_allow_html=True)

    if st.session_state.get("session_id"):
        st.markdown(
            f'''
<div style="padding:0.5rem 0.5rem 0.25rem">
  <div style="font-size:0.62rem;font-weight:600;color:#6b7280;
              text-transform:uppercase;letter-spacing:0.12em;margin-bottom:0.5rem;
              display:flex;align-items:center;gap:6px">
    <span style="width:7px;height:7px;background:#10b981;border-radius:50%;
                 box-shadow:0 0 0 3px rgba(16,185,129,0.18)"></span>
    Active Session
  </div>
  <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;
              background:#141925;color:#9ca3af;padding:6px 10px;border-radius:6px;
              border:1px solid #1f2937;overflow:hidden;text-overflow:ellipsis">
    {st.session_state.session_id[:30]}
  </div>
</div>''',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '''
<div style="padding:0.5rem;display:flex;align-items:center;gap:6px">
  <span style="width:7px;height:7px;background:#6b7280;border-radius:50%"></span>
  <span style="font-size:0.82rem;color:#9ca3af">No active session</span>
</div>''',
            unsafe_allow_html=True,
        )



# ══════════════════════════════════════════════════════════════════════
# PAGE: NEW WORKFLOW
# ══════════════════════════════════════════════════════════════════════
if page == "New Workflow":
    page_header(
        "New DQ Workflow",
        "Configure target tables and start AI-powered rule generation",
        icon="◈",
    )

    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "workflow_stage" not in st.session_state:
        st.session_state.workflow_stage = None

    st.markdown('<div class="dq-card">', unsafe_allow_html=True)
    section_heading("Step 1 — Target Configuration",
                    "Specify the GCP project and BigQuery tables to profile")
    with st.form("discovery_form"):
        col_a, col_b = st.columns(2)
        project_id = col_a.text_input("GCP Project ID", placeholder="my-gcp-project")
        dataset_id = col_b.text_input("BigQuery Dataset", placeholder="my_dataset")
        table_names_raw = st.text_area(
            "Table Names",
            placeholder="customers\norders\ntransactions",
            height=90,
        )
        col1, col2 = st.columns(2)
        include_tech = col1.checkbox("Technical Rules", value=True,
            help="Null checks, uniqueness, type validation, freshness, volume, schema drift")
        include_biz = col2.checkbox("Business Rules", value=True,
            help="LLM-inferred domain rules: cross-column constraints, SLA rules, business logic")
        st.markdown("<br>", unsafe_allow_html=True)
        submit_discovery = st.form_submit_button("Run Metadata Discovery", type="primary",
                                                  use_container_width=False)
    st.markdown('</div>', unsafe_allow_html=True)

    if submit_discovery:
        if not project_id or not dataset_id or not table_names_raw:
            st.error("All fields are required.")
        else:
            table_names = [t.strip() for t in table_names_raw.replace(",", "\n").splitlines() if t.strip()]
            with st.spinner("Scanning BigQuery schema and profiling tables…"):
                resp = api_post("/api/v1/discovery/start", {
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_names": table_names,
                })
            if resp.get("success"):
                data = resp["data"]
                st.session_state.session_id = data["session_id"]
                st.session_state.workflow_stage = "discovered"
                st.session_state.include_tech = include_tech
                st.session_state.include_biz = include_biz
                st.success(f"Discovery complete — session `{data['session_id']}`")
                with st.expander("Discovery details"):
                    st.json(data)
            else:
                st.error(f"Discovery failed: {resp.get('error', 'Unknown error')}")

    if st.session_state.get("session_id") and st.session_state.get("workflow_stage") == "discovered":
        st.markdown('<div class="dq-card">', unsafe_allow_html=True)
        section_heading(
            "Step 2 — Rule Generation",
            "AI engine analyses the schema and generates DQ rules",
        )

        inc_t = st.session_state.get("include_tech", True)
        inc_b = st.session_state.get("include_biz", True)

        parts = []
        if inc_t: parts.append("technical")
        if inc_b: parts.append("AI business")
        st.caption(f"Generating: **{' + '.join(parts)} rules**")

        # ── Business context input ─────────────────────────────────────
        if inc_b:
            st.markdown("<br>", unsafe_allow_html=True)
            section_heading(
                "Business Context",
                "Optional — extra domain knowledge sent to the AI to improve business rule quality",
            )

            ctx_col, file_col = st.columns([3, 2], gap="large")

            with ctx_col:
                st.markdown(
                    '<div style="font-size:0.8rem;font-weight:600;color:#374151;'
                    'margin-bottom:0.4rem">Natural language description</div>',
                    unsafe_allow_html=True,
                )
                custom_context_text = st.text_area(
                    "natural_language_context",
                    value=st.session_state.get("custom_context_text", ""),
                    placeholder=(
                        "• Amounts must always be positive\n"
                        "• customer_status: active → suspended → closed only\n"
                        "• Orders with status='shipped' need a tracking_number\n"
                        "• SLA: data must be < 6 hours old during 08:00–22:00 UTC"
                    ),
                    height=160,
                    label_visibility="collapsed",
                    help="Describe business rules, SLAs, state transitions, or domain constraints.",
                )
                if custom_context_text != st.session_state.get("custom_context_text", ""):
                    st.session_state.custom_context_text = custom_context_text

            with file_col:
                st.markdown(
                    '<div style="font-size:0.8rem;font-weight:600;color:#374151;'
                    'margin-bottom:0.4rem">Upload config / schema file</div>',
                    unsafe_allow_html=True,
                )
                uploaded_file = st.file_uploader(
                    "Upload context file",
                    type=["json", "yaml", "yml", "txt", "toml", "ini", "csv"],
                    label_visibility="collapsed",
                    help="Upload a JSON schema, YAML config, or plain-text rule definition. "
                         "Its contents will be merged with your description above.",
                )

                file_content = ""
                if uploaded_file is not None:
                    raw = uploaded_file.read()
                    try:
                        file_content = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        file_content = raw.decode("latin-1", errors="replace")

                    byte_size = len(raw)
                    size_label = f"{byte_size / 1024:.1f} KB" if byte_size >= 1024 else f"{byte_size} B"
                    st.markdown(
                        f'<div style="background:#f0fdf4;border:1px solid #a7f3d0;'
                        f'border-radius:8px;padding:0.6rem 0.85rem;margin-top:0.5rem">'
                        f'<div style="font-size:0.78rem;font-weight:600;color:#047857">'
                        f'✓ {uploaded_file.name}</div>'
                        f'<div style="font-size:0.72rem;color:#6b7280;margin-top:0.1rem">'
                        f'{size_label} · {uploaded_file.type or "text"}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    with st.expander("Preview file content"):
                        preview = file_content[:2000]
                        suffix = "\n…(truncated)" if len(file_content) > 2000 else ""
                        st.code(preview + suffix, language="json" if uploaded_file.name.endswith(".json") else "text")

            # Build combined context
            parts_ctx: list[str] = []
            if custom_context_text.strip():
                parts_ctx.append(custom_context_text.strip())
            if file_content.strip():
                parts_ctx.append(
                    f"--- Uploaded file: {uploaded_file.name} ---\n{file_content.strip()}"
                )
            custom_context: str | None = "\n\n".join(parts_ctx) or None

            if custom_context:
                char_count = len(custom_context)
                st.caption(f"Context ready — {char_count:,} characters will be sent to the AI.")
        else:
            custom_context = None

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Generate Rules", type="primary"):
            with st.spinner("Rule Intelligence Engine analysing schema…"):
                resp = api_post("/api/v1/rules/generate", {
                    "session_id": st.session_state.session_id,
                    "include_technical": inc_t,
                    "include_business": inc_b,
                    "custom_context": custom_context or None,
                })
            if resp.get("success"):
                data = resp["data"]
                st.session_state.workflow_stage = "rules_generated"
                c1, c2, c3 = st.columns(3)
                c1.metric("Technical Rules", data.get("technical_rules", 0))
                c2.metric("Business Rules", data.get("business_rules", 0))
                c3.metric("Total Rules", data.get("total_rules", 0))
                st.success(f"{data.get('total_rules', 0)} rules generated. Review them in **Rules Manager**.")
            else:
                st.error(f"Rule generation failed: {resp.get('error', 'Unknown error')}")
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# PAGE: RULES MANAGER
# ══════════════════════════════════════════════════════════════════════
elif page == "Rules Manager":
    page_header(
        "Rules Manager",
        "Review, curate, and configure DQ rules before approval",
        icon="⊞",
    )

    st.markdown('<div class="dq-card-sm">', unsafe_allow_html=True)
    session_id = st.text_input("Session ID", value=st.session_state.get("session_id", ""),
                                placeholder="session_abc123…")
    st.markdown('</div>', unsafe_allow_html=True)

    if not session_id:
        st.info("Enter a session ID to load rules.")
        st.stop()

    resp = api_get(f"/api/v1/rules/{session_id}")
    if not resp.get("success"):
        st.error(f"Error loading rules: {resp.get('error')}")
        st.stop()

    all_rules: list[dict] = resp.get("data", {}).get("rules", [])
    if not all_rules:
        st.info("No rules found for this session. Run rule generation first.")
        st.stop()

    tech_rules = [r for r in all_rules if r.get("source") == "technical"]
    biz_rules  = [r for r in all_rules if r.get("source") == "business"]

    sel_key = f"selections_{session_id}"
    if sel_key not in st.session_state:
        st.session_state[sel_key] = {r["rule_id"]: r.get("is_active", True) for r in all_rules}

    deleted_key = f"deleted_{session_id}"
    if deleted_key not in st.session_state:
        st.session_state[deleted_key] = set()

    SEV_COLOR = {"FAIL": "#dc2626", "WARN": "#d97706", "INFO": "#2563eb"}

    def _render_rule_section(rules: list[dict], title: str, icon: str, source: str) -> None:
        visible = [r for r in rules if r["rule_id"] not in st.session_state[deleted_key]]
        selected = sum(1 for r in visible if st.session_state[sel_key].get(r["rule_id"], True))

        st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.85rem">
  <div style="display:flex;align-items:baseline;gap:0.6rem">
    <span style="font-size:1.05rem;font-weight:700;color:#1e293b">{title}</span>
    <span style="font-size:0.85rem;color:#94a3b8;font-weight:500">
        {selected} of {len(visible)} selected
    </span>
  </div>
</div>""", unsafe_allow_html=True)

        if not visible:
            st.caption("No rules in this category.")
            return

        qc1, qc2, _ = st.columns([1, 1, 8])
        if qc1.button("Select All", key=f"sa_{source}"):
            for r in visible: st.session_state[sel_key][r["rule_id"]] = True
            st.rerun()
        if qc2.button("Clear All", key=f"ca_{source}"):
            for r in visible: st.session_state[sel_key][r["rule_id"]] = False
            st.rerun()

        # Column header row
        h_cols = st.columns([0.04, 0.30, 0.14, 0.10, 0.16, 0.08, 0.06])
        for hc, lbl in zip(h_cols, ["", "Rule", "Category", "Severity", "Column", "SQL", ""]):
            hc.markdown(
                f'<div style="font-size:0.65rem;font-weight:700;color:#94a3b8;'
                f'text-transform:uppercase;letter-spacing:0.07em;padding-bottom:0.3rem">{lbl}</div>',
                unsafe_allow_html=True,
            )

        for rule in visible:
            rid = rule["rule_id"]
            sev = rule.get("severity", "INFO")
            sev_color = SEV_COLOR.get(sev, "#475569")
            col_check, col_name, col_cat, col_sev, col_col, col_sql, col_del = st.columns(
                [0.04, 0.30, 0.14, 0.10, 0.16, 0.08, 0.06]
            )
            with col_check:
                new_val = st.checkbox("", value=st.session_state[sel_key].get(rid, True),
                                      key=f"cb_{rid}", label_visibility="collapsed")
                st.session_state[sel_key][rid] = new_val
            with col_name:
                opacity = "1" if new_val else "0.45"
                st.markdown(
                    f'<div style="font-size:0.82rem;font-weight:{"600" if new_val else "400"};'
                    f'color:#1e293b;opacity:{opacity};padding-top:2px">{rule["rule_name"]}</div>'
                    + (f'<div style="font-size:0.7rem;color:#94a3b8;opacity:{opacity}">'
                       f'{rule.get("description","")[:65]}{"…" if len(rule.get("description",""))>65 else ""}</div>'
                       if rule.get("description") else ""),
                    unsafe_allow_html=True,
                )
            with col_cat:
                st.markdown(
                    f'<div style="font-size:0.75rem;color:#475569;padding-top:4px">'
                    f'{rule.get("category","—")}</div>',
                    unsafe_allow_html=True,
                )
            with col_sev:
                st.markdown(badge(sev), unsafe_allow_html=True)
            with col_col:
                st.markdown(
                    f'<div style="font-size:0.75rem;color:#475569;padding-top:4px;'
                    f'font-family:monospace">{rule.get("column") or "—"}</div>',
                    unsafe_allow_html=True,
                )
            with col_sql:
                st.markdown(
                    '<div style="font-size:0.85rem;padding-top:2px">'
                    + ("✅" if rule.get("has_sql") else '⏳') + '</div>',
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("✕", key=f"del_{rid}", help="Remove rule"):
                    st.session_state[deleted_key].add(rid)
                    st.session_state[sel_key].pop(rid, None)
                    st.rerun()

    st.markdown('<div class="dq-card">', unsafe_allow_html=True)
    _render_rule_section(tech_rules, "Technical DQ Rules", "⚙", "technical")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dq-card">', unsafe_allow_html=True)
    _render_rule_section(biz_rules, "Business DQ Rules", "◈", "business")
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("🤖  AI Rule Builder  —  Describe in natural language"):
        ai_chat_key    = f"ai_chat_{session_id}"
        ai_pending_key = f"ai_pending_{session_id}"

        if ai_chat_key not in st.session_state:
            st.session_state[ai_chat_key] = []
        if ai_pending_key not in st.session_state:
            st.session_state[ai_pending_key] = None

        if not st.session_state[ai_chat_key]:
            st.info(
                "Describe your data quality rule in plain English and the AI will generate "
                "BigQuery SQL for you. The rule is then added to the rules list, included in "
                "the approval workflow, and compiled into the stored procedure.\n\n"
                "**Examples:** "
                "_Check that email is never null in the customers table_ · "
                "_Flag orders where amount is negative_ · "
                "_Ensure no duplicate user_id in the users table_"
            )

        for _msg in st.session_state[ai_chat_key]:
            with st.chat_message(_msg["role"]):
                st.markdown(_msg["content"])

        # ── Pending rule preview ──────────────────────────────────────
        _pending = st.session_state[ai_pending_key]
        if _pending and _pending.get("sql"):
            st.markdown("---")
            st.markdown("**📋 Review Generated Rule — confirm to add**")
            _pc1, _pc2 = st.columns([3, 1])
            with _pc1:
                st.code(_pending["sql"], language="sql")
            with _pc2:
                _sev = _pending.get("severity", "WARN")
                _sev_color = {"FAIL": "#dc2626", "WARN": "#d97706", "INFO": "#2563eb"}.get(_sev, "#475569")
                st.markdown(
                    f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'
                    f'padding:0.85rem;font-size:0.82rem">'
                    f'<div style="font-weight:600;margin-bottom:6px">{_pending.get("rule_name","")}</div>'
                    f'<div>Category: <b>{_pending.get("category","")}</b></div>'
                    f'<div>Severity: <b style="color:{_sev_color}">{_sev}</b></div>'
                    f'<div>Table: <code>{_pending.get("table_name","")}</code></div>'
                    + (f'<div>Column: <code>{_pending.get("column_name","")}</code></div>'
                       if _pending.get("column_name") else "")
                    + '</div>',
                    unsafe_allow_html=True,
                )
                if _pending.get("explanation"):
                    st.caption(_pending["explanation"])

            _ac1, _ac2, _ = st.columns([2, 2, 6])
            with _ac1:
                if st.button("✓ Add Rule", type="primary", key=f"ai_add_{session_id}"):
                    _r = api_post("/api/v1/rules/add-custom", {
                        "session_id":  session_id,
                        "rule_name":   _pending["rule_name"],
                        "category":    _pending["category"],
                        "severity":    _pending["severity"],
                        "table_name":  _pending.get("table_name", ""),
                        "column_name": _pending.get("column_name") or None,
                        "description": _pending.get("description", "AI-generated rule"),
                        "custom_sql":  _pending["sql"],
                    })
                    if _r.get("success"):
                        _rid = _r["data"]["rule_id"]
                        st.session_state[ai_chat_key].append({
                            "role": "assistant",
                            "content": (
                                f"✅ Rule **{_pending['rule_name']}** (`{_rid}`) added to the "
                                "rules list. It will appear in the approval workflow and be "
                                "compiled into the consolidated stored procedure."
                            ),
                        })
                        st.session_state[ai_pending_key] = None
                        st.session_state.pop(sel_key, None)
                        st.session_state.pop(deleted_key, None)
                        st.rerun()
                    else:
                        st.error(f"Failed: {_r.get('error')}")
            with _ac2:
                if st.button("↩ Discard", key=f"ai_discard_{session_id}"):
                    st.session_state[ai_pending_key] = None
                    st.rerun()

        # ── Input form ───────────────────────────────────────────────
        st.markdown("---")
        with st.form(f"ai_rule_input_{session_id}", clear_on_submit=True):
            _ic1, _ic2 = st.columns([6, 1])
            _user_input = _ic1.text_input(
                "Message",
                placeholder="Describe your data quality rule in plain English…",
                label_visibility="collapsed",
            )
            _send = _ic2.form_submit_button("Send →", use_container_width=True)

        if _send and _user_input.strip():
            _msg_text = _user_input.strip()
            st.session_state[ai_chat_key].append({"role": "user", "content": _msg_text})
            with st.spinner("Generating rule SQL…"):
                _resp = api_post("/api/v1/rules/llm-generate", {
                    "session_id":   session_id,
                    "message":      _msg_text,
                    "chat_history": st.session_state[ai_chat_key][:-1],
                })
            _data = _resp.get("data", {}) if _resp.get("success") else {}
            if _resp.get("success"):
                if _data.get("clarification_needed"):
                    _reply = f"🔍 {_data['clarification_needed']}"
                    st.session_state[ai_pending_key] = None
                elif _data.get("sql"):
                    _cat = _data.get("category", "")
                    _sev2 = _data.get("severity", "")
                    _expl = _data.get("explanation", "")
                    _reply = (
                        f"Generated a **{_cat}** rule with **{_sev2}** severity. "
                        f"{_expl}\n\nReview the SQL below and click **Add Rule** to include it."
                    )
                    st.session_state[ai_pending_key] = _data
                else:
                    _reply = f"❌ {_data.get('error', 'Could not generate — try rephrasing.')}"
                    st.session_state[ai_pending_key] = None
            else:
                _reply = f"❌ {_resp.get('error', 'Service error — try again.')}"
                st.session_state[ai_pending_key] = None

            st.session_state[ai_chat_key].append({"role": "assistant", "content": _reply})
            st.rerun()

        if st.session_state[ai_chat_key]:
            if st.button("🗑 Clear conversation", key=f"ai_clear_{session_id}"):
                st.session_state[ai_chat_key] = []
                st.session_state[ai_pending_key] = None
                st.rerun()

    # Save bar
    all_visible = [r for r in all_rules if r["rule_id"] not in st.session_state[deleted_key]]
    total_selected = sum(1 for r in all_visible if st.session_state[sel_key].get(r["rule_id"], True))

    st.markdown('<div class="dq-card-sm">', unsafe_allow_html=True)
    save_c1, save_c2 = st.columns([5, 1])
    save_c1.markdown(
        f'<span style="font-size:0.9rem;font-weight:600;color:#1e293b">{total_selected} rules selected</span> '
        f'<span style="font-size:0.82rem;color:#94a3b8">of {len(all_visible)} active</span>',
        unsafe_allow_html=True,
    )
    if save_c2.button("Save & Continue →", type="primary", use_container_width=True):
        errors = []
        for rid in st.session_state[deleted_key]:
            if not api_delete(f"/api/v1/rules/{rid}", params={"session_id": session_id}).get("success"):
                errors.append(rid)
        for rule in all_visible:
            rid = rule["rule_id"]
            new_active = st.session_state[sel_key].get(rid, True)
            if new_active != rule.get("is_active", True):
                api_put(f"/api/v1/rules/{rid}", {"session_id": session_id, "is_active": new_active})
        if errors:
            st.warning(f"Some rules could not be removed: {errors}")
        else:
            st.success(f"{total_selected} rules saved. Go to **Approvals** to submit Checkpoint 1.")
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# PAGE: APPROVALS
# ══════════════════════════════════════════════════════════════════════
elif page == "Approvals":
    page_header(
        "Approval Checkpoints",
        "Human-in-the-loop governance gates for rule approval and DQ execution",
        icon="◎",
    )

    st.markdown('<div class="dq-card-sm">', unsafe_allow_html=True)
    session_id = st.text_input("Session ID", value=st.session_state.get("session_id", ""),
                                placeholder="session_abc123…")
    st.markdown('</div>', unsafe_allow_html=True)

    if not session_id:
        st.info("Enter a session ID to manage approvals.")
        st.stop()

    status_resp = api_get(f"/api/v1/approvals/{session_id}")
    appr_data = status_resp.get("data", {}) if status_resp.get("success") else {}
    cp1       = appr_data.get("approval_1_status", "pending")
    cp2       = appr_data.get("approval_2_status", "pending")
    cur_stage = appr_data.get("current_stage", "init")

    # Stepper
    STAGES = [
        ("Discovery",      cur_stage not in ("init",),                                  False),
        ("Rules Ready",    cur_stage not in ("init","metadata_discovery","technical_rules","business_rules"), False),
        ("CP1 Approved",   cp1 == "approved",                                           cp1 != "approved"),
        ("SQL Generated",  cp1 == "approved",                                           False),
        ("CP2 Approved",   cp2 == "approved",                                           cp2 != "approved" and cp1 == "approved"),
        ("Complete",       cur_stage == "complete",                                     False),
    ]
    st.markdown('<div class="dq-card-sm">', unsafe_allow_html=True)
    stepper(STAGES)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Checkpoint 1 ──────────────────────────────────────────────────
    st.markdown('<div class="dq-card">', unsafe_allow_html=True)
    c1_status_html = badge(cp1.upper())
    section_heading("Checkpoint 1 — Rule Set Approval")
    st.markdown(f"Status: {c1_status_html}", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    rules_resp  = api_get(f"/api/v1/rules/{session_id}")
    rules       = rules_resp.get("data", {}).get("rules", []) if rules_resp.get("success") else []
    active_rules = [r for r in rules if r.get("is_active", True)]

    if rules:
        tech_r = [r for r in active_rules if r.get("source") == "technical"]
        biz_r  = [r for r in active_rules if r.get("source") == "business"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Active Rules", len(active_rules))
        c2.metric("Technical", len(tech_r))
        c3.metric("Business / AI", len(biz_r))
        with st.expander("Preview active rules"):
            if active_rules:
                df_r = pd.DataFrame(active_rules)
                disp = [c for c in ["rule_name","source","category","severity","column","has_sql"] if c in df_r.columns]
                st.dataframe(df_r[disp], use_container_width=True, height=240)
    else:
        st.info("No rules found. Run rule generation first.")

    if cp1 != "approved":
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("cp1_form"):
            approver_id = st.text_input("Approver ID / Email", placeholder="data-steward@company.com")
            decision = st.radio("Decision", ["APPROVED", "REJECTED", "MODIFIED"], horizontal=True, key="cp1_dec")
            comments = st.text_area("Comments", placeholder="Rules look correct for this dataset.", key="cp1_comments")
            submitted = st.form_submit_button("Submit Checkpoint 1", type="primary")
        if submitted:
            if not approver_id:
                st.error("Approver ID is required.")
            else:
                with st.spinner("Submitting…" if decision != "APPROVED"
                                else "Approving and auto-generating SQL + stored procedure…"):
                    resp = api_post("/api/v1/approvals/submit", {
                        "session_id": session_id, "stage": "approval_1",
                        "status": decision.lower(), "approver_id": approver_id,
                        "comments": comments, "rule_modifications": [],
                    })
                if resp.get("success"):
                    if decision == "APPROVED":
                        st.success("Checkpoint 1 approved. SQL and stored procedure generated.")
                    elif decision == "REJECTED":
                        st.error("Checkpoint 1 rejected. Workflow halted.")
                    else:
                        st.warning("Sent back for modification.")
                    st.rerun()
                else:
                    st.error(f"Submission failed: {resp.get('error')}")
    else:
        st.success("Checkpoint 1 approved — stored procedure ready in BigQuery.")
        if active_rules:
            sql_ready = sum(1 for r in active_rules if r.get("has_sql"))
            st.caption(f"SQL generated for {sql_ready} / {len(active_rules)} active rules.")

        rb_col, _ = st.columns([1.4, 6])
        if rb_col.button("Rebuild Stored Procedure"):
            with st.spinner("Regenerating SQL and redeploying stored procedure…"):
                rb = api_post("/api/v1/sql/rebuild-sp", {"session_id": session_id})
            if rb.get("success"):
                d = rb.get("data", {})
                st.success(f"SP `{d.get('sp_name')}` rebuilt — {d.get('rules_with_sql')}/{d.get('total_rules')} rules updated.")
            else:
                st.error(f"Rebuild failed: {rb.get('error')}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── DAG Specification ──────────────────────────────────────────
    if cp1 == "approved":
        st.markdown('<div class="dq-card">', unsafe_allow_html=True)
        section_heading("DAG Specification", "JSON spec generated before DAG deployment", border_color="#0891b2")
        spec_resp = api_get(f"/api/v1/monitoring/dag-spec/{session_id}")
        spec_data = spec_resp.get("data", {}).get("spec", {}) if spec_resp.get("success") else {}
        if spec_data:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Tasks", len(spec_data.get("tasks", [])))
            col2.metric("Total Rules", spec_data.get("rules_summary", {}).get("total", 0))
            col3.metric("Schedule", spec_data.get("schedule", {}).get("description", "—"))
            st.markdown("<br>", unsafe_allow_html=True)
            section_heading("Tasks & Dependencies", border_color="#0891b2")
            for task in spec_data.get("tasks", []):
                with st.expander(f"📋 {task['task_id']} — {task['type']}"):
                    st.markdown(f"**Description:** {task['description']}")
                    st.markdown(f"**SQL Location:** `{task['sql_location']}`")
                    st.code(task['sql'], language="sql")
                    if task['dependencies']:
                        st.markdown(f"**Depends on:** {', '.join(task['dependencies'])}")
                    if task['rules_included']:
                        st.markdown(f"**Rules included:** {task['rules_included']}")
            st.markdown("<br>", unsafe_allow_html=True)
            section_heading("Rule Inventory", border_color="#0891b2")
            rules_summary = spec_data.get("rules_summary", {})
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Technical Rules", rules_summary.get("technical", 0))
            rc2.metric("Business Rules", rules_summary.get("business", 0))
            rc3.metric("Results Table", "dq_results")
            with st.expander("View full rule inventory"):
                df_inv = pd.DataFrame(spec_data.get("rule_inventory", []))
                if not df_inv.empty:
                    st.dataframe(df_inv, use_container_width=True, height=300)
            with st.expander("View raw JSON spec"):
                st.json(spec_data)
        else:
            st.caption("No DAG spec available yet — run pipeline and approve CP1 first.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Run DQ Checks (only when CP1 approved) ────────────────────────
    if cp1 == "approved":
    
    
        st.markdown('<div class="dq-card">', unsafe_allow_html=True)
        section_heading("Execute DQ Checks",
                        "Run the stored procedure and write results to BigQuery")

        tab_exec, tab_dag = st.tabs(["▶  Execute Now", "📅  Schedule via Airflow"])

        with tab_exec:
            st.caption("Calls the consolidated stored procedure and writes results to `dq_results`.")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Execute DQ Checks", type="primary", key="exec_now_btn"):
                with st.spinner("Running stored procedure…"):
                    exec_resp = api_post("/api/v1/sql/execute", {"session_id": session_id}, timeout=300)
                if exec_resp.get("success"):
                    d = exec_resp["data"]
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Total Rules", d.get("total_rules", 0))
                    c2.metric("Passed", d.get("passed", 0))
                    c3.metric("Failed", d.get("failed", 0))
                    c4.metric("Pass Rate", f"{d.get('pass_rate', 0) * 100:.1f}%")
                    st.success(
                        f"Run complete — health score {d.get('health_score', 0):.0f}/100 "
                        f"in {d.get('duration_seconds', 0):.1f}s. "
                        "View results in **Observability**."
                    )
                else:
                    st.error(f"Execution failed: {exec_resp.get('error')}")

        with tab_dag:
            col_sched, col_owner = st.columns(2)
            schedule = col_sched.text_input("Cron Schedule", value="0 6 * * *")
            owner    = col_owner.text_input("DAG Owner", value="data-quality")
            common = {"Daily 06:00":"0 6 * * *","Hourly":"0 * * * *",
                      "Every 6h":"0 */6 * * *","Mon 07:00":"0 7 * * 1","1st of month":"0 8 1 * *"}
            quick = st.selectbox("Quick presets", ["— custom —"] + list(common))
            if quick != "— custom —":
                schedule = common[quick]; st.caption(f"Cron: `{schedule}`")
            if st.button("Generate DAG", type="primary", key="gen_dag"):
                with st.spinner("Generating DAG…"):
                    dag_resp = api_post("/api/v1/monitoring/generate-dag",
                                        {"session_id": session_id, "schedule": schedule, "owner": owner})
                if dag_resp.get("success"):
                    d = dag_resp["data"]
                    st.success(f"DAG `{d['dag_id']}` — schedule `{d['schedule']}`")
                    st.code(d["dag_content"], language="python")
                    st.download_button(f"Download {d['filename']}", d["dag_content"],
                                       file_name=d["filename"], mime="text/x-python")
                else:
                    st.error(f"DAG generation failed: {dag_resp.get('error')}")
        st.markdown('</div>', unsafe_allow_html=True)

# ── Checkpoint 2 — DQ Results Review + Production Sign-off ────────
    if cp1 == "approved":
        st.markdown('<div class="dq-card">', unsafe_allow_html=True)
        c2_status_html = badge(cp2.upper())
        section_heading("Checkpoint 2 — Production Sign-off", "Review DQ results before certifying data for production", border_color="#6366f1")
        st.markdown(f"Status: {c2_status_html}", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # Fetch DQ results for review
        dq_review_resp = api_get(f"/api/v1/approvals/dq-results/{session_id}")
        dq_review = dq_review_resp.get("data", {}) if dq_review_resp.get("success") else {}

        if dq_review:
            summary = dq_review.get("summary", {})
            failures = dq_review.get("failures", [])
            prod_ready = dq_review.get("production_ready", False)
            recommendation = dq_review.get("recommendation", "")

            # KPI metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Rules", summary.get("total_rules", 0))
            c2.metric("Passed", summary.get("passed", 0))
            c3.metric("Failed", summary.get("failed", 0))
            c4.metric("Health Score", f"{summary.get('health_score', 0):.0f}/100")

            # Production readiness banner
            if prod_ready:
                st.success(f"{recommendation}")
            else:
                st.error(f"{recommendation}")

            # Failure details table
            if failures:
                st.markdown("<br>", unsafe_allow_html=True)
                section_heading("Failed Rules — Review Before Approving", border_color="#ef4444")
                df_cp2 = pd.DataFrame(failures)
                show_cp2 = [c for c in ["severity", "rule_layer", "rule_name", "rule_type",
                                         "table_name", "column_name", "observed_value",
                                         "expected_value", "failure_count"] if c in df_cp2.columns]
                st.dataframe(df_cp2[show_cp2], use_container_width=True, height=280)

                crit = sum(1 for f in failures if f.get("severity") == "FAIL")
                warn = sum(1 for f in failures if f.get("severity") == "WARN")
                tech_fail = sum(1 for f in failures if f.get("rule_layer") == "technical")
                biz_fail = sum(1 for f in failures if f.get("rule_layer") == "business")
                st.markdown(
                    f'<div style="font-size:0.82rem;color:#64748b;margin-top:0.5rem">'
                    f'{badge("FAIL")} {crit} critical &nbsp;&nbsp;'
                    f'{badge("WARN")} {warn} warnings &nbsp;&nbsp;'
                    f'🔧 {tech_fail} technical &nbsp;&nbsp;'
                    f'🤖 {biz_fail} business (AI)</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No DQ results available yet. Run DQ checks first via Execute DQ Checks or wait for the Composer DAG to complete.")

        # CP2 approval form — only show if not yet approved
        if cp2 != "approved":
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("cp2_form"):
                approver_id_2 = st.text_input("Approver ID / Email", placeholder="data-steward@company.com", key="cp2_approver")
                decision_2 = st.radio(
                    "Production Sign-off Decision",
                    ["APPROVED", "REJECTED"],
                    horizontal=True,
                    key="cp2_dec",
                    help="APPROVED = certify data for production use. REJECTED = flag for remediation."
                )
                comments_2 = st.text_area(
                    "Comments",
                    placeholder="DQ results reviewed. Health score acceptable for production." if not failures else "Critical failures found — rejecting until resolved.",
                    key="cp2_comments"
                )
                submitted_2 = st.form_submit_button("Submit Checkpoint 2", type="primary")

            if submitted_2:
                if not approver_id_2:
                    st.error("Approver ID is required.")
                else:
                    with st.spinner(
                        "Certifying data for production and refreshing reporting views..."
                        if decision_2 == "APPROVED"
                        else "Recording rejection..."
                    ):
                        resp2 = api_post("/api/v1/approvals/submit", {
                            "session_id": session_id,
                            "stage": "approval_2",
                            "status": decision_2.lower(),
                            "approver_id": approver_id_2,
                            "comments": comments_2,
                            "rule_modifications": [],
                        })
                    if resp2.get("success"):
                        if decision_2 == "APPROVED":
                            st.success("✅ Checkpoint 2 approved. Data certified for production. Reporting views refreshed.")
                        else:
                            st.error("❌ Checkpoint 2 rejected. Data NOT certified for production.")
                        st.rerun()
                    else:
                        st.error(f"Submission failed: {resp2.get('error')}")
        else:
            st.success("✅ Checkpoint 2 approved — data certified for production use. Workflow complete.")
            if summary:
                st.caption(
                    f"Certified at health score {summary.get('health_score', 0):.0f}/100 "
                    f"with {summary.get('passed', 0)}/{summary.get('total_rules', 0)} rules passing."
                )
        st.markdown('</div>', unsafe_allow_html=True)
# ══════════════════════════════════════════════════════════════════════
# PAGE: OBSERVABILITY DASHBOARD
# ══════════════════════════════════════════════════════════════════════
elif page == "Observability":
    tb1, tb2, _ = st.columns([0.9, 1.3, 6])
    if tb1.button("↻  Refresh"):
        st.rerun()
    trend_days = tb2.selectbox("Trend", [7, 14, 30], index=2, label_visibility="collapsed")

    page_header(
        "Observability",
        "Live DQ results from BigQuery views — updated on each run",
        icon="▣",
    )

    tab_dq, tab_obs = st.tabs(["🏢  Executive Dashboard", "📊  DQ Observability"])

    # ── EXECUTIVE DASHBOARD ────────────────────────────────────────────
    with tab_dq:
        st.markdown("<br>", unsafe_allow_html=True)

        kpi_resp = api_get("/api/v1/reporting/kpi")
        kpi = kpi_resp.get("data", {}) if kpi_resp.get("success") else {}

        pr     = kpi.get("pass_rate_pct", 0) or 0
        hs     = kpi.get("health_score", 0) or 0
        cf     = kpi.get("critical_failures", 0) or 0
        tot    = kpi.get("total_checks", 0) or 0
        passed = kpi.get("passed_checks", 0) or 0
        failed_kpi = kpi.get("failed_checks", 0) or 0

        hs_color = "#10b981" if hs >= 80 else ("#f59e0b" if hs >= 60 else "#ef4444")
        pr_color = "#10b981" if pr >= 80 else ("#f59e0b" if pr >= 60 else "#ef4444")
        cf_color = "#10b981" if cf == 0 else "#ef4444"

        # Health score banner
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);'
            f'border-radius:16px;padding:2rem 2.5rem;margin-bottom:1.5rem;'
            f'display:flex;align-items:center;justify-content:space-between;gap:2rem">'
            f'<div>'
            f'<div style="font-size:0.75rem;font-weight:600;color:#94a3b8;'
            f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem">Platform Health Score</div>'
            f'<div style="font-size:3.5rem;font-weight:800;color:{hs_color};letter-spacing:-0.04em;line-height:1">{hs:.0f}</div>'
            f'<div style="font-size:0.9rem;color:#64748b;margin-top:0.4rem">out of 100</div>'
            f'</div>'
            f'<div style="text-align:center">'
            f'<div style="font-size:0.75rem;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem">Status</div>'
            f'<div style="font-size:1.3rem;font-weight:700;color:#f1f5f9">{"✅ Healthy" if hs >= 80 else ("⚠️ At Risk" if hs >= 60 else "🚨 Critical")}</div>'
            f'<div style="font-size:0.85rem;color:#64748b;margin-top:0.3rem">{passed} passed · {failed_kpi} failed · {tot} total</div>'
            f'</div>'
            f'<div style="text-align:right">'
            f'<div style="font-size:0.75rem;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem">Pass Rate</div>'
            f'<div style="font-size:2.5rem;font-weight:800;color:{pr_color};letter-spacing:-0.03em">{pr:.1f}%</div>'
            f'<div style="font-size:0.85rem;color:#64748b;margin-top:0.3rem">{"Above target ✓" if pr >= 80 else "Below 80% target"}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        e1, e2, e3, e4 = st.columns(4)
        e1.markdown(kpi_tile("Total Checks", str(tot), accent="#4f46e5", icon="⊞"), unsafe_allow_html=True)
        e2.markdown(kpi_tile("Passed", str(passed), accent="#10b981", icon="✓"), unsafe_allow_html=True)
        e3.markdown(kpi_tile("Failed", str(failed_kpi), accent="#ef4444", icon="✕"), unsafe_allow_html=True)
        e4.markdown(kpi_tile("Critical Failures", str(cf),
            delta="All clear ✓" if cf == 0 else f"{cf} need attention",
            accent=cf_color, icon="⚠"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        exec_col1, exec_col2 = st.columns(2)

        with exec_col1:
            st.markdown('<div class="dq-card">', unsafe_allow_html=True)
            section_heading("Rule Coverage", "Technical vs Business DQ rules", border_color="#6366f1")
            tech_resp_e = api_get("/api/v1/reporting/technical-health")
            tech_data_e = tech_resp_e.get("data", {}).get("tables", []) if tech_resp_e.get("success") else []
            biz_resp_e  = api_get("/api/v1/reporting/business-health")
            biz_data_e  = biz_resp_e.get("data", {}).get("tables", []) if biz_resp_e.get("success") else []
            tech_total  = sum(t.get("total_checks", 0) for t in tech_data_e)
            tech_passed = sum(t.get("passed", 0) for t in tech_data_e)
            biz_total   = sum(t.get("total_checks", 0) for t in biz_data_e)
            biz_passed  = sum(t.get("passed", 0) for t in biz_data_e)
            tech_rate   = round(tech_passed / tech_total * 100, 1) if tech_total else 0
            biz_rate    = round(biz_passed  / biz_total  * 100, 1) if biz_total  else 0
            st.markdown(
                f'<div style="display:flex;flex-direction:column;gap:1.25rem;margin-top:0.5rem">'
                f'<div>'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:0.4rem">'
                f'<span style="font-size:0.85rem;font-weight:600;color:#374151">🔧 Technical Rules</span>'
                f'<span style="font-size:0.85rem;font-weight:700;color:#4f46e5">{tech_rate:.0f}%</span>'
                f'</div>'
                f'<div style="background:#e5e7eb;border-radius:99px;height:8px">'
                f'<div style="background:#4f46e5;width:{tech_rate}%;height:8px;border-radius:99px"></div>'
                f'</div>'
                f'<div style="font-size:0.75rem;color:#9ca3af;margin-top:0.3rem">{tech_passed}/{tech_total} checks passing</div>'
                f'</div>'
                f'<div>'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:0.4rem">'
                f'<span style="font-size:0.85rem;font-weight:600;color:#374151">🤖 Business Rules (AI)</span>'
                f'<span style="font-size:0.85rem;font-weight:700;color:#7c3aed">{biz_rate:.0f}%</span>'
                f'</div>'
                f'<div style="background:#e5e7eb;border-radius:99px;height:8px">'
                f'<div style="background:#7c3aed;width:{biz_rate}%;height:8px;border-radius:99px"></div>'
                f'</div>'
                f'<div style="font-size:0.75rem;color:#9ca3af;margin-top:0.3rem">{biz_passed}/{biz_total} checks passing</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)

        with exec_col2:
            st.markdown('<div class="dq-card">', unsafe_allow_html=True)
            section_heading("Table Health", "Latest run per table", border_color="#6366f1")
            health_resp_e = api_get("/api/v1/reporting/health")
            health_data_e = health_resp_e.get("data", {}).get("tables", []) if health_resp_e.get("success") else []
            if health_data_e:
                for t in health_data_e:
                    hs_t    = t.get("health_score", 0) or 0
                    color_t = "#10b981" if hs_t >= 80 else ("#f59e0b" if hs_t >= 60 else "#ef4444")
                    st.markdown(
                        f'<div style="display:flex;align-items:center;justify-content:space-between;padding:0.6rem 0;border-bottom:1px solid #f3f4f6">'
                        f'<div>'
                        f'<div style="font-size:0.85rem;font-weight:600;color:#1e293b">{t.get("table_name","")}</div>'
                        f'<div style="font-size:0.72rem;color:#9ca3af">{t.get("passed",0)}/{t.get("total_checks",0)} passing</div>'
                        f'</div>'
                        f'<div style="font-size:1.2rem;font-weight:700;color:{color_t}">{hs_t:.0f}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No table health data yet.")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        exec_col3, exec_col4 = st.columns([3, 2])

        with exec_col3:
            st.markdown('<div class="dq-card">', unsafe_allow_html=True)
            section_heading("Pass Rate Trend", f"Last {trend_days} days", border_color="#0891b2")
            trend_resp_e = api_get(f"/api/v1/reporting/trends?days={trend_days}")
            trend_data_e = trend_resp_e.get("data", {}).get("trends", []) if trend_resp_e.get("success") else []
            if trend_data_e:
                df_te = pd.DataFrame(trend_data_e)
                if "run_date" in df_te.columns and "pass_rate_pct" in df_te.columns:
                    df_te["run_date"] = pd.to_datetime(df_te["run_date"])
                    pivot_e = df_te.groupby("run_date")["pass_rate_pct"].mean().reset_index()
                    st.line_chart(pivot_e.set_index("run_date")["pass_rate_pct"], height=220, color="#0891b2")
            else:
                st.caption("No trend data yet.")
            st.markdown('</div>', unsafe_allow_html=True)

        with exec_col4:
            st.markdown('<div class="dq-card">', unsafe_allow_html=True)
            section_heading("Top Failures", "Most critical issues", border_color="#ef4444")
            failed_resp_e = api_get("/api/v1/reporting/failed-rules")
            failed_data_e = failed_resp_e.get("data", {}).get("rules", []) if failed_resp_e.get("success") else []
            if failed_data_e:
                for fe in failed_data_e[:5]:
                    sev_e = fe.get("severity", "WARN")
                    sev_color_e = "#ef4444" if sev_e == "FAIL" else "#f59e0b"
                    st.markdown(
                        f'<div style="padding:0.6rem 0;border-bottom:1px solid #f3f4f6">'
                        f'<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.2rem">'
                        f'<span style="width:8px;height:8px;border-radius:50%;background:{sev_color_e};flex-shrink:0"></span>'
                        f'<span style="font-size:0.82rem;font-weight:600;color:#1e293b">{fe.get("rule_type","").upper()}</span>'
                        f'</div>'
                        f'<div style="font-size:0.75rem;color:#6b7280;padding-left:1.25rem">'
                        f'{fe.get("table_name","")} · {fe.get("column_name","") or "table-level"}</div>'
                        f'<div style="font-size:0.72rem;color:#9ca3af;padding-left:1.25rem">'
                        f'{str(fe.get("observed_value",""))[:50]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                empty_state("No active failures", icon="✓", success=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="dq-card">', unsafe_allow_html=True)
        section_heading("Pipeline & Ingestion Status", "DAG health overview", border_color="#f59e0b")
        fresh_resp_e = api_get("/api/v1/reporting/freshness")
        fresh_data_e = fresh_resp_e.get("data", {}).get("tables", []) if fresh_resp_e.get("success") else []
        pip1, pip2, pip3 = st.columns(3)
        all_healthy_e = all(t.get("freshness_health") == "HEALTHY" for t in fresh_data_e) if fresh_data_e else True
        pip1.markdown(kpi_tile("Data Freshness", "HEALTHY" if all_healthy_e else "AT RISK", accent="#f59e0b", icon="🕐"), unsafe_allow_html=True)
        pip2.markdown(kpi_tile("SLA Breaches", str(sum(1 for t in fresh_data_e if t.get("sla_status") == "FAIL")), accent="#ef4444", icon="⚡"), unsafe_allow_html=True)
        pip3.markdown(kpi_tile("Tables Monitored", str(len(health_data_e)), accent="#4f46e5", icon="◈"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── DQ OBSERVABILITY TAB ───────────────────────────────────────────
    with tab_obs:
        kpi_resp2 = api_get("/api/v1/reporting/kpi")
        kpi2 = kpi_resp2.get("data", {}) if kpi_resp2.get("success") else {}

        c1, c2, c3, c4 = st.columns(4)
        if kpi2:
            pr2  = kpi2.get("pass_rate_pct", 0)
            hs2  = kpi2.get("health_score", 0)
            cf2  = kpi2.get("critical_failures", 0)
            tot2 = kpi2.get("total_checks", 0)
            hs_color2 = "#10b981" if hs2 >= 80 else ("#f59e0b" if hs2 >= 60 else "#ef4444")
            pr_color2 = "#10b981" if pr2 >= 80 else ("#f59e0b" if pr2 >= 60 else "#ef4444")
            cf_color2 = "#10b981" if cf2 == 0 else "#ef4444"
            pr_trend2 = "up" if pr2 >= 80 else ("flat" if pr2 >= 60 else "down")
            c1.markdown(kpi_tile("Pass Rate", f"{pr2:.1f}%", delta=f"{pr2-80:+.1f}% vs target", trend=pr_trend2, accent=pr_color2, icon="✓"), unsafe_allow_html=True)
            c2.markdown(kpi_tile("Health Score", f"{hs2:.0f}", help_text="out of 100", accent=hs_color2, icon="◈"), unsafe_allow_html=True)
            c3.markdown(kpi_tile("Critical Failures", str(cf2), delta="All clear" if cf2 == 0 else f"{cf2} need attention", trend="flat" if cf2 == 0 else "down", accent=cf_color2, icon="⚠"), unsafe_allow_html=True)
            c4.markdown(kpi_tile("Total Checks", str(tot2), help_text="rules evaluated", accent="#4f46e5", icon="⊞"), unsafe_allow_html=True)
        else:
            for col, lbl, ic in zip([c1, c2, c3, c4], ["Pass Rate", "Health Score", "Critical Failures", "Total Checks"], ["✓", "◈", "⚠", "⊞"]):
                col.markdown(kpi_tile(lbl, "—", accent="#9ca3af", icon=ic), unsafe_allow_html=True)
            st.info("No data yet. Execute DQ checks from the **Approvals** page.", icon="ℹ️")

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="dq-card">', unsafe_allow_html=True)
        failed_resp = api_get("/api/v1/reporting/failed-rules")
        failed_data = failed_resp.get("data", {}).get("rules", []) if failed_resp.get("success") else []
        section_heading("Active Failures", f"Last 7 days · {len(failed_data)} open issue(s) · from v_dq_failed_rules", border_color="#ef4444")
        if failed_data:
            df_f = pd.DataFrame(failed_data)
            show_f = [c for c in ["severity", "table_name", "column_name", "rule_type", "observed_value", "expected_value", "failure_count", "hours_open", "execution_time"] if c in df_f.columns]
            def _sev_style(val: str) -> str:
                return {"FAIL": "background:#fef2f2;color:#dc2626;font-weight:600", "WARN": "background:#fffbeb;color:#b45309;font-weight:600"}.get(val, "")
            styled = df_f[show_f].style.map(_sev_style, subset=["severity"]) if "severity" in df_f.columns else df_f[show_f]
            st.dataframe(styled, use_container_width=True, height=320)
            crit = sum(1 for r in failed_data if r.get("severity") == "FAIL")
            warn = sum(1 for r in failed_data if r.get("severity") == "WARN")
            st.markdown(f'<div style="margin-top:0.5rem;font-size:0.78rem;color:#64748b">{badge("FAIL")} {crit} critical &nbsp;&nbsp; {badge("WARN")} {warn} warnings</div>', unsafe_allow_html=True)
        else:
            empty_state("No active failures", sub="All DQ checks passed in the last 7 days.", icon="✓", success=True)
        st.markdown('</div>', unsafe_allow_html=True)

        col_h, col_t = st.columns([3, 2])

        with col_h:
            st.markdown('<div class="dq-card">', unsafe_allow_html=True)
            health_resp = api_get("/api/v1/reporting/health")
            health_data = health_resp.get("data", {}).get("tables", []) if health_resp.get("success") else []
            section_heading("Table Health", "v_dq_table_health — latest run per table", border_color="#6366f1")
            if health_data:
                df_h = pd.DataFrame(health_data)
                if "health_score" in df_h.columns:
                    df_h = df_h.sort_values("health_score", ascending=True)
                show_h = [c for c in ["table_name","health_score","pass_rate_pct","total_checks","passed","failed","critical_failures","hours_since_last_run"] if c in df_h.columns]
                def _hs_style(val):
                    if isinstance(val, (int, float)):
                        if val < 60:  return "color:#dc2626;font-weight:700"
                        if val < 80:  return "color:#d97706;font-weight:600"
                        return "color:#15803d;font-weight:600"
                    return ""
                hs_cols = [c for c in ["health_score","pass_rate_pct"] if c in df_h.columns]
                st.dataframe(df_h[show_h].style.map(_hs_style, subset=hs_cols) if hs_cols else df_h[show_h], use_container_width=True, height=280)
                total_failed = sum(t.get("failed", 0) for t in health_data)
                if total_failed == 0:
                    st.success(f"All checks passing across {len(health_data)} table(s).")
                else:
                    st.error(f"{total_failed} failure(s) across {len(health_data)} table(s).")
            else:
                st.caption("No table health data available yet.")
            st.markdown('</div>', unsafe_allow_html=True)

        with col_t:
            st.markdown('<div class="dq-card">', unsafe_allow_html=True)
            trend_resp = api_get(f"/api/v1/reporting/trends?days={trend_days}")
            trend_data = trend_resp.get("data", {}).get("trends", []) if trend_resp.get("success") else []
            section_heading(f"Pass Rate Trend", f"Last {trend_days} days · v_dq_trend_analysis", border_color="#6366f1")
            if trend_data:
                df_t = pd.DataFrame(trend_data)
                if "run_date" in df_t.columns and "pass_rate_pct" in df_t.columns:
                    df_t["run_date"] = pd.to_datetime(df_t["run_date"])
                    pivot = df_t.groupby("run_date")["pass_rate_pct"].mean().reset_index()
                    st.line_chart(pivot.set_index("run_date")["pass_rate_pct"], height=250, color="#6366f1")
            else:
                st.caption("No trend data available yet.")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="dq-card">', unsafe_allow_html=True)
        fresh_resp = api_get("/api/v1/reporting/freshness")
        fresh_data = fresh_resp.get("data", {}).get("tables", []) if fresh_resp.get("success") else []
        section_heading("Data Freshness", "SLA lag per table · v_dq_freshness_report", border_color="#f59e0b")
        if fresh_data:
            df_fr = pd.DataFrame(fresh_data)
            show_fr = [c for c in ["table_name","freshness_health","sla_status","current_lag","sla_max_lag_hours","last_checked_at"] if c in df_fr.columns]
            def _fresh_style(val: str) -> str:
                return {"HEALTHY": "background:#f0fdf4;color:#15803d;font-weight:600", "AT_RISK": "background:#fffbeb;color:#b45309;font-weight:600", "SLA_BREACH": "background:#fef2f2;color:#dc2626;font-weight:600"}.get(val, "")
            styled_fr = df_fr[show_fr].style.map(_fresh_style, subset=["freshness_health"]) if "freshness_health" in df_fr.columns else df_fr[show_fr]
            st.dataframe(styled_fr, use_container_width=True, height=220)
        else:
            st.caption("No freshness data available yet.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="dq-card">', unsafe_allow_html=True)
        section_heading("Technical DQ vs Business DQ Health", "Rule layer breakdown", border_color="#6366f1")
        tech_col, biz_col = st.columns(2)
        with tech_col:
            st.markdown("#### 🔧 Technical Rules")
            tech_resp = api_get("/api/v1/reporting/technical-health")
            tech_data = tech_resp.get("data", {}).get("tables", []) if tech_resp.get("success") else []
            if tech_data:
                df_tech = pd.DataFrame(tech_data)
                show_t = [c for c in ["table_name","health_score","pass_rate_pct","total_checks","passed","failed","completeness_checks","uniqueness_checks","validity_checks","freshness_checks"] if c in df_tech.columns]
                st.dataframe(df_tech[show_t], use_container_width=True, height=200)
                avg_health = df_tech["health_score"].mean() if "health_score" in df_tech.columns else 0
                color = "#10b981" if avg_health >= 80 else ("#f59e0b" if avg_health >= 60 else "#ef4444")
                st.markdown(f'<div style="font-size:0.9rem;font-weight:600;color:{color}">Avg Health: {avg_health:.1f}/100</div>', unsafe_allow_html=True)
            else:
                st.caption("No technical rule data yet.")
        with biz_col:
            st.markdown("#### 🤖 Business Rules (AI + Data-driven)")
            biz_resp = api_get("/api/v1/reporting/business-health")
            biz_data = biz_resp.get("data", {}).get("tables", []) if biz_resp.get("success") else []
            if biz_data:
                df_biz = pd.DataFrame(biz_data)
                show_b = [c for c in ["table_name","health_score","pass_rate_pct","total_checks","passed","failed","consistency_checks","integrity_checks","top_failures"] if c in df_biz.columns]
                st.dataframe(df_biz[show_b], use_container_width=True, height=200)
                avg_health = df_biz["health_score"].mean() if "health_score" in df_biz.columns else 0
                color = "#10b981" if avg_health >= 80 else ("#f59e0b" if avg_health >= 60 else "#ef4444")
                st.markdown(f'<div style="font-size:0.9rem;font-weight:600;color:{color}">Avg Health: {avg_health:.1f}/100</div>', unsafe_allow_html=True)
            else:
                st.caption("No business rule data yet.")
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ══════════════════════════════════════════════════════════════════════
elif page == "Settings":
    page_header("Settings", "Platform configuration and diagnostics", icon="◉")

    st.markdown('<div class="dq-card">', unsafe_allow_html=True)
    section_heading("API Connection")
    st.text_input("API Base URL", value=API_URL)
    st.text_input("API Key", value=API_KEY, type="password")
    if st.button("Test Connection", type="primary"):
        try:
            r = httpx.get(f"{API_URL}/health", headers=_HEADERS, timeout=5)
            if r.status_code == 200:
                st.success(f"Connected — {r.json()}")
            else:
                st.error(f"HTTP {r.status_code}")
        except Exception as exc:
            st.error(f"Connection failed: {exc}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dq-card">', unsafe_allow_html=True)
    section_heading("Session")
    st.code(st.session_state.get("session_id") or "No active session")
    if st.button("Clear Session"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dq-card">', unsafe_allow_html=True)
    section_heading("Token Usage & Cost", "Claude AI API consumption across all agents", border_color="#7c3aed")

    token_resp = api_get("/api/v1/reporting/token-usage")
    token_data = token_resp.get("data", {}) if token_resp.get("success") else {}

    if token_data:
        summary  = token_data.get("summary", {})
        by_agent = token_data.get("by_agent", [])
        recent   = token_data.get("recent", [])

        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Total API Calls", summary.get("total_calls", 0))
        t2.metric("Total Tokens", f"{summary.get('total_tokens', 0):,}")
        t3.metric("Input Tokens", f"{summary.get('total_input', 0):,}")
        t4.metric("Output Tokens", f"{summary.get('total_output', 0):,}")

        st.markdown("<br>", unsafe_allow_html=True)

        total_cost = summary.get("total_cost_usd", 0) or 0
        cost_color = "#10b981" if total_cost < 1 else ("#f59e0b" if total_cost < 5 else "#ef4444")
        st.markdown(
            f'<div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:10px;'
            f'padding:1rem 1.5rem;margin-bottom:1rem;display:flex;align-items:center;gap:1rem">'
            f'<div style="font-size:2rem;font-weight:800;color:{cost_color}">${total_cost:.4f}</div>'
            f'<div>'
            f'<div style="font-size:0.85rem;font-weight:600;color:#7c3aed">Estimated Total Cost (USD)</div>'
            f'<div style="font-size:0.75rem;color:#9ca3af;margin-top:0.2rem">'
            f'Based on Claude Sonnet pricing — $3/1M input · $15/1M output tokens</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        if by_agent:
            section_heading("Cost by Agent", border_color="#7c3aed")
            df_agent = pd.DataFrame(by_agent)
            show_agent = [c for c in ["agent_name", "calls", "total_tokens",
                                       "input_tokens", "output_tokens",
                                       "cost_usd", "avg_duration_seconds"] if c in df_agent.columns]
            st.dataframe(df_agent[show_agent], use_container_width=True, height=200)

        if recent:
            st.markdown("<br>", unsafe_allow_html=True)
            section_heading("Recent API Calls", border_color="#7c3aed")
            df_recent = pd.DataFrame(recent)
            show_recent = [c for c in ["created_at", "agent_name", "model",
                                        "input_tokens", "output_tokens",
                                        "estimated_cost_usd", "duration_seconds",
                                        "prompt_preview"] if c in df_recent.columns]
            st.dataframe(df_recent[show_recent], use_container_width=True, height=250)
    else:
        st.info("No token usage data yet. Run a pipeline to start tracking API costs.")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dq-card">', unsafe_allow_html=True)
    section_heading("Platform Info")
    st.markdown("""
| Component | Details |
|-----------|---------|
| LLM Engine | Claude (Anthropic) |
| Data Warehouse | Google BigQuery |
| Orchestration | Multi-agent pipeline |
| API | FastAPI + Pydantic v2 |
| Dashboard | Streamlit |
| SP Strategy | Consolidated per-session stored procedure |
| Version | 2.0.0 |
""")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("""
| Component | Details |
|-----------|---------|
| LLM Engine | Claude (Anthropic) |
| Data Warehouse | Google BigQuery |
| Orchestration | Multi-agent pipeline |
| API | FastAPI + Pydantic v2 |
| Dashboard | Streamlit |
| SP Strategy | Consolidated per-session stored procedure |
| Version | 2.0.0 |
""")
    st.markdown('</div>', unsafe_allow_html=True)