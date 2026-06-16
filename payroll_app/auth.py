import streamlit as st
from datetime import datetime, timedelta
from .database import get_db, hash_password, add_audit_log
from .config import PERMISSION_MODULES, ACCESS_LEVELS

def authenticate(username, password):
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE username=? AND status='Active'", (username,)).fetchone()
        if not user:
            add_audit_log(db, 'Login', 'Login', username=username, reason='User not found')
            return None, "User not found"

        if user['locked_until']:
            try:
                locked = datetime.strptime(user['locked_until'], '%Y-%m-%d %H:%M:%S')
                if locked > datetime.now():
                    add_audit_log(db, 'Login', 'Login', username=username, reason='Account locked')
                    return None, f"Account locked until {locked.strftime('%Y-%m-%d %H:%M:%S')}. Contact admin."
            except:
                pass

        if user['password_hash'] != hash_password(password):
            attempts = user['login_attempts'] + 1
            db.execute("UPDATE users SET login_attempts=? WHERE username=?", (attempts, username))
            if attempts >= 5:
                lock_time = (datetime.now() + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
                db.execute("UPDATE users SET locked_until=? WHERE username=?", (lock_time, username))
                add_audit_log(db, 'Login', 'Login', username=username, reason='Account locked after 5 failed attempts')
                return None, "Account locked after 5 failed attempts. Try again in 30 minutes."
            add_audit_log(db, 'Login', 'Login', username=username, reason=f'Invalid password attempt {attempts}/5')
            return None, f"Invalid password. Attempt {attempts}/5."

        db.execute("UPDATE users SET last_login=datetime('now','localtime'), login_attempts=0, locked_until=NULL WHERE username=?",
                   (username,))
        add_audit_log(db, 'Login', 'Login', username=username, reason='Login successful')
        return dict(user), "Success"

def change_password(user_id, old_password, new_password):
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or user['password_hash'] != hash_password(old_password):
            return False, "Current password is incorrect"
        db.execute("UPDATE users SET password_hash=? WHERE user_id=?", (hash_password(new_password), user_id))
        return True, "Password changed successfully"

def get_user_permissions(username):
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            return {}
        role = user['role']
        permissions = {}
        rp = db.execute('''SELECT p.module_code, rp.access_level FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            JOIN roles r ON rp.role_id = r.id
            WHERE r.name=?''', (role,)).fetchall()
        for p in rp:
            permissions[p['module_code']] = p['access_level']
        up = db.execute('''SELECT p.module_code, up.access_level FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id=?''', (user['user_id'],)).fetchall()
        for p in up:
            permissions[p['module_code']] = p['access_level']
        for mod in PERMISSION_MODULES:
            if mod not in permissions:
                permissions[mod] = 'No Access'
        return permissions

def check_permission(module, level='View Only'):
    if 'user' not in st.session_state:
        return False
    username = st.session_state.user['username']
    user = st.session_state.user
    if user['role'] == 'Super Admin':
        return True
    permissions = st.session_state.get('permissions', {})
    access = permissions.get(module, 'No Access')
    levels = ['No Access', 'View Only', 'Add', 'Edit', 'Disable', 'Export', 'Approve', 'Full Access']
    required_idx = levels.index(level) if level in levels else 1
    actual_idx = levels.index(access) if access in levels else 0
    return actual_idx >= required_idx

def can_view_salary():
    if 'user' not in st.session_state:
        return False
    u = st.session_state.user
    if u['role'] == 'Super Admin':
        return True
    return bool(u.get('can_view_salary', 0))

def can_view_company_cost():
    if 'user' not in st.session_state:
        return False
    u = st.session_state.user
    if u['role'] == 'Super Admin':
        return True
    return bool(u.get('can_view_company_cost', 0))

def mask_amount(val, show):
    if show:
        return f"E£ {val:,.2f}"
    return "**Restricted**"

def get_sidebar_menu():
    if 'user' not in st.session_state:
        return []
    role = st.session_state.user['role']
    if role == 'Super Admin':
        menus = [
            ("🏠", "Executive Dashboard"),
            ("⚠️", "Alerts Center"),
            ("📋", "Employees"),
            ("💰", "Employee Allowances"),
            ("📊", "Project Allocation"),
            ("💵", "Payroll Run Center"),
            ("📄", "Payroll Transactions"),
            ("📑", "Payroll Project Allocation"),
            ("🎯", "Bonus Calculator"),
            ("📕", "Bonus Register"),
            ("📗", "Bonus Reports"),
            ("🔄", "Salary Revisions"),
            ("🏦", "Bank Transfer"),
            ("🤝", "Bank Reconciliation"),
            ("📈", "Monthly Reports"),
            ("📅", "Yearly Summary"),
            ("📊", "Variance Report"),
            ("📁", "Executive Reports Package"),
            ("⚙️", "Payroll Setup"),
            ("🏗️", "Projects"),
            ("🏛️", "Organizations"),
            ("👥", "Users & Permissions"),
            ("📥", "Import / Export"),
            ("💾", "Backup & Restore"),
            ("📋", "Audit Log"),
        ]
    elif role == 'Admin':
        menus = [
            ("🏠", "Executive Dashboard"),
            ("⚠️", "Alerts Center"),
            ("📋", "Employees"),
            ("💰", "Employee Allowances"),
            ("📊", "Project Allocation"),
            ("💵", "Payroll Run Center"),
            ("📄", "Payroll Transactions"),
            ("📑", "Payroll Project Allocation"),
            ("🎯", "Bonus Calculator"),
            ("📕", "Bonus Register"),
            ("📗", "Bonus Reports"),
            ("🔄", "Salary Revisions"),
            ("🏦", "Bank Transfer"),
            ("🤝", "Bank Reconciliation"),
            ("📈", "Monthly Reports"),
            ("📅", "Yearly Summary"),
            ("📊", "Variance Report"),
            ("⚙️", "Payroll Setup"),
            ("🏗️", "Projects"),
            ("🏛️", "Organizations"),
            ("📥", "Import / Export"),
            ("💾", "Backup & Restore"),
            ("📋", "Audit Log"),
        ]
    elif role == 'Payroll Manager':
        menus = [
            ("🏠", "Executive Dashboard"),
            ("📋", "Employees"),
            ("💰", "Employee Allowances"),
            ("📊", "Project Allocation"),
            ("💵", "Payroll Run Center"),
            ("📄", "Payroll Transactions"),
            ("📑", "Payroll Project Allocation"),
            ("🎯", "Bonus Calculator"),
            ("📕", "Bonus Register"),
            ("📗", "Bonus Reports"),
            ("🏦", "Bank Transfer"),
            ("🤝", "Bank Reconciliation"),
            ("📈", "Monthly Reports"),
            ("📅", "Yearly Summary"),
            ("⚙️", "Payroll Setup"),
            ("🏗️", "Projects"),
        ]
    elif role == 'HR User':
        menus = [
            ("📋", "Employees"),
            ("💰", "Employee Allowances"),
            ("📊", "Project Allocation"),
            ("🔄", "Salary Revisions"),
            ("📈", "Monthly Reports"),
        ]
    elif role == 'Finance User':
        menus = [
            ("🏠", "Executive Dashboard"),
            ("💵", "Payroll Run Center"),
            ("📄", "Payroll Transactions"),
            ("📑", "Payroll Project Allocation"),
            ("🎯", "Bonus Calculator"),
            ("📕", "Bonus Register"),
            ("📗", "Bonus Reports"),
            ("🏦", "Bank Transfer"),
            ("🤝", "Bank Reconciliation"),
            ("📈", "Monthly Reports"),
            ("📅", "Yearly Summary"),
        ]
    else:
        menus = [
            ("🏠", "Executive Dashboard"),
            ("📈", "Monthly Reports"),
        ]
    return menus
