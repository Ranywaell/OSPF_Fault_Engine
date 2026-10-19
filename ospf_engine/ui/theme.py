"""Polished dark theme for the Streamlit dashboard.

Design tokens (kept in one place so colours never drift between components):

    surface      #0D1117   page background
    surface-1    #161B22   raised cards
    surface-2    #1F2630   inset code, chips
    border       #30363D   default border
    border-mute  #21262D   subtle border
    text         #E6EDF3   primary
    text-mute    #8B949E   secondary
    text-faint   #6E7681   tertiary
    blue         #58A6FF   primary accent / hyperlinks
    red          #F85149   CONFIG / ROOT_CAUSE
    orange       #F0883E   STRONG / LIKELY_ROOT
    yellow       #D29922   WEAK / CONTRIBUTING
    cyan         #6EAEFF   SIDE_EFFECT
    grey         #8B949E   POSSIBLE
    green        #3FB950   success / OK
"""

from __future__ import annotations


CUSTOM_CSS = """
<style>
    /* ---------- Base layout --------------------------------------------- */

    .main .block-container {
        padding-top: 1.4rem;
        padding-bottom: 4rem;
        max-width: 1320px;
    }

    /* Headings ----------------------------------------------------------- */
    h1, h2, h3, h4 { color: #E6EDF3; letter-spacing: 0.1px; }
    h1 { font-weight: 700; margin: 0 0 0.4rem 0; }
    h2 {
        font-weight: 600;
        margin: 1.6rem 0 0.6rem 0;
        padding-bottom: 0.35rem;
        border-bottom: 1px solid #21262D;
    }
    h3 { font-weight: 600; margin-top: 1.0rem; }

    a, a:visited { color: #58A6FF; text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* ---------- Sidebar ------------------------------------------------- */

    [data-testid="stSidebar"] {
        background: #0B0F14 !important;
        border-right: 1px solid #21262D;
    }
    [data-testid="stSidebar"] h1 {
        font-size: 1.20rem !important;
        margin-bottom: 0 !important;
    }
    [data-testid="stSidebar"] .sb-tagline {
        color: #8B949E;
        font-size: 0.80rem;
        margin: 0 0 1rem 0;
    }
    [data-testid="stSidebar"] hr { margin: 0.6rem 0 !important; }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        padding: 8px 10px;
        margin: 2px 0;
        border-radius: 6px;
        border: 1px solid transparent;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: #161B22;
        border-color: #21262D;
    }

    /* ---------- Hero card (used on Home + tops of pages) ---------------- */

    .fe-hero {
        background:
            radial-gradient(circle at 12% 0%, rgba(88,166,255,0.18) 0%, transparent 38%),
            radial-gradient(circle at 90% 100%, rgba(240,136,62,0.12) 0%, transparent 40%),
            #0F141B;
        border: 1px solid #21262D;
        border-radius: 14px;
        padding: 28px 32px;
        margin-bottom: 1.4rem;
    }
    .fe-hero-eyebrow {
        color: #58A6FF;
        font-family: "JetBrains Mono", "Fira Code", monospace;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    .fe-hero-title {
        color: #E6EDF3;
        font-size: 2.0rem;
        font-weight: 700;
        margin: 0 0 0.4rem 0;
        line-height: 1.15;
    }
    .fe-hero-sub {
        color: #8B949E;
        font-size: 1.00rem;
        max-width: 880px;
        line-height: 1.55;
    }
    .fe-hero-row {
        display: flex;
        gap: 18px;
        margin-top: 1.2rem;
        flex-wrap: wrap;
    }
    .fe-hero-stat {
        background: #0B0F14;
        border: 1px solid #21262D;
        border-radius: 10px;
        padding: 10px 16px;
        min-width: 140px;
    }
    .fe-hero-stat-label {
        color: #6E7681;
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    .fe-hero-stat-value {
        color: #E6EDF3;
        font-size: 1.20rem;
        font-weight: 700;
        font-family: "JetBrains Mono", monospace;
    }

    /* ---------- Reusable card ------------------------------------------- */

    .fe-card {
        background: #0F141B;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 18px 20px;
        margin: 0 0 12px 0;
    }
    .fe-card-title {
        font-weight: 700;
        color: #E6EDF3;
        font-size: 1.02rem;
        margin: 0 0 0.3rem 0;
    }
    .fe-card-sub {
        color: #8B949E;
        font-size: 0.88rem;
        margin: 0 0 0.8rem 0;
        line-height: 1.5;
    }
    .fe-card-body { color: #C9D1D9; line-height: 1.55; }

    /* Step card (used on the Home "How to use" section) */
    .fe-step {
        background: #0F141B;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 18px 20px 20px 20px;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    .fe-step-num {
        width: 32px; height: 32px;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(88,166,255,0.12);
        color: #58A6FF;
        font-weight: 700;
        font-family: "JetBrains Mono", monospace;
        margin-bottom: 0.7rem;
        border: 1px solid rgba(88,166,255,0.35);
    }
    .fe-step-title {
        color: #E6EDF3;
        font-weight: 700;
        font-size: 1.04rem;
        margin: 0 0 0.4rem 0;
    }
    .fe-step-body {
        color: #8B949E;
        font-size: 0.92rem;
        line-height: 1.55;
        flex-grow: 1;
        margin-bottom: 0.8rem;
    }

    /* Fault category chip grid ------------------------------------------ */
    .fe-cat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 10px;
        margin-top: 0.6rem;
    }
    .fe-cat {
        background: #0F141B;
        border: 1px solid #21262D;
        border-radius: 10px;
        padding: 12px 14px;
    }
    .fe-cat-name {
        color: #E6EDF3;
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 0.25rem;
    }
    .fe-cat-list {
        color: #8B949E;
        font-size: 0.85rem;
        line-height: 1.55;
    }

    /* ---------- Ranked-fault card -------------------------------------- */

    .fe-fault {
        background: #0F141B;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 12px;
    }
    .fe-fault-root      { border-left: 4px solid #F85149; }
    .fe-fault-likely    { border-left: 4px solid #F0883E; }
    .fe-fault-contrib   { border-left: 4px solid #D29922; }
    .fe-fault-side      { border-left: 4px solid #6EAEFF; }
    .fe-fault-possible  { border-left: 4px solid #6E7681; }

    .fe-fault-head {
        display: flex; align-items: center; gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 0.4rem;
    }
    .fe-fault-name {
        color: #E6EDF3; font-weight: 700; font-size: 1.05rem;
    }
    .fe-fault-pct {
        margin-left: auto;
        color: #8B949E;
        font-family: "JetBrains Mono", monospace;
        font-size: 0.95rem;
    }
    .fe-fault-cause { color: #C9D1D9; line-height: 1.55; margin: 0.4rem 0; }
    .fe-fault-meta { color: #8B949E; font-size: 0.84rem; }

    /* Pills (level + classification) ------------------------------------ */
    .ev-pill {
        display: inline-block;
        padding: 2px 9px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.4px;
        font-family: "JetBrains Mono", monospace;
        border: 1px solid transparent;
    }
    .ev-pill-config { background: rgba(248,81,73,0.15);  color: #F85149; border-color: rgba(248,81,73,0.45);  }
    .ev-pill-strong { background: rgba(240,136,62,0.15); color: #F0883E; border-color: rgba(240,136,62,0.45); }
    .ev-pill-weak   { background: rgba(210,153,34,0.15); color: #D29922; border-color: rgba(210,153,34,0.45); }
    .ev-pill-root   { background: rgba(248,81,73,0.15);  color: #F85149; border-color: rgba(248,81,73,0.45);  }
    .ev-pill-likely { background: rgba(240,136,62,0.15); color: #F0883E; border-color: rgba(240,136,62,0.45); }
    .ev-pill-side   { background: rgba(110,174,255,0.15); color: #6EAEFF; border-color: rgba(110,174,255,0.45); }
    .ev-pill-poss   { background: rgba(139,148,158,0.15); color: #8B949E; border-color: rgba(139,148,158,0.45); }

    /* Confidence bar ----------------------------------------------------- */
    .conf-bar {
        height: 6px; background: #21262D;
        border-radius: 3px; margin: 6px 0 8px 0;
        overflow: hidden;
    }
    .conf-bar-fill { height: 100%; }
    .conf-bar-fill-config { background: linear-gradient(90deg, #F85149, #F0883E); }
    .conf-bar-fill-strong { background: linear-gradient(90deg, #F0883E, #D29922); }
    .conf-bar-fill-weak   { background: linear-gradient(90deg, #D29922, #6E7681); }

    /* ---------- Diagnosis chain ---------------------------------------- */
    .diag-chain {
        background: #0B0F14;
        border-left: 3px solid #58A6FF;
        padding: 10px 14px;
        margin: 4px 0;
        font-family: "JetBrains Mono", "Fira Code", monospace;
        color: #C9D1D9;
        font-size: 0.92rem;
        border-radius: 0 6px 6px 0;
    }

    /* ---------- Metrics ------------------------------------------------- */
    [data-testid="stMetric"] {
        background: #0F141B;
        border: 1px solid #21262D;
        border-radius: 10px;
        padding: 14px 18px;
    }
    [data-testid="stMetricLabel"] {
        color: #8B949E !important;
        font-size: 0.80rem !important;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    [data-testid="stMetricValue"] {
        color: #E6EDF3 !important;
        font-family: "JetBrains Mono", monospace !important;
        font-size: 1.5rem !important;
    }

    /* ---------- Code blocks -------------------------------------------- */
    pre, code, kbd, samp {
        font-family: "JetBrains Mono", "Fira Code", monospace !important;
    }
    pre {
        background: #0B0F14 !important;
        border: 1px solid #21262D !important;
        border-radius: 8px !important;
    }

    /* ---------- Expanders ---------------------------------------------- */
    .streamlit-expanderHeader,
    [data-testid="stExpander"] > details > summary {
        background: #0F141B !important;
        border-radius: 8px;
        padding: 10px 14px !important;
        font-weight: 600 !important;
        border: 1px solid #21262D;
    }

    /* ---------- Buttons ------------------------------------------------- */
    .stButton > button,
    .stDownloadButton > button {
        border-radius: 8px;
        border: 1px solid #30363D;
        background: #161B22;
        color: #E6EDF3;
        font-weight: 600;
        padding: 8px 18px;
        transition: border-color 120ms ease, background 120ms ease;
    }
    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: #58A6FF;
        background: #1F2630;
        color: #FFFFFF;
    }
    .stButton > button[kind="primary"] {
        background: #1F6FEB;
        border-color: #1F6FEB;
        color: #FFFFFF;
    }
    .stButton > button[kind="primary"]:hover {
        background: #388BFD;
        border-color: #388BFD;
    }

    /* ---------- Tabs ---------------------------------------------------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid #21262D;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border: none;
        color: #8B949E;
        font-weight: 600;
        padding: 10px 16px;
        border-radius: 6px 6px 0 0;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #E6EDF3;
        border-bottom: 2px solid #58A6FF;
    }

    /* ---------- Tables -------------------------------------------------- */
    [data-testid="stTable"] table {
        background: #0F141B;
        border: 1px solid #21262D;
        border-radius: 8px;
        overflow: hidden;
    }
    [data-testid="stTable"] th {
        background: #161B22 !important;
        color: #8B949E !important;
        font-weight: 600 !important;
        border-bottom: 1px solid #21262D !important;
    }
    [data-testid="stTable"] td {
        border-bottom: 1px solid #161B22 !important;
        color: #C9D1D9 !important;
    }

    /* ---------- File uploader ------------------------------------------ */
    [data-testid="stFileUploaderDropzone"] {
        background: #0F141B !important;
        border: 1px dashed #30363D !important;
        border-radius: 12px !important;
    }

    /* ---------- Misc ---------------------------------------------------- */
    hr { border-color: #21262D !important; }
    .fe-footer {
        text-align: center;
        color: #6E7681;
        font-size: 0.80rem;
        margin-top: 2.4rem;
        padding-top: 1.2rem;
        border-top: 1px solid #21262D;
    }

    .fe-tip {
        background: rgba(88,166,255,0.06);
        border: 1px solid rgba(88,166,255,0.30);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 0.6rem 0 0.4rem 0;
        color: #C9D1D9;
        font-size: 0.92rem;
        line-height: 1.55;
    }
    .fe-tip-label {
        color: #58A6FF;
        font-family: "JetBrains Mono", monospace;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-right: 6px;
    }
</style>
"""


def inject(st_module) -> None:
    """Inject the design-system CSS into the active Streamlit page."""
    st_module.markdown(CUSTOM_CSS, unsafe_allow_html=True)
