import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')
try: os.remove('payroll.db')
except: pass
from payroll_app.database import DatabaseManager, get_db
from payroll_app.database import get_conn
db = DatabaseManager()
with get_db() as w:
    cols = w.execute("PRAGMA table_info(employee_bonuses)").fetchall()
    print('employee_bonuses columns:')
    for c in cols:
        print(f'  {c[1]} ({c[2]})')
