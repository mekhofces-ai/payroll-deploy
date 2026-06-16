import streamlit as st
import pandas as pd
from datetime import datetime
from ..database import get_db
from ..auth import check_permission
from ..ui import page_header, fmt_currency, status_badge, divider, footer, apply_custom_css, export_download_link

def show():
    apply_custom_css()
    page_header("Audit Log", "Track all sensitive system changes")

    if not check_permission('Audit Log', 'View Only'):
        st.error("Access denied.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        module_filter = st.selectbox("Module", ["All", "Employee", "Payroll", "Allowance", "Bonus", "Setup", "User", "Permission", "Import", "Export", "Login"], key="audit_mod")
    with c2:
        action_filter = st.selectbox("Action", ["All", "Created", "Updated", "Deleted", "Login", "Logout", "Generated", "Exported", "Imported", "Approved", "Rejected", "Closed", "Reopened", "Transferred"], key="audit_act")
    with c3:
        date_from = st.text_input("From Date (YYYY-MM-DD)", value="", key="audit_from")

    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if module_filter != "All":
        query += " AND module=?"
        params.append(module_filter)
    if action_filter != "All":
        query += " AND action=?"
        params.append(action_filter)
    if date_from:
        query += " AND timestamp >= ?"
        params.append(date_from)
    query += " ORDER BY timestamp DESC LIMIT 200"

    with get_db() as db:
        records = db.execute(query, params).fetchall()

    if records:
        data = []
        for r in records:
            d = dict(r)
            data.append(d)
        df = pd.DataFrame(data)
        cols = ['timestamp', 'username', 'action', 'module', 'table_name', 'record_id', 'reason']
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)
        export_download_link(df, f"audit_log_{datetime.now().strftime('%Y%m%d')}.xlsx")

        for r in records[:5]:
            r = dict(r)
            with st.expander(f"{r['timestamp']} - {r['action']} by {r['username']}"):
                st.write(f"**Module:** {r['module']} | **Table:** {r['table_name']} | **Record:** {r['record_id']}")
                st.write(f"**Reason:** {r['reason'] or 'N/A'}")
                if r.get('changed_fields'):
                    st.write(f"**Changed Fields:** {r['changed_fields']}")
                if r.get('old_values'):
                    st.write(f"**Old Values:** {r['old_values']}")
                if r.get('new_values'):
                    st.write(f"**New Values:** {r['new_values']}")
    else:
        st.info("No audit records found.")

    st.divider()
    st.subheader("Audit Summary")
    with get_db() as db:
        summary = db.execute('''SELECT action, COUNT(*) as count FROM audit_log 
            WHERE timestamp >= date('now','-30 days')
            GROUP BY action ORDER BY count DESC''').fetchall()
    if summary:
        st.dataframe(pd.DataFrame([dict(s) for s in summary]), use_container_width=True)
