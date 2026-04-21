"""
app.py - Macroeconomic Database Explorer
Supports CPI, Balance of Payments, Monetary & Financial Statistics, Fiscal Statistics, Interest Rates, and National Accounts
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

MAP_TABLE = {
    'CONSUMER PRICE INDEX AND INFLATION': 'FACT_CPI',
    'BALANCE OF PAYMENTS': 'FACT_BOP',
    'MONETARY AND FINANCIAL STATISTICS': 'FACT_MONETARY',
    'FISCAL STATISTICS': 'FACT_FISC',
    'INTEREST RATES': 'FACT_INTEREST',
    'NATIONAL ACCOUNTS': 'FACT_GDP',
}

# Maps our indicator_type keys to the SECTION values actually stored in
# DIM_INDICATOR.SECTION.  Use None for tables whose DB section code is unknown
# — those fall back to a fact-table JOIN in get_indicators.
DB_SECTION_MAP = {
    'CONSUMER PRICE INDEX AND INFLATION': 'CPI',
    'BALANCE OF PAYMENTS': 'BOP',
    'MONETARY AND FINANCIAL STATISTICS': None,
    'FISCAL STATISTICS': None,
    'INTEREST RATES': None,
    'NATIONAL ACCOUNTS': None,
}

try:
    from .database import (
        get_oracle_connection,
        get_data,
        get_locations,
        get_units,
        get_units_for_indicators,
        test_connection,
        get_indicators
    )
except ImportError:
    # Running directly (e.g., streamlit run app.py)
    from database import (
        get_oracle_connection,
        get_data,
        get_locations,
        get_units,
        get_units_for_indicators,
        test_connection,
        get_indicators
    )

# ────────────────────────────────────────────────
#   Page config & global styling
# ────────────────────────────────────────────────
st.set_page_config(page_title="Macroeconomic Database Explorer", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ══════════════════════════════════════════════════════════════════
       GLOBAL FOUNDATIONS
    ══════════════════════════════════════════════════════════════════ */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: linear-gradient(145deg, #f8fafc, #f1f5f9);
    }

    /* Smooth transitions on all interactive elements */
    *, *::before, *::after {
        transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
    }

    /* Custom scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }

    /* Focus states for accessibility */
    button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {
        outline: 2px solid #3b82f6 !important;
        outline-offset: 2px !important;
    }

    /* Enhanced dividers */
    hr {
        margin: 1.8rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #e2e8f0 20%, #e2e8f0 80%, transparent);
    }

    /* ══════════════════════════════════════════════════════════════════
       ANIMATIONS
    ══════════════════════════════════════════════════════════════════ */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-10px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    /* ══════════════════════════════════════════════════════════════════
       SIDEBAR STYLING
    ══════════════════════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
    }

    section[data-testid="stSidebar"] * {
        color: white !important;
    }

    section[data-testid="stSidebar"] .stMarkdown {
        color: white !important;
    }

    section[data-testid="stSidebar"] h3 {
        color: white !important;
        font-weight: 600 !important;
    }

    section[data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.1) !important;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent) !important;
    }

    section[data-testid="stSidebar"] button {
        color: white !important;
        background: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        backdrop-filter: blur(10px);
    }

    section[data-testid="stSidebar"] button:hover {
        background: rgba(255, 255, 255, 0.15) !important;
        border-color: rgba(255, 255, 255, 0.3) !important;
    }

    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
    }

    /* ══════════════════════════════════════════════════════════════════
       TAB NAVIGATION
    ══════════════════════════════════════════════════════════════════ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: white;
        border-radius: 16px;
        padding: 10px 14px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    }

    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 12px;
        color: #475569;
        font-weight: 500;
        padding: 0 24px;
        background: transparent;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: #f1f5f9 !important;
        color: #1e293b !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35) !important;
    }

    /* ══════════════════════════════════════════════════════════════════
       BUTTONS
    ══════════════════════════════════════════════════════════════════ */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        font-weight: 600;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        border: none;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
    }

    .stButton > button:active {
        transform: translateY(0);
    }

    /* Download buttons */
    .stDownloadButton > button {
        background: white !important;
        color: #1e293b !important;
        border: 2px solid #e2e8f0 !important;
        border-radius: 10px !important;
    }

    .stDownloadButton > button:hover {
        border-color: #3b82f6 !important;
        background: #f8fafc !important;
    }

    /* ══════════════════════════════════════════════════════════════════
       EXPANDERS & FORM ELEMENTS
    ══════════════════════════════════════════════════════════════════ */
    .stExpander {
        background: white;
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    /* Input fields */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        border-radius: 10px !important;
        border: 2px solid #e2e8f0 !important;
    }

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15) !important;
    }

    /* Multiselect chips */
    .stMultiSelect [data-baseweb="tag"] {
        background: linear-gradient(135deg, #eff6ff, #dbeafe) !important;
        border-radius: 8px !important;
        border: 1px solid #bfdbfe !important;
        color: #1e40af !important;
    }

    /* ══════════════════════════════════════════════════════════════════
       ALERTS & MESSAGES
    ══════════════════════════════════════════════════════════════════ */
    .stAlert {
        border-radius: 12px !important;
        border: none !important;
    }

    div[data-testid="stNotification"] {
        border-radius: 12px !important;
    }

    /* Success messages */
    .element-container:has(.stSuccess) .stSuccess {
        background: linear-gradient(135deg, #ecfdf5, #d1fae5) !important;
        border-left: 4px solid #10b981 !important;
    }

    /* Error messages */
    .element-container:has(.stError) .stError {
        background: linear-gradient(135deg, #fef2f2, #fee2e2) !important;
        border-left: 4px solid #ef4444 !important;
    }

    /* Warning messages */
    .element-container:has(.stWarning) .stWarning {
        background: linear-gradient(135deg, #fffbeb, #fef3c7) !important;
        border-left: 4px solid #f59e0b !important;
    }

    /* Info messages */
    .element-container:has(.stInfo) .stInfo {
        background: linear-gradient(135deg, #eff6ff, #dbeafe) !important;
        border-left: 4px solid #3b82f6 !important;
    }

    /* ══════════════════════════════════════════════════════════════════
       DATA TABLE
    ══════════════════════════════════════════════════════════════════ */
    .stDataFrame {
        border-radius: 12px !important;
        overflow: hidden;
    }

    /* ══════════════════════════════════════════════════════════════════
       METRICS
    ══════════════════════════════════════════════════════════════════ */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e293b;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #64748b;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ══════════════════════════════════════════════════════════════════
       SPINNER
    ══════════════════════════════════════════════════════════════════ */
    .stSpinner > div {
        border-color: #3b82f6 transparent transparent transparent !important;
    }

    /* ══════════════════════════════════════════════════════════════════
       LOGIN FORM STYLING
    ══════════════════════════════════════════════════════════════════ */
    .login-container {
        max-width: 520px;
        margin: 2rem auto;
        background: white;
        border-radius: 24px;
        box-shadow: 0 8px 40px rgba(0,0,0,0.08);
        padding: 2.5rem;
        animation: fadeInUp 0.5s ease-out;
    }

    .login-hero {
        text-align: center;
        margin-bottom: 2rem;
    }

    .login-hero-icon {
        width: 80px;
        height: 80px;
        margin: 0 auto 1rem;
        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        border-radius: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 8px 24px rgba(59, 130, 246, 0.3);
    }

    .login-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.5rem;
    }

    .login-subtitle {
        color: #64748b;
        font-size: 0.95rem;
    }

    /* ══════════════════════════════════════════════════════════════════
       FILTER SECTION HEADERS
    ══════════════════════════════════════════════════════════════════ */
    .filter-section-time {
        background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
        border-left: 4px solid #0ea5e9;
        padding: 0.75rem 1rem;
        border-radius: 0 12px 12px 0;
        margin-bottom: 1rem;
    }

    .filter-section-location {
        background: linear-gradient(135deg, #fefce8, #fef9c3);
        border-left: 4px solid #eab308;
        padding: 0.75rem 1rem;
        border-radius: 0 12px 12px 0;
        margin-bottom: 1rem;
    }

    .filter-section-indicators {
        background: linear-gradient(135deg, #f5f3ff, #ede9fe);
        border-left: 4px solid #8b5cf6;
        padding: 0.75rem 1rem;
        border-radius: 0 12px 12px 0;
        margin-bottom: 1rem;
    }

    .filter-section-title {
        font-weight: 600;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0;
    }

    /* ══════════════════════════════════════════════════════════════════
       HEADER GLASSMORPHISM
    ══════════════════════════════════════════════════════════════════ */
    .header-glass {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 20px;
        padding: 1.25rem 1.5rem;
        box-shadow: 0 4px 24px rgba(0,0,0,0.06);
        border: 1px solid rgba(255, 255, 255, 0.6);
        margin-bottom: 1.5rem;
    }

    .header-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: -0.02em;
        margin: 0;
    }

    .header-subtitle {
        color: #64748b;
        font-size: 1rem;
        margin: 0.25rem 0 0 0;
    }

    .connection-dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        background: #22c55e;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse 2s infinite;
        box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
    }

    /* ══════════════════════════════════════════════════════════════════
       METRIC CARDS
    ══════════════════════════════════════════════════════════════════ */
    .metric-card-blue {
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        border: 1px solid #bfdbfe;
    }

    .metric-card-green {
        background: linear-gradient(135deg, #f0fdf4, #dcfce7);
        border: 1px solid #bbf7d0;
    }

    .metric-card-yellow {
        background: linear-gradient(135deg, #fffbeb, #fef3c7);
        border: 1px solid #fde68a;
    }

    .metric-card-purple {
        background: linear-gradient(135deg, #faf5ff, #f3e8ff);
        border: 1px solid #e9d5ff;
    }

    .metric-card {
        padding: 1.5rem;
        border-radius: 16px;
        text-align: center;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    }

    .metric-icon-badge {
        position: absolute;
        top: 12px;
        right: 12px;
        font-size: 1.5rem;
        opacity: 0.6;
    }

    .metric-label {
        font-size: 0.7rem;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.5rem;
    }

    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.2;
    }

    .metric-value-small {
        font-size: 1.25rem;
    }
    </style>
""", unsafe_allow_html=True)

