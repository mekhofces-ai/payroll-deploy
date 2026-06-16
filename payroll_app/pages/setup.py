import streamlit as st
import pandas as pd
import json
from datetime import datetime
from ..database import get_db, add_audit_log
from ..auth import check_permission
from ..config import TAX_LAW_175, TAX_CURRENT, DEFAULT_INSURANCE
from ..ui import page_header, fmt_currency, status_badge, divider, footer, apply_custom_css, export_download_link

def show():
    apply_custom_css()
    page_header("Payroll Setup", "Configure payroll settings and parameters")

    tabs = st.tabs(["Company Setup", "Tax Laws", "Tax Brackets", "Exemptions",
                    "Social Insurance", "Salary & Insurance Rules", "Allowance Types", "Projects", "Organizations"])

    with tabs[0]:
        show_company_setup()
    with tabs[1]:
        show_tax_laws()
    with tabs[2]:
        show_tax_brackets()
    with tabs[3]:
        show_exemptions()
    with tabs[4]:
        show_insurance()
    with tabs[5]:
        show_salary_rules()
    with tabs[6]:
        show_allowance_types()
    with tabs[7]:
        show_projects()
    with tabs[8]:
        show_organizations()

def show_company_setup():
    if not check_permission('Payroll Setup', 'Edit'):
        st.warning("View only mode.")
    with get_db() as db:
        orgs = db.execute("SELECT * FROM organizations").fetchall()

    for org in orgs:
        o = dict(org)
        with st.form(f"org_{o['org_id']}"):
            c1, c2 = st.columns(2)
            with c1:
                code = st.text_input("Code", value=o['code'])
                name = st.text_input("Name", value=o['name'])
                tax_no = st.text_input("Tax Registration No", value=o['tax_reg_no'])
            with c2:
                ins_no = st.text_input("Social Insurance No", value=o['social_insurance_no'])
                address = st.text_input("Address", value=o['address'])
                bank = st.text_input("Bank Account", value=o['bank_account'])
            if st.form_submit_button("💾 Update"):
                with get_db() as db2:
                    db2.execute("UPDATE organizations SET code=?, name=?, tax_reg_no=?, social_insurance_no=?, address=?, bank_account=? WHERE org_id=?",
                               (code, name, tax_no, ins_no, address, bank, o['org_id']))
                st.success("Updated.")

