import sqlite3
import os
import json
import hashlib
from datetime import datetime, date
from contextlib import contextmanager
from .config import DB_PATH

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA encoding='UTF-8'")
    return conn

@contextmanager
def get_db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def add_audit_log(db, action, module, table_name=None, record_id=None,
                  old_values=None, new_values=None, changed_fields=None,
                  username=None, reason=None, approval_ref=None):
    username = username or 'system'
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    old_str = json.dumps(old_values, ensure_ascii=False, default=str) if old_values else None
    new_str = json.dumps(new_values, ensure_ascii=False, default=str) if new_values else None
    fields_str = json.dumps(changed_fields, ensure_ascii=False) if changed_fields else None
    db.execute('''INSERT INTO audit_log 
        (action, module, table_name, record_id, old_values, new_values, changed_fields,
         username, timestamp, reason, approval_ref)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
               (action, module, table_name, str(record_id) if record_id else None,
                old_str, new_str, fields_str,
                username, timestamp, reason, approval_ref))

class DatabaseManager:
    def __init__(self):
        self.conn = get_conn()
        self.create_tables()
        self.seed_default_data()

    def create_tables(self):
        conn = self.conn
        c = conn.cursor()

        c.executescript('''
        CREATE TABLE IF NOT EXISTS organizations (
            org_id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            tax_reg_no TEXT DEFAULT '',
            social_insurance_no TEXT DEFAULT '',
            address TEXT DEFAULT '',
            bank_account TEXT DEFAULT '',
            status TEXT DEFAULT 'Active'
        );

        CREATE TABLE IF NOT EXISTS sponsors (
            sponsor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'Active'
        );

        CREATE TABLE IF NOT EXISTS departments (
            department_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'Active'
        );

        CREATE TABLE IF NOT EXISTS sections (
            section_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (department_id) REFERENCES departments(department_id)
        );

        CREATE TABLE IF NOT EXISTS positions (
            position_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'Active'
        );

        CREATE TABLE IF NOT EXISTS projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_code TEXT UNIQUE NOT NULL,
            project_name TEXT NOT NULL,
            client_name TEXT DEFAULT '',
            organization TEXT DEFAULT '',
            location TEXT DEFAULT '',
            status TEXT DEFAULT 'Active',
            start_date TEXT DEFAULT '',
            end_date TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT UNIQUE NOT NULL,
            organization TEXT DEFAULT '',
            sponsor TEXT DEFAULT '',
            arabic_name TEXT NOT NULL,
            english_name TEXT DEFAULT '',
            position TEXT DEFAULT '',
            department TEXT DEFAULT '',
            section TEXT DEFAULT '',
            default_project TEXT DEFAULT '',
            hiring_date TEXT DEFAULT '',
            basic_salary REAL DEFAULT 0,
            net_salary REAL DEFAULT 0,
            gross_salary REAL DEFAULT 0,
            new_net_salary REAL DEFAULT 0,
            new_allowance REAL DEFAULT 0,
            new_net_earning REAL DEFAULT 0,
            insurance_salary_base REAL DEFAULT 0,
            bank_name TEXT DEFAULT '',
            bank_account TEXT DEFAULT '',
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS employee_project_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            project_code TEXT NOT NULL,
            allocation_type TEXT DEFAULT 'Percentage',
            percentage REAL DEFAULT 100,
            fixed_amount REAL DEFAULT 0,
            effective_from TEXT DEFAULT '',
            effective_to TEXT DEFAULT '',
            is_primary INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code),
            FOREIGN KEY (project_code) REFERENCES projects(project_code)
        );

        CREATE TABLE IF NOT EXISTS allowance_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_taxable_default TEXT DEFAULT 'Yes',
            is_insurance_default TEXT DEFAULT 'No',
            payment_type_default TEXT DEFAULT 'Net',
            status TEXT DEFAULT 'Active'
        );

        CREATE TABLE IF NOT EXISTS employee_allowances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            allowance_type TEXT DEFAULT '',
            allowance_name TEXT NOT NULL,
            amount REAL DEFAULT 0,
            calc_type TEXT DEFAULT 'Fixed Amount',
            payment_type TEXT DEFAULT 'Net',
            taxable TEXT DEFAULT 'Yes',
            insurance_applicable TEXT DEFAULT 'No',
            recurring TEXT DEFAULT 'Monthly',
            project_charging_method TEXT DEFAULT 'Follow Employee Project Allocation',
            specific_project TEXT DEFAULT '',
            effective_from TEXT DEFAULT '',
            effective_to TEXT DEFAULT '',
            department TEXT DEFAULT '',
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            status TEXT DEFAULT 'Draft',
            project_filter TEXT DEFAULT '',
            department_filter TEXT DEFAULT '',
            sponsor_filter TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS payroll_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            employee_code TEXT NOT NULL,
            arabic_name TEXT DEFAULT '',
            organization TEXT DEFAULT '',
            sponsor TEXT DEFAULT '',
            position TEXT DEFAULT '',
            department TEXT DEFAULT '',
            section TEXT DEFAULT '',
            default_project TEXT DEFAULT '',
            project_allocation_summary TEXT DEFAULT '',
            base_net_salary REAL DEFAULT 0,
            recurring_net_allowances REAL DEFAULT 0,
            recurring_gross_allowances REAL DEFAULT 0,
            onetime_net_allowances REAL DEFAULT 0,
            onetime_gross_allowances REAL DEFAULT 0,
            total_allowances REAL DEFAULT 0,
            net_earning REAL DEFAULT 0,
            estimated_gross REAL DEFAULT 0,
            basic_salary REAL DEFAULT 0,
            insurance_base_before REAL DEFAULT 0,
            insurance_base_after REAL DEFAULT 0,
            employee_insurance REAL DEFAULT 0,
            company_insurance REAL DEFAULT 0,
            taxable_amount REAL DEFAULT 0,
            monthly_tax REAL DEFAULT 0,
            annual_tax REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            net_transfer_amount REAL DEFAULT 0,
            total_company_cost REAL DEFAULT 0,
            transfer_date TEXT DEFAULT '',
            transfer_ref TEXT DEFAULT '',
            payment_status TEXT DEFAULT 'Pending',
            approval_status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code),
            UNIQUE(employee_code, year, month)
        );

        CREATE TABLE IF NOT EXISTS payroll_project_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_transaction_id INTEGER,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            employee_code TEXT NOT NULL,
            arabic_name TEXT DEFAULT '',
            department TEXT DEFAULT '',
            section TEXT DEFAULT '',
            project_code TEXT NOT NULL,
            allocation_percent REAL DEFAULT 0,
            allocated_net_salary REAL DEFAULT 0,
            allocated_allowances REAL DEFAULT 0,
            allocated_gross REAL DEFAULT 0,
            allocated_tax REAL DEFAULT 0,
            allocated_employee_insurance REAL DEFAULT 0,
            allocated_company_insurance REAL DEFAULT 0,
            allocated_total_cost REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Pending',
            FOREIGN KEY (payroll_transaction_id) REFERENCES payroll_transactions(id)
        );

        CREATE TABLE IF NOT EXISTS employee_bonuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            arabic_name TEXT DEFAULT '',
            organization TEXT DEFAULT '',
            sponsor TEXT DEFAULT '',
            position TEXT DEFAULT '',
            department TEXT DEFAULT '',
            section TEXT DEFAULT '',
            default_project TEXT DEFAULT '',
            bonus_project TEXT DEFAULT '',
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            bonus_date TEXT DEFAULT '',
            bonus_type TEXT DEFAULT 'Net Bonus',
            bonus_category TEXT DEFAULT 'Performance Bonus',
            bonus_amount_entered REAL DEFAULT 0,
            net_bonus_amount REAL DEFAULT 0,
            gross_bonus_amount REAL DEFAULT 0,
            tax_before REAL DEFAULT 0,
            tax_after REAL DEFAULT 0,
            tax_diff REAL DEFAULT 0,
            emp_ins_before REAL DEFAULT 0,
            emp_ins_after REAL DEFAULT 0,
            emp_ins_diff REAL DEFAULT 0,
            comp_ins_before REAL DEFAULT 0,
            comp_ins_after REAL DEFAULT 0,
            comp_ins_diff REAL DEFAULT 0,
            gross_before REAL DEFAULT 0,
            gross_after REAL DEFAULT 0,
            gross_diff REAL DEFAULT 0,
            net_before REAL DEFAULT 0,
            net_after REAL DEFAULT 0,
            net_increase REAL DEFAULT 0,
            comp_cost_before REAL DEFAULT 0,
            comp_cost_after REAL DEFAULT 0,
            comp_cost_diff REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Planned',
            approval_status TEXT DEFAULT 'Draft',
            approved_by TEXT DEFAULT '',
            approved_date TEXT DEFAULT '',
            paid_date TEXT DEFAULT '',
            payment_ref TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS bonus_project_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bonus_id INTEGER,
            employee_code TEXT NOT NULL,
            project_code TEXT NOT NULL,
            allocation_percent REAL DEFAULT 0,
            allocated_net_bonus REAL DEFAULT 0,
            allocated_gross_bonus REAL DEFAULT 0,
            allocated_tax_diff REAL DEFAULT 0,
            allocated_emp_ins_diff REAL DEFAULT 0,
            allocated_comp_ins_diff REAL DEFAULT 0,
            allocated_comp_cost_diff REAL DEFAULT 0,
            year INTEGER,
            month INTEGER,
            FOREIGN KEY (bonus_id) REFERENCES employee_bonuses(id)
        );

        CREATE TABLE IF NOT EXISTS bonus_simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT,
            bonus_type TEXT,
            amount REAL,
            result_data TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS salary_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            arabic_name TEXT DEFAULT '',
            department TEXT DEFAULT '',
            section TEXT DEFAULT '',
            project TEXT DEFAULT '',
            old_basic REAL DEFAULT 0,
            new_basic REAL DEFAULT 0,
            old_net REAL DEFAULT 0,
            new_net REAL DEFAULT 0,
            old_allowance REAL DEFAULT 0,
            new_allowance REAL DEFAULT 0,
            old_net_earning REAL DEFAULT 0,
            new_net_earning REAL DEFAULT 0,
            old_gross REAL DEFAULT 0,
            new_gross REAL DEFAULT 0,
            gross_diff REAL DEFAULT 0,
            net_diff REAL DEFAULT 0,
            comp_cost_before REAL DEFAULT 0,
            comp_cost_after REAL DEFAULT 0,
            comp_cost_diff REAL DEFAULT 0,
            effective_from TEXT DEFAULT '',
            effective_to TEXT DEFAULT '',
            revision_type TEXT DEFAULT 'Annual Increase',
            reason TEXT DEFAULT '',
            approval_status TEXT DEFAULT 'Draft',
            approved_by TEXT DEFAULT '',
            approved_date TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS tax_laws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            law_number TEXT DEFAULT '',
            effective_from TEXT DEFAULT '',
            effective_to TEXT DEFAULT '',
            is_default INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS tax_brackets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tax_law_id INTEGER NOT NULL,
            year INTEGER DEFAULT 2024,
            income_from REAL DEFAULT 0,
            income_to REAL DEFAULT 0,
            tax_rate REAL DEFAULT 0,
            bracket_order INTEGER DEFAULT 0,
            is_skipped_for_higher_income INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (tax_law_id) REFERENCES tax_laws(id)
        );

        CREATE TABLE IF NOT EXISTS tax_exemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tax_law_id INTEGER NOT NULL,
            year INTEGER DEFAULT 2024,
            personal_exemption_annual REAL DEFAULT 0,
            additional_exemption_annual REAL DEFAULT 0,
            tax_free_bracket_annual REAL DEFAULT 0,
            total_annual_exemption REAL DEFAULT 0,
            round_down_to_10 INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT '',
            FOREIGN KEY (tax_law_id) REFERENCES tax_laws(id)
        );

        CREATE TABLE IF NOT EXISTS social_insurance_setup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER DEFAULT 2024,
            effective_from TEXT DEFAULT '',
            effective_to TEXT DEFAULT '',
            min_insurance_salary REAL DEFAULT 2600,
            max_insurance_salary REAL DEFAULT 16700,
            employee_share_pct REAL DEFAULT 0.11,
            company_share_pct REAL DEFAULT 0.1875,
            insurance_base_source TEXT DEFAULT 'Employee Insurance Salary/Base',
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS salary_calculation_setup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            basic_salary_source TEXT DEFAULT "Manual Basic Salary from Employee Master Data",
            basic_pct REAL DEFAULT 0,
            insurance_base_source TEXT DEFAULT "Manual Insurance Salary/Base from employee",
            include_taxable_allowances_in_insurance TEXT DEFAULT "No",
            include_gross_allowances_in_insurance TEXT DEFAULT "No",
            gross_up_tolerance REAL DEFAULT 1.0,
            max_iterations INTEGER DEFAULT 100,
            status TEXT DEFAULT "Active"
        );

        CREATE TABLE IF NOT EXISTS payment_statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT 'gray',
            status TEXT DEFAULT 'Active'
        );

        CREATE TABLE IF NOT EXISTS bank_transfer_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            arabic_name TEXT DEFAULT '',
            english_name TEXT DEFAULT '',
            bank_name TEXT DEFAULT '',
            bank_branch TEXT DEFAULT '',
            bank_account TEXT DEFAULT '',
            net_transfer_amount REAL DEFAULT 0,
            payment_month INTEGER,
            payment_year INTEGER,
            transfer_date TEXT DEFAULT '',
            transfer_ref TEXT DEFAULT '',
            payment_status TEXT DEFAULT 'Pending',
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS bank_reconciliation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            arabic_name TEXT DEFAULT '',
            payroll_net_amount REAL DEFAULT 0,
            actual_bank_amount REAL DEFAULT 0,
            difference REAL DEFAULT 0,
            transfer_date TEXT DEFAULT '',
            bank_ref TEXT DEFAULT '',
            status TEXT DEFAULT 'Not Transferred',
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS attendance_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            year INTEGER,
            month INTEGER,
            working_days REAL DEFAULT 0,
            paid_days REAL DEFAULT 0,
            unpaid_leave_days REAL DEFAULT 0,
            absence_days REAL DEFAULT 0,
            deduction_days REAL DEFAULT 0,
            daily_rate REAL DEFAULT 0,
            deduction_amount REAL DEFAULT 0,
            reason TEXT DEFAULT '',
            approval_status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS overtime_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            year INTEGER,
            month INTEGER,
            project_code TEXT DEFAULT '',
            overtime_date TEXT DEFAULT '',
            hours REAL DEFAULT 0,
            hourly_rate REAL DEFAULT 0,
            multiplier REAL DEFAULT 1.5,
            amount REAL DEFAULT 0,
            payment_type TEXT DEFAULT 'Net',
            taxable TEXT DEFAULT 'Yes',
            insurance_applicable TEXT DEFAULT 'No',
            approval_status TEXT DEFAULT 'Draft',
            reason TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS employee_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            doc_type TEXT DEFAULT '',
            file_name TEXT DEFAULT '',
            upload_date TEXT DEFAULT '',
            expiry_date TEXT DEFAULT '',
            uploaded_by TEXT DEFAULT '',
            status TEXT DEFAULT 'Valid',
            notes TEXT DEFAULT '',
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS payroll_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization TEXT DEFAULT '',
            year INTEGER,
            month INTEGER,
            cutoff_date TEXT DEFAULT '',
            payroll_gen_date TEXT DEFAULT '',
            hr_review_date TEXT DEFAULT '',
            finance_approval_date TEXT DEFAULT '',
            bank_transfer_date TEXT DEFAULT '',
            close_date TEXT DEFAULT '',
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT DEFAULT '',
            severity TEXT DEFAULT 'Info',
            title TEXT DEFAULT '',
            message TEXT DEFAULT '',
            employee_code TEXT DEFAULT '',
            module TEXT DEFAULT '',
            record_id INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            resolved_at TEXT DEFAULT '',
            resolved_by TEXT DEFAULT '',
            status TEXT DEFAULT 'Open'
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            module TEXT DEFAULT '',
            table_name TEXT DEFAULT '',
            record_id TEXT DEFAULT '',
            old_values TEXT DEFAULT '',
            new_values TEXT DEFAULT '',
            changed_fields TEXT DEFAULT '',
            username TEXT DEFAULT '',
            user_role TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now','localtime')),
            ip_address TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            approval_ref TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT DEFAULT '',
            mobile TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'Viewer',
            status TEXT DEFAULT 'Active',
            organization_access TEXT DEFAULT 'All',
            project_access TEXT DEFAULT 'All',
            department_access TEXT DEFAULT 'All',
            can_view_salary INTEGER DEFAULT 1,
            can_view_net_salary INTEGER DEFAULT 1,
            can_view_gross_salary INTEGER DEFAULT 1,
            can_view_tax INTEGER DEFAULT 1,
            can_view_social_insurance INTEGER DEFAULT 1,
            can_view_company_cost INTEGER DEFAULT 1,
            can_view_bonus_amount INTEGER DEFAULT 1,
            can_export_salary_data INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            last_login TEXT DEFAULT '',
            login_attempts INTEGER DEFAULT 0,
            locked_until TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'Active'
        );

        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            permission_name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'Active'
        );

        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER,
            permission_id INTEGER,
            access_level TEXT DEFAULT 'No Access',
            FOREIGN KEY (role_id) REFERENCES roles(id),
            FOREIGN KEY (permission_id) REFERENCES permissions(id)
        );

        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            permission_id INTEGER,
            access_level TEXT DEFAULT 'No Access',
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (permission_id) REFERENCES permissions(id)
        );

        CREATE TABLE IF NOT EXISTS user_project_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            project_code TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS user_department_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            department_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS approval_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_type TEXT NOT NULL,
            record_id INTEGER,
            requested_by TEXT DEFAULT '',
            requested_at TEXT DEFAULT (datetime('now','localtime')),
            status TEXT DEFAULT 'Pending',
            approved_by TEXT DEFAULT '',
            approved_at TEXT DEFAULT '',
            rejection_reason TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS approval_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            action TEXT DEFAULT '',
            action_by TEXT DEFAULT '',
            action_at TEXT DEFAULT (datetime('now','localtime')),
            comments TEXT DEFAULT '',
            FOREIGN KEY (request_id) REFERENCES approval_requests(id)
        );

        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backup_name TEXT NOT NULL,
            backup_type TEXT DEFAULT 'Manual',
            file_path TEXT DEFAULT '',
            file_size INTEGER DEFAULT 0,
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            notes TEXT DEFAULT ''
        );

        ''')

        conn.commit()
        print("[DB] All tables created successfully.")

    def seed_default_data(self):
        conn = self.conn
        c = conn.cursor()

        existing = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing > 0:
            print("[DB] Data already seeded, skipping.")
            return

        print("[DB] Seeding default data...")

        c.executemany("INSERT OR IGNORE INTO organizations (code, name, status) VALUES (?, ?, ?)", [
            ('AFM', 'AFM', 'Active'),
            ('PAYROLL', 'Payroll Pro', 'Active'),
        ])

        c.executemany("INSERT OR IGNORE INTO sponsors (name, status) VALUES (?, ?)", [
            ('Professional', 'Active'),
            ('AFM', 'Active'),
        ])

        c.executemany("INSERT OR IGNORE INTO departments (name, status) VALUES (?, ?)", [
            ('Services', 'Active'),
            ('Landscape Maintenance', 'Active'),
            ('Property Operations', 'Active'),
            ('Facility Projects Management', 'Active'),
            ('Health & Safety', 'Active'),
            ('Maintenance', 'Active'),
        ])

        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('Housekeeping', 1, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('Business Support', 1, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('Pest Control', 1, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('Fleet', 1, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('Agriculture', 2, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('Operations General', 3, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('Operations', 3, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('FPM General', 4, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('HSE General', 5, 'Active'))
        c.execute("INSERT OR IGNORE INTO sections (name, department_id, status) VALUES (?, ?, ?)",
                  ('Electrical', 6, 'Active'))

        c.executemany("INSERT OR IGNORE INTO positions (name, status) VALUES (?, ?)", [
            ('Janitor', 'Active'),
            ('Office Boy', 'Active'),
            ('HK Supervisor', 'Active'),
            ('Pest Control Technician', 'Active'),
            ('Agriculture Labor', 'Active'),
            ('Messenger', 'Active'),
            ('Site Service Senior Coordinator', 'Active'),
            ('Driver', 'Active'),
            ('Admin Assistant', 'Active'),
            ('HSE Supervisor', 'Active'),
            ('Assistant Facility Manager', 'Active'),
            ('Electrical Technician', 'Active'),
            ('Operations Supervisor', 'Active'),
        ])

        c.executemany("INSERT OR IGNORE INTO projects (project_code, project_name, client_name, organization, location, status, start_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            ('Chevron', 'Chevron', 'Chevron', 'AFM', 'Egypt', 'Active', '2022-01-01', 'Main project'),
            ('Chevron Upstream', 'Chevron Upstream', 'Chevron', 'AFM', 'Egypt', 'Active', '2022-01-01', 'Upstream project'),
        ])

        employees_data = [
            ('120918', 'AFM', 'Professional', 'حماده عامر جمعه', 'Janitor', 'Services', 'Housekeeping', 'Chevron', '30-Nov-22', 7500, 0, 7500),
            ('121009', 'AFM', 'Professional', 'بدريه عبد السلام السيد امام', 'Janitor', 'Services', 'Housekeeping', 'Chevron', '26-Dec-21', 7500, 0, 7500),
            ('122874', 'AFM', 'Professional', 'محمد فؤاد محمد سيد', 'Office Boy', 'Services', 'Business Support', 'Chevron', '1-Feb-23', 9338.49, 1231.92, 10570.41),
            ('122875', 'AFM', 'Professional', 'رابح ابوبكر شبل عبده', 'Office Boy', 'Services', 'Business Support', 'Chevron', '1-Mar-23', 9338.49, 1231.92, 10570.41),
            ('122876', 'AFM', 'Professional', 'وليد إبراهيم عبدالله احمد', 'Office Boy', 'Services', 'Business Support', 'Chevron', '1-Mar-23', 9338.49, 615.96, 9954.45),
            ('121915', 'AFM', 'Professional', 'حسام حنفي حسن صالح', 'HK Supervisor', 'Services', 'Housekeeping', 'Chevron', '15-Nov-22', 10206.25, 1679.74, 11885.99),
            ('128902', 'AFM', 'Professional', 'عبدالرحيم مصطفى محمد حمد', 'Janitor', 'Services', 'Housekeeping', 'Chevron', '23-Nov-25', 7500, 0, 7500),
            ('128903', 'AFM', 'Professional', 'احمد عبدالله عبدالله فتح الله النقيب', 'Janitor', 'Services', 'Housekeeping', 'Chevron', '30-Nov-25', 7500, 0, 7500),
            ('128027', 'AFM', 'Professional', 'حازم محمد حلمى محمد عبدالنبى', 'Pest Control Technician', 'Services', 'Pest Control', 'Chevron', '9-Apr-26', 5500, 0, 5500),
            ('122731', 'AFM', 'Professional', 'عبدالله عبدالله فتح الله النقيب', 'Agriculture Labor', 'Landscape Maintenance', 'Agriculture', 'Chevron', '2-Jan-23', 8579.82, 615.96, 9195.78),
            ('122732', 'AFM', 'Professional', 'محمد السيد محمد موسى الفقى', 'Agriculture Labor', 'Landscape Maintenance', 'Agriculture', 'Chevron', '2-Jan-23', 8579.82, 615.96, 9195.78),
            ('11914', 'AFM', 'AFM', 'يسرى محمود عبدالحميد سيد', 'Messenger', 'Property Operations', 'Operations General', 'Chevron', '1-Feb-23', 10252.18, 3310.82, 13563),
            ('11916', 'AFM', 'AFM', 'رضا سعيد محمد سالم غنيم الغواص', 'Messenger', 'Property Operations', 'Operations General', 'Chevron', '1-Feb-23', 9772.37, 3211.63, 12984),
            ('11918', 'AFM', 'AFM', 'محمود عبد العزيز عبد السلام محمد شرايف', 'Site Service Senior Coordinator', 'Property Operations', 'Operations General', 'Chevron', '1-Feb-23', 12296, 13969, 26265),
            ('11965', 'AFM', 'AFM', 'محمد رشاد يوسف صابر', 'Driver', 'Services', 'Fleet', 'Chevron', '1-Aug-23', 8481.40, 2956.77, 11438.17),
            ('11966', 'AFM', 'AFM', 'محمد حسن على محمد', 'Messenger', 'Property Operations', 'Operations', 'Chevron', '8-Jan-24', 9097.36, 3079.79, 12177.15),
            ('11995', 'AFM', 'AFM', 'أية سعد إبراهيم على جاد', 'Admin Assistant', 'Facility Projects Management', 'FPM General', 'Chevron', '1-Dec-24', 18000, 0, 18000),
            ('12019', 'AFM', 'AFM', 'محمد محسن أحمد محمد', 'HSE Supervisor', 'Health & Safety', 'HSE General', 'Chevron', '15-Jul-25', 30000, 0, 30000),
            ('12032', 'AFM', 'AFM', 'ساندى هانى إسحاق باباوى', 'Assistant Facility Manager', 'Facility Projects Management', 'FPM General', 'Chevron', '1-Sep-25', 24000, 0, 24000),
            ('122341', 'AFM', 'Professional', 'حسن عبدالجابر حسن أحمد', 'Electrical Technician', 'Maintenance', 'Electrical', 'Chevron Upstream', '18-Jan-23', 10000, 4417.90, 14417.90),
            ('121960', 'AFM', 'Professional', 'محمد عامر أبو الحسن', 'Janitor', 'Services', 'Housekeeping', 'Chevron Upstream', '27-Nov-22', 5539.83, 1642.94, 7182.77),
            ('126383', 'AFM', 'Professional', 'عادل احمد سيد احمد يوسف', 'Janitor', 'Services', 'Housekeeping', 'Chevron Upstream', '27-Aug-24', 5539.83, 1642.94, 7182.77),
            ('126384', 'AFM', 'Professional', 'احمد مهدى معوض موسي', 'HK Supervisor', 'Services', 'Housekeeping', 'Chevron Upstream', '26-Aug-24', 7709.61, 1668.25, 9377.86),
            ('124139', 'AFM', 'Professional', 'محمد سعيد فتحى احمد هنداوى', 'Janitor', 'Services', 'Housekeeping', 'Chevron Upstream', '18-Jul-24', 5539.83, 1642.94, 7182.77),
            ('124624', 'AFM', 'Professional', 'مصطفى كمال محمد احمد', 'HK Supervisor', 'Services', 'Housekeeping', 'Chevron Upstream', '6-Aug-24', 7709.61, 1668.25, 9377.86),
            ('126082', 'AFM', 'Professional', 'احمد صلاح محمد احمد', 'Janitor', 'Services', 'Housekeeping', 'Chevron Upstream', '6-Aug-24', 5539.83, 1642.94, 7182.77),
            ('126467', 'AFM', 'Professional', 'محمد حلمى عبدالباقى احمد', 'Janitor', 'Services', 'Housekeeping', 'Chevron Upstream', '26-Sep-24', 5539.83, 1642.94, 7182.77),
            ('129028', 'AFM', 'Professional', 'معتز محمود محمد محمود اسماعيل', 'Janitor', 'Services', 'Housekeeping', 'Chevron Upstream', '4-Jan-26', 5539.83, 1642.94, 7182.77),
            ('10864', 'AFM', 'AFM', 'احمد عيد راغب محمود', 'Office Boy', 'Services', 'Business Support', 'Chevron Upstream', '5-Oct-20', 7415, 4318, 11733),
            ('11423', 'AFM', 'AFM', 'محمود إبراهيم محمد رشدى عبد العزيز', 'Operations Supervisor', 'Property Operations', 'Operations General', 'Chevron Upstream', '1-Jun-21', 10945.24, 8567.76, 19513),
        ]

        for emp in employees_data:
            try:
                c.execute('''INSERT OR IGNORE INTO employees 
                    (employee_code, organization, sponsor, arabic_name, position, department, section, 
                     default_project, hiring_date, new_net_salary, new_allowance, new_net_earning,
                     net_salary, basic_salary, status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'Active')''',
                    (emp[0], emp[1], emp[2], emp[3], emp[4], emp[5], emp[6],
                     emp[7], emp[8], emp[9], emp[10], emp[11], emp[9], 0))
            except Exception as e:
                print(f"[DB] Warning: Could not insert employee {emp[0]}: {e}")

        cash_emp_code = c.execute("SELECT employee_code FROM employees").fetchall()
        for row in cash_emp_code:
            code = row['employee_code']
            proj = c.execute("SELECT default_project FROM employees WHERE employee_code=?", (code,)).fetchone()
            if proj:
                p = proj['default_project']
                exists = c.execute("SELECT id FROM employee_project_allocations WHERE employee_code=? AND project_code=?", (code, p)).fetchone()
                if not exists:
                    c.execute("INSERT INTO employee_project_allocations (employee_code, project_code, allocation_type, percentage, is_primary, status) VALUES (?,?,'Percentage',100,1,'Active')", (code, p))

        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Housing Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Transportation Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Meal Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Mobile Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Site Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Shift Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Project Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Temporary Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Other Allowance', 'Yes', 'No', 'Net', 'Active'))
        c.execute('''INSERT OR IGNORE INTO allowance_types (name, is_taxable_default, is_insurance_default, payment_type_default, status) VALUES (?,?,?,?,?)''',
                  ('Bonus', 'Yes', 'No', 'Net', 'Active'))

        emp_allowances = [
            ('122874', 1231.92, 'Monthly', 'Net', 'Housing Allowance'),
            ('122875', 1231.92, 'Monthly', 'Net', 'Housing Allowance'),
            ('122876', 615.96, 'Monthly', 'Net', 'Housing Allowance'),
            ('121915', 1679.74, 'Monthly', 'Net', 'Housing Allowance'),
            ('122731', 615.96, 'Monthly', 'Net', 'Housing Allowance'),
            ('122732', 615.96, 'Monthly', 'Net', 'Housing Allowance'),
            ('11914', 3310.82, 'Monthly', 'Net', 'Housing Allowance'),
            ('11916', 3211.63, 'Monthly', 'Net', 'Housing Allowance'),
            ('11965', 2956.77, 'Monthly', 'Net', 'Housing Allowance'),
            ('11966', 3079.79, 'Monthly', 'Net', 'Housing Allowance'),
            ('122341', 4417.90, 'Monthly', 'Net', 'Housing Allowance'),
            ('121960', 1642.94, 'Monthly', 'Net', 'Housing Allowance'),
            ('126383', 1642.94, 'Monthly', 'Net', 'Housing Allowance'),
            ('126384', 1668.25, 'Monthly', 'Net', 'Housing Allowance'),
            ('124139', 1642.94, 'Monthly', 'Net', 'Housing Allowance'),
            ('124624', 1668.25, 'Monthly', 'Net', 'Housing Allowance'),
            ('126082', 1642.94, 'Monthly', 'Net', 'Housing Allowance'),
            ('126467', 1642.94, 'Monthly', 'Net', 'Housing Allowance'),
            ('129028', 1642.94, 'Monthly', 'Net', 'Housing Allowance'),
            ('10864', 4318, 'Monthly', 'Net', 'Housing Allowance'),
            ('11423', 8567.76, 'Monthly', 'Net', 'Housing Allowance'),
        ]

        for allow in emp_allowances:
            existing_a = c.execute("SELECT id FROM employee_allowances WHERE employee_code=? AND amount=? AND recurring='Monthly'",
                                   (allow[0], allow[1])).fetchone()
            if not existing_a:
                c.execute('''INSERT INTO employee_allowances 
                    (employee_code, allowance_type, allowance_name, amount, calc_type, payment_type, taxable, insurance_applicable, recurring, status)
                    VALUES (?,?,?,?,'Fixed Amount',?, 'Yes', 'No', ?, 'Active')''',
                          (allow[0], allow[4], allow[4], allow[1], allow[3], allow[2]))

        c.executemany("INSERT OR IGNORE INTO payment_statuses (name, color, status) VALUES (?,?,?)", [
            ('Pending', 'orange', 'Active'),
            ('Transferred', 'blue', 'Active'),
            ('Hold', '#ff8c00', 'Active'),
            ('Cancelled', 'gray', 'Active'),
            ('Paid', 'green', 'Active'),
            ('Approved', 'green', 'Active'),
        ])

        seed_roles(c)
        seed_permissions(c)
        seed_users(c)
        seed_tax_data(c)
        seed_insurance_data(c)
        seed_calculation_setup(c)

        conn.commit()
        print("[DB] Seed data completed successfully.")

def seed_roles(c):
    roles = [
        ('Super Admin', 'Full access to all modules'),
        ('Admin', 'Full payroll access except super admin actions'),
        ('Payroll Manager', 'Payroll, employees, allowances, bonus, reports'),
        ('HR User', 'Employees and allowances with limited salary visibility'),
        ('Finance User', 'Salary, tax, insurance, bonus cost, reports'),
        ('Project Manager', 'Assigned projects only'),
        ('Viewer', 'Dashboard and reports only'),
    ]
    c.executemany("INSERT OR IGNORE INTO roles (name, description, status) VALUES (?,?, 'Active')", roles)

def seed_permissions(c):
    modules_list = [
        "Executive Dashboard", "Projects", "Employees", "Employee Project Allocation",
        "Employee Allowances", "Payroll Setup", "Payroll Run Center", "Payroll Transactions",
        "Payroll Project Cost Allocation", "Net to Gross Calculator", "Bonus Calculator",
        "Bonus Register", "Bonus Reports", "Yearly Summary", "Project Yearly Summary",
        "Reports", "Import / Export", "Data Quality Center", "Audit Log", "Users & Permissions"
    ]
    role_access = {
        'Super Admin': {m: 'Full Access' for m in modules_list},
        'Admin': {m: 'Full Access' for m in modules_list if m not in ['Users & Permissions']},
        'Payroll Manager': {m: 'Full Access' for m in ['Payroll Run Center', 'Payroll Transactions', 'Payroll Project Cost Allocation',
                            'Employees', 'Employee Allowances', 'Employee Project Allocation', 'Bonus Calculator', 'Bonus Register',
                            'Bonus Reports', 'Reports', 'Net to Gross Calculator', 'Yearly Summary', 'Project Yearly Summary']},
        'HR User': {m: 'Edit' if m in ['Employees', 'Employee Allowances', 'Employee Project Allocation'] else 'View Only'
                    for m in modules_list},
        'Finance User': {m: 'Full Access' for m in ['Payroll Transactions', 'Payroll Project Cost Allocation',
                         'Bonus Calculator', 'Bonus Register', 'Bonus Reports', 'Reports']},
        'Project Manager': {m: 'View Only' for m in modules_list},
        'Viewer': {m: 'View Only' if m in ['Executive Dashboard', 'Reports'] else 'No Access' for m in modules_list},
    }
    for mod in modules_list:
        c.execute("INSERT OR IGNORE INTO permissions (module_code, permission_name, description, status) VALUES (?,?,?, 'Active')",
                  (mod, mod, mod))

    for role_name, access_map in role_access.items():
        role = c.execute("SELECT id FROM roles WHERE name=?", (role_name,)).fetchone()
        if not role:
            continue
        for mod_name, access_level in access_map.items():
            perm = c.execute("SELECT id FROM permissions WHERE module_code=?", (mod_name,)).fetchone()
            if perm:
                existing = c.execute("SELECT id FROM role_permissions WHERE role_id=? AND permission_id=?", (role['id'], perm['id'])).fetchone()
                if not existing:
                    c.execute("INSERT INTO role_permissions (role_id, permission_id, access_level) VALUES (?,?,?)",
                              (role['id'], perm['id'], access_level))

def seed_users(c):
    users = [
        ('Super Admin', 'superadmin', 'superadmin123', 'Super Admin'),
        ('Admin User', 'admin', 'admin123', 'Admin'),
        ('Payroll Manager', 'payroll', 'payroll123', 'Payroll Manager'),
        ('HR User', 'hr', 'hr123', 'HR User'),
        ('Finance User', 'finance', 'finance123', 'Finance User'),
        ('Viewer User', 'viewer', 'viewer123', 'Viewer'),
    ]
    for uname, username, pw, role in users:
        existing = c.execute("SELECT user_id FROM users WHERE username=?", (username,)).fetchone()
        if not existing:
            c.execute("INSERT INTO users (full_name, username, password_hash, role, status) VALUES (?,?,?,?, 'Active')",
                      (uname, username, hash_password(pw), role))

def seed_tax_data(c):
    c.execute("SELECT id FROM tax_laws WHERE name='Egypt Current Income Tax Setup 2024/2026'").fetchone()

    c.execute('''INSERT OR IGNORE INTO tax_laws (id, name, law_number, effective_from, is_default, status)
        VALUES (1, 'Egypt Income Tax Law 175/2023', '175/2023', '2023-10-31', 0, 'Active')''')
    c.execute('''INSERT OR IGNORE INTO tax_laws (id, name, law_number, effective_from, is_default, status)
        VALUES (2, 'Egypt Current Income Tax Setup 2024/2026', 'Law 7/2024 / Current', '2024-02-21', 1, 'Active')''')

    law175_brackets = [
        (1, 2023, 0, 30000, 0, 1),
        (1, 2023, 30000, 45000, 0.10, 2),
        (1, 2023, 45000, 60000, 0.15, 3),
        (1, 2023, 60000, 200000, 0.20, 4),
        (1, 2023, 200000, 400000, 0.225, 5),
        (1, 2023, 400000, 1200000, 0.25, 6),
        (1, 2023, 1200000, 999999999, 0.275, 7),
    ]
    for b in law175_brackets:
        existing = c.execute("SELECT id FROM tax_brackets WHERE tax_law_id=? AND bracket_order=?", (b[0], b[5])).fetchone()
        if not existing:
            c.execute("INSERT INTO tax_brackets (tax_law_id, year, income_from, income_to, tax_rate, bracket_order, status) VALUES (?,?,?,?,?,?, 'Active')", b)

    current_brackets = [
        (2, 2024, 0, 40000, 0, 1),
        (2, 2024, 40000, 55000, 0.10, 2),
        (2, 2024, 55000, 70000, 0.15, 3),
        (2, 2024, 70000, 200000, 0.20, 4),
        (2, 2024, 200000, 400000, 0.225, 5),
        (2, 2024, 400000, 1200000, 0.25, 6),
        (2, 2024, 1200000, 999999999, 0.275, 7),
    ]
    for b in current_brackets:
        existing = c.execute("SELECT id FROM tax_brackets WHERE tax_law_id=? AND bracket_order=?", (b[0], b[5])).fetchone()
        if not existing:
            c.execute("INSERT INTO tax_brackets (tax_law_id, year, income_from, income_to, tax_rate, bracket_order, status) VALUES (?,?,?,?,?,?, 'Active')", b)

    c.execute("INSERT OR IGNORE INTO tax_exemptions (tax_law_id, year, personal_exemption_annual, additional_exemption_annual, tax_free_bracket_annual, total_annual_exemption, round_down_to_10, status) VALUES (1, 2023, 15000, 0, 0, 15000, 1, 'Active')")
    c.execute("INSERT OR IGNORE INTO tax_exemptions (tax_law_id, year, personal_exemption_annual, additional_exemption_annual, tax_free_bracket_annual, total_annual_exemption, round_down_to_10, status) VALUES (2, 2024, 20000, 0, 0, 20000, 1, 'Active')")
    c.execute("INSERT OR IGNORE INTO tax_exemptions (tax_law_id, year, personal_exemption_annual, additional_exemption_annual, tax_free_bracket_annual, total_annual_exemption, round_down_to_10, status) VALUES (2, 2025, 20000, 0, 0, 20000, 1, 'Active')")
    c.execute("INSERT OR IGNORE INTO tax_exemptions (tax_law_id, year, personal_exemption_annual, additional_exemption_annual, tax_free_bracket_annual, total_annual_exemption, round_down_to_10, status) VALUES (2, 2026, 20000, 0, 0, 20000, 1, 'Active')")

def seed_insurance_data(c):
    existing = c.execute("SELECT id FROM social_insurance_setup WHERE year=2024").fetchone()
    if not existing:
        c.execute('''INSERT INTO social_insurance_setup (year, effective_from, effective_to, min_insurance_salary, max_insurance_salary, employee_share_pct, company_share_pct, insurance_base_source, status)
            VALUES (2024, '2024-01-01', '2024-12-31', 2600, 16700, 0.11, 0.1875, 'Employee Insurance Salary/Base', 'Active')''')
    existing = c.execute("SELECT id FROM social_insurance_setup WHERE year=2025").fetchone()
    if not existing:
        c.execute('''INSERT INTO social_insurance_setup (year, effective_from, effective_to, min_insurance_salary, max_insurance_salary, employee_share_pct, company_share_pct, insurance_base_source, status)
            VALUES (2025, '2025-01-01', '2025-12-31', 2600, 16700, 0.11, 0.1875, 'Employee Insurance Salary/Base', 'Active')''')
    existing = c.execute("SELECT id FROM social_insurance_setup WHERE year=2026").fetchone()
    if not existing:
        c.execute('''INSERT INTO social_insurance_setup (year, effective_from, effective_to, min_insurance_salary, max_insurance_salary, employee_share_pct, company_share_pct, insurance_base_source, status)
            VALUES (2026, '2026-01-01', '2026-12-31', 2600, 16700, 0.11, 0.1875, 'Employee Insurance Salary/Base', 'Active')''')

def seed_calculation_setup(c):
    existing = c.execute("SELECT id FROM salary_calculation_setup").fetchone()
    if not existing:
        c.execute("INSERT INTO salary_calculation_setup (basic_salary_source, basic_pct, insurance_base_source, include_taxable_allowances_in_insurance, include_gross_allowances_in_insurance, gross_up_tolerance, max_iterations, status) VALUES ('Manual Basic Salary from Employee Master Data', 0, 'Manual Insurance Salary/Base from employee', 'No', 'No', 1.0, 100, 'Active')")
    else:
        c.execute("UPDATE salary_calculation_setup SET basic_pct=basic_pct_from_gross WHERE basic_pct IS NULL OR basic_pct=0")
        c.execute("UPDATE salary_calculation_setup SET include_taxable_allowances_in_insurance='No' WHERE include_taxable_allowances_in_insurance IS NULL")
        c.execute("UPDATE salary_calculation_setup SET include_gross_allowances_in_insurance='No' WHERE include_gross_allowances_in_insurance IS NULL")
