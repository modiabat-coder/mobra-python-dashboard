"""Centralized Streamlit styling for the MOBRA institutional interface."""

from __future__ import annotations

import streamlit as st

from mobra.config import (
    ACCENT_COLOR,
    BACKGROUND_COLOR,
    BORDER_COLOR,
    BORDER_STRONG_COLOR,
    DANGER_COLOR,
    INFO_COLOR,
    MUTED_TEXT_COLOR,
    PRIMARY_COLOR,
    PRIMARY_DARK,
    SECONDARY_COLOR,
    SIDEBAR_MUTED_COLOR,
    SIDEBAR_TEXT_COLOR,
    SUCCESS_COLOR,
    SURFACE_ALT_COLOR,
    SURFACE_COLOR,
    TEXT_COLOR,
    WARNING_COLOR,
)


def apply_global_styles() -> None:
    """Apply the shared visual system once per Streamlit rerun."""
    st.markdown(
        f"""
        <style>
        :root {{
            --mobra-primary: {PRIMARY_COLOR};
            --mobra-primary-dark: {PRIMARY_DARK};
            --mobra-secondary: {SECONDARY_COLOR};
            --mobra-accent: {ACCENT_COLOR};
            --mobra-success: {SUCCESS_COLOR};
            --mobra-warning: {WARNING_COLOR};
            --mobra-danger: {DANGER_COLOR};
            --mobra-info: {INFO_COLOR};
            --mobra-bg: {BACKGROUND_COLOR};
            --mobra-surface: {SURFACE_COLOR};
            --mobra-surface-alt: {SURFACE_ALT_COLOR};
            --mobra-text: {TEXT_COLOR};
            --mobra-muted: {MUTED_TEXT_COLOR};
            --mobra-border: {BORDER_COLOR};
            --mobra-border-strong: {BORDER_STRONG_COLOR};
            --mobra-sidebar-text: {SIDEBAR_TEXT_COLOR};
            --mobra-sidebar-muted: {SIDEBAR_MUTED_COLOR};
            --mobra-radius-sm: 8px;
            --mobra-radius: 12px;
            --mobra-radius-lg: 14px;
            --mobra-shadow: 0 2px 10px rgba(8,42,56,.055);
            --mobra-focus: 0 0 0 3px rgba(57,167,160,.34);
        }}
        html, body, [class*="css"] {{
            font-family: Aptos, Inter, "Noto Sans Arabic", "Segoe UI", Tahoma, Arial, sans-serif;
        }}
        *, *::before, *::after {{ box-sizing: border-box; }}
        [data-testid="stAppViewContainer"] {{
            background: var(--mobra-bg);
            color: var(--mobra-text);
        }}
        [data-testid="stHeader"] {{
            background: rgba(244,247,248,.94);
        }}
        [data-testid="stMainBlockContainer"] {{
            max-width: 1480px;
            padding-top: .95rem;
            padding-bottom: 3rem;
        }}
        [data-testid="stSidebar"] {{
            background: var(--mobra-primary-dark);
            border-right: 1px solid rgba(255,255,255,.1);
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
            overflow-x: hidden;
        }}
        [data-testid="stSidebar"] * {{
            color: var(--mobra-sidebar-text);
        }}
        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] small {{
            color: var(--mobra-sidebar-muted) !important;
        }}
        [data-testid="stSidebar"] [data-testid="stImage"] {{
            width: 118%;
            max-width: none;
            margin: .55rem 0 .8rem -9%;
        }}
        [data-testid="stSidebar"] [data-testid="stImage"] img {{
            width: 100%;
            max-height: 94px;
            object-fit: contain;
        }}
        .mobra-sidebar-rule {{
            height: 1px;
            background: rgba(255,255,255,.12);
            margin: .75rem 0 1rem;
        }}
        .mobra-sidebar-source {{
            display: inline-flex;
            max-width: 100%;
            margin: .18rem 0 .72rem;
            padding: .32rem .58rem;
            border: 1px solid rgba(113,208,202,.42);
            border-radius: 999px;
            background: rgba(57,167,160,.17);
            color: var(--mobra-sidebar-text);
            font-size: .78rem;
            font-weight: 750;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }}
        .mobra-sidebar-file {{
            margin: .06rem 0 .68rem;
            color: var(--mobra-sidebar-text);
            font-size: .9rem;
            line-height: 1.4;
            overflow-wrap: anywhere;
            word-break: break-word;
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] > div {{
            border-color: rgba(255,255,255,.26) !important;
            background: #F7FBFC !important;
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] *,
        [data-testid="stSidebar"] [data-baseweb="select"] svg {{
            color: var(--mobra-primary-dark) !important;
            fill: var(--mobra-primary-dark) !important;
            -webkit-text-fill-color: var(--mobra-primary-dark) !important;
        }}
        [data-testid="stSidebar"] .react-aria-ComboBox [role="group"] {{
            background: #F7FBFC !important;
            border-color: rgba(255,255,255,.26) !important;
            border-radius: var(--mobra-radius-sm);
        }}
        [data-testid="stSidebar"] .react-aria-ComboBox input,
        [data-testid="stSidebar"] .react-aria-ComboBox button,
        [data-testid="stSidebar"] .react-aria-ComboBox svg {{
            color: var(--mobra-primary-dark) !important;
            fill: var(--mobra-primary-dark) !important;
            -webkit-text-fill-color: var(--mobra-primary-dark) !important;
        }}
        h1, h2, h3, h4 {{
            color: var(--mobra-primary);
            letter-spacing: -.015em;
        }}
        h1 {{ font-size: clamp(1.9rem, 2.3vw, 2.15rem) !important; }}
        h2 {{ font-size: clamp(1.32rem, 1.8vw, 1.68rem) !important; }}
        h3 {{ font-size: 1.12rem !important; }}
        p, li {{ line-height: 1.55; }}
        hr {{ border-color: var(--mobra-border) !important; }}
        [data-testid="stMetric"] {{
            background: var(--mobra-surface);
            border: 1px solid var(--mobra-border);
            border-radius: var(--mobra-radius);
            box-shadow: var(--mobra-shadow);
            padding: .9rem 1rem;
        }}
        .stButton > button,
        .stDownloadButton > button {{
            border-radius: 9px;
            border: 1px solid var(--mobra-secondary);
            min-height: 2.65rem;
            font-weight: 650;
        }}
        .stButton > button:hover,
        .stDownloadButton > button:hover {{
            border-color: var(--mobra-primary);
            color: var(--mobra-primary);
        }}
        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {{
            background: var(--mobra-primary);
            color: white;
            border-color: var(--mobra-primary);
        }}
        button:focus-visible,
        input:focus-visible,
        textarea:focus-visible,
        [role="combobox"]:focus-visible,
        [role="tab"]:focus-visible {{
            outline: 2px solid var(--mobra-accent) !important;
            outline-offset: 2px;
            box-shadow: var(--mobra-focus) !important;
        }}
        button:disabled,
        input:disabled,
        [aria-disabled="true"] {{
            opacity: .55 !important;
            cursor: not-allowed !important;
        }}
        .stTextInput input,
        .stNumberInput input,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] textarea {{
            border-radius: var(--mobra-radius-sm) !important;
            border-color: var(--mobra-border-strong) !important;
        }}
        [data-testid="stFileUploaderDropzone"] {{
            background: #F8FBFB;
            border: 1.5px dashed #8FAEB5;
            border-radius: var(--mobra-radius);
            padding: 1.1rem;
        }}
        [data-testid="stDataFrame"] {{
            border: 1px solid var(--mobra-border);
            border-radius: 10px;
            overflow: hidden;
            background: white;
        }}
        [data-baseweb="tab-list"] {{
            gap: .25rem;
            border-bottom: 1px solid var(--mobra-border);
            overflow-x: auto;
        }}
        [data-baseweb="tab"] {{
            border-radius: 8px 8px 0 0;
            padding: .65rem 1rem;
            font-weight: 650;
            white-space: nowrap;
        }}
        [data-baseweb="tab"][aria-selected="true"] {{
            color: var(--mobra-secondary);
            background: #EAF4F4;
        }}
        [data-testid="stAlert"] {{
            border-radius: 10px;
            border-width: 1px;
        }}
        .mobra-hero {{
            background: var(--mobra-surface);
            border: 1px solid var(--mobra-border);
            border-left: 5px solid var(--mobra-secondary);
            border-radius: var(--mobra-radius-lg);
            padding: 1.25rem 1.4rem;
            margin-bottom: 1.1rem;
            box-shadow: var(--mobra-shadow);
        }}
        .mobra-eyebrow {{
            color: var(--mobra-secondary);
            font-size: .75rem;
            font-weight: 800;
            letter-spacing: .09em;
        }}
        .mobra-hero h1 {{ margin: .2rem 0 .12rem; }}
        .mobra-hero h3 {{
            margin: 0;
            color: var(--mobra-text);
            font-size: 1rem !important;
            font-weight: 650;
            letter-spacing: 0;
        }}
        .mobra-hero p {{ margin: .45rem 0 0; color: var(--mobra-muted); }}
        .mobra-page-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            border-bottom: 1px solid var(--mobra-border);
            padding: 1.55rem 0 .78rem;
            margin-bottom: 1.05rem;
        }}
        .mobra-page-heading {{
            display: flex;
            align-items: flex-start;
            min-width: 0;
        }}
        .mobra-page-header h1 {{
            margin: 0;
            padding: 0 !important;
        }}
        .mobra-page-header p {{
            margin: .25rem 0 0;
            color: var(--mobra-muted);
            max-width: 860px;
        }}
        .mobra-page-icon {{
            width: 2.75rem;
            height: 2.75rem;
            border-radius: 9px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #E6F2F2;
            color: var(--mobra-primary);
            font-size: 1.2rem;
            padding: .2rem;
            margin: 0 .72rem 0 0;
            flex: none;
            object-fit: contain;
        }}
        .mobra-page-icon-fallback {{ padding: 0; }}
        .mobra-header-status {{
            color: var(--mobra-primary);
            background: #EAF4F4;
            margin-top: .2rem;
            white-space: nowrap;
        }}
        .mobra-help {{
            color: var(--mobra-muted);
            cursor: help;
        }}
        .mobra-section {{
            display: flex;
            align-items: center;
            gap: .7rem;
            margin: 1.55rem 0 .7rem;
        }}
        .mobra-section h2 {{ margin: 0; }}
        .mobra-section-line {{ height: 1px; flex: 1; background: var(--mobra-border); }}
        .mobra-metric-grid {{
            display: grid;
            grid-template-columns: repeat(var(--metric-columns, 4), minmax(0, 1fr));
            gap: .75rem;
            width: 100%;
            margin: .1rem 0 .85rem;
        }}
        .mobra-metric-card {{
            min-width: 0;
            min-height: 122px;
            background: var(--mobra-surface);
            border: 1px solid var(--mobra-border);
            border-top: 3px solid var(--metric-accent, var(--mobra-secondary));
            border-radius: var(--mobra-radius);
            padding: .92rem 1rem;
            box-shadow: var(--mobra-shadow);
            overflow-wrap: anywhere;
        }}
        .mobra-metric-label {{
            color: var(--mobra-muted);
            font-size: .76rem;
            font-weight: 750;
            letter-spacing: .035em;
            text-transform: uppercase;
        }}
        .mobra-metric-value {{
            color: var(--mobra-primary);
            font-size: clamp(1.45rem, 2vw, 1.78rem);
            font-weight: 800;
            line-height: 1.17;
            margin: .38rem 0 .2rem;
            overflow-wrap: anywhere;
        }}
        .mobra-metric-note {{
            color: var(--mobra-muted);
            font-size: .79rem;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }}
        .mobra-badge {{
            display: inline-flex;
            align-items: center;
            gap: .3rem;
            border-radius: 999px;
            padding: .25rem .58rem;
            font-size: .76rem;
            font-weight: 750;
            line-height: 1.2;
            border: 1px solid currentColor;
        }}
        .mobra-decision {{
            border-radius: var(--mobra-radius-lg);
            border: 1px solid color-mix(in srgb, var(--decision-color) 35%, white);
            border-left: 8px solid var(--decision-color);
            background: color-mix(in srgb, var(--decision-color) 7%, white);
            padding: 1.2rem 1.35rem;
            margin: .7rem 0 1.2rem;
        }}
        .mobra-decision-label {{
            color: var(--decision-color);
            font-weight: 800;
            font-size: .78rem;
            letter-spacing: .08em;
        }}
        .mobra-decision h2 {{ color: var(--decision-color); margin: .28rem 0; }}
        .mobra-decision p {{ color: var(--mobra-text); margin: .35rem 0 0; }}
        .mobra-empty {{
            text-align: center;
            background: white;
            border: 1px dashed #AFC4C9;
            border-radius: var(--mobra-radius-lg);
            padding: 2.2rem 1.25rem;
            margin: 1rem 0;
        }}
        .mobra-empty-icon {{ font-size: 2.2rem; margin-bottom: .5rem; }}
        .mobra-empty h3 {{ margin: .25rem 0; }}
        .mobra-empty p {{ color: var(--mobra-muted); margin: .25rem auto; max-width: 620px; }}
        .mobra-step {{
            display: flex;
            gap: .75rem;
            align-items: flex-start;
            padding: .7rem .2rem;
        }}
        .mobra-step-number {{
            width: 1.8rem;
            height: 1.8rem;
            flex: none;
            border-radius: 50%;
            background: var(--mobra-primary);
            color: white;
            font-weight: 800;
            display: inline-flex;
            justify-content: center;
            align-items: center;
        }}
        .mobra-step strong {{ color: var(--mobra-primary); }}
        @media (max-width: 1200px) {{
            .mobra-metric-grid {{
                grid-template-columns: repeat(min(var(--metric-columns, 4), 2), minmax(0, 1fr));
            }}
        }}
        @media (max-width: 850px) {{
            [data-testid="stMainBlockContainer"] {{
                padding-left: 1rem;
                padding-right: 1rem;
            }}
            .mobra-page-header {{ display: block; }}
            .mobra-header-status {{ margin: .7rem 0 0 3.15rem; }}
            [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; }}
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
                flex: 1 1 210px !important;
                width: auto !important;
                min-width: min(210px, 100%) !important;
            }}
        }}
        @media (max-width: 780px) {{
            .mobra-metric-grid {{ grid-template-columns: minmax(0, 1fr); }}
            .mobra-metric-card {{ min-height: 108px; }}
            .mobra-page-heading {{ align-items: flex-start; }}
            .mobra-page-header p {{ font-size: .92rem; }}
        }}
        @media print {{
            [data-testid="stSidebar"], [data-testid="stHeader"] {{ display:none !important; }}
            [data-testid="stMainBlockContainer"] {{ max-width:none; padding:0; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