def show_tax_laws():
    if not check_permission('Payroll Setup', 'Edit'):
        st.warning("View only mode.")
    with get_db() as db:
        laws = db.execute("SELECT * FROM tax_laws ORDER BY is_default DESC, id").fetchall()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📜 Apply Law 175/2023 Preset"):
            with get_db() as db:
                law = db.execute("SELECT id FROM tax_laws WHERE name='Egypt Income Tax Law 175/2023'").fetchone()
                if law:
                    db.execute("UPDATE tax_laws SET is_default=0")
                    db.execute("UPDATE tax_laws SET is_default=1 WHERE id=?", (law['id'],))
                    db.execute("DELETE FROM tax_brackets WHERE tax_law_id=?", (law['id'],))
                    for i, b in enumerate(TAX_LAW_175['brackets']):
                        db.execute("INSERT INTO tax_brackets (tax_law_id, year, income_from, income_to, tax_rate, bracket_order, status) VALUES (?,?,?,?,?,?,'Active')",
                                  (law['id'], 2023, b[0], b[1], b[2], i+1))
                    ex = db.execute("SELECT id FROM tax_exemptions WHERE tax_law_id=? AND year=2023", (law['id'],)).fetchone()
                    if ex:
                        db.execute("UPDATE tax_exemptions SET personal_exemption_annual=?, additional_exemption_annual=?, tax_free_bracket_annual=? WHERE id=?",
                                  (TAX_LAW_175['personal_exemption'], TAX_LAW_175['additional_exemption'], TAX_LAW_175['tax_free_bracket'], ex['id']))
                    st.success("Law 175/2023 applied.")
                    st.rerun()
    with col2:
        if st.button("📜 Apply Current Tax 2024/2026 Preset"):
            with get_db() as db:
                law = db.execute("SELECT id FROM tax_laws WHERE name='Egypt Current Income Tax Setup 2024/2026'").fetchone()
                if law:
                    db.execute("UPDATE tax_laws SET is_default=0")
                    db.execute("UPDATE tax_laws SET is_default=1 WHERE id=?", (law['id'],))
                    db.execute("DELETE FROM tax_brackets WHERE tax_law_id=?", (law['id'],))
                    for y in [2024, 2025, 2026]:
                        for i, b in enumerate(TAX_CURRENT['brackets']):
                            db.execute("INSERT INTO tax_brackets (tax_law_id, year, income_from, income_to, tax_rate, bracket_order, status) VALUES (?,?,?,?,?,?,'Active')",
                                      (law['id'], y, b[0], b[1], b[2], i+1))
                    for y in [2024, 2025, 2026]:
                        ex = db.execute("SELECT id FROM tax_exemptions WHERE tax_law_id=? AND year=?", (law['id'], y)).fetchone()
                        if ex:
                            db.execute("UPDATE tax_exemptions SET personal_exemption_annual=?, additional_exemption_annual=?, tax_free_bracket_annual=? WHERE id=?",
                                      (TAX_CURRENT['personal_exemption'], TAX_CURRENT['additional_exemption'], TAX_CURRENT['tax_free_bracket'], ex['id']))
                        else:
                            db.execute("INSERT INTO tax_exemptions (tax_law_id, year, personal_exemption_annual, additional_exemption_annual, tax_free_bracket_annual, total_annual_exemption, round_down_to_10, status) VALUES (?,?,?,?,?,?,1,'Active')",
                                      (law['id'], y, TAX_CURRENT['personal_exemption'], TAX_CURRENT['additional_exemption'], TAX_CURRENT['tax_free_bracket'],
                                       TAX_CURRENT['personal_exemption'] + TAX_CURRENT['additional_exemption'] + TAX_CURRENT['tax_free_bracket']))
                    st.success("Current tax setup applied.")
                    st.rerun()

    st.subheader("Tax Laws")
    for law in laws:
        l = dict(law)
        with st.expander(f"{'⭐ ' if l['is_default'] else ''}{l['name']} ({l['status']})"):
            with st.form(f"law_{l['id']}"):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Name", value=l['name'])
                    law_no = st.text_input("Law Number", value=l['law_number'])
                with c2:
                    eff_from = st.text_input("Effective From", value=l['effective_from'])
                    is_default = st.checkbox("Default Law", value=bool(l['is_default']))
                if st.form_submit_button("Update"):
                    with get_db() as db:
                        if is_default:
                            db.execute("UPDATE tax_laws SET is_default=0")
                        db.execute("UPDATE tax_laws SET name=?, law_number=?, effective_from=?, is_default=? WHERE id=?",
                                  (name, law_no, eff_from, int(is_default), l['id']))
                    add_audit_log(db, 'Updated', 'Setup', 'tax_laws', l['id'],
                                  username=st.session_state.get('user',{}).get('username','system'),
                                  reason=f'Tax law updated: {name}')
                    st.success("Tax law updated.")
                    st.rerun()

    with st.expander("➕ Add Tax Law"):
        with st.form("new_law"):
            name = st.text_input("Name")
            law_no = st.text_input("Law Number")
            eff_from = st.text_input("Effective From")
            if st.form_submit_button("Add"):
                with get_db() as db:
                    db.execute("INSERT INTO tax_laws (name, law_number, effective_from, status) VALUES (?,?,?,'Active')", (name, law_no, eff_from))
                st.success("Tax law added.")
                st.rerun()

