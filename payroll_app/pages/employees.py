import streamlit as st
import pandas as pd
from datetime import datetime
from ..database import get_db, add_audit_log
from ..auth import check_permission, can_view_salary
from ..services import calculate_payroll_for_employee, get_employee_allocations_summary
from ..ui import page_header, fmt_currency, status_badge, divider, footer, apply_custom_css

def show():
    apply_custom_css()
    tabs = st.tabs(["Employees", "Employee Allowances", "Project Allocation", "Salary Revisions", "Documents"])

    with tabs[0]:
        show_employees()
    with tabs[1]:
        show_allowances()
    with tabs[2]:
        show_allocation()
    with tabs[3]:
        show_salary_revisions()
    with tabs[4]:
        show_documents()

def show_employees():
    page_header("Employees", "Manage employee master data")
    show_salary = can_view_salary()

    with get_db() as db:
        sponsors = [r['name'] for r in db.execute("SELECT name FROM sponsors WHERE status='Active'").fetchall()]
        departments = [r['name'] for r in db.execute("SELECT name FROM departments WHERE status='Active'").fetchall()]
        sections = [r['name'] for r in db.execute("SELECT name FROM sections WHERE status='Active'").fetchall()]
        positions = [r['name'] for r in db.execute("SELECT name FROM positions WHERE status='Active'").fetchall()]
        projects = [r['project_code'] for r in db.execute("SELECT project_code FROM projects WHERE status='Active'").fetchall()]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        search = st.text_input("Search by name/code", key="emp_search")
    with col2:
        dept_filter = st.selectbox("Department", ["All"] + departments, key="emp_dept")
    with col3:
        proj_filter = st.selectbox("Project", ["All"] + projects, key="emp_proj")
    with col4:
        status_filter = st.selectbox("Status", ["All", "Active", "Inactive"], key="emp_status")

    query = "SELECT * FROM employees WHERE 1=1"
    params = []
    if search:
        query += " AND (arabic_name LIKE ? OR employee_code LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if dept_filter != "All":
        query += " AND department=?"
        params.append(dept_filter)
    if proj_filter != "All":
        query += " AND default_project=?"
        params.append(proj_filter)
    if status_filter != "All":
        query += " AND status=?"
        params.append(status_filter)
    query += " ORDER BY employee_code"

    with get_db() as db:
        employees = db.execute(query, params).fetchall()

    if 'show_new_emp' not in st.session_state:
        st.session_state.show_new_emp = False

    if st.button("➕ Add Employee"):
        st.session_state.show_new_emp = True

    if st.session_state.show_new_emp:
        show_employee_form(None)
    elif employees:
        data = []
        for e in employees:
            d = dict(e)
            d['status_badge'] = status_badge(d['status'])
            if show_salary:
                d['new_net_salary'] = fmt_currency(d['new_net_salary'])
                d['new_allowance'] = fmt_currency(d['new_allowance'])
                d['new_net_earning'] = fmt_currency(d['new_net_earning'])
            else:
                d['new_net_salary'] = "Restricted"
                d['new_allowance'] = "Restricted"
                d['new_net_earning'] = "Restricted"
            data.append(d)

        df = pd.DataFrame(data)
        cols = ['employee_code', 'arabic_name', 'position', 'department', 'section',
                'default_project', 'sponsor', 'new_net_salary', 'new_allowance', 'new_net_earning', 'status']
        col_labels = {
            'employee_code': 'Code', 'arabic_name': 'Arabic Name', 'position': 'Position',
            'department': 'Department', 'section': 'Section', 'default_project': 'Default Project',
            'sponsor': 'Sponsor', 'new_net_salary': 'Base Net Salary',
            'new_allowance': 'Active Allowances', 'new_net_earning': 'Total Net Earning',
            'status': 'Status'
        }
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)

        for e in employees:
            e = dict(e)
            with st.expander(f"✏️ {e['arabic_name']} ({e['employee_code']})"):
                show_employee_form(e)
    else:
        st.info("No employees found.")

