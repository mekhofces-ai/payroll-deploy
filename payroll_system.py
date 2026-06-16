#!/usr/bin/env python3
"""
Payroll Management System
Complete professional payroll system for managing employees, projects,
allowances, payroll calculation, bonus tracking, and more.

Run with:
    pip install streamlit pandas openpyxl xlsxwriter
    python -m streamlit run payroll_system.py --server.address 127.0.0.1 --server.port 8505
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from payroll_app.database import DatabaseManager, get_db, add_audit_log
from payroll_app.auth import authenticate, get_user_permissions, get_sidebar_menu, can_view_salary, can_view_company_cost
from payroll_app.ui import apply_custom_css, page_header, footer, fmt_currency, status_badge
from payroll_app.config import APP_NAME, APP_VERSION, CURRENCY_SYMBOL

st.set_page_config(
    page_title=APP_NAME,
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session():
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.page = "Login"
        st.session_state.user = None
        st.session_state.authenticated = False
        st.session_state.permissions = {}

def init_database():
    if 'db_initialized' not in st.session_state:
        try:
            db = DatabaseManager()
            st.session_state.db_initialized = True
        except Exception as e:
            st.error(f"Database initialization error: {e}")
            st.stop()

def login_page():
    apply_custom_css()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center;padding:3rem 0">
            <h1 style="font-size:2.5rem;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                💰 Payroll Pro
            </h1>
            <p style="color:#6c757d;font-size:1rem;">Payroll Management System</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="card" style="max-width:400px;margin:auto">', unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="Enter your username", key="login_user")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_pass")

            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button("🔑 Login", type="primary", use_container_width=True):
                    if username and password:
                        user, msg = authenticate(username, password)
                        if user:
                            st.session_state.user = user
                            st.session_state.authenticated = True
                            st.session_state.permissions = get_user_permissions(username)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Please enter username and password.")
            with col_b:
                if st.button("Reset", use_container_width=True):
                    st.rerun()

            st.markdown("""
            <div style="margin-top:1.5rem;padding:1rem;background:#f8f9fa;border-radius:8px;font-size:0.8rem">
                <b>Demo Credentials:</b><br>
                superadmin / superadmin123<br>
                admin / admin123<br>
                payroll / payroll123<br>
                hr / hr123<br>
                finance / finance123<br>
                viewer / viewer123
            </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

def main_app():
    apply_custom_css()

    user = st.session_state.user
    username = user['username']
    role = user['role']

    with st.sidebar:
        st.markdown(f"""
        <div style="padding:1rem 0;text-align:center">
            <div style="font-size:2rem;margin-bottom:0.3rem">💰</div>
            <div style="font-weight:700;color:white;font-size:1.1rem">Payroll Pro</div>
            <div style="color:#a0a0c0;font-size:0.75rem">v{APP_VERSION}</div>
            <div style="margin-top:0.8rem;padding:0.5rem;background:rgba(255,255,255,0.1);border-radius:8px">
                <div style="color:white;font-weight:600;font-size:0.9rem">{user['full_name']}</div>
                <div style="color:#a0a0c0;font-size:0.75rem">{role}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        menus = get_sidebar_menu()
        selected = st.radio("Navigation", [m[1] for m in menus], index=0,
                          label_visibility="collapsed", key="nav_radio")
        st.session_state.page = selected

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔒 Logout", use_container_width=True):
                with get_db() as db:
                    add_audit_log(db, 'Logout', 'Login', username=st.session_state.user.get('username'))
                st.session_state.authenticated = False
                st.session_state.user = None
                st.session_state.page = "Login"
                st.rerun()
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()

    page = st.session_state.get('page', 'Executive Dashboard')

    router = {
        "Executive Dashboard": "dashboard",
        "Alerts Center": "tools",
        "Employees": "employees",
        "Employee Allowances": "employees",
        "Project Allocation": "employees",
        "Payroll Run Center": "payroll",
        "Payroll Transactions": "payroll",
        "Payroll Project Allocation": "payroll",
        "Net to Gross Calculator": "payroll",
        "Bank Transfer": "payroll",
        "Bank Reconciliation": "payroll",
        "Payslips": "payroll",
        "Bonus Calculator": "bonus",
        "Bonus Register": "bonus",
        "Bonus Reports": "bonus",
        "Monthly Reports": "reports",
        "Yearly Summary": "reports",
        "Project Summary": "reports",
        "Variance Report": "reports",
        "Executive Reports Package": "reports",
        "Payroll Setup": "setup",
        "Projects": "setup",
        "Organizations": "setup",
        "Users & Permissions": "users",
        "Audit Log": "audit",
        "Import / Export": "tools",
        "Backup & Restore": "tools",
        "Data Quality Center": "tools",
        "Scenario Simulation": "tools",
        "Salary Revisions": "employees",
        "Documents": "employees",
    }

    module_map = router.get(page, "dashboard")
    try:
        if module_map == "dashboard":
            from payroll_app.pages.dashboard import show as show_page
        elif module_map == "employees":
            from payroll_app.pages.employees import show as show_page
        elif module_map == "payroll":
            from payroll_app.pages.payroll import show as show_page
        elif module_map == "bonus":
            from payroll_app.pages.bonus import show as show_page
        elif module_map == "reports":
            from payroll_app.pages.reports import show as show_page
        elif module_map == "setup":
            from payroll_app.pages.setup import show as show_page
        elif module_map == "users":
            from payroll_app.pages.users import show as show_page
        elif module_map == "audit":
            from payroll_app.pages.audit import show as show_page
        elif module_map == "tools":
            from payroll_app.pages.tools import show as show_page
        else:
            from payroll_app.pages.dashboard import show as show_page
        show_page()
    except Exception as e:
        st.error(f"Error loading page: {e}")
        import traceback
        st.exception(e)

    footer()

def main():
    init_session()
    init_database()

    if not st.session_state.authenticated:
        login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
