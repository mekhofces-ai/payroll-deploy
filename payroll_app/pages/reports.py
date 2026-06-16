import streamlit as st
import pandas as pd
from datetime import datetime
from ..database import get_db
from ..auth import check_permission
from ..ui import page_header, fmt_currency, status_badge, divider, footer, apply_custom_css, export_download_link

def show():
    apply_custom_css()
    page_header("Reports", "Payroll reports and analysis")

    tabs = st.tabs(["Monthly Reports", "Yearly Summary", "Project Summary", "Variance Report", "Executive Reports Package"])

    with tabs[0]:
        show_monthly_reports()
    with tabs[1]:
        show_yearly_summary()
    with tabs[2]:
        show_project_summary()
    with tabs[3]:
        show_variance()
    with tabs[4]:
        show_executive_package()

def show_monthly_reports():
    year = st.selectbox("Year", range(2026, 2019, -1), key="mr_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="mr_month", index=datetime.now().month - 1)

    with get_db() as db:
        transactions = db.execute('''SELECT * FROM payroll_transactions WHERE year=? AND month=? ORDER BY employee_code''', (year, month)).fetchall()

    if transactions:
        df = pd.DataFrame([dict(t) for t in transactions])
        st.subheader("Monthly Payroll Report")
        cols = ['employee_code', 'arabic_name', 'department', 'section', 'base_net_salary',
                'net_earning', 'total_allowances', 'estimated_gross', 'basic_salary', 'employee_insurance',
                'company_insurance', 'monthly_tax', 'total_deductions', 'net_transfer_amount',
                'total_company_cost', 'payment_status']
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)
        export_download_link(df, f"monthly_payroll_{year}_{month}.xlsx")

        st.subheader("Summary")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.metric("Total Employees", len(transactions))
        with c2: st.metric("Total Net Earning", fmt_currency(sum(t['net_earning'] or 0 for t in transactions)))
        with c3: st.metric("Total Net Transfer", fmt_currency(sum(t['net_transfer_amount'] or 0 for t in transactions)))
        with c4: st.metric("Total Gross", fmt_currency(sum(t['estimated_gross'] or 0 for t in transactions)))
        with c5: st.metric("Company Cost", fmt_currency(sum(t['total_company_cost'] or 0 for t in transactions)))

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Tax", fmt_currency(sum(t['monthly_tax'] or 0 for t in transactions)))
        with c2: st.metric("Employee Insurance", fmt_currency(sum(t['employee_insurance'] or 0 for t in transactions)))
        with c3: st.metric("Company Insurance", fmt_currency(sum(t['company_insurance'] or 0 for t in transactions)))
        with c4: st.metric("Total Allowances", fmt_currency(sum(t['total_allowances'] or 0 for t in transactions)))

    else:
        st.info("No data for this period.")

def show_yearly_summary():
    year = st.selectbox("Year", range(2026, 2019, -1), key="ys_year", index=0)

    with get_db() as db:
        data = db.execute('''SELECT employee_code, arabic_name, department, section, default_project,
            COUNT(*) as paid_months,
            SUM(base_net_salary) as total_base_net,
            SUM(net_earning) as total_net_earning,
            SUM(total_allowances) as total_allowances,
            SUM(estimated_gross) as total_gross,
            SUM(monthly_tax) as total_tax,
            SUM(employee_insurance) as total_emp_ins,
            SUM(company_insurance) as total_comp_ins,
            SUM(net_transfer_amount) as total_net,
            SUM(total_company_cost) as total_cost
            FROM payroll_transactions WHERE year=?
            GROUP BY employee_code ORDER BY employee_code''', (year,)).fetchall()

    if data:
        df = pd.DataFrame([dict(d) for d in data])
        st.subheader(f"Yearly Employee Summary - {year}")
        st.dataframe(df, use_container_width=True)
        export_download_link(df, f"yearly_summary_{year}.xlsx")

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Total Employees", len(data))
        with c2: st.metric("Total Net Paid", fmt_currency(sum(d['total_net'] or 0 for d in data)))
        with c3: st.metric("Total Company Cost", fmt_currency(sum(d['total_cost'] or 0 for d in data)))

        with get_db() as db:
            bonus_data = db.execute('''SELECT employee_code,
                SUM(net_bonus_amount) as total_net_bonus,
                SUM(comp_cost_diff) as total_bonus_cost
                FROM employee_bonuses WHERE year=? AND approval_status IN ('Approved','Paid')
                GROUP BY employee_code''', (year,)).fetchall()
        if bonus_data:
            st.subheader("Yearly Bonus Summary")
            df_bonus = pd.DataFrame([dict(b) for b in bonus_data])
            st.dataframe(df_bonus, use_container_width=True)
    else:
        st.info("No yearly data available.")