def show_employee_form(emp):
    with get_db() as db:
        sponsors = [r['name'] for r in db.execute("SELECT name FROM sponsors WHERE status='Active'").fetchall()]
        departments = [r['name'] for r in db.execute("SELECT name FROM departments WHERE status='Active'").fetchall()]
        sections = [r['name'] for r in db.execute("SELECT name FROM sections WHERE status='Active'").fetchall()]
        positions = [r['name'] for r in db.execute("SELECT name FROM positions WHERE status='Active'").fetchall()]
        projects = [r['project_code'] for r in db.execute("SELECT project_code FROM projects WHERE status='Active'").fetchall()]

    with st.form(key=f"emp_form_{emp['employee_code'] if emp else 'new'}"):
        c1, c2 = st.columns(2)
        with c1:
            code = st.text_input("Employee Code", value=emp['employee_code'] if emp else "", disabled=bool(emp))
            arabic = st.text_input("Arabic Name", value=emp['arabic_name'] if emp else "")
            english = st.text_input("English Name", value=emp.get('english_name', '') if emp else "")
            pos = st.selectbox("Position", positions, index=positions.index(emp['position']) if emp and emp['position'] in positions else 0)
        with c2:
            org = st.text_input("Organization", value=emp['organization'] if emp else "AFM")
            sponsor = st.selectbox("Sponsor", sponsors, index=sponsors.index(emp['sponsor']) if emp and emp['sponsor'] in sponsors else 0)
            dept = st.selectbox("Department", departments, index=departments.index(emp['department']) if emp and emp['department'] in departments else 0)
            section = st.selectbox("Section", sections, index=sections.index(emp['section']) if emp and emp['section'] in sections else 0)

        c1, c2 = st.columns(2)
        with c1:
            default_proj = st.selectbox("Default Project", projects, index=projects.index(emp['default_project']) if emp and emp['default_project'] in projects else 0)
            hire_date = st.text_input("Hiring Date (DD-Mon-YY)", value=emp['hiring_date'] if emp else "")
            basic_salary = st.number_input("Basic Salary", min_value=0.0, value=float(emp['basic_salary'] or 0) if emp else 0.0, step=100.0)
        with c2:
            new_net = st.number_input("Base Net Salary", min_value=0.0, value=float(emp['new_net_salary'] or 0) if emp else 0.0, step=100.0)
            new_allow = st.number_input("Active Allowances (Total)", min_value=0.0, value=float(emp['new_allowance'] or 0) if emp else 0.0, step=10.0)
            ins_base = st.number_input("Insurance Salary/Base", min_value=0.0, value=float(emp['insurance_salary_base'] or 0) if emp else 0.0, step=100.0)
            status = st.selectbox("Status", ['Active', 'Inactive'], index=0 if not emp or emp['status'] == 'Active' else 1)

        c1, c2 = st.columns(2)
        with c1:
            bank_name = st.text_input("Bank Name", value=emp['bank_name'] if emp else "")
            bank_account = st.text_input("Bank Account / IBAN", value=emp['bank_account'] if emp else "")
        with c2:
            notes = st.text_area("Notes", value=emp['notes'] if emp else "")

        submitted = st.form_submit_button("💾 Save Employee")
        if submitted:
            if not code or not arabic:
                st.error("Employee Code and Arabic Name are required.")
                return
            new_earning = new_net + new_allow
            with get_db() as db:
                username = st.session_state.get('user', {}).get('username', 'system')
                if emp:
                    db.execute('''UPDATE employees SET organization=?, sponsor=?, arabic_name=?, english_name=?,
                        position=?, department=?, section=?, default_project=?, hiring_date=?, basic_salary=?,
                        new_net_salary=?, new_allowance=?, new_net_earning=?, insurance_salary_base=?,
                        bank_name=?, bank_account=?, status=?, notes=?,
                        updated_at=datetime('now','localtime') WHERE employee_code=?''',
                               (org, sponsor, arabic, english, pos, dept, section, default_proj, hire_date,
                                basic_salary, new_net, new_allow, new_earning, ins_base, bank_name, bank_account,
                                status, notes, code))
                    add_audit_log(db, 'Updated', 'Employee', 'employees', code,
                                  username=username, reason='Employee details updated')
                    st.success(f"Employee {code} updated.")
                else:
                    try:
                        db.execute('''INSERT INTO employees (employee_code, organization, sponsor, arabic_name, english_name,
                            position, department, section, default_project, hiring_date, basic_salary,
                            new_net_salary, new_allowance, new_net_earning, insurance_salary_base,
                            bank_name, bank_account, status, notes)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                                   (code, org, sponsor, arabic, english, pos, dept, section, default_proj, hire_date,
                                    basic_salary, new_net, new_allow, new_earning, ins_base, bank_name, bank_account,
                                    status, notes))

                        exists = db.execute("SELECT id FROM employee_project_allocations WHERE employee_code=? AND project_code=?",
                                            (code, default_proj)).fetchone()
                        if not exists:
                            db.execute('''INSERT INTO employee_project_allocations (employee_code, project_code, allocation_type, percentage, is_primary, status)
                                VALUES (?,?,'Percentage',100,1,'Active')''', (code, default_proj))

                        if new_allow > 0:
                            existing_a = db.execute("SELECT id FROM employee_allowances WHERE employee_code=? AND amount=? AND recurring='Monthly' AND status='Active'",
                                                    (code, new_allow)).fetchone()
                            if not existing_a:
                                db.execute('''INSERT INTO employee_allowances (employee_code, allowance_type, allowance_name, amount, calc_type,
                                    payment_type, taxable, insurance_applicable, recurring, status)
                                    VALUES (?, 'Housing Allowance', 'Housing Allowance', ?, 'Fixed Amount', 'Net', 'Yes', 'No', 'Monthly', 'Active')''',
                                           (code, new_allow))

                        add_audit_log(db, 'Created', 'Employee', 'employees', code,
                                      username=username, reason='Employee created')
                        st.success(f"Employee {code} added.")
                        st.session_state.show_new_emp = False
                    except Exception as ex:
                        st.error(f"Error: {ex}")
            st.rerun()

def show_allowances():
    page_header("Employee Allowances", "Manage employee allowances")
    if not check_permission('Employee Allowances', 'View Only'):
        st.error("Access denied."); return

    with get_db() as db:
        employees = db.execute("SELECT employee_code, arabic_name FROM employees WHERE status='Active' ORDER BY employee_code").fetchall()
        emp_options = {f"{e['employee_code']} - {e['arabic_name']}": e['employee_code'] for e in employees}
        allowance_types = [r['name'] for r in db.execute("SELECT name FROM allowance_types WHERE status='Active'").fetchall()]

    emp_sel = st.selectbox("Employee", ["All"] + list(emp_options.keys()), key="allow_emp")
    atype_filter = st.selectbox("Allowance Type", ["All"] + allowance_types, key="allow_type")

    query = "SELECT ea.*, e.arabic_name FROM employee_allowances ea JOIN employees e ON ea.employee_code=e.employee_code WHERE 1=1"
    params = []
    if emp_sel != "All":
        query += " AND ea.employee_code=?"
        params.append(emp_options[emp_sel])
    if atype_filter != "All":
        query += " AND ea.allowance_type=?"
        params.append(atype_filter)
    query += " ORDER BY ea.id DESC"

    with get_db() as db:
        allowances = db.execute(query, params).fetchall()

    if st.button("➕ Add Allowance"):
        show_allowance_form(None, emp_options, allowance_types)

    if allowances:
        df = pd.DataFrame([dict(a) for a in allowances])
        cols = ['employee_code', 'allowance_name', 'amount', 'payment_type', 'recurring', 'taxable', 'status']
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)

        for a in allowances:
            a = dict(a)
            with st.expander(f"✏️ {a['allowance_name']} - {a['arabic_name']} (E£{a['amount']:,.2f})"):
                show_allowance_form(a, emp_options, allowance_types)
    else:
        st.info("No allowances found.")

def show_allowance_form(allow, emp_options, allowance_types):
    with st.form(key=f"allow_form_{allow['id'] if allow else 'new'}"):
        c1, c2 = st.columns(2)
        with c1:
            emp_code = st.selectbox("Employee", list(emp_options.keys()),
                                    index=list(emp_options.values()).index(allow['employee_code']) if allow and allow['employee_code'] in emp_options.values() else 0) if not allow else f"{allow['employee_code']} - {allow.get('arabic_name','')}"
            if allow:
                emp_code_key = allow['employee_code']
            else:
                emp_code_key = emp_options.get(emp_code, '')
            atype = st.selectbox("Allowance Type", allowance_types,
                                 index=allowance_types.index(allow['allowance_type']) if allow and allow['allowance_type'] in allowance_types else 0)
            amount = st.number_input("Amount", min_value=0.0, value=float(allow['amount']) if allow else 0.0, step=10.0)
        with c2:
            payment_type = st.selectbox("Payment Type", ['Net', 'Gross'],
                                        index=0 if not allow or allow['payment_type'] == 'Net' else 1)
            recurring = st.selectbox("Recurring", ['Monthly', 'One Time', 'Temporary'],
                                     index=['Monthly', 'One Time', 'Temporary'].index(allow['recurring']) if allow and allow['recurring'] in ['Monthly', 'One Time', 'Temporary'] else 0)
            taxable = st.selectbox("Taxable", ['Yes', 'No'], index=0 if not allow or allow['taxable'] == 'Yes' else 1)
            status = st.selectbox("Status", ['Active', 'Inactive'], index=0 if not allow or allow['status'] == 'Active' else 1)

        submitted = st.form_submit_button("💾 Save Allowance")
        if submitted:
            with get_db() as db:
                if allow:
                    db.execute('''UPDATE employee_allowances SET allowance_type=?, amount=?, payment_type=?, taxable=?, recurring=?, status=? WHERE id=?''',
                               (atype, amount, payment_type, taxable, recurring, status, allow['id']))
                else:
                    actual_code = emp_options.get(emp_code, '') if not allow else allow['employee_code']
                    db.execute('''INSERT INTO employee_allowances (employee_code, allowance_type, allowance_name, amount, calc_type, payment_type, taxable, insurance_applicable, recurring, status)
                        VALUES (?,?,?,?,'Fixed Amount',?,?,'No',?,'Active')''',
                               (actual_code, atype, atype, amount, payment_type, taxable, recurring))
            st.success("Allowance updated." if allow else "Allowance added.")
            st.rerun()

def show_allocation():
    page_header("Project Allocation", "Manage employee project allocations")
    if not check_permission('Employee Project Allocation', 'View Only'):
        st.error("Access denied."); return

    with get_db() as db:
        employees = db.execute("SELECT employee_code, arabic_name FROM employees WHERE status='Active' ORDER BY employee_code").fetchall()
        projects = [r['project_code'] for r in db.execute("SELECT project_code FROM projects WHERE status='Active'").fetchall()]

    emp_sel = st.selectbox("Employee", [f"{e['employee_code']} - {e['arabic_name']}" for e in employees], key="alloc_emp")

    if emp_sel:
        emp_code = emp_sel.split(" - ")[0]
        with get_db() as db:
            allocs = db.execute("SELECT * FROM employee_project_allocations WHERE employee_code=? ORDER BY is_primary DESC", (emp_code,)).fetchall()

        if st.button("➕ Add Allocation"):
            show_allocation_form(None, emp_code, projects)

        if allocs:
            df = pd.DataFrame([dict(a) for a in allocs])
            st.dataframe(df[['project_code', 'allocation_type', 'percentage', 'status']], use_container_width=True)

            for a in allocs:
                a = dict(a)
                with st.expander(f"✏️ {a['project_code']} - {a['percentage']}%"):
                    show_allocation_form(a, emp_code, projects)

            total_pct = sum(a['percentage'] for a in allocs if a['status'] == 'Active' and a['allocation_type'] == 'Percentage')
            if total_pct != 100:
                st.warning(f"⚠️ Total active allocation percentage: {total_pct}%. Should be 100%.")
            else:
                st.success(f"✅ Total allocation: {total_pct}%")
        else:
            st.info("No allocations. Employee will use 100% default project.")

def show_allocation_form(alloc, emp_code, projects):
    with st.form(key=f"alloc_form_{alloc['id'] if alloc else 'new'}"):
        proj = st.selectbox("Project", projects,
                            index=projects.index(alloc['project_code']) if alloc and alloc['project_code'] in projects else 0)
        pct = st.number_input("Allocation %", min_value=0.0, max_value=100.0,
                              value=float(alloc['percentage']) if alloc else 0.0, step=5.0)
        is_primary = st.checkbox("Primary Project", value=bool(alloc['is_primary']) if alloc else False)
        status = st.selectbox("Status", ['Active', 'Inactive'],
                              index=0 if not alloc or alloc['status'] == 'Active' else 1)
        submitted = st.form_submit_button("💾 Save")
        if submitted:
            with get_db() as db:
                if alloc:
                    db.execute('''UPDATE employee_project_allocations SET project_code=?, percentage=?, is_primary=?, status=? WHERE id=?''',
                               (proj, pct, int(is_primary), status, alloc['id']))
                else:
                    db.execute('''INSERT INTO employee_project_allocations (employee_code, project_code, percentage, is_primary, status)
                        VALUES (?,?,?,?, 'Active')''', (emp_code, proj, pct, int(is_primary)))
            st.success("Allocation saved.")
            st.rerun()

def show_salary_revisions():
    page_header("Salary Revisions", "Employee salary change history")
    if not check_permission('Employees', 'View Only'):
        st.error("Access denied."); return

    with get_db() as db:
        employees = db.execute("SELECT employee_code, arabic_name FROM employees WHERE status='Active' ORDER BY employee_code").fetchall()
        revisions = db.execute('''SELECT sr.*, e.arabic_name FROM salary_revisions sr
            JOIN employees e ON sr.employee_code=e.employee_code ORDER BY sr.created_at DESC''').fetchall()

    if st.button("➕ New Salary Revision"):
        show_revision_form(None, employees)

    if revisions:
        df = pd.DataFrame([dict(r) for r in revisions])
        cols = ['employee_code', 'arabic_name', 'old_net', 'new_net', 'net_diff', 'revision_type', 'effective_from', 'approval_status']
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)

        for r in revisions:
            r = dict(r)
            with st.expander(f"✏️ {r['arabic_name']} - {r['revision_type']} ({fmt_currency(r['net_diff'])})"):
                show_revision_form(r, employees)
    else:
        st.info("No salary revisions yet.")

def show_revision_form(rev, employees):
    emp_options = {f"{e['employee_code']} - {e['arabic_name']}": e['employee_code'] for e in employees}
    with st.form(key=f"rev_form_{rev['id'] if rev else 'new'}"):
        emp_sel = st.selectbox("Employee", list(emp_options.keys()),
                               index=list(emp_options.values()).index(rev['employee_code']) if rev and rev['employee_code'] in emp_options.values() else 0)
        c1, c2 = st.columns(2)
        with c1:
            old_net = st.number_input("Old Net Salary", value=float(rev['old_net']) if rev else 0.0, step=100.0)
            new_net = st.number_input("New Net Salary", value=float(rev['new_net']) if rev else 0.0, step=100.0)
            old_basic = st.number_input("Old Basic Salary", value=float(rev['old_basic']) if rev else 0.0, step=100.0)
            new_basic = st.number_input("New Basic Salary", value=float(rev['new_basic']) if rev else 0.0, step=100.0)
        with c2:
            rev_type = st.selectbox("Revision Type", ['Annual Increase', 'Promotion', 'Market Adjustment', 'Correction', 'Contract Change', 'Other'],
                                    index=['Annual Increase', 'Promotion', 'Market Adjustment', 'Correction', 'Contract Change', 'Other'].index(rev['revision_type']) if rev and rev['revision_type'] in ['Annual Increase', 'Promotion', 'Market Adjustment', 'Correction', 'Contract Change', 'Other'] else 0)
            effective = st.text_input("Effective From (DD-Mon-YY)", value=rev['effective_from'] if rev else "")
            reason = st.text_area("Reason", value=rev['reason'] if rev else "")
        submitted = st.form_submit_button("💾 Save Revision")
        if submitted:
            actual_code = emp_options[emp_sel]
            with get_db() as db:
                emp = db.execute("SELECT * FROM employees WHERE employee_code=?", (actual_code,)).fetchone()
                if not emp:
                    st.error("Employee not found"); return
                emp = dict(emp)
                net_diff = new_net - old_net
                if rev:
                    db.execute('''UPDATE salary_revisions SET old_net=?, new_net=?, old_basic=?, new_basic=?,
                        revision_type=?, effective_from=?, reason=? WHERE id=?''',
                               (old_net, new_net, old_basic, new_basic, rev_type, effective, reason, rev['id']))
                else:
                    old_allowance = emp.get('new_allowance', 0) or 0
                    new_allowance = old_allowance
                    old_net_earning = old_net + old_allowance
                    new_net_earning = new_net + new_allowance
                    db.execute('''INSERT INTO salary_revisions (employee_code, arabic_name, department, section, project,
                        old_basic, new_basic, old_net, new_net, old_allowance, new_allowance,
                        old_net_earning, new_net_earning, net_diff, revision_type, reason, effective_from, approval_status)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Draft')''',
                               (actual_code, emp['arabic_name'], emp['department'], emp['section'],
                                emp['default_project'], old_basic, new_basic, old_net, new_net,
                                old_allowance, new_allowance, old_net_earning, new_net_earning,
                                net_diff, rev_type, reason, effective))
                    db.execute('''UPDATE employees SET new_net_salary=?, new_allowance=?, new_net_earning=?, 
                        basic_salary=?, updated_at=datetime('now','localtime') WHERE employee_code=?''',
                               (new_net, new_allowance, new_net_earning, new_basic, actual_code))
            st.success("Salary revision saved.")
            st.rerun()

