import streamlit as st
from datetime import datetime
from .config import CURRENCY_SYMBOL

def apply_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700&display=swap');
    * { font-family: 'Cairo', 'Segoe UI', sans-serif; }
    .stApp { background-color: #f8f9fa; }
    .main > div { padding: 0 1rem; }
    h1, h2, h3 { color: #1a1a2e; font-weight: 700; }
    h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
    h2 { font-size: 1.2rem !important; margin-bottom: 0.5rem !important; }
    h3 { font-size: 1rem !important; color: #495057; }
    .stSidebar { background-color: #1a1a2e !important; }
    .stSidebar .sidebar-content { background-color: #1a1a2e; }
    .stSidebar label, .stSidebar p, .stSidebar span { color: #e0e0e0 !important; }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 8px;
        font-weight: 600; font-size: 0.85rem; transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: translateY(-1px); box-shadow: 0 4px 15px rgba(102,126,234,0.4);
    }
    .stButton > button[type="secondary"] {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; color: #1a1a2e; }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem !important; color: #6c757d; font-weight: 500; }
    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #e9ecef; }
    .stDataFrame th { background-color: #f1f3f5; font-weight: 600; font-size: 0.8rem; padding: 10px; }
    .stDataFrame td { padding: 8px 10px; font-size: 0.8rem; }
    .stTextInput > div > div, .stSelectbox > div > div, .stNumberInput > div > div {
        border-radius: 8px; border: 1px solid #dee2e6; background: white;
    }
    .stTextInput > div > div:focus-within, .stSelectbox > div > div:focus-within {
        border-color: #667eea; box-shadow: 0 0 0 2px rgba(102,126,234,0.1);
    }
    div.stTabs [data-baseweb="tab-list"] { gap: 2px; background: white; padding: 5px; border-radius: 12px; }
    div.stTabs [data-baseweb="tab"] {
        border-radius: 8px; padding: 8px 20px; font-weight: 500; color: #495057;
    }
    div.stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
    }
    .card {
        background: white; padding: 1.5rem; border-radius: 16px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06); margin-bottom: 1rem;
        border: 1px solid #f0f0f0;
    }
    .stat-card {
        background: white; padding: 1.2rem; border-radius: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04); text-align: center;
        border-left: 4px solid #667eea;
    }
    .stat-card .value { font-size: 1.6rem; font-weight: 700; color: #1a1a2e; }
    .stat-card .label { font-size: 0.8rem; color: #6c757d; margin-top: 0.3rem; }
    .badge {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    .badge-active { background: #d4edda; color: #155724; }
    .badge-inactive { background: #e9ecef; color: #495057; }
    .badge-pending { background: #fff3cd; color: #856404; }
    .badge-approved { background: #d4edda; color: #155724; }
    .badge-rejected { background: #f8d7da; color: #721c24; }
    .badge-paid { background: #d4edda; color: #155724; }
    .badge-hold { background: #ffe0b2; color: #e65100; }
    .badge-cancelled { background: #e9ecef; color: #495057; }
    .badge-draft { background: #cce5ff; color: #004085; }
    .badge-closed { background: #e2e3e5; color: #383d41; }
    .badge-critical { background: #f8d7da; color: #721c24; }
    .badge-warning { background: #fff3cd; color: #856404; }
    .badge-info { background: #cce5ff; color: #004085; }
    .badge-transferred { background: #d4edda; color: #155724; }
    .page-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 1.5rem 2rem; border-radius: 16px; margin-bottom: 1.5rem;
    }
    .page-header h1 { color: white; margin: 0; font-size: 1.5rem; }
    .page-header p { color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; font-size: 0.9rem; }
    .divider { height: 1px; background: #e9ecef; margin: 1.5rem 0; }
    .footer-text { text-align: center; color: #adb5bd; font-size: 0.8rem; padding: 2rem 0; border-top: 1px solid #e9ecef; margin-top: 3rem; }
    .stAlert { border-radius: 12px; border: none; }
    .stSuccess { background: #d4edda; color: #155724; }
    .stInfo { background: #cce5ff; color: #004085; }
    .stWarning { background: #fff3cd; color: #856404; }
    .stError { background: #f8d7da; color: #721c24; }
    hr { margin: 1rem 0; border: 0; border-top: 1px solid #e9ecef; }
    .row-widget.stRadio > div { flex-direction: row; gap: 0.5rem; }
    .row-widget.stCheckbox { margin: 0.5rem 0; }
    section[data-testid="stSidebar"] .stButton button {
        width: 100%; text-align: left; background: transparent; color: #e0e0e0;
        padding: 0.6rem 1rem; border-radius: 8px; border: none;
        font-size: 0.85rem; transition: all 0.2s;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(255,255,255,0.1); color: white;
    }
    .st-emotion-cache-1wivap2 { background-color: #1a1a2e; }
    .st-emotion-cache-1m6wrpl { background-color: #1a1a2e; }
    </style>
    """, unsafe_allow_html=True)

def page_header(title, subtitle=None):
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="page-header"><h1>{title}</h1>{subtitle_html}</div>', unsafe_allow_html=True)

def metric_card(label, value, delta=None):
    col = st.columns(1)[0]
    with col:
        st.metric(label=label, value=value, delta=delta)

def status_badge(status):
    status = str(status).lower().strip()
    mapping = {
        'active': 'badge-active', 'inactive': 'badge-inactive',
        'pending': 'badge-pending', 'approved': 'badge-approved',
        'rejected': 'badge-rejected', 'paid': 'badge-paid',
        'hold': 'badge-hold', 'cancelled': 'badge-cancelled',
        'draft': 'badge-draft', 'closed': 'badge-closed',
        'critical': 'badge-critical', 'warning': 'badge-warning',
        'info': 'badge-info', 'transferred': 'badge-transferred',
        'generated': 'badge-info', 'submitted': 'badge-pending',
        'planned': 'badge-info',
    }
    cls = mapping.get(status, 'badge-info')
    return f'<span class="badge {cls}">{status.title()}</span>'

def fmt_currency(val):
    if val is None:
        return f"{CURRENCY_SYMBOL} 0.00"
    return f"{CURRENCY_SYMBOL} {val:,.2f}"

def fmt_date(val):
    if not val:
        return "-"
    try:
        d = datetime.strptime(str(val), '%Y-%m-%d')
        return d.strftime('%d-%b-%Y')
    except:
        return str(val)

def section_title(title):
    st.markdown(f"<h3 style='margin-top: 1.5rem; margin-bottom: 0.8rem; color: #1a1a2e;'>{title}</h3>",
                unsafe_allow_html=True)

def info_box(text, type="info"):
    icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
    icon = icons.get(type, "ℹ️")
    st.info(f"{icon} {text}")

def divider():
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

def footer():
    st.markdown(f'<div class="footer-text">Payroll Management System v1.0.0 &copy; {datetime.now().year} | All rights reserved</div>',
                unsafe_allow_html=True)

def filter_bar(cols_config):
    """Create a filter bar with multiple columns. cols_config is a list of (label, key, type, options) tuples."""
    cols = st.columns(len(cols_config))
    filters = {}
    for i, (label, key, ftype, options) in enumerate(cols_config):
        with cols[i]:
            if ftype == 'select':
                filters[key] = st.selectbox(label, options, key=f"filter_{key}")
            elif ftype == 'multiselect':
                filters[key] = st.multiselect(label, options, key=f"filter_{key}")
            elif ftype == 'number':
                filters[key] = st.number_input(label, value=options.get('default', 0), key=f"filter_{key}")
    return filters

def render_table(df, use_container_width=True, height=None):
    if df is None or df.empty:
        st.info("No data available.")
        return
    st.dataframe(df, use_container_width=use_container_width, height=height)

def export_download_link(df, filename, label="Download Excel"):
    try:
        import pandas as pd
        import openpyxl
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            ws = writer.sheets['Sheet1']
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col) + 2
                ws.column_dimensions[col[0].column_letter].width = min(max_len, 50)
        output.seek(0)
        st.download_button(label=label, data=output, file_name=filename,
                          mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except:
        st.warning("Install openpyxl for Excel export: pip install openpyxl")