# ──── Header ────────────────────────────────────────────────────────────────
import os
logo_path = os.path.join(os.path.dirname(__file__), "botlogo.png")

# Show connection indicator when connected
connection_indicator = '<span class="connection-dot"></span>' if st.session_state.get('connected', False) else ''

st.markdown(f"""
    <div class="header-glass">
        <div style="text-align: center;">
            <h1 class="header-title" style="margin: 0;">
                {connection_indicator}Macroeconomic Database Explorer
            </h1>
            <p class="header-subtitle" style="margin: 0.25rem 0 0 0;">
                Bank of Tanzania Hub for Macroeconomic and Financial Statistics
            </p>
        </div>
    </div>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
#   Session state & login
# ────────────────────────────────────────────────
if 'connected' not in st.session_state:
    st.session_state.connected = False
    st.session_state.conn = None

if not st.session_state.connected:
    # Create centered columns for the form
    col_space1, col_form, col_space2 = st.columns([1, 2, 1])

    with col_form:
        with st.form("login"):
            st.markdown("""
                <div class="filter-section-indicators" style="margin-bottom: 1.5rem;">
                    <p class="filter-section-title" style="color: #6d28d9;">🔐 Credentials</p>
                </div>
            """, unsafe_allow_html=True)

            username = st.text_input("Username", value=os.getenv("DB_USERNAME", ""), placeholder="Enter your username")
            password = st.text_input("Password", type="password", value=os.getenv("DB_PASSWORD", ""), placeholder="Enter your password")

            st.markdown("""
                <div class="filter-section-time" style="margin: 1.5rem 0 1rem 0;">
                    <p class="filter-section-title" style="color: #0369a1;">🖥️ Server Configuration</p>
                </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                host = st.text_input("Host", value=os.getenv("DB_HOST", ""),
                                   help="Database server hostname or IP",
                                   placeholder="172.16.1.219")
            with col2:
                port = st.number_input("Port", value=int(os.getenv("DB_PORT", "1522")), min_value=1, max_value=65535,
                                     help="Database port number")

            service_name = st.text_input("Service Name", value=os.getenv("DB_SERVICE_NAME", ""),
                                       help="Database service name",
                                       placeholder="BOT6DB")

            st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

            submitted = st.form_submit_button("🔌 Connect to Database", type="primary", use_container_width=True)

            if submitted:
                username = username.strip()
                host = host.strip()
                service_name = service_name.strip()
                missing = [name for name, val in [
                    ("Username", username),
                    ("Password", password),
                    ("Host", host),
                    ("Service Name", service_name),
                ] if not val]
                if not missing:
                    with st.spinner("🔄 Establishing connection..."):
                        try:
                            conn = get_oracle_connection(username, password, host, int(port), service_name)
                            if conn:
                                st.session_state.connected = True
                                st.session_state.conn = conn
                                st.session_state.connection_info = {
                                    'username': username,
                                    'host': host,
                                    'port': port,
                                    'service_name': service_name
                                }
                                st.success("Connected successfully! Redirecting...")
                                st.rerun()
                            else:
                                st.error("Connection failed. Please verify your credentials.")
                        except Exception as e:
                            st.error(f"Connection error: {str(e)}")
                else:
                    st.warning(f"Please fill in: {', '.join(missing)}")
    st.stop()

conn = st.session_state.conn

# Load reference data with error handling
try:
    locations = get_locations(conn) or ["Tanzania"]
    units = get_units(conn) or []
except Exception as e:
    st.error(f"Error loading reference data: {e}")
    locations = ["Tanzania"]
    units = []

# ────────────────────────────────────────────────
#   Enhanced render_data_display (Plotly + metrics)
# ────────────────────────────────────────────────
def render_data_display(df: pd.DataFrame, title: str, indicator_type: str, filters: dict = None, conn = None):
    """Enhanced data display with better visualizations and metrics"""
    if df.empty:
        st.warning(f"No data found for {title}. Try adjusting your filters.")
        return

    st.markdown(f"### {title} Results")
    st.markdown("---")

    # Enhanced metrics cards with colored gradients and icons
    cols = st.columns(4)

    # Total rows - Blue gradient
    with cols[0]:
        st.markdown(f"""
            <div class='metric-card metric-card-blue'>
                <span class='metric-icon-badge'>📊</span>
                <div class='metric-label' style='color: #1d4ed8;'>Total Records</div>
                <div class='metric-value'>{len(df):,}</div>
            </div>
        """, unsafe_allow_html=True)

    # Time period - Green gradient
    time_col = next((c for c in ["TIME_PERIOD", "YEAR", "FISCAL_YEAR", "PERIOD"] if c in df.columns), None)
    if time_col:
        min_val = df[time_col].min()
        max_val = df[time_col].max()
        try:
            if hasattr(min_val, 'strftime'):
                min_str = min_val.strftime('%Y-%m-%d')
                max_str = max_val.strftime('%Y-%m-%d')
            else:
                min_str = str(min_val)
                max_str = str(max_val)
        except:
            min_str = str(min_val)
            max_str = str(max_val)
        time_range = f"{min_str} — {max_str}"
        with cols[1]:
            st.markdown(f"""
                <div class='metric-card metric-card-green'>
                    <span class='metric-icon-badge'>📅</span>
                    <div class='metric-label' style='color: #15803d;'>Time Range</div>
                    <div class='metric-value metric-value-small'>{time_range}</div>
                </div>
            """, unsafe_allow_html=True)

    # Number of series - Yellow gradient
    numeric = df.select_dtypes("number").columns.tolist()
    with cols[2]:
        st.markdown(f"""
            <div class='metric-card metric-card-yellow'>
                <span class='metric-icon-badge'>📈</span>
                <div class='metric-label' style='color: #a16207;'>Data Series</div>
                <div class='metric-value'>{len(numeric)}</div>
            </div>
        """, unsafe_allow_html=True)

    # Location - Purple gradient
    location_val = df.get("LOCATION_NAME", df.get("LOCATION", pd.Series(["—"]))).iloc[0]
    with cols[3]:
        st.markdown(f"""
            <div class='metric-card metric-card-purple'>
                <span class='metric-icon-badge'>🌍</span>
                <div class='metric-label' style='color: #7c3aed;'>Location</div>
                <div class='metric-value' style='font-size: 1.4rem;'>{location_val}</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
    
    # Show indicator descriptions if available
    if 'DESCRIPTION' in df.columns:
        indicator_desc = df[['INDICATOR_NAME', 'DESCRIPTION']].drop_duplicates() if 'INDICATOR_NAME' in df.columns else pd.DataFrame()
        
        if not indicator_desc.empty and indicator_desc['DESCRIPTION'].notna().any():
            with st.expander("📋 Indicator Descriptions", expanded=False):
                for _, row in indicator_desc.iterrows():
                    if pd.notna(row['DESCRIPTION']) and row['DESCRIPTION'].strip():
                        st.markdown(f"""
                            <div style='background: #f8fafc; padding: 0.8rem; border-radius: 6px; margin-bottom: 0.8rem; border-left: 3px solid #3b82f6;'>
                                <div style='font-weight: 600; color: #1e293b; margin-bottom: 0.3rem;'>{row['INDICATOR_NAME']}</div>
                                <div style='color: #64748b; font-size: 0.9rem;'>{row['DESCRIPTION']}</div>
                            </div>
                        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # Enhanced Plotly chart with improved colors and layout
    if time_col and len(numeric) > 0:
        id_vars = [time_col]
        if "LOCATION_NAME" in df.columns:
            id_vars.append("LOCATION_NAME")
        elif "LOCATION" in df.columns:
            id_vars.append("LOCATION")

        value_vars = [c for c in df.columns if c not in id_vars + ["UNIT_NAME", "INDICATOR_CODE", "LOCATION_CODE", "DESCRIPTION"]]

        if value_vars:
            df_long = pd.melt(df, id_vars=id_vars, value_vars=value_vars,
                             var_name="Indicator", value_name="Value")
            df_long = df_long.dropna(subset=["Value"])
            df_long = df_long.sort_values(time_col)

            # Get chart type from session state (default to Line)
            chart_type = st.session_state.get('chart_type', 'Line')

            if chart_type == "Bar":
                fig = px.bar(
                    df_long,
                    x=time_col,
                    y="Value",
                    color="Indicator",
                    barmode="group",
                    title=f"{title} — Time Series",
                    height=600
                )
            else:
                fig = px.line(
                    df_long,
                    x=time_col,
                    y="Value",
                    color="Indicator",
                    markers=False,
                    title=f"{title} — Time Series",
                    height=600
                )

            fig.update_layout(
                hovermode="x unified",
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=1.01,
                    bgcolor="rgba(255,255,255,0.95)",
                    bordercolor="rgba(0,0,0,0.2)",
                    borderwidth=1,
                    font=dict(size=11)
                ),
                xaxis_title=None,
                yaxis_title="Value",
                margin=dict(l=60, r=200, t=80, b=60),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="white",
                font=dict(family="Inter, sans-serif"),
                title_font_size=18,
                title_font_color="#1e293b",
                title_x=0.02
            )

            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)', tickangle=-45)
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')

            # Check if x-axis contains year data (integers between 1900-2100)
            try:
                x_values = df_long[time_col].dropna()
                if x_values.dtype in ['int64', 'float64']:
                    min_val, max_val = x_values.min(), x_values.max()
                    if 1900 <= min_val <= 2100 and 1900 <= max_val <= 2100:
                        # It's year data - display as integers without comma separator
                        fig.update_xaxes(dtick=1, tickformat=".0f")
            except:
                pass

            if df_long["Value"].max() > 1e6:
                fig.update_yaxes(tickformat=",")

            fig.update_traces(
                hovertemplate="<b>%{fullData.name}</b><br>" +
                             time_col + ": %{x}<br>" +
                             "Value: %{y:,.2f}<extra></extra>",
                line=dict(width=2.5)
            )

            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Data table with enhanced display
    with st.expander("📋 View Raw Data & Download", expanded=False):
        display_df = df.copy()
        
        for col in numeric:
            if display_df[col].dtype in ['float64', 'float32']:
                display_df[col] = display_df[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "—")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)
        
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download CSV",
                csv,
                f"{indicator_type.lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )
        with col_dl2:
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                # Data sheet
                df.to_excel(writer, index=False, sheet_name='Data')

                # Metadata sheet (SDMX-style) - if conn available
                if conn:
                    try:
                        fact_table = MAP_TABLE.get(indicator_type, 'FACT_CPI')

                        # Get indicators from filters or extract from loaded data columns
                        selected_indicators = []
                        if filters and filters.get('selected_indicators'):
                            selected_indicators = filters.get('selected_indicators')
                        else:
                            # Extract indicator names from DataFrame columns (excluding standard columns)
                            standard_cols = ['TIME_PERIOD', 'YEAR', 'MONTH', 'QUARTER', 'LOCATION_NAME',
                                           'LOCATION', 'UNIT', 'DESCRIPTION', 'INDICATOR_TYPE', 'SECTION']
                            selected_indicators = [col for col in df.columns if col not in standard_cols]

                        selected_units = filters.get('selected_units') if filters else []

                        # Build metadata query - must have at least indicator filter
                        if selected_indicators:
                            params = {}
                            ind_placeholders = ','.join([f':ind{i}' for i in range(len(selected_indicators))])
                            params.update({f'ind{i}': name for i, name in enumerate(selected_indicators)})

                            unit_filter = ""
                            if selected_units:
                                unit_placeholders = ','.join([f':unit{i}' for i in range(len(selected_units))])
                                unit_filter = f"AND u.UNIT IN ({unit_placeholders})"
                                params.update({f'unit{i}': name for i, name in enumerate(selected_units)})

                            metadata_query = f"""
                                SELECT DISTINCT
                                    i.INDICATOR_NAME,
                                    i.DESCRIPTION,
                                    i.DEFINITION,
                                    i.INDICATOR_TYPE,
                                    i.SECTION,
                                    u.UNIT,
                                    l.LOCATION_NAME,
                                    s.SOURCE
                                FROM {fact_table} f
                                JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
                                LEFT JOIN DIM_UNITS u ON f.UNIT_ID = u.UNIT_ID
                                JOIN DIM_LOCATION l ON f.LOCATION_ID = l.LOCATION_ID
                                LEFT JOIN DIM_SOURCES s ON f.SOURCE_ID = s.SOURCE_ID
                                WHERE i.INDICATOR_NAME IN ({ind_placeholders})
                                {unit_filter}
                                ORDER BY i.INDICATOR_NAME
                            """

                            cursor = conn.cursor()
                            cursor.execute(metadata_query, params)
                            rows = cursor.fetchall()
                            columns = [desc[0] for desc in cursor.description]
                            cursor.close()

                            if rows:
                                metadata_df = pd.DataFrame(rows, columns=columns)
                                metadata_df.to_excel(writer, index=False, sheet_name='Metadata')
                    except Exception as e:
                        pass  # Skip metadata sheet if query fails

            excel_buffer.seek(0)

            st.download_button(
                "📊 Download Excel",
                excel_buffer.getvalue(),
                f"{indicator_type.lower()}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

# ────────────────────────────────────────────────
#   Reusable Filter Component
# ────────────────────────────────────────────────
def render_filters(indicator_type: str, locations: list, units: list, conn, data_frequency: str = 'monthly'):
    """Reusable filter component for all indicator tabs.

    Args:
        data_frequency: Native frequency of the data — 'monthly', 'quarterly', or 'annual'.
                        When 'annual', frequency conversion is disabled and aggregation
                        is locked to 'annual'.
    """

    # Query Builder header
    st.markdown("""
        <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
            <div style='background: linear-gradient(135deg, #3b82f6, #1d4ed8); width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center;'>
                <span style='font-size: 1.1rem;'>🔍</span>
            </div>
            <div>
                <h4 style='margin: 0; color: #1e293b; font-size: 1.1rem; font-weight: 600;'>Query Builder</h4>
                <p style='margin: 0; color: #64748b; font-size: 0.8rem;'>Configure your data filters below</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("📋 Filters & Options", expanded=True):
        col_time_loc, col_ind_units = st.columns([1.4, 1])

        with col_time_loc:
            # Time Period Section - Blue gradient
            st.markdown("""
                <div class="filter-section-time">
                    <p class="filter-section-title" style="color: #0369a1;">⏰ Time Period</p>
                </div>
            """, unsafe_allow_html=True)

            use_range = st.checkbox(
                "Use date range instead of years",
                value=False,
                key=f"{indicator_type}_use_range",
                help="Select specific months within a date range"
            )

            if use_range:
                c1, c2 = st.columns(2)
                with c1:
                    start_dt = st.date_input(
                        "Start date",
                        value=pd.to_datetime("2020-01-01"),
                        min_value=pd.to_datetime("1960-01-01"),
                        max_value=pd.to_datetime("2050-12-31"),
                        key=f"{indicator_type}_start_dt"
                    )
                with c2:
                    end_dt = st.date_input(
                        "End date",
                        value=pd.Timestamp.today(),
                        min_value=pd.to_datetime("1960-01-01"),
                        max_value=pd.to_datetime("2050-12-31"),
                        key=f"{indicator_type}_end_dt"
                    )
                start_year = start_dt.year
                end_year = end_dt.year
                start_month = start_dt.month
                end_month = end_dt.month
            else:
                c1, c2 = st.columns(2)
                with c1:
                    start_year = st.number_input(
                        "From year",
                        min_value=1960,
                        max_value=2050,
                        value=2020,
                        key=f"{indicator_type}_from_year"
                    )
                with c2:
                    end_year = st.number_input(
                        "To year",
                        min_value=1960,
                        max_value=2050,
                        value=2023,
                        key=f"{indicator_type}_to_year"
                    )
                start_month = end_month = None

            # Location & Aggregation Section - Yellow gradient
            st.markdown("""
                <div class="filter-section-location" style="margin-top: 1.25rem;">
                    <p class="filter-section-title" style="color: #a16207;">📍 Location & Aggregation</p>
                </div>
            """, unsafe_allow_html=True)

            location = st.selectbox(
                "Location",
                locations,
                index=locations.index("Tanzania") if "Tanzania" in locations else 0,
                key=f"{indicator_type}_location_select"
            )

            aggregation_labels = {
                "monthly": "Monthly",
                "quarterly": "Quarterly",
                "annual": "Annual (Calendar Year)",
                "fiscal_year": "Annual (Fiscal Year)"
            }
            if data_frequency == 'annual':
                aggregation = 'annual'
                st.selectbox(
                    "Aggregation level",
                    ["annual"],
                    format_func=lambda x: aggregation_labels.get(x, x),
                    key=f"{indicator_type}_agg_select",
                    disabled=True,
                    help="This dataset is annual-frequency — frequency conversion is not available"
                )
            else:
                aggregation = st.selectbox(
                    "Aggregation level",
                    ["monthly", "quarterly", "annual", "fiscal_year"],
                    format_func=lambda x: aggregation_labels.get(x, x),
                    key=f"{indicator_type}_agg_select",
                    help="Choose how to aggregate the time series data"
                )

        with col_ind_units:
            # Indicators & Units Section - Purple gradient
            st.markdown("""
                <div class="filter-section-indicators">
                    <p class="filter-section-title" style="color: #6d28d9;">📊 Indicators & Units</p>
                </div>
            """, unsafe_allow_html=True)

            try:
                db_section = DB_SECTION_MAP.get(indicator_type)
                if db_section:
                    # Use the DB's own SECTION code — reliable for tables
                    # whose section label is known (CPI, BOP).
                    ind_df = get_indicators(conn, section=db_section)
                else:
                    # Section code unknown — discover indicators via fact table join.
                    ind_df = get_indicators(conn, fact_table=MAP_TABLE.get(indicator_type))
                if not ind_df.empty:
                    ind_map = {}
                    for _, row in ind_df.iterrows():
                        desc = str(row.get('DESCRIPTION', '') or '').strip()
                        label = desc if desc else row['INDICATOR_NAME']
                        ind_map[label] = row['INDICATOR_NAME']
                    ind_options = sorted(ind_map.keys())
                else:
                    ind_map = {}
                    ind_options = []
            except Exception as e:
                ind_map = {}
                ind_options = []
                st.caption(f"Could not load indicators: {str(e)[:50]}")

            selected_labels = st.multiselect(
                "Indicators",
                options=ind_options,
                default=[],
                key=f"{indicator_type}_indicators_ms",
                placeholder="All (if empty)",
                help=f"Select specific {indicator_type} indicators to display"
            )
            selected_indicators = [ind_map[label] for label in selected_labels]

            # Get units relevant to selected indicators (from fact table join)
            if selected_indicators:
                # Convert to tuple for caching
                available_units = get_units_for_indicators(conn, tuple(selected_indicators), indicator_type)
            else:
                # No indicators selected - show all units for this type
                available_units = units if units else []

            if available_units:
                selected_units = st.multiselect(
                    "Units",
                    options=available_units,
                    default=[],
                    key=f"{indicator_type}_units_ms",
                    placeholder="All (if empty)",
                    help="Units available for the selected indicators"
                )
            else:
                selected_units = []
                if selected_indicators:
                    st.caption("No units found for selected indicators")
    
    if selected_indicators:
        with st.expander("📋 Selected Indicator Descriptions & Metadata", expanded=False):
            try:
                # Determine fact table based on indicator type
                fact_table = MAP_TABLE.get(indicator_type, 'FACT_CPI')

                # Build query with indicator filter
                ind_placeholders = ','.join([f':ind{i}' for i in range(len(selected_indicators))])
                params = {f'ind{i}': name for i, name in enumerate(selected_indicators)}

                # Add unit filter if units are selected
                unit_filter = ""
                if selected_units:
                    unit_placeholders = ','.join([f':unit{i}' for i in range(len(selected_units))])
                    unit_filter = f"AND u.UNIT IN ({unit_placeholders})"
                    params.update({f'unit{i}': name for i, name in enumerate(selected_units)})

                query = f"""
                    SELECT DISTINCT
                        i.INDICATOR_NAME,
                        i.DESCRIPTION,
                        i.DEFINITION,
                        i.INDICATOR_TYPE,
                        i.SECTION,
                        u.UNIT,
                        l.LOCATION_NAME,
                        s.SOURCE
                    FROM {fact_table} f
                    JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
                    LEFT JOIN DIM_UNITS u ON f.UNIT_ID = u.UNIT_ID
                    JOIN DIM_LOCATION l ON f.LOCATION_ID = l.LOCATION_ID
                    LEFT JOIN DIM_SOURCES s ON f.SOURCE_ID = s.SOURCE_ID
                    WHERE i.INDICATOR_NAME IN ({ind_placeholders})
                    {unit_filter}
                    ORDER BY i.INDICATOR_NAME, l.LOCATION_NAME
                """

                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                cursor.close()

                if rows:
                    # Create DataFrame for download
                    metadata_df = pd.DataFrame(rows, columns=columns)

                    # Display descriptions with source, units, and location info
                    # Group by indicator to show unique descriptions
                    for indicator_name in metadata_df['INDICATOR_NAME'].unique():
                        indicator_rows = metadata_df[metadata_df['INDICATOR_NAME'] == indicator_name]
                        indicator_data = indicator_rows.iloc[0]
                        description = indicator_data.get('DESCRIPTION', None)
                        definition = indicator_data.get('DEFINITION', None)

                        # Get all distinct units for this indicator
                        units = indicator_rows['UNIT'].dropna().unique()
                        units_str = ', '.join([str(u) for u in units if u]) or 'N/A'

                        # Get all distinct locations
                        locations = indicator_rows['LOCATION_NAME'].unique()
                        locations_str = ', '.join([str(loc) for loc in locations if loc])

                        # Get source (should be same for all rows of same indicator)
                        source = indicator_data.get('SOURCE', 'N/A') or 'N/A'

                        definition_html = (
                            f"<div style='color: #475569; font-size: 0.85rem; line-height: 1.5; margin-top: 0.3rem;'>"
                            f"<strong>Definition:</strong> {definition}</div>"
                            if definition and str(definition).strip() else ""
                        )

                        st.markdown(f"""
                            <div style='background: #f8fafc; padding: 0.8rem; border-radius: 6px; margin-bottom: 0.8rem; border-left: 3px solid #3b82f6;'>
                                <div style='font-weight: 600; color: #1e293b; margin-bottom: 0.3rem; font-size: 0.95rem;'>{indicator_name}</div>
                                <div style='color: #64748b; font-size: 0.85rem; line-height: 1.5;'>{description if description and str(description).strip() else 'No description available'}</div>
                                {definition_html}
                                <div style='color: #475569; font-size: 0.8rem; margin-top: 0.4rem;'><strong>Source:</strong> {source} | <strong>Unit(s):</strong> {units_str} | <strong>Location(s):</strong> {locations_str}</div>
                            </div>
                        """, unsafe_allow_html=True)

                    # Download buttons for metadata
                    st.markdown("---")
                    st.markdown("**📥 Download Indicator Metadata**")
                    col_csv, col_excel = st.columns(2)

                    with col_csv:
                        csv_data = metadata_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "📄 Download CSV",
                            csv_data,
                            f"{indicator_type.lower()}_indicator_metadata.csv",
                            "text/csv",
                            use_container_width=True,
                            key=f"{indicator_type}_metadata_csv"
                        )

                    with col_excel:
                        excel_buffer = BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            metadata_df.to_excel(writer, index=False, sheet_name='Indicator Metadata')
                        excel_buffer.seek(0)

                        st.download_button(
                            "📊 Download Excel",
                            excel_buffer.getvalue(),
                            f"{indicator_type.lower()}_indicator_metadata.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            key=f"{indicator_type}_metadata_xlsx"
                        )
                else:
                    st.info("No descriptions found for selected indicators.")
            except Exception as e:
                st.warning(f"Could not load descriptions: {str(e)[:100]}")

    return {
        'start_year': start_year,
        'end_year': end_year,
        'start_month': start_month,
        'end_month': end_month,
        'location': location,
        'aggregation': aggregation,
        'selected_indicators': selected_indicators or None,
        'selected_units': selected_units or None
    }

# ──── Tabs ──────────────────────────────────────────────────────────────────
tab_cpi, tab_bop, tab_monetary, tab_fiscal, tab_interest, tab_gdp, tab_combined = st.tabs([
    "📈 CPI & Inflation",
    "💰 Balance of Payments",
    "🏦 Monetary & Financial",
    "📑 Fiscal Statistics",
    "💹 Interest Rates",
    "🏭 National Accounts",
    "🔗 Combined Query",
])

# ────────────────────────────────────────────────
#   CPI Tab
# ────────────────────────────────────────────────
with tab_cpi:
    st.markdown("### Consumer Price Index (CPI)")
    st.markdown("Track inflation and price changes over time")
    st.markdown("---")

    filters = render_filters("CONSUMER PRICE INDEX AND INFLATION", locations, units, conn)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    if st.button("🔄 Load CPI Data", type="primary", use_container_width=True, key="load_cpi"):
        with st.spinner("📊 Querying CPI data from database..."):
            try:
                df = get_data(
                    conn, "CONSUMER PRICE INDEX AND INFLATION",
                    start_year=filters['start_year'],
                    end_year=filters['end_year'],
                    start_month=filters['start_month'],
                    end_month=filters['end_month'],
                    location=filters['location'],
                    indicator_names=filters['selected_indicators'],
                    unit_names=filters['selected_units'],
                    aggregation=filters['aggregation'],
                    wide_format=True
                )
                render_data_display(df, "Consumer Price Index and Inflation", "CONSUMER PRICE INDEX AND INFLATION", filters, conn)
            except Exception as e:
                st.error(f"Error loading CPI data: {str(e)}")
                st.info("Please check your database connection and filter settings.")

# ────────────────────────────────────────────────
#   Balance of Payments Tab
# ────────────────────────────────────────────────
with tab_bop:
    st.markdown("### Balance of Payments")
    st.markdown("Analyze international transactions and foreign exchange flows")
    st.markdown("---")

    filters = render_filters("BALANCE OF PAYMENTS", locations, units, conn)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    if st.button("🔄 Load BOP Data", type="primary", use_container_width=True, key="load_bop"):
        with st.spinner("📊 Querying Balance of Payments data from database..."):
            try:
                df = get_data(
                    conn, "BALANCE OF PAYMENTS",
                    start_year=filters['start_year'],
                    end_year=filters['end_year'],
                    start_month=filters['start_month'],
                    end_month=filters['end_month'],
                    location=filters['location'],
                    indicator_names=filters['selected_indicators'],
                    unit_names=filters['selected_units'],
                    aggregation=filters['aggregation'],
                    wide_format=True
                )
                render_data_display(df, "Balance of Payments", "BALANCE OF PAYMENTS", filters, conn)
            except Exception as e:
                st.error(f"Error loading Balance of Payments data: {str(e)}")
                st.info("Please check your database connection and filter settings.")

# ────────────────────────────────────────────────
#   Monetary and Financial Statistics Tab
# ────────────────────────────────────────────────
with tab_monetary:
    st.markdown("### Monetary and Financial Statistics")
    st.markdown("Analyze money supply, credit, and financial sector data")
    st.markdown("---")

    filters = render_filters("MONETARY AND FINANCIAL STATISTICS", locations, units, conn)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    if st.button("🔄 Load Monetary Data", type="primary", use_container_width=True, key="load_monetary"):
        with st.spinner("📊 Querying Monetary and Financial Statistics from database..."):
            try:
                df = get_data(
                    conn, "MONETARY AND FINANCIAL STATISTICS",
                    start_year=filters['start_year'],
                    end_year=filters['end_year'],
                    start_month=filters['start_month'],
                    end_month=filters['end_month'],
                    location=filters['location'],
                    indicator_names=filters['selected_indicators'],
                    unit_names=filters['selected_units'],
                    aggregation=filters['aggregation'],
                    wide_format=True
                )
                render_data_display(df, "Monetary and Financial Statistics", "MONETARY AND FINANCIAL STATISTICS", filters, conn)
            except Exception as e:
                st.error(f"Error loading Monetary and Financial Statistics: {str(e)}")
                st.info("Please check your database connection and filter settings.")

# ────────────────────────────────────────────────
#   Fiscal Statistics Tab
# ────────────────────────────────────────────────
with tab_fiscal:
    st.markdown("### Fiscal Statistics")
    st.markdown("Analyze government revenues, expenditures and fiscal position")
    st.markdown("---")

    filters = render_filters("FISCAL STATISTICS", locations, units, conn)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    if st.button("🔄 Load Fiscal Data", type="primary", use_container_width=True, key="load_fiscal"):
        with st.spinner("📊 Querying Fiscal Statistics from database..."):
            try:
                df = get_data(
                    conn, "FISCAL STATISTICS",
                    start_year=filters['start_year'],
                    end_year=filters['end_year'],
                    start_month=filters['start_month'],
                    end_month=filters['end_month'],
                    location=filters['location'],
                    indicator_names=filters['selected_indicators'],
                    unit_names=filters['selected_units'],
                    aggregation=filters['aggregation'],
                    wide_format=True
                )
                render_data_display(df, "Fiscal Statistics", "FISCAL STATISTICS", filters, conn)
            except Exception as e:
                st.error(f"Error loading Fiscal Statistics: {str(e)}")
                st.info("Please check your database connection and filter settings.")

# ────────────────────────────────────────────────
#   Interest Rates Tab
# ────────────────────────────────────────────────
with tab_interest:
    st.markdown("### Interest Rates")
    st.markdown("Track lending, deposit and policy interest rates")
    st.markdown("---")

    filters = render_filters("INTEREST RATES", locations, units, conn)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    if st.button("🔄 Load Interest Rate Data", type="primary", use_container_width=True, key="load_interest"):
        with st.spinner("📊 Querying Interest Rates from database..."):
            try:
                df = get_data(
                    conn, "INTEREST RATES",
                    start_year=filters['start_year'],
                    end_year=filters['end_year'],
                    start_month=filters['start_month'],
                    end_month=filters['end_month'],
                    location=filters['location'],
                    indicator_names=filters['selected_indicators'],
                    unit_names=filters['selected_units'],
                    aggregation=filters['aggregation'],
                    wide_format=True
                )
                render_data_display(df, "Interest Rates", "INTEREST RATES", filters, conn)
            except Exception as e:
                st.error(f"Error loading Interest Rates: {str(e)}")
                st.info("Please check your database connection and filter settings.")

# ────────────────────────────────────────────────
#   National Accounts Tab
# ────────────────────────────────────────────────
with tab_gdp:
    st.markdown("### National Accounts")
    st.markdown("Analyze GDP, economic output, and national income data")
    st.markdown("---")

    filters = render_filters("NATIONAL ACCOUNTS", locations, units, conn)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    if st.button("🔄 Load National Accounts Data", type="primary", use_container_width=True, key="load_gdp"):
        with st.spinner("📊 Querying National Accounts data from database..."):
            try:
                df = get_data(
                    conn, "NATIONAL ACCOUNTS",
                    start_year=filters['start_year'],
                    end_year=filters['end_year'],
                    start_month=filters['start_month'],
                    end_month=filters['end_month'],
                    location=filters['location'],
                    indicator_names=filters['selected_indicators'],
                    unit_names=filters['selected_units'],
                    aggregation=filters['aggregation'],
                    wide_format=True
                )
                render_data_display(df, "National Accounts", "NATIONAL ACCOUNTS", filters, conn)
            except Exception as e:
                st.error(f"Error loading National Accounts data: {str(e)}")
                st.info("Please check your database connection and filter settings.")

# ────────────────────────────────────────────────
#   Combined Query Tab
# ────────────────────────────────────────────────
with tab_combined:
    st.markdown("### Combined Query")
    st.markdown("Select indicators from multiple data groups to build a single merged dataset")
    st.markdown("---")

    # ── Shared time / location / aggregation ──────────────────────────
    st.markdown("""
        <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
            <div style='background: linear-gradient(135deg, #3b82f6, #1d4ed8); width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center;'>
                <span style='font-size: 1.1rem;'>🔍</span>
            </div>
            <div>
                <h4 style='margin: 0; color: #1e293b; font-size: 1.1rem; font-weight: 600;'>Query Builder</h4>
                <p style='margin: 0; color: #64748b; font-size: 0.8rem;'>Set shared filters then pick indicators from each group</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("📋 Time, Location & Aggregation", expanded=True):
        col_t_c, col_l_c = st.columns([1.4, 1])

        with col_t_c:
            st.markdown("""
                <div class="filter-section-time">
                    <p class="filter-section-title" style="color: #0369a1;">⏰ Time Period</p>
                </div>
            """, unsafe_allow_html=True)

            use_range_c = st.checkbox("Use date range instead of years", value=False, key="combined_use_range")
            if use_range_c:
                c1, c2 = st.columns(2)
                with c1:
                    start_dt_c = st.date_input("Start date", value=pd.to_datetime("2020-01-01"),
                                               min_value=pd.to_datetime("1960-01-01"),
                                               max_value=pd.to_datetime("2050-12-31"),
                                               key="combined_start_dt")
                with c2:
                    end_dt_c = st.date_input("End date", value=pd.to_datetime("2023-12-31"),
                                             min_value=pd.to_datetime("1960-01-01"),
                                             max_value=pd.to_datetime("2050-12-31"),
                                             key="combined_end_dt")
                c_start_year  = start_dt_c.year
                c_end_year    = end_dt_c.year
                c_start_month = start_dt_c.month
                c_end_month   = end_dt_c.month
            else:
                c1, c2 = st.columns(2)
                with c1:
                    c_start_year = st.number_input("From year", min_value=1960, max_value=2050,
                                                    value=2020, key="combined_from_year")
                with c2:
                    c_end_year = st.number_input("To year", min_value=1960, max_value=2050,
                                                  value=2023, key="combined_to_year")
                c_start_month = c_end_month = None

        with col_l_c:
            st.markdown("""
                <div class="filter-section-location" style="margin-top: 0;">
                    <p class="filter-section-title" style="color: #a16207;">📍 Location & Aggregation</p>
                </div>
            """, unsafe_allow_html=True)

            c_location = st.selectbox(
                "Location", locations,
                index=locations.index("Tanzania") if "Tanzania" in locations else 0,
                key="combined_location"
            )
            c_aggregation_labels = {
                "monthly": "Monthly",
                "quarterly": "Quarterly",
                "annual": "Annual (Calendar Year)",
                "fiscal_year": "Annual (Fiscal Year)"
            }
            c_aggregation = st.selectbox(
                "Aggregation level",
                ["monthly", "quarterly", "annual", "fiscal_year"],
                format_func=lambda x: c_aggregation_labels.get(x, x),
                key="combined_agg_select",
                help="National Accounts is always annual — other groups follow this setting"
            )

    # ── Per-group indicator selectors ──────────────────────────────────
    st.markdown("#### Select Indicators by Group")
    st.caption("Open any group below and pick indicators to include in the combined dataset.")

    COMBINED_GROUPS = [
        ("CONSUMER PRICE INDEX AND INFLATION", "📈 CPI & Inflation"),
        ("BALANCE OF PAYMENTS",                "💰 Balance of Payments"),
        ("MONETARY AND FINANCIAL STATISTICS",   "🏦 Monetary & Financial"),
        ("FISCAL STATISTICS",                   "📑 Fiscal Statistics"),
        ("INTEREST RATES",                      "💹 Interest Rates"),
        ("NATIONAL ACCOUNTS",                   "🏭 National Accounts"),
    ]

    c_group_selections = {}  # group_key → list[INDICATOR_NAME]

    for g_key, g_label in COMBINED_GROUPS:
        with st.expander(g_label, expanded=False):
            try:
                g_db_section = DB_SECTION_MAP.get(g_key)
                if g_db_section:
                    g_ind_df = get_indicators(conn, section=g_db_section)
                else:
                    g_ind_df = get_indicators(conn, fact_table=MAP_TABLE.get(g_key))

                if not g_ind_df.empty:
                    g_ind_map = {}
                    for _, row in g_ind_df.iterrows():
                        desc = str(row.get('DESCRIPTION', '') or '').strip()
                        label = desc if desc else row['INDICATOR_NAME']
                        g_ind_map[label] = row['INDICATOR_NAME']
                    g_ind_options = sorted(g_ind_map.keys())
                else:
                    g_ind_map = {}
                    g_ind_options = []
            except Exception as _e:
                g_ind_map = {}
                g_ind_options = []
                st.caption(f"Could not load indicators: {str(_e)[:60]}")

            g_selected_labels = st.multiselect(
                "Indicators",
                options=g_ind_options,
                default=[],
                key=f"combined_{g_key}_indicators",
                placeholder="Select indicators from this group…"
            )
            if g_selected_labels:
                c_group_selections[g_key] = [g_ind_map[lbl] for lbl in g_selected_labels]

    # ── Load button ─────────────────────────────────────────────────────
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    c_total_selected = sum(len(v) for v in c_group_selections.values())
    if c_total_selected == 0:
        st.info("Select at least one indicator from any group above, then click **Load Combined Data**.")

    if st.button("🔄 Load Combined Data", type="primary", use_container_width=True, key="load_combined"):
        if c_total_selected == 0:
            st.warning("Please select at least one indicator before loading.")
        else:
            with st.spinner("📊 Querying data across groups and merging…"):
                try:
                    combined_df = None
                    merge_keys  = ['TIME_PERIOD', 'LOCATION_NAME']

                    for g_key, ind_names in c_group_selections.items():
                        part_df = get_data(
                            conn, g_key,
                            start_year=c_start_year,
                            end_year=c_end_year,
                            start_month=c_start_month,
                            end_month=c_end_month,
                            location=c_location,
                            indicator_names=ind_names,
                            aggregation=c_aggregation,
                            wide_format=True
                        )

                        if part_df.empty:
                            st.warning(f"No data returned for **{g_key}** — skipping.")
                            continue

                        # Keep only TIME_PERIOD, LOCATION_NAME and indicator value columns
                        extra_cols = [c for c in part_df.columns
                                      if c not in merge_keys and c in
                                      ('YEAR', 'MONTH', 'QUARTER', 'FISCAL_YEAR',
                                       'INDICATOR_TYPE', 'DESCRIPTION', 'UNIT', 'SECTION')]
                        part_df = part_df.drop(columns=extra_cols, errors='ignore')

                        if combined_df is None:
                            combined_df = part_df
                        else:
                            combined_df = pd.merge(combined_df, part_df, on=merge_keys, how='outer')

                    if combined_df is not None and not combined_df.empty:
                        combined_df = combined_df.sort_values(merge_keys).reset_index(drop=True)
                        render_data_display(combined_df, "Combined Query Results", "COMBINED",
                                            filters=None, conn=conn)
                    else:
                        st.warning("No data found for the selected indicators and time period.")

                except Exception as e:
                    st.error(f"Error loading combined data: {str(e)}")

# ────────────────────────────────────────────────
#   Sidebar (Enhanced)
# ────────────────────────────────────────────────
with st.sidebar:
    # Database icon
    st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <svg width="80" height="80" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C8 2 4 3.5 4 5.5V18.5C4 20.5 8 22 12 22C16 22 20 20.5 20 18.5V5.5C20 3.5 16 2 12 2Z"
                      fill="url(#grad1)" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M4 12C4 14 8 15.5 12 15.5C16 15.5 20 14 20 12"
                      stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M4 8.5C4 10.5 8 12 12 12C16 12 20 10.5 20 8.5"
                      stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                <ellipse cx="12" cy="5.5" rx="8" ry="3.5" fill="#3b82f6" opacity="0.3"/>
                <defs>
                    <linearGradient id="grad1" x1="12" y1="2" x2="12" y2="22" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stop-color="#3b82f6"/>
                        <stop offset="100%" stop-color="#1e40af"/>
                    </linearGradient>
                </defs>
            </svg>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🎛️ Database Controls")

    # Connection status indicator
    st.markdown("""
        <div style='display: flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.75rem; background: rgba(34, 197, 94, 0.15); border-radius: 10px; border: 1px solid rgba(34, 197, 94, 0.3); margin: 1rem 0;'>
            <span style='display: inline-block; width: 10px; height: 10px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);'></span>
            <span style='color: #86efac; font-weight: 500; font-size: 0.9rem;'>Connected</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="border-color: rgba(255,255,255,0.15); margin: 1rem 0;">', unsafe_allow_html=True)

    # Connection test button
    if st.button("🔄 Test Connection", use_container_width=True, key="test_conn_btn"):
        ok, msg, ts = test_connection(conn)
        if ok:
            st.success(f"Active - Server time: {ts}")
        else:
            st.error(f"{msg}")

    st.markdown('<hr style="border-color: rgba(255,255,255,0.15); margin: 1rem 0;">', unsafe_allow_html=True)

    # Database info
    with st.expander("ℹ️ Connection Info", expanded=False):
        try:
            st.markdown(f"""
                <div style='background: rgba(59, 130, 246, 0.15); padding: 1rem; border-radius: 10px; border: 1px solid rgba(59, 130, 246, 0.3);'>
                    <p style='margin: 0.5rem 0; color: #e2e8f0; font-size: 0.85rem;'><strong>User:</strong> {conn.username if hasattr(conn, 'username') else 'N/A'}</p>
                    <p style='margin: 0.5rem 0; color: #e2e8f0; font-size: 0.85rem;'><strong>DSN:</strong> {conn.dsn if hasattr(conn, 'dsn') else 'N/A'}</p>
                </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown("""
                <div style='background: rgba(239, 68, 68, 0.15); padding: 1rem; border-radius: 10px; border: 1px solid rgba(239, 68, 68, 0.3);'>
                    <p style='margin: 0; color: #fca5a5; font-size: 0.85rem;'>Connection details unavailable</p>
                </div>
            """, unsafe_allow_html=True)

    # Display Options section
    with st.expander("🎨 Display Options", expanded=True):
        chart_type = st.radio(
            "Chart Type",
            options=["Line", "Bar"],
            index=0,
            key="chart_type_selector",
            horizontal=True
        )
        st.session_state.chart_type = chart_type

        st.markdown("""
            <div style='background: rgba(139, 92, 246, 0.15); padding: 0.75rem; border-radius: 10px; border: 1px solid rgba(139, 92, 246, 0.3); margin-top: 0.75rem;'>
                <p style='margin: 0.3rem 0; color: #e2e8f0; font-size: 0.8rem;'><strong>Number Format:</strong> Thousands separator</p>
                <p style='margin: 0.3rem 0; color: #e2e8f0; font-size: 0.8rem;'><strong>Date Format:</strong> YYYY-MM-DD</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr style="border-color: rgba(255,255,255,0.15); margin: 1rem 0;">', unsafe_allow_html=True)

    # Disconnect button with red tint
    st.markdown("""
        <style>
        div[data-testid="stSidebar"] button[kind="secondary"] {
            background: rgba(239, 68, 68, 0.15) !important;
            border: 1px solid rgba(239, 68, 68, 0.4) !important;
            color: #fca5a5 !important;
        }
        div[data-testid="stSidebar"] button[kind="secondary"]:hover {
            background: rgba(239, 68, 68, 0.25) !important;
            border-color: rgba(239, 68, 68, 0.6) !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if st.button("🔌 Disconnect", type="secondary", use_container_width=True, key="disconnect_btn"):
        try:
            conn.close()
            st.success("Disconnected successfully")
        except Exception as e:
            st.warning(f"Disconnect warning: {e}")
        finally:
            st.session_state.connected = False
            st.session_state.conn = None
            st.rerun()

    st.markdown('<hr style="border-color: rgba(255,255,255,0.15); margin: 1.5rem 0;">', unsafe_allow_html=True)

    # Quick Stats
    with st.expander("📊 Quick Stats", expanded=False):
        st.markdown("""
            <div style='background: rgba(16, 185, 129, 0.15); padding: 1rem; border-radius: 10px; border: 1px solid rgba(16, 185, 129, 0.3);'>
                <p style='margin: 0.5rem 0; color: #e2e8f0; font-size: 0.85rem;'><strong>Tables:</strong> CPI, BOP, Monetary, Fiscal, Interest Rates</p>
                <p style='margin: 0.5rem 0; color: #e2e8f0; font-size: 0.85rem;'><strong>Coverage:</strong> Tanzania Macroeconomic Data</p>
                <p style='margin: 0.5rem 0; color: #e2e8f0; font-size: 0.85rem;'><strong>Status:</strong> Active & Expanding</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr style="border-color: rgba(255,255,255,0.15); margin: 1.5rem 0;">', unsafe_allow_html=True)

    # Footer
    st.markdown("""
        <div style='text-align: center; padding: 1rem 0;'>
            <div style='background: rgba(255,255,255,0.05); padding: 0.75rem; border-radius: 10px; margin-bottom: 0.75rem;'>
                <small style='color: #cbd5e1; font-weight: 500;'>Macroeconomic Database v2.0</small>
            </div>
            <small style='color: #64748b;'>© 2026 Tanzania Economic Data</small>
        </div>
    """, unsafe_allow_html=True)