def show_project_summary():
    year = st.selectbox("Year", range(2026, 2019, -1), key="ps_year", index=0)

    with get_db() as db:
        monthly_data = db.execute('''SELECT project_code,
            COUNT(DISTINCT employee_code) as headcount,
            SUM(allocated_net_salary) as total_net,
            SUM(allocated_allowances) as total_allowances,
            SUM(allocated_gross) as total_gross,
            SUM(allocated_tax) as total_tax,
            SUM(allocated_employee_insurance) as total_emp_ins,
            SUM(allocated_company_insurance) as total_comp_ins,
            SUM(allocated_total_cost) as total_cost
            FROM payroll_project_allocations WHERE year=?
            GROUP BY project_code ORDER BY total_cost DESC''', (year,)).fetchall()

    if monthly_data:
        df = pd.DataFrame([dict(d) for d in monthly_data])
        st.subheader(f"Project Yearly Summary - {year}")
        st.dataframe(df, use_container_width=True)
        export_download_link(df, f"project_summary_{year}.xlsx")

        st.subheader("Monthly Project Cost Breakdown")
        with get_db() as db:
            monthly = db.execute('''SELECT project_code, month,
                SUM(allocated_total_cost) as monthly_cost
                FROM payroll_project_allocations WHERE year=?
                GROUP BY project_code, month ORDER BY project_code, month''', (year,)).fetchall()
        if monthly:
            pivot = pd.pivot_table(pd.DataFrame([dict(m) for m in monthly]),
                                    values='monthly_cost', index='project_code', columns='month', aggfunc='sum', fill_value=0)
            st.dataframe(pivot, use_container_width=True)
    else:
        st.info("No project data for this year.")

def show_variance():
    page_header("Payroll Variance Report", "Compare current month with previous month")
    year = st.selectbox("Year", range(2026, 2019, -1), key="var_year", index=0)
    month = st.selectbox("Month", range(2, 13), key="var_month", index=datetime.now().month - 2 if datetime.now().month > 1 else 0)

    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year = year - 1

    with get_db() as db:
        current = db.execute('''SELECT employee_code, arabic_name, department, section, default_project,
            net_transfer_amount, total_allowances, estimated_gross, monthly_tax, employee_insurance, total_company_cost
            FROM payroll_transactions WHERE year=? AND month=?''', (year, month)).fetchall()
        previous = db.execute('''SELECT employee_code, arabic_name, department, section, default_project,
            net_transfer_amount, total_allowances, estimated_gross, monthly_tax, employee_insurance, total_company_cost
            FROM payroll_transactions WHERE year=? AND month=?''', (prev_year, prev_month)).fetchall()

    if current and previous:
        prev_dict = {p['employee_code']: dict(p) for p in previous}
        rows = []
        for c in current:
            c = dict(c)
            p = prev_dict.get(c['employee_code'])
            if p:
                net_diff = (c['net_transfer_amount'] or 0) - (p['net_transfer_amount'] or 0)
                gross_diff = (c['estimated_gross'] or 0) - (p['estimated_gross'] or 0)
                tax_diff = (c['monthly_tax'] or 0) - (p['monthly_tax'] or 0)
                ins_diff = (c['employee_insurance'] or 0) - (p['employee_insurance'] or 0)
                cost_diff = (c['total_company_cost'] or 0) - (p['total_company_cost'] or 0)
                allow_diff = (c['total_allowances'] or 0) - (p['total_allowances'] or 0)
                variance_reason = "Salary Increase" if net_diff > 0 else ("Deduction" if net_diff < 0 else "No Change")
                rows.append({
                    'Employee Code': c['employee_code'],
                    'Arabic Name': c['arabic_name'],
                    'Department': c['department'],
                    'Previous Net': p['net_transfer_amount'],
                    'Current Net': c['net_transfer_amount'],
                    'Net Difference': net_diff,
                    'Allowance Difference': allow_diff,
                    'Gross Difference': gross_diff,
                    'Tax Difference': tax_diff,
                    'Insurance Difference': ins_diff,
                    'Cost Difference': cost_diff,
                    'Variance Reason': variance_reason,
                })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
            export_download_link(df, f"variance_{year}_{month}.xlsx")

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Total Payroll Increase", fmt_currency(sum(r['Net Difference'] for r in rows if r['Net Difference'] > 0)))
            with c2: st.metric("Total Payroll Decrease", fmt_currency(abs(sum(r['Net Difference'] for r in rows if r['Net Difference'] < 0))))
            with c3: st.metric("Total Cost Variance", fmt_currency(sum(r['Cost Difference'] for r in rows)))
            with c4: st.metric("Employees with Change", sum(1 for r in rows if r['Net Difference'] != 0))

            high_variance = [r for r in rows if abs(r['Net Difference']) > 1000]
            if high_variance:
                st.warning(f"⚠️ {len(high_variance)} employees have variance > E£1,000")
                st.dataframe(pd.DataFrame(high_variance), use_container_width=True)
    else:
        st.info("Need data for both current and previous months.")

