import streamlit as st
import pandas as pd
from datetime import datetime
from ..database import get_db, add_audit_log
from ..auth import check_permission
from ..services import calculate_bonus_cost
from ..ui import page_header, fmt_currency, status_badge, divider, footer, apply_custom_css, export_download_link

def show():
    apply_custom_css()
    tabs = st.tabs(["Bonus Calculator", "Bonus Register", "Bonus Reports"])

    with tabs[0]:
        show_calculator()
    with tabs[1]:
        show_register()
    with tabs[2]:
        show_reports()

def show_calculator():
    page_header("Bonus Calculator", "Calculate bonus cost before and after with full cost analysis")
    if not check_permission('Bonus Calculator', 'View Only'):
        st.error("Access denied."); return

    if 'bonus_result' not in st.session_state:
        st.session_state.bonus_result = None

    with get_db() as db:
        employees = db.execute("SELECT employee_code, arabic_name, new_net_salary, position, department, section, default_project FROM employees WHERE status='Active' ORDER BY employee_code").fetchall()

    if not employees:
        st.info("No employees found.")
        return

    emp_sel = st.selectbox("Select Employee", [f"{e['employee_code']} - {e['arabic_name']}" for e in employees], key="bonus_emp")
    emp_code = emp_sel.split(" - ")[0] if emp_sel else employees[0]['employee_code']

    selected_emp = next((e for e in employees if e['employee_code'] == emp_code), None)

    with st.container():
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            bonus_type = st.selectbox("Bonus Type", ["Net Bonus", "Gross Bonus"],
                                     help="Net Bonus: employee receives exact amount net after tax/insurance. Gross Bonus: bonus added to gross salary")
            bonus_amount = st.number_input("Bonus Amount (EGP)", min_value=0.0, value=5000.0, step=500.0, format="%.2f")
        with col2:
            bonus_category = st.selectbox("Bonus Category", ["Performance Bonus", "Project Bonus", "Eid Bonus", "Annual Bonus", "Retention Bonus", "Overtime Bonus", "Exceptional Bonus", "Other"])
            bonus_reason = st.text_area("Reason / Notes", "", placeholder="Why is this bonus being given?")
        with col3:
            if selected_emp:
                st.markdown(f"""
                <div style="background:#f8f9fa;padding:1rem;border-radius:12px;border:1px solid #e9ecef">
                    <div style="font-size:0.8rem;color:#6c757d;margin-bottom:0.5rem">Employee Info</div>
                    <div style="font-weight:600;font-size:1rem">{selected_emp['arabic_name']}</div>
                    <div style="font-size:0.85rem;color:#495057">{selected_emp['position'] or 'N/A'}</div>
                    <div style="font-size:0.8rem;color:#6c757d">{selected_emp['department'] or ''} | {selected_emp['default_project'] or ''}</div>
                    <div style="font-size:0.8rem;color:#6c757d;margin-top:0.3rem">Base Net Salary: <b>{fmt_currency(selected_emp['new_net_salary'])}</b></div>
                </div>
                """, unsafe_allow_html=True)

    year = st.selectbox("Year", range(2026, 2019, -1), key="bonus_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="bonus_month", index=datetime.now().month - 1)

    calculate = st.button("🧮 Calculate Bonus Cost", type="primary", use_container_width=True)

    if calculate:
        with st.spinner("Calculating bonus cost..."):
            st.session_state.bonus_result = calculate_bonus_cost(emp_code, bonus_type, bonus_amount, year, month)

    result = st.session_state.bonus_result
    if result:
            cost_multiplier = result['comp_cost_diff'] / result['net_increase'] if result['net_increase'] > 0 else 0

            st.markdown("""
            <div style="background:linear-gradient(135deg,#667eea15,#764ba215);padding:1.5rem;border-radius:16px;border:1px solid #667eea30;margin:1rem 0">
            """, unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Bonus Amount Entered", fmt_currency(result['bonus_amount_entered']),
                         delta=f"{result['bonus_type']}")
            with c2:
                st.metric("Net Increase to Employee", fmt_currency(result['net_increase']))
            with c3:
                st.metric("Gross Amount Needed", fmt_currency(result['gross_diff']),
                         delta=f"Gross-up: {((result['gross_diff']/result['net_increase']-1)*100):.1f}%" if result['net_increase'] > 0 else None)
            with c4:
                st.metric("Total Company Cost Impact", fmt_currency(result['comp_cost_diff']),
                         delta=f"{cost_multiplier:.2f}x multiplier", delta_color="inverse")

            st.markdown("</div>", unsafe_allow_html=True)

            st.subheader("Before / After Comparison")
            comparison_data = {
                'Metric': ['Net Salary', 'Gross Salary', 'Monthly Tax', 'Employee Insurance', 'Company Insurance', 'Total Company Cost'],
                'Before Bonus': [fmt_currency(result['net_before']), fmt_currency(result['gross_before']),
                                fmt_currency(result['tax_before']), fmt_currency(result['emp_ins_before']),
                                fmt_currency(result['comp_ins_before']), fmt_currency(result['comp_cost_before'])],
                'After Bonus': [fmt_currency(result['net_after']), fmt_currency(result['gross_after']),
                               fmt_currency(result['tax_after']), fmt_currency(result['emp_ins_after']),
                               fmt_currency(result['comp_ins_after']), fmt_currency(result['comp_cost_after'])],
                'Difference': [fmt_currency(result['net_increase']), fmt_currency(result['gross_diff']),
                              fmt_currency(result['tax_diff']), fmt_currency(result['emp_ins_diff']),
                              fmt_currency(result['comp_ins_diff']), fmt_currency(result['comp_cost_diff'])],
            }
            st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)

            with st.expander("📊 Detailed Cost Breakdown"):
                detail_cols = st.columns(2)
                with detail_cols[0]:
                    st.markdown("**Net Bonus Details**" if result['bonus_type'] == 'Net Bonus' else "**Gross Bonus Details**")
                    st.write(f"Bonus Type: {result['bonus_type']}")
                    st.write(f"Entered Amount: {fmt_currency(result['bonus_amount_entered'])}")
                    st.write(f"Net Bonus Amount: {fmt_currency(result['net_bonus_amount'])}")
                    st.write(f"Gross Bonus Amount: {fmt_currency(result['gross_bonus_amount'])}")
                with detail_cols[1]:
                    st.markdown("**Cost Analysis**")
                    st.write(f"Net Increase to Employee: {fmt_currency(result['net_increase'])}")
                    st.write(f"Company Cost Before: {fmt_currency(result['comp_cost_before'])}")
                    st.write(f"Company Cost After: {fmt_currency(result['comp_cost_after'])}")
                    st.write(f"Company Cost Difference: **{fmt_currency(result['comp_cost_diff'])}**")
                    st.write(f"Cost Multiplier: **{cost_multiplier:.2f}x**")
                    st.write(f"(Every E£1 net to employee costs company E£{cost_multiplier:.2f})")

            st.subheader("Save Bonus")
            savec1, savec2, savec3 = st.columns(3)
            with savec1:
                if st.button("💾 Save as Actual Bonus", use_container_width=True):
                    try:
                        with get_db() as db:
                            emp_db = db.execute("SELECT * FROM employees WHERE employee_code=?", (emp_code,)).fetchone()
                            if not emp_db:
                                st.error("Employee not found.")
                                st.stop()
                            db.execute('''INSERT INTO employee_bonuses 
                                (employee_code, arabic_name, organization, sponsor, position, department, section,
                                 default_project, bonus_project, year, month, bonus_date, bonus_type, bonus_category,
                                 bonus_amount_entered, net_bonus_amount, gross_bonus_amount,
                                 tax_before, tax_after, tax_diff, emp_ins_before, emp_ins_after, emp_ins_diff,
                                 comp_ins_before, comp_ins_after, comp_ins_diff, gross_before, gross_after, gross_diff,
                                 net_before, net_after, net_increase, comp_cost_before, comp_cost_after, comp_cost_diff,
                                 payment_status, approval_status, reason, created_by)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Planned','Draft',?,?)''',
                                       (emp_code, result['arabic_name'], emp_db['organization'], emp_db['sponsor'],
                                        emp_db['position'], emp_db['department'], emp_db['section'],
                                        emp_db['default_project'], emp_db['default_project'],
                                        year, month, bonus_type, bonus_category, bonus_amount,
                                        result['net_bonus_amount'], result['gross_bonus_amount'],
                                        result['tax_before'], result['tax_after'], result['tax_diff'],
                                        result['emp_ins_before'], result['emp_ins_after'], result['emp_ins_diff'],
                                        result['comp_ins_before'], result['comp_ins_after'], result['comp_ins_diff'],
                                        result['gross_before'], result['gross_after'], result['gross_diff'],
                                        result['net_before'], result['net_after'], result['net_increase'],
                                        result['comp_cost_before'], result['comp_cost_after'], result['comp_cost_diff'],
                                        bonus_reason, st.session_state.get('user',{}).get('username','system')))
                            add_audit_log(db, 'Created', 'Bonus', 'employee_bonuses', f"{emp_code} - E£{bonus_amount:,.2f}", st.session_state.get('user',{}).get('username','system'))
                            st.success("✅ Bonus saved as actual bonus record.")
                            st.session_state.bonus_result = None
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error saving bonus: {e}")

            with savec2:
                if st.button("💾 Save as Simulation", use_container_width=True):
                    with get_db() as db:
                        db.execute("INSERT INTO bonus_simulations (employee_code, bonus_type, amount, result_data, created_by) VALUES (?,?,?,?,?)",
                                   (emp_code, bonus_type, bonus_amount, str(result), st.session_state.get('user',{}).get('username','system')))
                    st.success("✅ Simulation saved.")

            with savec3:
                export_df = pd.DataFrame([
                    {'Metric': 'Bonus Amount', 'Value': bonus_amount, 'After': bonus_amount},
                    {'Metric': 'Net Before', 'Value': result['net_before'], 'After': result['net_after']},
                    {'Metric': 'Gross Before', 'Value': result['gross_before'], 'After': result['gross_after']},
                    {'Metric': 'Tax Before', 'Value': result['tax_before'], 'After': result['tax_after']},
                    {'Metric': 'Company Insurance Before', 'Value': result['comp_ins_before'], 'After': result['comp_ins_after']},
                    {'Metric': 'Company Cost Before', 'Value': result['comp_cost_before'], 'After': result['comp_cost_after']},
                    {'Metric': 'Company Cost Difference', 'Value': 0, 'After': result['comp_cost_diff']},
                ])
                export_download_link(export_df, f"bonus_calc_{emp_code}_{year}_{month}.xlsx", "📥 Export to Excel")

    st.divider()
    with get_db() as db:
        sims = db.execute("SELECT * FROM bonus_simulations WHERE employee_code=? ORDER BY created_at DESC LIMIT 5", (emp_code,)).fetchall()
    if sims:
        st.subheader("Recent Simulations for this Employee")
        for s in sims:
            st.caption(f"📌 {s['bonus_type']}: E£{s['amount']:,.2f} on {s['created_at']}")

