import streamlit as st
import pandas as pd
import os
import json
import shutil
from datetime import datetime
from ..database import get_db, DB_PATH
from ..auth import check_permission
from ..services import generate_payroll
from ..ui import page_header, fmt_currency, status_badge, divider, footer, apply_custom_css, export_download_link

def show():
    apply_custom_css()
    page_header("Tools & Utilities", "Import, export, backup, and system tools")

    tabs = st.tabs(["Import / Export", "Backup & Restore", "Data Quality Center", "Alerts Center", "Scenario Simulation"])

    with tabs[0]:
        show_import_export()
    with tabs[1]:
        show_backup()
    with tabs[2]:
        show_data_quality()
    with tabs[3]:
        show_alerts()
    with tabs[4]:
        show_simulation()

def show_import_export():
    if not check_permission('Import / Export', 'View Only'):
        st.error("Access denied."); return

    st.subheader("Import Data")
    import_type = st.selectbox("Import Type", ["Employees", "Allowances", "Project Allocations", "Bonuses", "Salary Revisions"])

    uploaded_file = st.file_uploader("Choose Excel/CSV file", type=['xlsx', 'csv'], key="import_file")

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.dataframe(df.head(), use_container_width=True)

            if st.button("📥 Validate & Import"):
                with get_db() as db:
                    imported = 0
                    errors = []
                    for _, row in df.iterrows():
                        try:
                            if import_type == "Employees":
                                code = str(row.get('employee_code', row.get('Employee Code', '')))
                                if code:
                                    existing = db.execute("SELECT employee_id FROM employees WHERE employee_code=?", (code,)).fetchone()
                                    if existing:
                                        db.execute('''UPDATE employees SET arabic_name=?, position=?, department=?, section=?,
                                            default_project=?, new_net_salary=?, new_allowance=?, status='Active',
                                            updated_at=datetime('now','localtime') WHERE employee_code=?''',
                                                   (str(row.get('arabic_name', row.get('Arabic Name', ''))),
                                                    str(row.get('position', row.get('Position', ''))),
                                                    str(row.get('department', row.get('Department', ''))),
                                                    str(row.get('section', row.get('Section', ''))),
                                                    str(row.get('default_project', row.get('Default Project', ''))),
                                                    float(row.get('new_net_salary', row.get('New Net Salary', 0)) or 0),
                                                    float(row.get('new_allowance', row.get('New Allowance', 0)) or 0),
                                                    code))
                                    else:
                                        db.execute('''INSERT INTO employees (employee_code, arabic_name, position, department, section,
                                            default_project, new_net_salary, new_allowance, status)
                                            VALUES (?,?,?,?,?,?,?,?,'Active')''',
                                                   (code, str(row.get('arabic_name', row.get('Arabic Name', ''))),
                                                    str(row.get('position', row.get('Position', ''))),
                                                    str(row.get('department', row.get('Department', ''))),
                                                    str(row.get('section', row.get('Section', ''))),
                                                    str(row.get('default_project', row.get('Default Project', ''))),
                                                    float(row.get('new_net_salary', row.get('New Net Salary', 0)) or 0),
                                                    float(row.get('new_allowance', row.get('New Allowance', 0)) or 0)))
                            elif import_type == "Allowances":
                                emp_code = str(row.get('employee_code', row.get('Employee Code', '')))
                                amount = float(row.get('amount', row.get('Amount', 0)) or 0)
                                atype = str(row.get('allowance_type', row.get('Allowance Type', 'Other')))
                                if emp_code and amount > 0:
                                    db.execute('''INSERT INTO employee_allowances (employee_code, allowance_type, allowance_name, amount,
                                        calc_type, payment_type, taxable, insurance_applicable, recurring, status)
                                        VALUES (?,?,?,?,'Fixed Amount','Net','Yes','No','Monthly','Active')''',
                                               (emp_code, atype, atype, amount))
                            imported += 1
                        except Exception as e:
                            errors.append(f"Row {_+2}: {e}")
                    st.success(f"Imported {imported} records.")
                    if errors:
                        for e in errors[:5]:
                            st.warning(e)
                    st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")

    st.subheader("Download Templates")
    if st.button("📄 Download Employees Template"):
        template = pd.DataFrame({
            'employee_code': ['EX001'],
            'arabic_name': ['Example Name'],
            'position': ['Position'],
            'department': ['Department'],
            'section': ['Section'],
            'default_project': ['Project'],
            'new_net_salary': [5000.0],
            'new_allowance': [0.0],
        })
        export_download_link(template, "employees_template.xlsx", "Download Template")

    st.subheader("Export All Data")
    if st.button("📤 Export All Data"):
        try:
            import io
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                with get_db() as db:
                    tables = ['employees', 'employee_allowances', 'employee_project_allocations', 'payroll_transactions',
                              'payroll_project_allocations', 'employee_bonuses', 'salary_revisions', 'projects',
                              'tax_laws', 'tax_brackets', 'tax_exemptions', 'social_insurance_setup', 'users',
                              'allowance_types', 'audit_log']
                    for table in tables:
                        try:
                            data = db.execute(f"SELECT * FROM {table}").fetchall()
                            if data:
                                df = pd.DataFrame([dict(r) for r in data])
                                df.to_excel(writer, sheet_name=table[:31], index=False)
                        except:
                            pass
            output.seek(0)
            st.download_button("📥 Download Full Export", data=output, file_name=f"payroll_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            st.success("Export generated.")
        except Exception as e:
            st.error(f"Export error: {e}")

def show_backup():
    page_header("Backup & Restore", "Database backup and restoration")
    if not check_permission('Payroll Setup', 'Edit'):
        st.error("Access denied."); return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Create Backup")
        backup_name = st.text_input("Backup Name", value=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if st.button("💾 Create Backup"):
            try:
                from ..config import BACKUP_DIR
                backup_path = os.path.join(BACKUP_DIR, f"{backup_name}.db")
                shutil.copy2(DB_PATH, backup_path)
                file_size = os.path.getsize(backup_path)
                with get_db() as db:
                    db.execute("INSERT INTO backups (backup_name, backup_type, file_path, file_size, created_by) VALUES (?,?,?,?,?)",
                               (backup_name, 'Manual', backup_path, file_size, st.session_state.get('user',{}).get('username','system')))
                st.success(f"Backup created: {backup_name} ({file_size/1024:.1f} KB)")

                import io
                data_export = io.BytesIO()
                with pd.ExcelWriter(data_export, engine='openpyxl') as writer:
                    for table in ['employees', 'payroll_transactions', 'employee_allowances', 'employee_bonuses']:
                        try:
                            rows = db.execute(f"SELECT * FROM {table}").fetchall()
                            if rows:
                                pd.DataFrame([dict(r) for r in rows]).to_excel(writer, sheet_name=table[:31], index=False)
                        except:
                            pass
                data_export.seek(0)
                st.download_button("📥 Download Excel Backup", data=data_export,
                                   file_name=f"{backup_name}.xlsx",
                                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            except Exception as e:
                st.error(f"Backup error: {e}")

    with col2:
        st.subheader("Restore Backup")
        from ..config import BACKUP_DIR
        backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')] if os.path.exists(BACKUP_DIR) else []
        if backups:
            selected_backup = st.selectbox("Select Backup", backups)
            if st.button("⚠️ Restore Database", type="secondary"):
                if st.checkbox("I confirm this will overwrite the current database"):
                    try:
                        backup_path = os.path.join(BACKUP_DIR, selected_backup)
                        shutil.copy2(backup_path, DB_PATH)
                        st.success("Database restored successfully. Please restart the app.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Restore error: {e}")
        else:
            st.info("No backups available.")

    with get_db() as db:
        history = db.execute("SELECT * FROM backups ORDER BY created_at DESC LIMIT 10").fetchall()
    if history:
        st.subheader("Backup History")
        st.dataframe(pd.DataFrame([dict(h) for h in history]), use_container_width=True)

def show_data_quality():
    page_header("Data Quality Center", "Check for data quality issues")

    issues = []

    with get_db() as db:
        missing_hire = db.execute("SELECT COUNT(*) FROM employees WHERE (hiring_date IS NULL OR hiring_date='') AND status='Active'").fetchone()[0]
        if missing_hire:
            issues.append({"Issue": "Missing Hiring Date", "Count": missing_hire, "Severity": "Warning"})

        missing_dept = db.execute("SELECT COUNT(*) FROM employees WHERE (department IS NULL OR department='') AND status='Active'").fetchone()[0]
        if missing_dept:
            issues.append({"Issue": "Missing Department", "Count": missing_dept, "Severity": "Warning"})

        missing_project = db.execute("SELECT COUNT(*) FROM employees WHERE (default_project IS NULL OR default_project='') AND status='Active'").fetchone()[0]
        if missing_project:
            issues.append({"Issue": "Missing Default Project", "Count": missing_project, "Severity": "Critical"})

        no_salary = db.execute("SELECT COUNT(*) FROM employees WHERE (new_net_salary IS NULL OR new_net_salary=0) AND status='Active'").fetchone()[0]
        if no_salary:
            issues.append({"Issue": "Active Employee Without Salary", "Count": no_salary, "Severity": "Critical"})

        no_bank = db.execute("SELECT COUNT(*) FROM employees WHERE (bank_account IS NULL OR bank_account='') AND status='Active'").fetchone()[0]
        if no_bank:
            issues.append({"Issue": "Missing Bank Account", "Count": no_bank, "Severity": "Warning"})

        bad_alloc = db.execute('''SELECT employee_code FROM employee_project_allocations 
            WHERE status='Active' AND allocation_type='Percentage'
            GROUP BY employee_code HAVING ABS(SUM(percentage) - 100) > 0.01''').fetchall()
        for ba in bad_alloc:
            issues.append({"Issue": f"Allocation not 100% - {ba['employee_code']}", "Count": 1, "Severity": "Critical"})

        neg_salary = db.execute("SELECT COUNT(*) FROM employees WHERE new_net_salary < 0").fetchone()[0]
        if neg_salary:
            issues.append({"Issue": "Negative Salary", "Count": neg_salary, "Severity": "Critical"})

        missing_ins = db.execute("SELECT COUNT(*) FROM social_insurance_setup WHERE status='Active'").fetchone()[0]
        if not missing_ins:
            issues.append({"Issue": "Missing Insurance Setup", "Count": 1, "Severity": "Critical"})

        missing_tax = db.execute("SELECT COUNT(*) FROM tax_laws WHERE status='Active'").fetchone()[0]
        if not missing_tax:
            issues.append({"Issue": "Missing Tax Setup", "Count": 1, "Severity": "Critical"})

    if issues:
        df_issues = pd.DataFrame(issues)
        for _, row in df_issues.iterrows():
            sev = row['Severity']
            icon = "🔴" if sev == "Critical" else ("🟡" if sev == "Warning" else "🔵")
            st.write(f"{icon} **{row['Issue']}** - {int(row['Count'])} record(s)")
        st.subheader("Issues Summary")
        st.dataframe(df_issues, use_container_width=True)
    else:
        st.success("✅ No data quality issues found.")

def show_alerts():
    page_header("Alerts Center", "System alerts and notifications")

    with get_db() as db:
        alerts = db.execute("SELECT * FROM alerts WHERE status='Open' ORDER BY created_at DESC LIMIT 50").fetchall()

    if not alerts:
        with get_db() as db:
            employees = db.execute("SELECT employee_code, arabic_name FROM employees WHERE status='Active'").fetchall()
            for emp in employees:
                e = dict(emp)
                if not db.execute("SELECT id FROM employee_project_allocations WHERE employee_code=? AND status='Active'", (e['employee_code'],)).fetchone():
                    db.execute("INSERT INTO alerts (alert_type, severity, title, message, employee_code, module, status) VALUES (?,?,?,?,?,?,'Open')",
                               ('allocation', 'Warning', 'Employee without project allocation', f"{e['arabic_name']} has no active project allocation.", e['employee_code'], 'Employees'))

            no_bank = db.execute("SELECT employee_code, arabic_name FROM employees WHERE (bank_account IS NULL OR bank_account='') AND status='Active'").fetchall()
            for nb in no_bank:
                nb = dict(nb)
                existing = db.execute("SELECT id FROM alerts WHERE alert_type='bank' AND employee_code=? AND status='Open'", (nb['employee_code'],)).fetchone()
                if not existing:
                    db.execute("INSERT INTO alerts (alert_type, severity, title, message, employee_code, module, status) VALUES (?,?,?,?,?,?,'Open')",
                               ('bank', 'Warning', 'Missing bank account', f"{nb['arabic_name']} has no bank account.", nb['employee_code'], 'Employees'))

            alerts = db.execute("SELECT * FROM alerts WHERE status='Open' ORDER BY created_at DESC LIMIT 50").fetchall()

    if alerts:
        for a in alerts:
            a = dict(a)
            sev_icon = {"Critical": "🔴", "Warning": "🟡", "Info": "🔵"}
            icon = sev_icon.get(a['severity'], "🔵")
            with st.container():
                col1, col2, col3 = st.columns([0.7, 0.2, 0.1])
                with col1:
                    st.write(f"{icon} **{a['title']}** - {a['message']}")
                    st.caption(f"{a['created_at']} | {a['module']}")
                with col2:
                    st.text(f"")
                with col3:
                    if st.button("✓", key=f"res_{a['id']}"):
                        with get_db() as db2:
                            db2.execute("UPDATE alerts SET status='Resolved', resolved_at=datetime('now','localtime'), resolved_by=? WHERE id=?",
                                       (st.session_state.get('user',{}).get('username',''), a['id']))
                        st.rerun()
                st.divider()
    else:
        st.success("✅ No open alerts.")

    st.subheader("Alert Statistics")
    with get_db() as db:
        stats = db.execute("SELECT severity, COUNT(*) as count FROM alerts WHERE status='Open' GROUP BY severity").fetchall()
    if stats:
        st.dataframe(pd.DataFrame([dict(s) for s in stats]), use_container_width=True)

def show_simulation():
    page_header("Scenario Simulation", "Simulate payroll changes before applying")

    scenario_type = st.selectbox("Scenario Type", [
        "Increase All Employees by %",
        "Add Fixed Bonus to Selected",
        "Change Tax Exemption",
        "Change Insurance Setup",
        "Custom Scenario"
    ])

    year = st.selectbox("Year", range(2026, 2019, -1), key="sim_year", index=0)
    month = st.selectbox("Month", range(1, 13), key="sim_month", index=datetime.now().month - 1)

    with get_db() as db:
        current_cost = db.execute("SELECT COALESCE(SUM(total_company_cost),0) FROM payroll_transactions WHERE year=? AND month=?", (year, month)).fetchone()[0]
        current_net = db.execute("SELECT COALESCE(SUM(net_transfer_amount),0) FROM payroll_transactions WHERE year=? AND month=?", (year, month)).fetchone()[0]

    st.metric("Current Total Company Cost", fmt_currency(current_cost))
    st.metric("Current Total Net Payroll", fmt_currency(current_net))

    if scenario_type == "Increase All Employees by %":
        pct = st.slider("Increase Percentage", 0, 100, 10) / 100
        new_cost = current_cost * (1 + pct)
        st.metric("New Estimated Cost", fmt_currency(new_cost))
        st.metric("Cost Difference", fmt_currency(new_cost - current_cost), delta=f"{pct*100:.0f}%")

    elif scenario_type == "Add Fixed Bonus to Selected":
        with get_db() as db:
            employees = db.execute("SELECT employee_code, arabic_name FROM employees WHERE status='Active'").fetchall()
        emp_sel = st.multiselect("Select Employees", [f"{e['employee_code']} - {e['arabic_name']}" for e in employees])
        bonus_amount = st.number_input("Bonus Amount per Employee", 0.0, value=5000.0, step=500.0)
        bonus_type = st.selectbox("Bonus Type", ["Net Bonus", "Gross Bonus"])
        from ..services import calculate_bonus_cost
        total_cost_diff = 0
        for emp_s in emp_sel:
            ec = emp_s.split(" - ")[0]
            result = calculate_bonus_cost(ec, bonus_type, bonus_amount, year, month)
            if result:
                total_cost_diff += result['comp_cost_diff']
        st.metric("Total Bonus Cost Impact", fmt_currency(total_cost_diff))
        st.metric("New Total Company Cost", fmt_currency(current_cost + total_cost_diff))

    elif scenario_type == "Change Tax Exemption":
        new_exemption = st.number_input("New Additional Exemption", 0.0, value=25000.0, step=1000.0)
        st.info(f"Increasing additional exemption from E£20,000 to E£{new_exemption:,.0f} will reduce tax burden.")
        st.metric("Estimated Tax Reduction", "(calculation depends on individual salaries)")

    elif scenario_type == "Change Insurance Setup":
        new_min = st.number_input("New Min Insurance Salary", 0.0, value=3000.0, step=100.0)
        new_max = st.number_input("New Max Insurance Salary", 0.0, value=20000.0, step=500.0)
        st.info(f"This change affects insurance calculations for all employees.")

    if st.button("💾 Save Scenario Report"):
        scenario_data = {
            'type': scenario_type,
            'year': year,
            'month': month,
            'current_cost': current_cost,
            'current_net': current_net,
            'timestamp': datetime.now().isoformat(),
        }
        st.success("Scenario saved.")
        df_sc = pd.DataFrame([scenario_data])
        export_download_link(df_sc, f"scenario_{datetime.now().strftime('%Y%m%d')}.xlsx")
