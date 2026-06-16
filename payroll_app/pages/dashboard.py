import streamlit as st
import pandas as pd
from datetime import datetime
from ..database import get_db
from ..auth import check_permission
from ..ui import page_header, fmt_currency, status_badge, footer, apply_custom_css

def show():
    if not check_permission('Executive Dashboard', 'View Only'):
        st.error("Access denied.")
        return

    apply_custom_css()
    page_header("Executive Dashboard", "High-level overview of payroll operations")

    year = st.sidebar.selectbox("Year", range(2026, 2019, -1), index=0)
    month = st.sidebar.selectbox("Month", range(1, 13), index=datetime.now().month - 1)

    with get_db() as db:
        emp_count = db.execute("SELECT COUNT(*) FROM employees WHERE status='Active'").fetchone()[0]
        proj_count = db.execute("SELECT COUNT(*) FROM projects WHERE status='Active'").fetchone()[0]

        payroll = db.execute('''SELECT COALESCE(SUM(net_transfer_amount),0) as total_net,
            COALESCE(SUM(total_company_cost),0) as total_cost,
            COALESCE(SUM(monthly_tax),0) as total_tax,
            COALESCE(SUM(employee_insurance),0) as total_emp_ins,
            COALESCE(SUM(company_insurance),0) as total_comp_ins,
            COALESCE(SUM(net_earning),0) as total_net_earning,
            COUNT(*) as emp_paid
            FROM payroll_transactions WHERE year=? AND month=?''', (year, month)).fetchone()

        bonus_cost = db.execute("SELECT COALESCE(SUM(comp_cost_diff),0) FROM employee_bonuses WHERE year=? AND month=? AND payment_status IN ('Approved','Paid')",
                                (year, month)).fetchone()[0]
        pending_transfers = db.execute("SELECT COUNT(*) FROM payroll_transactions WHERE year=? AND month=? AND payment_status='Pending'",
                                       (year, month)).fetchone()[0]

        allowance_count = db.execute("SELECT COUNT(*) FROM employee_allowances WHERE status='Active'").fetchone()[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f'<div class="stat-card"><div class="value">{emp_count}</div><div class="label">Active Employees</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card"><div class="value">{proj_count}</div><div class="label">Active Projects</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card"><div class="value">{fmt_currency(payroll[5])}</div><div class="label">Total Net Earning ({month}/{year})</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-card"><div class="value">{fmt_currency(payroll[0])}</div><div class="label">Net Transfer Amount</div></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="stat-card"><div class="value">{fmt_currency(payroll[1])}</div><div class="label">Total Company Cost</div></div>', unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f'<div class="stat-card"><div class="value">{fmt_currency(payroll[2])}</div><div class="label">Total Monthly Tax</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card"><div class="value">{fmt_currency(payroll[3])}</div><div class="label">Total Employee Insurance</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card"><div class="value">{fmt_currency(payroll[4])}</div><div class="label">Total Company Insurance</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-card"><div class="value">{fmt_currency(bonus_cost)}</div><div class="label">Bonus Cost This Month</div></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="stat-card"><div class="value">{pending_transfers}</div><div class="label">Pending Transfers</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    with get_db() as db:
        proj_costs = db.execute('''SELECT p.project_code as project,
            COALESCE(SUM(pa.allocated_total_cost),0) as total_cost,
            COUNT(DISTINCT pa.employee_code) as headcount
            FROM payroll_project_allocations pa
            JOIN projects p ON pa.project_code = p.project_code
            WHERE pa.year=? AND pa.month=?
            GROUP BY pa.project_code''', (year, month)).fetchall()

        dept_costs = db.execute('''SELECT department, COUNT(*) as count,
            COALESCE(SUM(total_company_cost),0) as total_cost
            FROM payroll_transactions WHERE year=? AND month=?
            GROUP BY department''', (year, month)).fetchall()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Payroll Cost by Project")
        if proj_costs:
            df_proj = pd.DataFrame([dict(r) for r in proj_costs])
            df_proj['total_cost'] = df_proj['total_cost'].round(2)
            st.dataframe(df_proj, use_container_width=True)
            try:
                st.bar_chart(df_proj.set_index('project')['total_cost'])
            except:
                pass

    with col2:
        st.subheader("Payroll Cost by Department")
        if dept_costs:
            df_dept = pd.DataFrame([dict(r) for r in dept_costs])
            df_dept['total_cost'] = df_dept['total_cost'].round(2)
            st.dataframe(df_dept, use_container_width=True)
            try:
                st.bar_chart(df_dept.set_index('department')['total_cost'])
            except:
                pass

    st.markdown("---")
    with get_db() as db:
        top_emps = db.execute('''SELECT employee_code, arabic_name, department,
            total_company_cost FROM payroll_transactions
            WHERE year=? AND month=?
            ORDER BY total_company_cost DESC LIMIT 10''', (year, month)).fetchall()

    if top_emps:
        st.subheader("Top 10 Employees by Company Cost")
        df_top = pd.DataFrame([dict(r) for r in top_emps])
        df_top['total_company_cost'] = df_top['total_company_cost'].round(2)
        st.dataframe(df_top, use_container_width=True)

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        with get_db() as db:
            sponsor_data = db.execute('''SELECT sponsor, COUNT(*) as count
                FROM employees WHERE status='Active' GROUP BY sponsor''').fetchall()
        if sponsor_data:
            st.subheader("Employees by Sponsor")
            st.dataframe(pd.DataFrame([dict(r) for r in sponsor_data]), use_container_width=True)

    with c2:
        with get_db() as db:
            pay_status = db.execute('''SELECT payment_status, COUNT(*) as count
                FROM payroll_transactions WHERE year=? AND month=?
                GROUP BY payment_status''', (year, month)).fetchall()
        if pay_status:
            st.subheader("Payment Status Distribution")
            st.dataframe(pd.DataFrame([dict(r) for r in pay_status]), use_container_width=True)

    footer()
