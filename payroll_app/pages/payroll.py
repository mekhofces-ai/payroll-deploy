import streamlit as st
import pandas as pd
from datetime import datetime
from ..database import get_db, add_audit_log
from ..auth import check_permission, can_view_salary, can_view_company_cost
from ..services import generate_payroll, recalculate_payroll, calculate_payroll_for_employee, net_to_gross
from ..ui import page_header, fmt_currency, status_badge, divider, footer, apply_custom_css, export_download_link

def show():
    apply_custom_css()
    tabs = st.tabs(["Payroll Run Center", "Payroll Transactions", "Payroll Project Allocation",
                    "Net to Gross Calculator", "Bank Transfer", "Bank Reconciliation", "Payslips"])

    with tabs[0]:
        show_payroll_run_center()
    with tabs[1]:
        show_transactions()
    with tabs[2]:
        show_project_allocation()
    with tabs[3]:
        show_calculator()
    with tabs[4]:
        show_bank_transfer()
    with tabs[5]:
        show_reconciliation()
    with tabs[6]:
        show_payslips()

def show_payroll_run_center():
    page_header("Payroll Run Center", "Generate and manage payroll runs")
    if not check_permission('Payroll Run Center', 'View Only'):
        st.error("Access denied."); return

    year = st.selectbox("Year", range(2026, 2019, -1), key="pr_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="pr_month", index=datetime.now().month - 1)

    with get_db() as db:
        projects = [r['project_code'] for r in db.execute("SELECT project_code FROM projects WHERE status='Active'").fetchall()]
        departments = [r['name'] for r in db.execute("SELECT name FROM departments WHERE status='Active'").fetchall()]
        sponsors = [r['name'] for r in db.execute("SELECT name FROM sponsors WHERE status='Active'").fetchall()]
        runs = db.execute("SELECT * FROM payroll_runs WHERE year=? AND month=? ORDER BY id DESC", (year, month)).fetchall()

    c1, c2, c3 = st.columns(3)
    with c1:
        proj_filter = st.selectbox("Project Filter", ["All"] + projects, key="pr_proj")
    with c2:
        dept_filter = st.selectbox("Department Filter", ["All"] + departments, key="pr_dept")
    with c3:
        sponsor_filter = st.selectbox("Sponsor Filter", ["All"] + sponsors, key="pr_spon")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("⚙️ Generate Payroll", use_container_width=True):
            if not check_permission('Payroll Run Center', 'Add'):
                st.error("No permission.")
            else:
                with st.spinner("Generating payroll..."):
                    pf = proj_filter if proj_filter != "All" else None
                    df = dept_filter if dept_filter != "All" else None
                    sf = sponsor_filter if sponsor_filter != "All" else None
                    results = generate_payroll(year, month, pf, df, sf)
                    with get_db() as db2:
                        add_audit_log(db2, 'Generated', 'Payroll', 'payroll_transactions',
                                      f'{year}-{month}', username=st.session_state.get('user',{}).get('username','system'),
                                      reason=f'Payroll generated for {len(results)} employees')
                    st.success(f"Payroll generated for {len(results)} employees.")
                    st.rerun()
    with col2:
        if st.button("🔄 Recalculate", use_container_width=True):
            if not check_permission('Payroll Run Center', 'Edit'):
                st.error("No permission.")
            else:
                recalculate_payroll(year, month)
                with get_db() as db2:
                    add_audit_log(db2, 'Updated', 'Payroll', 'payroll_transactions',
                                  f'{year}-{month}', username=st.session_state.get('user',{}).get('username','system'),
                                  reason='Payroll recalculated')
                st.success("Payroll recalculated.")
                st.rerun()
    with col3:
        if st.button("📋 Submit for Approval", use_container_width=True, type="secondary"):
            with get_db() as db:
                db.execute("UPDATE payroll_runs SET status='Submitted' WHERE year=? AND month=?", (year, month))
                add_audit_log(db, 'Submitted', 'Payroll', 'payroll_runs',
                              f'{year}-{month}', username=st.session_state.get('user',{}).get('username','system'),
                              reason='Payroll submitted for approval')
            st.success("Submitted for approval.")
            st.rerun()
    with col4:
        with get_db() as db:
            run = db.execute("SELECT * FROM payroll_runs WHERE year=? AND month=? ORDER BY id DESC LIMIT 1", (year, month)).fetchone()
            if run and run['status'] == 'Submitted':
                with get_db() as db2:
                    db2.execute("UPDATE payroll_runs SET status='Closed' WHERE id=?", (run['id'],))
                    db2.execute("UPDATE payroll_transactions SET approval_status='Approved' WHERE year=? AND month=?", (year, month))
                    add_audit_log(db2, 'Approved', 'Payroll', 'payroll_transactions',
                                  f'{year}-{month}', username=st.session_state.get('user',{}).get('username','system'),
                                  reason='Payroll approved and closed')
                st.success("Payroll closed.")
                st.rerun()

    if runs:
        st.subheader("Payroll Run History")
        df = pd.DataFrame([dict(r) for r in runs])
        st.dataframe(df[['year', 'month', 'status', 'created_at']], use_container_width=True)

    st.divider()
    with get_db() as db:
        summary = db.execute('''SELECT COUNT(*) as count, 
            COALESCE(SUM(net_transfer_amount),0) as total_net,
            COALESCE(SUM(total_company_cost),0) as total_cost,
            COALESCE(SUM(employee_insurance),0) as total_emp_ins,
            COALESCE(SUM(company_insurance),0) as total_comp_ins,
            COALESCE(SUM(monthly_tax),0) as total_tax
            FROM payroll_transactions WHERE year=? AND month=?''', (year, month)).fetchone()

    if summary and summary['count'] > 0:
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Employees Paid", summary['count'])
        with c2: st.metric("Total Net", fmt_currency(summary['total_net']))
        with c3: st.metric("Total Tax", fmt_currency(summary['total_tax']))
        with c4: st.metric("Company Cost", fmt_currency(summary['total_cost']))

        with get_db() as db:
            transactions = db.execute('''SELECT employee_code, arabic_name, net_transfer_amount, total_company_cost,
                monthly_tax, employee_insurance, payment_status, approval_status
                FROM payroll_transactions WHERE year=? AND month=? ORDER BY employee_code''', (year, month)).fetchall()
        if transactions:
            df_t = pd.DataFrame([dict(t) for t in transactions])
            st.dataframe(df_t, use_container_width=True)
            export_download_link(df_t, f"payroll_{year}_{month}.xlsx")

def show_transactions():
    page_header("Payroll Transactions", "Detailed payroll transactions")
    if not check_permission('Payroll Transactions', 'View Only'):
        st.error("Access denied."); return
    show_sal = can_view_salary()

    year = st.selectbox("Year", range(2026, 2019, -1), key="pt_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="pt_month", index=datetime.now().month - 1)

    with get_db() as db:
        transactions = db.execute('''SELECT * FROM payroll_transactions WHERE year=? AND month=? ORDER BY employee_code''', (year, month)).fetchall()

    if transactions:
        data = []
        for t in transactions:
            d = dict(t)
            fmt_fields = ['base_net_salary', 'net_earning', 'net_transfer_amount', 'estimated_gross',
                          'basic_salary', 'employee_insurance', 'company_insurance', 'monthly_tax', 'total_company_cost']
            if show_sal:
                for f in fmt_fields:
                    if f in d:
                        d[f] = fmt_currency(d[f])
            else:
                for f in fmt_fields:
                    if f in d:
                        d[f] = "Restricted"
            data.append(d)
        df = pd.DataFrame(data)
        cols = ['employee_code', 'arabic_name', 'department', 'base_net_salary', 'net_earning',
                'net_transfer_amount', 'estimated_gross', 'basic_salary', 'employee_insurance',
                'company_insurance', 'monthly_tax', 'total_company_cost', 'payment_status', 'approval_status']
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)
        st.caption("**base_net_salary** = Base Net Salary | **net_earning** = Total Net Earning")
        export_download_link(df, f"transactions_{year}_{month}.xlsx")

        if check_permission('Payroll Transactions', 'Edit'):
            with st.expander("⚡ Bulk Update Payment Status"):
                new_status = st.selectbox("New Status", ['Pending', 'Transferred', 'Hold', 'Cancelled', 'Paid'])
                if st.button("Update All"):
                    with get_db() as db2:
                        db2.execute("UPDATE payroll_transactions SET payment_status=? WHERE year=? AND month=?", (new_status, year, month))
                    st.success(f"All transactions updated to {new_status}")
                    st.rerun()
    else:
        st.info("No transactions for this period.")

def show_project_allocation():
    page_header("Payroll Project Allocation", "View payroll cost by project")
    if not check_permission('Payroll Project Cost Allocation', 'View Only'):
        st.error("Access denied."); return

    year = st.selectbox("Year", range(2026, 2019, -1), key="pa_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="pa_month", index=datetime.now().month - 1)

    with get_db() as db:
        allocations = db.execute('''SELECT pa.*, p.project_name FROM payroll_project_allocations pa
            JOIN projects p ON pa.project_code = p.project_code
            WHERE pa.year=? AND pa.month=? ORDER BY pa.project_code, pa.employee_code''', (year, month)).fetchall()

    if allocations:
        df = pd.DataFrame([dict(a) for a in allocations])
        show_cols = ['employee_code', 'arabic_name', 'project_code', 'allocation_percent',
                     'allocated_net_salary', 'allocated_gross', 'allocated_tax',
                     'allocated_employee_insurance', 'allocated_company_insurance', 'allocated_total_cost']
        show_cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[show_cols], use_container_width=True)
        export_download_link(df, f"project_allocation_{year}_{month}.xlsx")

        st.subheader("Summary by Project")
        summary = df.groupby('project_code').agg({
            'allocated_net_salary': 'sum', 'allocated_gross': 'sum',
            'allocated_tax': 'sum', 'allocated_total_cost': 'sum',
            'employee_code': 'nunique'
        }).reset_index()
        st.dataframe(summary, use_container_width=True)
    else:
        st.info("No project allocations for this period.")

def show_calculator():
    page_header("Net to Gross Calculator", "Calculate required gross salary from target net")
    if not check_permission('Net to Gross Calculator', 'View Only'):
        st.error("Access denied."); return

    with get_db() as db:
        employees = db.execute("SELECT employee_code, arabic_name, new_net_salary, basic_salary, insurance_salary_base FROM employees WHERE status='Active' ORDER BY employee_code").fetchall()

    emp_sel = st.selectbox("Employee (optional)", ["Custom"] + [f"{e['employee_code']} - {e['arabic_name']}" for e in employees], key="calc_emp")
    target_net = st.number_input("Target Net Salary", min_value=0.0, value=10000.0, step=500.0)
    year = st.selectbox("Year", range(2026, 2019, -1), key="calc_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="calc_month", index=datetime.now().month - 1)

    emp_data = {'basic_salary': 0, 'insurance_salary_base': 0, 'new_net_salary': 0}
    basic_override = None
    ins_override = None

    if emp_sel != "Custom":
        emp_code = emp_sel.split(" - ")[0]
        for e in employees:
            if e['employee_code'] == emp_code:
                emp_data = dict(e)
                break
        basic_override = st.number_input("Basic Salary Override", value=float(emp_data.get('basic_salary', 0) or 0), step=100.0)
        ins_override = st.number_input("Insurance Base Override", value=float(emp_data.get('insurance_salary_base', 0) or 0), step=100.0)

    if st.button("🧮 Calculate", type="primary"):
        result = net_to_gross(target_net, emp_data, year, month,
                              basic_override=basic_override or 0, insurance_override=ins_override or 0)
        if result:
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Target Net Salary", fmt_currency(result['target_net']))
                st.metric("Estimated Gross Salary", fmt_currency(result['estimated_gross']))
                st.metric("Basic Salary", fmt_currency(result['basic_salary']))
                st.metric("Employee Insurance", fmt_currency(result['employee_insurance']))
                st.metric("Company Insurance", fmt_currency(result['company_insurance']))
            with c2:
                st.metric("Monthly Tax", fmt_currency(result['monthly_tax']))
                st.metric("Annual Tax", fmt_currency(result['annual_tax']))
                st.metric("Total Deductions", fmt_currency(result['total_deductions']))
                st.metric("Final Net Salary", fmt_currency(result['final_net']))
                st.metric("Total Company Cost", fmt_currency(result['total_company_cost']))

            st.subheader("Tax Breakdown")
            st.write(f"Annual Taxable Income: {fmt_currency(result['annual_taxable_income'])}")
            st.write(f"Effective Tax Rate: {result['effective_tax_rate']}%")
            st.write(f"Personal Exemption: {fmt_currency(result['personal_exemption_used'])}")
            st.write(f"Additional Exemption: {fmt_currency(result['additional_exemption_used'])}")
            st.write(f"Tax Free Bracket: {fmt_currency(result['tax_free_used'])}")

            if result.get('tax_brackets'):
                st.subheader("Bracket Details")
                bracket_data = []
                for b in result['tax_brackets']:
                    bracket_data.append({
                        'From': fmt_currency(b['bracket']['income_from']),
                        'To': fmt_currency(b['bracket']['income_to']),
                        'Rate': f"{b['rate']*100:.1f}%",
                        'Taxable Amount': fmt_currency(b['taxable_in_bracket']),
                        'Tax': fmt_currency(b['tax'])
                    })
                st.dataframe(pd.DataFrame(bracket_data), use_container_width=True)

def show_bank_transfer():
    page_header("Bank Transfer", "Generate and manage bank transfer files")
    if not check_permission('Payroll Run Center', 'View Only'):
        st.error("Access denied."); return

    year = st.selectbox("Year", range(2026, 2019, -1), key="bt_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="bt_month", index=datetime.now().month - 1)

    if st.button("📤 Generate Bank Transfer File"):
        with get_db() as db:
            transactions = db.execute('''SELECT employee_code, arabic_name, english_name, 
                net_transfer_amount, COALESCE(bank_name,'') as bank_name, COALESCE(bank_account,'') as bank_account
                FROM payroll_transactions WHERE year=? AND month=? 
                AND payment_status NOT IN ('Cancelled','Hold')
                ORDER BY employee_code''', (year, month)).fetchall()

        if transactions:
            data = []
            missing_bank = 0
            for t in transactions:
                t = dict(t)
                if not t.get('bank_account'):
                    missing_bank += 1
                    continue
                data.append({
                    'Employee Code': t['employee_code'],
                    'Arabic Name': t['arabic_name'],
                    'Bank Name': t['bank_name'],
                    'Bank Account': t['bank_account'],
                    'Net Transfer': t['net_transfer_amount'],
                    'Payment Month': month,
                    'Payment Year': year,
                })
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
                export_download_link(df, f"bank_transfer_{year}_{month}.xlsx", "Download Bank Transfer File")
                if missing_bank > 0:
                    st.warning(f"{missing_bank} employees excluded due to missing bank account.")

                if st.button("✅ Mark as Transferred"):
                    with get_db() as db2:
                        cnt = 0
                        for t in transactions:
                            t = dict(t)
                            if t.get('bank_account'):
                                db2.execute('''UPDATE payroll_transactions SET payment_status='Transferred', 
                                    transfer_date=datetime('now','localtime'), transfer_ref=? 
                                    WHERE employee_code=? AND year=? AND month=?''',
                                           (f"TFR-{year}{month:02d}-{t['employee_code']}", t['employee_code'], year, month))
                                cnt += 1
                        add_audit_log(db2, 'Transferred', 'Payroll', 'payroll_transactions',
                                      f'{year}-{month}', username=st.session_state.get('user',{}).get('username','system'),
                                      reason=f'{cnt} employees marked as transferred')
                    st.success("Marked as transferred.")
                    st.rerun()
            else:
                st.warning("No valid transactions for transfer.")
        else:
            st.info("No transactions found for this period.")

    st.divider()
    with get_db() as db:
        transfers = db.execute('''SELECT employee_code, arabic_name, net_transfer_amount, transfer_date, transfer_ref, payment_status
            FROM payroll_transactions WHERE year=? AND month=? AND payment_status='Transferred'
            ORDER BY employee_code''', (year, month)).fetchall()
    if transfers:
        st.subheader("Transferred Records")
        df = pd.DataFrame([dict(t) for t in transfers])
        st.dataframe(df, use_container_width=True)

def show_reconciliation():
    page_header("Bank Reconciliation", "Reconcile payroll with bank transfers")
    year = st.selectbox("Year", range(2026, 2019, -1), key="rec_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="rec_month", index=datetime.now().month - 1)

    with get_db() as db:
        transactions = db.execute('''SELECT employee_code, arabic_name, net_transfer_amount, transfer_date, transfer_ref, payment_status
            FROM payroll_transactions WHERE year=? AND month=? ORDER BY employee_code''', (year, month)).fetchall()

    if transactions:
        data = []
        for t in transactions:
            t = dict(t)
            actual = st.number_input(f"Actual bank amount for {t['employee_code']}", value=float(t['net_transfer_amount']), key=f"actual_{t['employee_code']}")
            diff = t['net_transfer_amount'] - actual
            status = "Matched" if abs(diff) < 0.01 else ("Overpaid" if diff > 0 else "Underpaid")
            data.append({
                'Employee': t['employee_code'],
                'Name': t['arabic_name'],
                'Payroll Amount': fmt_currency(t['net_transfer_amount']),
                'Bank Amount': fmt_currency(actual),
                'Difference': fmt_currency(abs(diff)),
                'Status': status
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)

        if st.button("💾 Save Reconciliation"):
            with get_db() as db2:
                for t in transactions:
                    t = dict(t)
                    actual = st.session_state.get(f"actual_{t['employee_code']}", t['net_transfer_amount'])
                    diff = t['net_transfer_amount'] - actual
                    rec_status = "Matched" if abs(diff) < 0.01 else ("Overpaid" if diff > 0 else "Underpaid")
                    existing = db2.execute("SELECT id FROM bank_reconciliation WHERE employee_code=? AND transfer_date=?", (t['employee_code'], t['transfer_date'] or '')).fetchone()
                    if existing:
                        db2.execute("UPDATE bank_reconciliation SET payroll_net_amount=?, actual_bank_amount=?, difference=?, status=? WHERE id=?",
                                   (t['net_transfer_amount'], actual, diff, rec_status, existing['id']))
                    else:
                        db2.execute('''INSERT INTO bank_reconciliation (employee_code, arabic_name, payroll_net_amount, actual_bank_amount, difference, status)
                            VALUES (?,?,?,?,?,?)''', (t['employee_code'], t['arabic_name'], t['net_transfer_amount'], actual, diff, rec_status))
            st.success("Reconciliation saved.")
            st.rerun()

        export_download_link(df, f"reconciliation_{year}_{month}.xlsx")
    else:
        st.info("No transactions for reconciliation.")

def show_payslips():
    page_header("Payslips", "Generate employee payslips")
    year = st.selectbox("Year", range(2026, 2019, -1), key="ps_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="ps_month", index=datetime.now().month - 1)

    with get_db() as db:
        employees = db.execute("SELECT employee_code, arabic_name FROM employees WHERE status='Active' ORDER BY employee_code").fetchall()

    emp_sel = st.selectbox("Employee", ["All"] + [f"{e['employee_code']} - {e['arabic_name']}" for e in employees], key="ps_emp")

    if emp_sel != "All":
        emp_code = emp_sel.split(" - ")[0]
        with get_db() as db:
            trans = db.execute('''SELECT * FROM payroll_transactions WHERE employee_code=? AND year=? AND month=?''',
                               (emp_code, year, month)).fetchone()
        if trans:
            t = dict(trans)
            st.markdown(f"""
            <div style="background:white;padding:2rem;border-radius:16px;border:1px solid #e0e0e0;max-width:600px;margin:auto">
                <h2 style="text-align:center;color:#1a1a2e;margin-bottom:0">{st.session_state.get('company_name','Payroll Pro')}</h2>
                <p style="text-align:center;color:#6c757d;font-size:0.9rem">Payslip - {month}/{year}</p>
                <hr>
                <table style="width:100%;font-size:0.9rem">
                    <tr><td>Employee Code:</td><td><b>{t['employee_code']}</b></td></tr>
                    <tr><td>Name:</td><td><b>{t['arabic_name']}</b></td></tr>
                    <tr><td>Department:</td><td>{t['department']}</td></tr>
                    <tr><td>Section:</td><td>{t['section']}</td></tr>
                    <tr><td>Position:</td><td>{t['position']}</td></tr>
                </table>
                <hr>
                <table style="width:100%;font-size:0.9rem">
                    <tr><td>Base Net Salary:</td><td style="text-align:right">{fmt_currency(t['base_net_salary'])}</td></tr>
                    <tr><td>Allowances:</td><td style="text-align:right">{fmt_currency(t['total_allowances'])}</td></tr>
                    <tr><td>Gross Salary:</td><td style="text-align:right">{fmt_currency(t['estimated_gross'])}</td></tr>
                    <tr><td>Employee Insurance:</td><td style="text-align:right">-{fmt_currency(t['employee_insurance'])}</td></tr>
                    <tr><td>Monthly Tax:</td><td style="text-align:right">-{fmt_currency(t['monthly_tax'])}</td></tr>
                    <tr style="border-top:2px solid #333"><td><b>Net Transfer Amount:</b></td><td style="text-align:right"><b>{fmt_currency(t['net_transfer_amount'])}</b></td></tr>
                </table>
                <hr>
                <p style="text-align:center;font-size:0.8rem;color:#6c757d">
                    Payment Status: {t['payment_status']} | Generated: {datetime.now().strftime('%d-%b-%Y %H:%M')}
                </p>
            </div>
            """, unsafe_allow_html=True)

            df_single = pd.DataFrame([t])
            export_download_link(df_single, f"payslip_{emp_code}_{year}_{month}.xlsx")
        else:
            st.info("No payslip for this employee/period.")
    else:
        with get_db() as db:
            transactions = db.execute('''SELECT employee_code, arabic_name, net_transfer_amount, estimated_gross,
                employee_insurance, monthly_tax, payment_status
                FROM payroll_transactions WHERE year=? AND month=? ORDER BY employee_code''', (year, month)).fetchall()
        if transactions:
            df = pd.DataFrame([dict(t) for t in transactions])
            st.dataframe(df, use_container_width=True)
            if st.button("📄 Generate All Payslips"):
                export_download_link(df, f"all_payslips_{year}_{month}.xlsx")
        else:
            st.info("No payslips for this period.")
