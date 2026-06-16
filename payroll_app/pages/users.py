import streamlit as st
import pandas as pd
from datetime import datetime
from ..database import get_db, hash_password, add_audit_log
from ..auth import check_permission, get_user_permissions
from ..config import PERMISSION_MODULES, ACCESS_LEVELS
from ..ui import page_header, fmt_currency, status_badge, divider, footer, apply_custom_css

def show():
    apply_custom_css()
    page_header("Users & Permissions", "Manage system users and their access rights")

    if not check_permission('Users & Permissions', 'View Only'):
        st.error("Access denied.")
        return

    tabs = st.tabs(["Users", "Roles", "Permissions"])

    with tabs[0]:
        show_users()
    with tabs[1]:
        show_roles()
    with tabs[2]:
        show_permissions()

def show_users():
    if check_permission('Users & Permissions', 'Add'):
        with st.expander("➕ Add New User"):
            with st.form("new_user"):
                c1, c2 = st.columns(2)
                with c1:
                    full_name = st.text_input("Full Name")
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    email = st.text_input("Email")
                with c2:
                    role = st.selectbox("Role", ['Super Admin', 'Admin', 'Payroll Manager', 'HR User', 'Finance User', 'Project Manager', 'Viewer'])
                    mobile = st.text_input("Mobile")
                    status = st.selectbox("Status", ['Active', 'Inactive'])
                if st.form_submit_button("Create User"):
                    with get_db() as db:
                        existing = db.execute("SELECT user_id FROM users WHERE username=?", (username,)).fetchone()
                        if existing:
                            st.error("Username already exists.")
                        else:
                            db.execute('''INSERT INTO users (full_name, username, email, mobile, password_hash, role, status, created_by)
                                VALUES (?,?,?,?,?,?,?,?)''',
                                       (full_name, username, email, mobile, hash_password(password), role, status,
                                        st.session_state.get('user',{}).get('username','system')))
                            add_audit_log(db, 'Created', 'User', 'users', username,
                                          username=st.session_state.get('user',{}).get('username','system'),
                                          reason=f'User {username} created with role {role}')
                            st.success(f"User {username} created.")
                            st.rerun()

    with get_db() as db:
        users = db.execute('''SELECT u.*, COALESCE(u.last_login, 'Never') as last_login_display
            FROM users u ORDER BY u.created_at DESC''').fetchall()

    if users:
        user_data = []
        for u in users:
            u = dict(u)
            u['status_badge'] = status_badge(u['status'])
            u['password_hash'] = "****"
            user_data.append(u)

        df = pd.DataFrame(user_data)
        cols = ['username', 'full_name', 'role', 'status', 'email', 'last_login_display']
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)

        for u in users:
            u = dict(u)
            if check_permission('Users & Permissions', 'Edit'):
                with st.expander(f"✏️ {u['username']} ({u['full_name']})"):
                    with st.form(f"edit_user_{u['user_id']}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            full_name = st.text_input("Full Name", value=u['full_name'])
                            email = st.text_input("Email", value=u['email'])
                            mobile = st.text_input("Mobile", value=u['mobile'])
                        with c2:
                            role = st.selectbox("Role", ['Super Admin', 'Admin', 'Payroll Manager', 'HR User', 'Finance User', 'Project Manager', 'Viewer'],
                                               index=['Super Admin', 'Admin', 'Payroll Manager', 'HR User', 'Finance User', 'Project Manager', 'Viewer'].index(u['role']) if u['role'] in ['Super Admin', 'Admin', 'Payroll Manager', 'HR User', 'Finance User', 'Project Manager', 'Viewer'] else 0)
                            status = st.selectbox("Status", ['Active', 'Inactive', 'Locked'],
                                                  index=['Active', 'Inactive', 'Locked'].index(u['status']) if u['status'] in ['Active', 'Inactive', 'Locked'] else 0)

                        st.subheader("Salary Visibility")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            can_sal = st.checkbox("Can View Salary", value=bool(u['can_view_salary']))
                            can_net = st.checkbox("Can View Net Salary", value=bool(u['can_view_net_salary']))
                        with c2:
                            can_gross = st.checkbox("Can View Gross Salary", value=bool(u['can_view_gross_salary']))
                            can_tax = st.checkbox("Can View Tax", value=bool(u['can_view_tax']))
                        with c3:
                            can_ins = st.checkbox("Can View Social Insurance", value=bool(u['can_view_social_insurance']))
                            can_cost = st.checkbox("Can View Company Cost", value=bool(u['can_view_company_cost']))
                            can_bonus = st.checkbox("Can View Bonus Amount", value=bool(u['can_view_bonus_amount']))
                            can_export = st.checkbox("Can Export Salary Data", value=bool(u['can_export_salary_data']))

                        new_password = st.text_input("New Password (leave empty to keep)", type="password")
                        if st.form_submit_button("💾 Update User"):
                            with get_db() as db:
                                db.execute('''UPDATE users SET full_name=?, email=?, mobile=?, role=?, status=?,
                                    can_view_salary=?, can_view_net_salary=?, can_view_gross_salary=?,
                                    can_view_tax=?, can_view_social_insurance=?, can_view_company_cost=?,
                                    can_view_bonus_amount=?, can_export_salary_data=?
                                    WHERE user_id=?''',
                                           (full_name, email, mobile, role, status, int(can_sal), int(can_net),
                                            int(can_gross), int(can_tax), int(can_ins), int(can_cost),
                                            int(can_bonus), int(can_export), u['user_id']))
                                if new_password:
                                    db.execute("UPDATE users SET password_hash=? WHERE user_id=?", (hash_password(new_password), u['user_id']))
                            add_audit_log(db, 'Updated', 'User', 'users', u['username'],
                                          username=st.session_state.get('user',{}).get('username','system'),
                                          reason=f'User {u["username"]} updated')
                            st.success("User updated.")
                            st.rerun()

def show_roles():
    with get_db() as db:
        roles = db.execute("SELECT * FROM roles WHERE status='Active'").fetchall()

    st.subheader("System Roles")
    for r in roles:
        r = dict(r)
        with st.expander(f"{r['name']} - {r['description']}"):
            with get_db() as db:
                perms = db.execute('''SELECT p.module_code, rp.access_level FROM role_permissions rp
                    JOIN permissions p ON rp.permission_id = p.id
                    WHERE rp.role_id=?''', (r['id'],)).fetchall()

            perm_dict = {p['module_code']: p['access_level'] for p in perms}
            with st.form(f"role_perms_{r['id']}"):
                cols = st.columns(3)
                for i, mod in enumerate(PERMISSION_MODULES):
                    with cols[i % 3]:
                        current = perm_dict.get(mod, 'No Access')
                        new_level = st.selectbox(mod, ACCESS_LEVELS,
                                                 index=ACCESS_LEVELS.index(current) if current in ACCESS_LEVELS else 0,
                                                 key=f"rp_{r['id']}_{mod}")
                if st.form_submit_button("💾 Save Role Permissions"):
                    with get_db() as db2:
                        for mod in PERMISSION_MODULES:
                            level = st.session_state[f"rp_{r['id']}_{mod}"]
                            perm = db2.execute("SELECT id FROM permissions WHERE module_code=?", (mod,)).fetchone()
                            if perm:
                                existing = db2.execute("SELECT id FROM role_permissions WHERE role_id=? AND permission_id=?", (r['id'], perm['id'])).fetchone()
                                if existing:
                                    db2.execute("UPDATE role_permissions SET access_level=? WHERE id=?", (level, existing['id']))
                                else:
                                    db2.execute("INSERT INTO role_permissions (role_id, permission_id, access_level) VALUES (?,?,?)", (r['id'], perm['id'], level))
                    add_audit_log(db2, 'Updated', 'Permission', 'role_permissions', r['id'],
                                  username=st.session_state.get('user',{}).get('username','system'),
                                  reason=f'Role permissions updated for {r["name"]}')
                    st.success("Role permissions updated.")
                    st.rerun()

def show_permissions():
    with get_db() as db:
        perms = db.execute("SELECT * FROM permissions WHERE status='Active' ORDER BY module_code").fetchall()

    st.subheader("System Permissions")
    st.info("Permissions define access to system modules. Roles inherit their access levels from the Role Permissions setup.")
    if perms:
        df = pd.DataFrame([dict(p) for p in perms])
        st.dataframe(df[['module_code', 'permission_name']], use_container_width=True)
