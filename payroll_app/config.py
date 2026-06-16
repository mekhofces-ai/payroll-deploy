import os

APP_NAME = "Payroll Management System"
APP_VERSION = "1.0.0"
COMPANY_NAME = "Payroll Pro"
CURRENCY = "EGP"
CURRENCY_SYMBOL = "E£"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "payroll.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(BACKUP_DIR, exist_ok=True)

TAX_LAW_175 = {
    "name": "Egypt Income Tax Law 175/2023",
    "law_number": "175/2023",
    "effective_from": "2023-10-31",
    "personal_exemption": 15000,
    "additional_exemption": 0,
    "tax_free_bracket": 30000,
    "round_down_to_10": True,
    "brackets": [
        (0, 30000, 0),
        (30000, 45000, 0.10),
        (45000, 60000, 0.15),
        (60000, 200000, 0.20),
        (200000, 400000, 0.225),
        (400000, 1200000, 0.25),
        (1200000, float('inf'), 0.275),
    ]
}

TAX_CURRENT = {
    "name": "Egypt Current Income Tax Setup 2024/2026",
    "law_number": "Law 7/2024 / Current",
    "effective_from": "2024-02-21",
    "personal_exemption": 20000,
    "additional_exemption": 20000,
    "tax_free_bracket": 40000,
    "round_down_to_10": True,
    "brackets": [
        (0, 40000, 0),
        (40000, 55000, 0.10),
        (55000, 70000, 0.15),
        (70000, 200000, 0.20),
        (200000, 400000, 0.225),
        (400000, 1200000, 0.25),
        (1200000, float('inf'), 0.275),
    ]
}

DEFAULT_INSURANCE = {
    "min_salary": 2600,
    "max_salary": 16700,
    "employee_share": 0.11,
    "company_share": 0.1875,
}

SIDEBAR_GROUPS = {
    "Executive": ["Executive Dashboard", "Alerts Center", "Scenario Simulation"],
    "Employees": ["Employees", "Employee Allowances", "Project Allocation", "Salary Revisions", "Documents"],
    "Payroll": ["Payroll Run Center", "Payroll Transactions", "Payroll Project Allocation", "Bank Transfer", "Bank Reconciliation", "Payslips"],
    "Bonus": ["Bonus Calculator", "Bonus Register", "Bonus Reports"],
    "Reports": ["Monthly Reports", "Yearly Summary", "Project Summary", "Variance Report", "Executive Reports Package"],
    "Setup": ["Payroll Setup", "Projects", "Organizations", "Users & Permissions", "Backup & Restore", "Audit Log"],
}

PERMISSION_MODULES = [
    "Executive Dashboard", "Projects", "Employees", "Employee Project Allocation",
    "Employee Allowances", "Payroll Setup", "Payroll Run Center", "Payroll Transactions",
    "Payroll Project Cost Allocation", "Net to Gross Calculator", "Bonus Calculator",
    "Bonus Register", "Bonus Reports", "Yearly Summary", "Project Yearly Summary",
    "Reports", "Import / Export", "Data Quality Center", "Audit Log", "Users & Permissions"
]

ACCESS_LEVELS = ["No Access", "View Only", "Add", "Edit", "Disable", "Export", "Approve", "Full Access"]

MONTHS_AR = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}