def show_executive_package():
    page_header("Executive Reports Package", "One-click comprehensive Excel report")
    year = st.selectbox("Year", range(2026, 2019, -1), key="ex_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="ex_month", index=datetime.now().month - 1)

    if st.button("📦 Generate Executive Package", type="primary"):
        try:
            import io
            import openpyxl
            output = io.BytesIO()

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                with get_db() as db:
                    transactions = db.execute('''SELECT employee_code, arabic_name, department, section, sponsor,
                        base_net_salary, net_earning, total_allowances, estimated_gross, basic_salary,
                        employee_insurance, company_insurance, monthly_tax, net_transfer_amount,
                        total_company_cost, payment_status
                        FROM payroll_transactions WHERE year=? AND month=? ORDER BY employee_code''',
                                             (year, month)).fetchall()
                if transactions:
                    df = pd.DataFrame([dict(t) for t in transactions])
                    df.to_excel(writer, sheet_name='Monthly Payroll', index=False)
                    ws = writer.sheets['Monthly Payroll']
                    ws.column_dimensions['A'].width = 15
                    ws.column_dimensions['B'].width = 30
                    ws.column_dimensions['C'].width = 20
                    ws.column_dimensions['D'].width = 20
                    ws.column_dimensions['E'].width = 15
                    ws.column_dimensions['F'].width = 15
                    ws.column_dimensions['G'].width = 15
                    ws.column_dimensions['H'].width = 15
                    ws.column_dimensions['I'].width = 15
                    ws.column_dimensions['J'].width = 15
                    ws.column_dimensions['K'].width = 15
                    ws.column_dimensions['L'].width = 15
                    ws.column_dimensions['M'].width = 15
                    ws.column_dimensions['N'].width = 15

                with get_db() as db:
                    proj = db.execute('''SELECT project_code, SUM(allocated_total_cost) as total_cost,
                        COUNT(DISTINCT employee_code) as headcount
                        FROM payroll_project_allocations WHERE year=? AND month=?
                        GROUP BY project_code''', (year, month)).fetchall()
                if proj:
                    pd.DataFrame([dict(p) for p in proj]).to_excel(writer, sheet_name='Project Cost', index=False)

                with get_db() as db:
                    bonuses = db.execute('''SELECT employee_code, arabic_name, bonus_type, bonus_category,
                        bonus_amount_entered, comp_cost_diff, payment_status
                        FROM employee_bonuses WHERE year=? AND month=?''', (year, month)).fetchall()
                if bonuses:
                    pd.DataFrame([dict(b) for b in bonuses]).to_excel(writer, sheet_name='Bonuses', index=False)

                summary_data = {
                    'Metric': ['Total Employees', 'Total Net Earning', 'Total Net Transfer', 'Total Gross',
                               'Total Tax', 'Total Employee Insurance',
                               'Total Company Insurance', 'Total Company Cost', 'Total Allowances'],
                    'Value': [
                        len(transactions),
                        sum(t['net_earning'] or 0 for t in transactions),
                        sum(t['net_transfer_amount'] or 0 for t in transactions),
                        sum(t['estimated_gross'] or 0 for t in transactions),
                        sum(t['monthly_tax'] or 0 for t in transactions),
                        sum(t['employee_insurance'] or 0 for t in transactions),
                        sum(t['company_insurance'] or 0 for t in transactions),
                        sum(t['total_company_cost'] or 0 for t in transactions),
                        sum(t['total_allowances'] or 0 for t in transactions),
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Dashboard Summary', index=False)

            output.seek(0)
            st.download_button("📥 Download Executive Package", data=output,
                              file_name=f"executive_package_{year}_{month}.xlsx",
                              mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            st.success("Executive package generated successfully!")
        except Exception as e:
            st.error(f"Error generating package: {e}")
            st.info("Install openpyxl: pip install openpyxl xlsxwriter")