def show_documents():
    page_header("Employee Documents", "Manage employee documents")
    with get_db() as db:
        employees = db.execute("SELECT employee_code, arabic_name FROM employees WHERE status='Active' ORDER BY employee_code").fetchall()
        documents = db.execute('''SELECT ed.*, e.arabic_name FROM employee_documents ed
            JOIN employees e ON ed.employee_code=e.employee_code ORDER BY ed.id DESC''').fetchall()

    emp_sel = st.selectbox("Employee", [f"{e['employee_code']} - {e['arabic_name']}" for e in employees] if employees else [""], key="doc_emp")
    if st.button("➕ Add Document"):
        if emp_sel:
            emp_code = emp_sel.split(" - ")[0]
            with st.form("doc_form"):
                doc_type = st.selectbox("Document Type", ['Contract', 'National ID', 'Insurance Form', 'Work Permit', 'Bank Letter', 'Medical Certificate', 'Other'])
                file_name = st.text_input("File Name")
                expiry = st.text_input("Expiry Date")
                submitted = st.form_submit_button("Save")
                if submitted:
                    with get_db() as db:
                        db.execute("INSERT INTO employee_documents (employee_code, doc_type, file_name, expiry_date, uploaded_by, status) VALUES (?,?,?,?,?,'Valid')",
                                   (emp_code, doc_type, file_name, expiry, st.session_state.get('user', {}).get('username', 'system')))
                    st.success("Document added.")
            if emp is None:
                st.session_state.show_new_emp = False
            st.rerun()

    if documents:
        df = pd.DataFrame([dict(d) for d in documents])
        cols = ['employee_code', 'arabic_name', 'doc_type', 'file_name', 'expiry_date', 'status']
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)
    else:
        st.info("No documents.")