def show_tax_brackets():
    if not check_permission('Payroll Setup', 'Edit'):
        st.warning("View only mode.")
    with get_db() as db:
        laws = db.execute("SELECT id, name FROM tax_laws WHERE status='Active'").fetchall()

    law_sel = st.selectbox("Tax Law", [f"{l['id']} - {l['name']}" for l in laws], key="tb_law")
    if law_sel:
        law_id = int(law_sel.split(" - ")[0])
        year = st.selectbox("Year", range(2026, 2019, -1), key="tb_year", index=0)

        with get_db() as db:
            brackets = db.execute("SELECT * FROM tax_brackets WHERE tax_law_id=? AND year=? AND status='Active' ORDER BY bracket_order", (law_id, year)).fetchall()

        st.subheader(f"Tax Brackets ({year})")
        if brackets:
            df = pd.DataFrame([dict(b) for b in brackets])
            st.dataframe(df[['bracket_order', 'income_from', 'income_to', 'tax_rate']], use_container_width=True)

            for b in brackets:
                b = dict(b)
                with st.form(f"bracket_{b['id']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: inc_from = st.number_input("From", value=float(b['income_from']), step=1000.0)
                    with c2: inc_to = st.number_input("To", value=float(b['income_to']) if b['income_to'] < 999999999 else 999999999, step=1000.0)
                    with c3: rate = st.number_input("Rate %", value=float(b['tax_rate'] * 100), step=0.5) / 100
                    with c4: order = st.number_input("Order", value=int(b['bracket_order']))
                    if st.form_submit_button("Update"):
                        with get_db() as db2:
                            db2.execute("UPDATE tax_brackets SET income_from=?, income_to=?, tax_rate=?, bracket_order=? WHERE id=?",
                                       (inc_from, inc_to, rate, order, b['id']))
                            add_audit_log(db2, 'Updated', 'Setup', 'tax_brackets', b['id'],
                                          username=st.session_state.get('user',{}).get('username','system'),
                                          reason=f'Bracket {b["bracket_order"]}: {inc_from}-{inc_to} @ {rate*100:.1f}%')
                        st.success("Bracket updated.")
                        st.rerun()
        else:
            st.info("No brackets for this law/year combination.")

        with st.expander("➕ Add Bracket"):
            with st.form("new_bracket"):
                c1, c2, c3, c4 = st.columns(4)
                with c1: inc_from = st.number_input("From", 0.0, step=1000.0)
                with c2: inc_to = st.number_input("To", 100000.0, step=1000.0)
                with c3: rate = st.number_input("Rate %", 0.0, step=0.5) / 100
                with c4: order = st.number_input("Order", 1, step=1)
                if st.form_submit_button("Add"):
                    with get_db() as db2:
                        db2.execute("INSERT INTO tax_brackets (tax_law_id, year, income_from, income_to, tax_rate, bracket_order, status) VALUES (?,?,?,?,?,?,'Active')",
                                  (law_id, year, inc_from, inc_to, rate, order))
                    st.success("Bracket added.")
                    st.rerun()

def show_exemptions():
    if not check_permission('Payroll Setup', 'Edit'):
        st.warning("View only mode.")
    with get_db() as db:
        exemptions = db.execute('''SELECT e.*, l.name as law_name FROM tax_exemptions e
            JOIN tax_laws l ON e.tax_law_id = l.id ORDER BY e.year DESC, l.name''').fetchall()

    for ex in exemptions:
        e = dict(ex)
        with st.form(f"ex_{e['id']}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.text(f"Law: {e['law_name']}")
                st.text(f"Year: {e['year']}")
                personal = st.number_input("Personal Exemption", value=float(e['personal_exemption_annual'] or 0), step=1000.0)
            with c2:
                additional = st.number_input("Additional Exemption", value=float(e['additional_exemption_annual'] or 0), step=1000.0)
                tax_free = st.number_input("Tax Free Bracket", value=float(e['tax_free_bracket_annual'] or 0), step=1000.0)
            with c3:
                round_down = st.checkbox("Round Down to Nearest 10", value=bool(e['round_down_to_10']))
                total = personal + additional + tax_free
                st.metric("Total Exemption", fmt_currency(total))
            if st.form_submit_button("Update"):
                with get_db() as db2:
                    db2.execute("UPDATE tax_exemptions SET personal_exemption_annual=?, additional_exemption_annual=?, tax_free_bracket_annual=?, total_annual_exemption=?, round_down_to_10=? WHERE id=?",
                               (personal, additional, tax_free, total, int(round_down), e['id']))
                    add_audit_log(db2, 'Updated', 'Setup', 'tax_exemptions', e['id'],
                                  username=st.session_state.get('user',{}).get('username','system'),
                                  reason=f'Exemption year {e["year"]}: personal={personal}')
                st.success("Exemption updated.")
                st.rerun()

def show_insurance():
    page_header("Social Insurance Setup", "Configure social insurance parameters")
    if not check_permission('Payroll Setup', 'Edit'):
        st.warning("View only mode.")

    st.info("Default minimum insurance salary: E£2,600 | Maximum: E£16,700 | Employee Share: 11% | Company Share: 18.75%. Update from setup if official limits change.")

    with get_db() as db:
        setups = db.execute("SELECT * FROM social_insurance_setup ORDER BY year DESC").fetchall()

    for s in setups:
        si = dict(s)
        with st.form(f"si_{si['id']}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.text(f"Year: {si['year']}")
                min_sal = st.number_input("Minimum Insurance Salary", value=float(si['min_insurance_salary']), step=100.0)
                max_sal = st.number_input("Maximum Insurance Salary", value=float(si['max_insurance_salary']), step=100.0)
            with c2:
                emp_share = st.number_input("Employee Share %", value=float(si['employee_share_pct'] * 100), step=0.5) / 100
                comp_share = st.number_input("Company Share %", value=float(si['company_share_pct'] * 100), step=0.5) / 100
            with c3:
                base_source = st.selectbox("Insurance Base Source",
                                           ['Employee Insurance Salary/Base', 'Employee Basic Salary', 'Gross Salary', 'Fixed Manual Amount', 'No Insurance'],
                                           index=['Employee Insurance Salary/Base', 'Employee Basic Salary', 'Gross Salary', 'Fixed Manual Amount', 'No Insurance'].index(si['insurance_base_source']) if si['insurance_base_source'] in ['Employee Insurance Salary/Base', 'Employee Basic Salary', 'Gross Salary', 'Fixed Manual Amount', 'No Insurance'] else 0)
                eff_from = st.text_input("Effective From", value=si['effective_from'])
            if st.form_submit_button("Update"):
                with get_db() as db2:
                    db2.execute("UPDATE social_insurance_setup SET min_insurance_salary=?, max_insurance_salary=?, employee_share_pct=?, company_share_pct=?, insurance_base_source=?, effective_from=? WHERE id=?",
                               (min_sal, max_sal, emp_share, comp_share, base_source, eff_from, si['id']))
                    add_audit_log(db2, 'Updated', 'Setup', 'social_insurance_setup', si['id'],
                                  username=st.session_state.get('user',{}).get('username','system'),
                                  reason=f'Insurance setup year {si["year"]} updated')
                st.success("Insurance setup updated.")
                st.rerun()

def show_salary_rules():
    page_header("Salary & Insurance Calculation Rules", "Configure how basic salary and insurance are calculated")
    if not check_permission('Payroll Setup', 'Edit'):
        st.warning("View only mode.")

    with get_db() as db:
        setup = db.execute("SELECT * FROM salary_calculation_setup WHERE status='Active' LIMIT 1").fetchone()
        ins_setups = db.execute("SELECT * FROM social_insurance_setup ORDER BY year DESC").fetchall()

    if setup:
        s = dict(setup)
        st.info("These rules control how Basic Salary and Insurance Base are calculated during payroll generation. Changes apply to future payroll runs only.")

        with st.form("salary_rules"):
            st.subheader("Basic Salary Source")
            basic_sources = [
                'Manual Basic Salary from Employee Master Data',
                'Equal to Gross Salary excluding allowances',
                'Equal to Gross Salary including allowances',
                'Percentage of Gross Salary',
                'Percentage of Net Salary',
                'Fixed formula from setup',
                'No Basic Salary calculation, use manual only'
            ]
            basic_idx = basic_sources.index(s['basic_salary_source']) if s['basic_salary_source'] in basic_sources else 0
            basic_source = st.selectbox("Basic Salary Source", basic_sources, index=basic_idx,
                help="How should the Basic Salary be determined?")

            pct_visible = basic_source in ['Percentage of Gross Salary', 'Percentage of Net Salary']
            basic_pct = 0
            if pct_visible:
                pct_val = float(s.get('basic_pct', s.get('basic_pct_from_gross', 0)) or 0) * 100
                basic_pct = st.slider("Percentage (%)", 0, 100, int(pct_val), 5,
                                     help="The percentage used to calculate Basic Salary") / 100

            st.divider()
            st.subheader("Insurance Base Source")
            ins_sources = [
                'Manual Insurance Salary/Base from employee',
                'Basic Salary',
                'Gross Salary excluding allowances',
                'Gross Salary including allowances',
                'Net Salary',
                'Net Earning',
                'No Insurance'
            ]
            ins_idx = ins_sources.index(s['insurance_base_source']) if s['insurance_base_source'] in ins_sources else 0
            ins_source = st.selectbox("Insurance Base Source", ins_sources, index=ins_idx,
                help="What amount should be used as the base for social insurance calculation?")

            st.subheader("Insurance Inclusion Rules")
            c1, c2 = st.columns(2)
            with c1:
                inc_taxable = st.selectbox("Include taxable allowances in insurance base",
                    ['No', 'Yes'],
                    index=0 if s.get('include_taxable_allowances_in_insurance', 'No') != 'Yes' else 1)
            with c2:
                inc_gross = st.selectbox("Include gross allowances in insurance base",
                    ['No', 'Yes'],
                    index=0 if s.get('include_gross_allowances_in_insurance', 'No') != 'Yes' else 1)

            st.divider()
            st.subheader("Gross-up Settings")
            c1, c2 = st.columns(2)
            with c1:
                tolerance = st.number_input("Gross-up Tolerance (EGP)", value=float(s['gross_up_tolerance']), step=0.5,
                                           help="Maximum allowed difference between target and calculated net")
            with c2:
                max_iter = st.number_input("Max Iterations", value=int(s['max_iterations']), step=10,
                                          help="Maximum calculation iterations for gross-up convergence")

            st.divider()
            st.subheader("Social Insurance Limits & Rates (by Year)")
            current_ins = ins_setups[0] if ins_setups else None
            if current_ins:
                ci = dict(current_ins)
                st.write(f"**Year: {int(ci['year'])}**")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    min_sal = st.number_input("Min Insurance Salary", value=float(ci['min_insurance_salary']), step=100.0)
                with c2:
                    max_sal = st.number_input("Max Insurance Salary", value=float(ci['max_insurance_salary']), step=100.0)
                with c3:
                    emp_share = st.number_input("Employee Share %", value=float(ci['employee_share_pct'] * 100), step=0.5) / 100
                with c4:
                    comp_share = st.number_input("Company Share %", value=float(ci['company_share_pct'] * 100), step=0.5) / 100

            if st.form_submit_button("💾 Save All Rules"):
                with get_db() as db2:
                    db2.execute('''UPDATE salary_calculation_setup SET 
                        basic_salary_source=?, basic_pct=?, insurance_base_source=?,
                        include_taxable_allowances_in_insurance=?, include_gross_allowances_in_insurance=?,
                        gross_up_tolerance=?, max_iterations=? WHERE id=?''',
                               (basic_source, basic_pct, ins_source, inc_taxable, inc_gross,
                                tolerance, max_iter, s['id']))
                    if current_ins:
                        db2.execute('''UPDATE social_insurance_setup SET 
                            min_insurance_salary=?, max_insurance_salary=?, 
                            employee_share_pct=?, company_share_pct=? WHERE id=?''',
                                   (min_sal, max_sal, emp_share, comp_share, current_ins['id']))
                    add_audit_log(db2, 'Updated', 'Setup', 'salary_calculation_setup', s['id'],
                                  username=st.session_state.get('user',{}).get('username','system'),
                                  reason=f'Salary & insurance rules updated: basic={basic_source}, ins={ins_source}')
                st.success("All rules saved successfully.")
                st.rerun()

def show_allowance_types():
    page_header("Allowance Types", "Manage allowance type definitions")
    if not check_permission('Payroll Setup', 'Edit'):
        st.warning("View only mode.")

    with get_db() as db:
        types = db.execute("SELECT * FROM allowance_types WHERE status='Active' ORDER BY name").fetchall()

    for t in types:
        at = dict(t)
        with st.form(f"at_{at['id']}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("Name", value=at['name'])
            with c2:
                taxable = st.selectbox("Taxable Default", ['Yes', 'No'], index=0 if at['is_taxable_default'] == 'Yes' else 1)
                insurance = st.selectbox("Insurance Default", ['Yes', 'No'], index=0 if at['is_insurance_default'] == 'Yes' else 1)
            with c3:
                payment_type = st.selectbox("Payment Type Default", ['Net', 'Gross'], index=0 if at['payment_type_default'] == 'Net' else 1)
            if st.form_submit_button("Update"):
                with get_db() as db2:
                    db2.execute("UPDATE allowance_types SET is_taxable_default=?, is_insurance_default=?, payment_type_default=? WHERE id=?",
                               (taxable, insurance, payment_type, at['id']))
                st.success("Updated.")
                st.rerun()

    with st.expander("➕ Add Allowance Type"):
        with st.form("new_at"):
            name = st.text_input("Name")
            if st.form_submit_button("Add"):
                with get_db() as db:
                    db.execute("INSERT INTO allowance_types (name, status) VALUES (?,'Active')", (name,))
                st.success("Added.")
                st.rerun()

def show_projects():
    page_header("Projects", "Manage projects")
    if not check_permission('Projects', 'View Only'):
        st.error("Access denied."); return

    with get_db() as db:
        projects = db.execute("SELECT * FROM projects ORDER BY project_code").fetchall()

    if st.button("➕ Add Project"):
        with st.form("new_project"):
            c1, c2 = st.columns(2)
            with c1:
                code = st.text_input("Project Code")
                name = st.text_input("Project Name")
                client = st.text_input("Client Name")
            with c2:
                org = st.text_input("Organization")
                location = st.text_input("Location")
                start_date = st.text_input("Start Date")
            notes = st.text_area("Notes")
            if st.form_submit_button("Save"):
                with get_db() as db2:
                    try:
                        db2.execute("INSERT INTO projects (project_code, project_name, client_name, organization, location, start_date, status, notes) VALUES (?,?,?,?,?,?,'Active',?)",
                                   (code, name, client, org, location, start_date, notes))
                        st.success("Project added.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    if projects:
        df = pd.DataFrame([dict(p) for p in projects])
        st.dataframe(df[['project_code', 'project_name', 'client_name', 'organization', 'status']], use_container_width=True)

        for p in projects:
            p = dict(p)
            with st.expander(f"✏️ {p['project_code']} - {p['project_name']}"):
                with st.form(f"proj_{p['project_id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        name = st.text_input("Name", value=p['project_name'])
                        client = st.text_input("Client", value=p['client_name'])
                    with c2:
                        loc = st.text_input("Location", value=p['location'])
                        status = st.selectbox("Status", ['Active', 'Inactive'], index=0 if p['status'] == 'Active' else 1)
                    if st.form_submit_button("Update"):
                        with get_db() as db2:
                            db2.execute("UPDATE projects SET project_name=?, client_name=?, location=?, status=? WHERE project_id=?",
                                       (name, client, loc, status, p['project_id']))
                        st.success("Updated.")
                        st.rerun()

def show_organizations():
    page_header("Organizations", "Manage organizations")
    with get_db() as db:
        orgs = db.execute("SELECT * FROM organizations WHERE status='Active'").fetchall()
        sponsors = db.execute("SELECT * FROM sponsors WHERE status='Active'").fetchall()
        departments = db.execute("SELECT * FROM departments WHERE status='Active'").fetchall()
        sections = db.execute("SELECT * FROM sections WHERE status='Active'").fetchall()

    tabs = st.tabs(["Organizations", "Sponsors", "Departments", "Sections"])

    with tabs[0]:
        if st.button("➕ Add Organization"):
            with st.form("new_org"):
                code = st.text_input("Code")
                name = st.text_input("Name")
                if st.form_submit_button("Save"):
                    with get_db() as db2:
                        db2.execute("INSERT INTO organizations (code, name, status) VALUES (?,?,'Active')", (code, name))
                    st.success("Added.")
                    st.rerun()
        if orgs:
            st.dataframe(pd.DataFrame([dict(o) for o in orgs]), use_container_width=True)

    with tabs[1]:
        if st.button("➕ Add Sponsor"):
            with st.form("new_sp"):
                name = st.text_input("Name")
                if st.form_submit_button("Save"):
                    with get_db() as db2:
                        db2.execute("INSERT INTO sponsors (name, status) VALUES (?,'Active')", (name,))
                    st.success("Added.")
                    st.rerun()
        if sponsors:
            st.dataframe(pd.DataFrame([dict(s) for s in sponsors]), use_container_width=True)

    with tabs[2]:
        if st.button("➕ Add Department"):
            with st.form("new_dept"):
                name = st.text_input("Name")
                if st.form_submit_button("Save"):
                    with get_db() as db2:
                        db2.execute("INSERT INTO departments (name, status) VALUES (?,'Active')", (name,))
                    st.success("Added.")
                    st.rerun()
        if departments:
            st.dataframe(pd.DataFrame([dict(d) for d in departments]), use_container_width=True)

    with tabs[3]:
        with get_db() as db:
            depts = db.execute("SELECT department_id, name FROM departments WHERE status='Active'").fetchall()
        if st.button("➕ Add Section"):
            with st.form("new_sec"):
                name = st.text_input("Name")
                dept = st.selectbox("Department", [f"{d['department_id']} - {d['name']}" for d in depts] if depts else [""])
                if st.form_submit_button("Save"):
                    dept_id = int(dept.split(" - ")[0]) if dept else 1
                    with get_db() as db2:
                        db2.execute("INSERT INTO sections (name, department_id, status) VALUES (?,?,'Active')", (name, dept_id))
                    st.success("Added.")
                    st.rerun()
        if sections:
            st.dataframe(pd.DataFrame([dict(s) for s in sections]), use_container_width=True)