def show_register():
    page_header("Bonus Register", "Track all employee bonuses")
    if not check_permission('Bonus Register', 'View Only'):
        st.error("Access denied."); return

    year = st.selectbox("Year", range(2026, 2019, -1), key="reg_year", index=0)
    month = st.selectbox("Month", ["All"] + list(range(1, 13)), key="reg_month", index=0)

    query = "SELECT eb.*, e.arabic_name FROM employee_bonuses eb JOIN employees e ON eb.employee_code=e.employee_code WHERE eb.year=?"
    params = [year]
    if month != "All":
        query += " AND eb.month=?"
        params.append(month)
    query += " ORDER BY eb.created_at DESC"

    with get_db() as db:
        bonuses = db.execute(query, params).fetchall()

    if st.button("➕ Add Bonus (Quick)"):
        with get_db() as db:
            employees = db.execute("SELECT employee_code, arabic_name FROM employees WHERE status='Active'").fetchall()
        with st.form("quick_bonus"):
            emp_sel = st.selectbox("Employee", [f"{e['employee_code']} - {e['arabic_name']}" for e in employees])
            btype = st.selectbox("Type", ["Net Bonus", "Gross Bonus"])
            bcat = st.selectbox("Category", ["Performance Bonus", "Project Bonus", "Eid Bonus", "Annual Bonus", "Retention Bonus", "Overtime Bonus", "Exceptional Bonus", "Other"])
            amount = st.number_input("Amount", 0.0, step=500.0)
            if st.form_submit_button("Save"):
                emp_code_q = emp_sel.split(" - ")[0]
                result = calculate_bonus_cost(emp_code_q, btype, amount, year, 1)
                if result:
                    emp = dict(db.execute("SELECT * FROM employees WHERE employee_code=?", (emp_code_q,)).fetchone())
                    db.execute('''INSERT INTO employee_bonuses (employee_code, arabic_name, organization, sponsor, position,
                        department, section, default_project, bonus_project, year, month, bonus_type, bonus_category,
                        bonus_amount_entered, net_bonus_amount, gross_bonus_amount, tax_before, tax_after, tax_diff,
                        emp_ins_before, emp_ins_after, emp_ins_diff, comp_ins_before, comp_ins_after, comp_ins_diff,
                        gross_before, gross_after, gross_diff, net_before, net_after, net_increase, comp_cost_before,
                        comp_cost_after, comp_cost_diff, payment_status, approval_status, created_by)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Planned','Draft',?)''',
                               (emp_code_q, emp['arabic_name'], emp['organization'], emp['sponsor'], emp['position'],
                                emp['department'], emp['section'], emp['default_project'], emp['default_project'],
                                year, month if month != "All" else 1, btype, bcat, amount,
                                result['net_bonus_amount'], result['gross_bonus_amount'],
                                result['tax_before'], result['tax_after'], result['tax_diff'],
                                result['emp_ins_before'], result['emp_ins_after'], result['emp_ins_diff'],
                                result['comp_ins_before'], result['comp_ins_after'], result['comp_ins_diff'],
                                result['gross_before'], result['gross_after'], result['gross_diff'],
                                result['net_before'], result['net_after'], result['net_increase'],
                                result['comp_cost_before'], result['comp_cost_after'], result['comp_cost_diff'],
                                st.session_state.get('user',{}).get('username','system')))
                    st.success("Bonus added.")
                    st.rerun()

    if bonuses:
        df = pd.DataFrame([dict(b) for b in bonuses])
        cols = ['employee_code', 'arabic_name', 'bonus_type', 'bonus_category', 'bonus_amount_entered',
                'net_bonus_amount', 'gross_bonus_amount', 'comp_cost_diff', 'payment_status', 'approval_status', 'year', 'month']
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)

        if check_permission('Bonus Register', 'Edit'):
            for b in bonuses:
                b = dict(b)
                with st.expander(f"✏️ {b['arabic_name']} - E£{b['bonus_amount_entered']:,.2f} ({b['bonus_type']})"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button(f"Approve #{b['id']}", key=f"app_b{b['id']}"):
                            with get_db() as db2:
                                db2.execute("UPDATE employee_bonuses SET approval_status='Approved', approved_by=?, approved_date=datetime('now','localtime') WHERE id=?",
                                           (st.session_state.get('user',{}).get('username',''), b['id']))
                            st.success("Approved.")
                            st.rerun()
                    with c2:
                        if st.button(f"Mark Paid #{b['id']}", key=f"pay_b{b['id']}"):
                            with get_db() as db2:
                                db2.execute("UPDATE employee_bonuses SET payment_status='Paid', paid_date=datetime('now','localtime') WHERE id=?", (b['id'],))
                                st.success("Marked paid.")
                                st.rerun()
                    with c3:
                        new_status = st.selectbox("Payment Status", ['Planned', 'Approved', 'Paid', 'Cancelled', 'Hold'], key=f"ps_b{b['id']}")
                        if st.button("Update Status", key=f"upd_b{b['id']}"):
                            with get_db() as db2:
                                db2.execute("UPDATE employee_bonuses SET payment_status=? WHERE id=?", (new_status, b['id']))
                            st.success("Status updated.")
                            st.rerun()
        export_download_link(df, f"bonus_register_{year}.xlsx")
    else:
        st.info("No bonuses recorded.")

def show_reports():
    page_header("Bonus Reports", "Analyze bonus distribution")
    if not check_permission('Bonus Reports', 'View Only'):
        st.error("Access denied."); return

    report_type = st.selectbox("Report Type", [
        "Annual Bonus Summary by Employee",
        "Monthly Bonus Report",
        "Project Bonus Report",
        "Department Bonus Report",
        "Sponsor Bonus Report",
        "Bonus Cost Analysis",
        "Pending / Unpaid Bonus Report"
    ], key="bonus_rep")

    year = st.selectbox("Year", range(2026, 2019, -1), key="br_year", index=0)

    if report_type == "Annual Bonus Summary by Employee":
        with get_db() as db:
            data = db.execute('''SELECT employee_code, arabic_name, department, section, default_project, sponsor,
                year, SUM(net_bonus_amount) as total_net, SUM(gross_bonus_amount) as total_gross,
                SUM(tax_diff) as total_tax, SUM(emp_ins_diff) as total_emp_ins,
                SUM(comp_ins_diff) as total_comp_ins, SUM(comp_cost_diff) as total_cost,
                COUNT(*) as bonus_count, MAX(bonus_date) as last_bonus
                FROM employee_bonuses WHERE year=? AND approval_status IN ('Approved','Paid')
                GROUP BY employee_code ORDER BY total_cost DESC''', (year,)).fetchall()
        if data:
            df = pd.DataFrame([dict(d) for d in data])
            st.dataframe(df, use_container_width=True)
            st.subheader("Summary")
            st.metric("Total Employees with Bonus", len(data))
            st.metric("Total Bonus Cost", fmt_currency(sum(d['total_cost'] for d in data)))
            export_download_link(df, f"annual_bonus_summary_{year}.xlsx")

    elif report_type == "Monthly Bonus Report":
        month = st.selectbox("Month", range(1, 13), key="br_month")
        with get_db() as db:
            data = db.execute('''SELECT year, month, employee_code, arabic_name, department, section, default_project,
                bonus_category, bonus_type, net_bonus_amount, gross_bonus_amount, comp_cost_diff, payment_status, approval_status
                FROM employee_bonuses WHERE year=? AND month=? ORDER BY employee_code''', (year, month)).fetchall()
        if data:
            df = pd.DataFrame([dict(d) for d in data])
            st.dataframe(df, use_container_width=True)
            export_download_link(df, f"monthly_bonus_{year}_{month}.xlsx")

    elif report_type == "Project Bonus Report":
        with get_db() as db:
            data = db.execute('''SELECT bonus_project as project, year, month,
                SUM(net_bonus_amount) as total_net, SUM(gross_bonus_amount) as total_gross,
                SUM(comp_cost_diff) as total_cost, COUNT(DISTINCT employee_code) as emp_count, COUNT(*) as rec_count
                FROM employee_bonuses WHERE year=? AND approval_status IN ('Approved','Paid')
                GROUP BY bonus_project ORDER BY total_cost DESC''', (year,)).fetchall()
        if data:
            df = pd.DataFrame([dict(d) for d in data])
            st.dataframe(df, use_container_width=True)
            export_download_link(df, f"project_bonus_{year}.xlsx")

    elif report_type == "Department Bonus Report":
        with get_db() as db:
            data = db.execute('''SELECT department, section, year,
                SUM(net_bonus_amount) as total_net, SUM(gross_bonus_amount) as total_gross,
                SUM(comp_cost_diff) as total_cost, COUNT(DISTINCT employee_code) as emp_count
                FROM employee_bonuses WHERE year=? AND approval_status IN ('Approved','Paid')
                GROUP BY department ORDER BY total_cost DESC''', (year,)).fetchall()
        if data:
            df = pd.DataFrame([dict(d) for d in data])
            st.dataframe(df, use_container_width=True)

    elif report_type == "Sponsor Bonus Report":
        with get_db() as db:
            data = db.execute('''SELECT sponsor as sponsor_name, year,
                SUM(net_bonus_amount) as total_net, SUM(gross_bonus_amount) as total_gross,
                SUM(comp_cost_diff) as total_cost, COUNT(DISTINCT employee_code) as emp_count
                FROM employee_bonuses WHERE year=? AND approval_status IN ('Approved','Paid')
                GROUP BY sponsor ORDER BY total_cost DESC''', (year,)).fetchall()
        if data:
            df = pd.DataFrame([dict(d) for d in data])
            st.dataframe(df, use_container_width=True)

    elif report_type == "Bonus Cost Analysis":
        with get_db() as db:
            data = db.execute('''SELECT employee_code, arabic_name, year, bonus_type, bonus_category,
                net_bonus_amount, gross_bonus_amount, tax_diff, emp_ins_diff, comp_ins_diff, comp_cost_diff
                FROM employee_bonuses WHERE year=? AND approval_status IN ('Approved','Paid')
                ORDER BY comp_cost_diff DESC''', (year,)).fetchall()
        if data:
            rows = []
            for d in data:
                r = dict(d)
                r['cost_multiplier'] = round(r['comp_cost_diff'] / r['net_bonus_amount'], 4) if r['net_bonus_amount'] > 0 else 0
                rows.append(r)
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)

    elif report_type == "Pending / Unpaid Bonus Report":
        with get_db() as db:
            data = db.execute('''SELECT employee_code, arabic_name, department, default_project,
                bonus_date, bonus_amount_entered, payment_status, approval_status, reason, created_at
                FROM employee_bonuses WHERE payment_status IN ('Planned','Hold') OR approval_status='Draft'
                ORDER BY created_at DESC''').fetchall()
        if data:
            df = pd.DataFrame([dict(d) for d in data])
            st.dataframe(df, use_container_width=True)

    if not data:
        st.info("No bonus data for the selected criteria.")
