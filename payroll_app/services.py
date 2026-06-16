import math
from datetime import datetime
from .database import get_db

def get_tax_setup(tax_law_id=None, year=None):
    with get_db() as db:
        if tax_law_id:
            law = db.execute("SELECT * FROM tax_laws WHERE id=? AND status='Active'", (tax_law_id,)).fetchone()
        else:
            law = db.execute("SELECT * FROM tax_laws WHERE is_default=1 AND status='Active'").fetchone()
        if not law:
            law = db.execute("SELECT * FROM tax_laws WHERE status='Active' LIMIT 1").fetchone()
        if not law:
            return None
        year = year or datetime.now().year
        brackets = db.execute("SELECT * FROM tax_brackets WHERE tax_law_id=? AND year=? AND status='Active' ORDER BY bracket_order",
                              (law['id'], year)).fetchall()
        if not brackets:
            latest = db.execute("SELECT MAX(year) as my FROM tax_brackets WHERE tax_law_id=? AND status='Active'", (law['id'],)).fetchone()
            if latest and latest['my']:
                brackets = db.execute("SELECT * FROM tax_brackets WHERE tax_law_id=? AND year=? AND status='Active' ORDER BY bracket_order",
                                      (law['id'], latest['my'])).fetchall()
        exemption = db.execute("SELECT * FROM tax_exemptions WHERE tax_law_id=? AND year=? AND status='Active'",
                               (law['id'], year)).fetchone()
        if not exemption:
            exemption = db.execute("SELECT * FROM tax_exemptions WHERE tax_law_id=? AND status='Active' ORDER BY year DESC LIMIT 1",
                                   (law['id'],)).fetchone()
        return {
            'law': dict(law) if law else None,
            'brackets': [dict(b) for b in brackets],
            'exemption': dict(exemption) if exemption else None
        }

def get_insurance_setup(year=None):
    with get_db() as db:
        year = year or datetime.now().year
        setup = db.execute("SELECT * FROM social_insurance_setup WHERE year=? AND status='Active'", (year,)).fetchone()
        if not setup:
            setup = db.execute("SELECT * FROM social_insurance_setup WHERE status='Active' ORDER BY year DESC LIMIT 1").fetchone()
        return dict(setup) if setup else None

def get_calculation_setup():
    with get_db() as db:
        setup = db.execute("SELECT * FROM salary_calculation_setup WHERE status='Active' LIMIT 1").fetchone()
        if not setup:
            setup = db.execute("SELECT * FROM salary_calculation_setup LIMIT 1").fetchone()
        return dict(setup) if setup else {
            'basic_salary_source': 'Manual Basic Salary from Employee Master Data',
            'basic_pct': 0,
            'insurance_base_source': 'Manual Insurance Salary/Base from employee',
            'include_taxable_allowances_in_insurance': 'No',
            'include_gross_allowances_in_insurance': 'No',
            'gross_up_tolerance': 1.0,
            'max_iterations': 100,
        }

def get_basic_salary(employee, gross_salary, total_net_earning, setup, override=None):
    if override is not None and override > 0:
        return override
    source = setup.get('basic_salary_source', 'Manual Basic Salary from Employee Master Data')
    manual = employee.get('basic_salary', 0) or 0

    if source == 'Manual Basic Salary from Employee Master Data':
        if manual > 0:
            return manual
        return gross_salary * 0.7

    elif source == 'Equal to Gross Salary excluding allowances':
        return gross_salary

    elif source == 'Equal to Gross Salary including allowances':
        return gross_salary

    elif source == 'Percentage of Gross Salary':
        pct = setup.get('basic_pct', 0) or 0
        return gross_salary * pct

    elif source == 'Percentage of Net Salary':
        pct = setup.get('basic_pct', 0) or 0
        base_net = employee.get('new_net_salary', 0) or 0
        return base_net * pct

    elif source == 'Fixed formula from setup':
        return gross_salary * 0.7

    else:
        if manual > 0:
            return manual
        return gross_salary * 0.7

def get_insurance_base(employee, basic_salary, gross_salary, total_net_earning, setup, insurance_setup,
                       net_allowances=0, gross_allowances=0):
    source = setup.get('insurance_base_source', 'Manual Insurance Salary/Base from employee')
    manual_ins = employee.get('insurance_salary_base', 0) or 0

    total_gross_allowances = gross_allowances
    if setup.get('include_gross_allowances_in_insurance', 'No') != 'Yes':
        total_gross_allowances = 0

    if source == 'Manual Insurance Salary/Base from employee':
        base = manual_ins if manual_ins > 0 else basic_salary
    elif source == 'Basic Salary':
        base = basic_salary
    elif source == 'Gross Salary excluding allowances':
        base = gross_salary
    elif source == 'Gross Salary including allowances':
        base = gross_salary + total_gross_allowances
    elif source == 'Net Salary':
        base = employee.get('new_net_salary', 0) or 0
    elif source == 'Net Earning':
        base = total_net_earning
    elif source == 'No Insurance':
        return 0, 0, 0, 0
    else:
        base = manual_ins if manual_ins > 0 else basic_salary

    base_before = base

    if insurance_setup:
        min_sal = insurance_setup['min_insurance_salary']
        max_sal = insurance_setup['max_insurance_salary']
        if base < min_sal:
            base = min_sal
        elif base > max_sal:
            base = max_sal

    return base_before, base, 0, 0

def calculate_insurance(employee, year, insurance_override=None, basic_salary=None, gross_salary=None,
                        total_net_earning=None, net_allowances=0, gross_allowances=0):
    setup = get_calculation_setup()
    insurance_setup = get_insurance_setup(year)

    if not insurance_setup:
        return {'employee_insurance': 0, 'company_insurance': 0, 'base_before': 0, 'base_after': 0,
                'emp_share_pct': 0, 'comp_share_pct': 0, 'min_sal': 0, 'max_sal': 999999}

    if insurance_override is not None and insurance_override > 0:
        base_before = insurance_override
        base = insurance_override
        min_sal = insurance_setup.get('min_insurance_salary', 0)
        max_sal = insurance_setup.get('max_insurance_salary', 999999)
        if base < min_sal:
            base = min_sal
        elif base > max_sal:
            base = max_sal
    else:
        base_before, base, _, _ = get_insurance_base(
            employee, basic_salary or 0, gross_salary or 0, total_net_earning or 0,
            setup, insurance_setup, net_allowances, gross_allowances
        )

    emp_ins = base * insurance_setup['employee_share_pct']
    comp_ins = base * insurance_setup['company_share_pct']

    return {
        'employee_insurance': round(emp_ins, 2),
        'company_insurance': round(comp_ins, 2),
        'base_before': round(base_before, 2),
        'base_after': round(base, 2),
        'emp_share_pct': insurance_setup['employee_share_pct'],
        'comp_share_pct': insurance_setup['company_share_pct'],
        'min_sal': insurance_setup['min_insurance_salary'],
        'max_sal': insurance_setup['max_insurance_salary'],
    }

def calculate_tax(annual_gross_income, employee_annual_insurance, tax_law_id=None, year=None,
                  personal_exemption_override=None, additional_exemption_override=None,
                  taxable_allowances=0, non_taxable_allowances=0):
    setup = get_tax_setup(tax_law_id, year)
    if not setup or not setup['exemption']:
        return {'annual_tax': 0, 'monthly_tax': 0, 'effective_rate': 0, 'brackets': [], 'annual_taxable_income': 0}

    ex = setup['exemption']
    personal_ex = personal_exemption_override or ex['personal_exemption_annual'] or 0
    additional_ex = additional_exemption_override or ex['additional_exemption_annual'] or 0
    tax_free = ex['tax_free_bracket_annual'] or 0
    round_down = bool(ex['round_down_to_10'])

    annual_taxable = annual_gross_income - employee_annual_insurance
    if annual_taxable < 0:
        annual_taxable = 0

    total_exemption = personal_ex + additional_ex
    after_exemption = annual_taxable - total_exemption
    if after_exemption < 0:
        after_exemption = 0

    tax_free_used = min(tax_free, after_exemption)
    final_taxable = after_exemption - tax_free_used
    if final_taxable < 0:
        final_taxable = 0

    if round_down:
        final_taxable = math.floor(final_taxable / 10) * 10

    brackets = setup['brackets']
    annual_income = final_taxable

    if annual_income <= 600000:
        pass
    elif annual_income <= 700000:
        brackets = [b for b in brackets if b['income_from'] >= 40000]
    elif annual_income <= 800000:
        brackets = [b for b in brackets if b['income_from'] >= 55000]
    elif annual_income <= 900000:
        brackets = [b for b in brackets if b['income_from'] >= 70000]
    elif annual_income <= 1200000:
        brackets = [b for b in brackets if b['income_from'] >= 200000]
    else:
        for b in brackets:
            if b['income_to'] >= 1200000:
                annual_tax = annual_income * b['tax_rate']
                bracket_details = [{'bracket': b, 'taxable_in_bracket': annual_income, 'tax': annual_tax, 'rate': b['tax_rate']}]
                monthly_tax = annual_tax / 12
                return {
                    'annual_tax': round(annual_tax, 2),
                    'monthly_tax': round(monthly_tax, 2),
                    'effective_rate': round((annual_tax / annual_gross_income * 100) if annual_gross_income > 0 else 0, 2),
                    'brackets': bracket_details,
                    'annual_taxable_income': round(final_taxable, 2),
                    'personal_exemption_used': personal_ex,
                    'additional_exemption_used': additional_ex,
                    'tax_free_used': tax_free_used,
                    'total_exemption': total_exemption + tax_free_used
                }

    annual_tax = 0
    bracket_details = []
    remaining = annual_income

    for b in brackets:
        if remaining <= 0:
            break
        b_from = b['income_from']
        b_to = b['income_to']
        if b_to > 100000000:
            b_to = remaining + b_from
        bracket_size = min(b_to - b_from, remaining)
        if bracket_size < 0:
            bracket_size = 0
        if bracket_size > 0:
            bracket_tax = bracket_size * b['tax_rate']
            annual_tax += bracket_tax
            bracket_details.append({
                'bracket': b,
                'taxable_in_bracket': round(bracket_size, 2),
                'tax': round(bracket_tax, 2),
                'rate': b['tax_rate']
            })
            remaining -= bracket_size

    monthly_tax = annual_tax / 12
    effective_rate = (annual_tax / annual_gross_income * 100) if annual_gross_income > 0 else 0

    return {
        'annual_tax': round(annual_tax, 2),
        'monthly_tax': round(monthly_tax, 2),
        'effective_rate': round(effective_rate, 2),
        'brackets': bracket_details,
        'annual_taxable_income': round(final_taxable, 2),
        'personal_exemption_used': personal_ex,
        'additional_exemption_used': additional_ex,
        'tax_free_used': tax_free_used,
        'total_exemption': total_exemption + tax_free_used
    }

def _get_marginal_rate(tax_setup, annual_taxable_income):
    """Determine marginal tax rate for given annual taxable income."""
    brackets = tax_setup['brackets']
    if not brackets:
        return 0

    thresh = annual_taxable_income
    if thresh <= 600000:
        pass
    elif thresh <= 700000:
        brackets = [b for b in brackets if b['income_from'] >= 40000]
    elif thresh <= 800000:
        brackets = [b for b in brackets if b['income_from'] >= 55000]
    elif thresh <= 900000:
        brackets = [b for b in brackets if b['income_from'] >= 70000]
    elif thresh <= 1200000:
        brackets = [b for b in brackets if b['income_from'] >= 200000]
    else:
        return next((b['tax_rate'] for b in reversed(brackets)
                     if b['income_to'] >= 1200000), 0.25)

    for b in sorted(brackets, key=lambda x: x['income_from'], reverse=True):
        if thresh >= b['income_from']:
            return b['tax_rate']
    return 0

def net_to_gross(target_net_earning, employee, year, month, tax_law_id=None,
                 net_allowances=0, gross_allowances=0, basic_override=None, insurance_override=None):
    setup = get_calculation_setup()
    tolerance = setup['gross_up_tolerance'] if setup else 1.0
    max_iter = setup['max_iterations'] if setup else 100
    tax_setup = get_tax_setup(tax_law_id, year)
    ex = (tax_setup or {}).get('exemption') or {}
    personal_ex = ex.get('personal_exemption_annual', 0) or 0
    additional_ex = ex.get('additional_exemption_annual', 0) or 0
    tax_free = ex.get('tax_free_bracket_annual', 0) or 0
    total_fixed_exemption = personal_ex + additional_ex + tax_free

    base_emp_ins = 0
    est = target_net_earning * 1.3
    if est < target_net_earning + 1000:
        est = target_net_earning + 1000

    for i in range(max_iter):
        basic_salary = get_basic_salary(employee, est, target_net_earning, setup, basic_override)
        ins_result = calculate_insurance(
            employee, year, insurance_override, basic_salary, est,
            target_net_earning, net_allowances, gross_allowances
        )
        emp_ins = ins_result['employee_insurance']
        base_emp_ins = emp_ins  # store for final use

        annual_gross = est * 12
        annual_ins = emp_ins * 12
        tax_result = calculate_tax(annual_gross, annual_ins, tax_law_id, year)
        monthly_tax = tax_result['monthly_tax']
        comp_ins = ins_result['company_insurance']

        calculated_net = est - monthly_tax - emp_ins
        diff = target_net_earning - calculated_net

        if abs(diff) <= tolerance:
            break

        annual_taxable = max(0, annual_gross - annual_ins - total_fixed_exemption)
        marginal_rate = _get_marginal_rate(tax_setup, annual_taxable) if tax_setup else 0
        denom = max(0.01, 1 - marginal_rate)
        adjustment = diff / denom
        est += adjustment
        if est < target_net_earning:
            est = target_net_earning + 100

    total_deductions = monthly_tax + base_emp_ins
    final_net = est - total_deductions
    total_company_cost = est + comp_ins
    basic_salary = get_basic_salary(employee, est, target_net_earning, setup, basic_override)

    return {
        'target_net_earning': round(target_net_earning, 2),
        'estimated_gross': round(est, 2),
        'basic_salary': round(basic_salary, 2),
        'insurance_base_before': ins_result['base_before'],
        'insurance_base_after': ins_result['base_after'],
        'employee_insurance': round(base_emp_ins, 2),
        'company_insurance': round(comp_ins, 2),
        'monthly_tax': round(monthly_tax, 2),
        'annual_tax': round(tax_result['annual_tax'], 2),
        'total_deductions': round(total_deductions, 2),
        'final_net': round(final_net, 2),
        'total_company_cost': round(total_company_cost, 2),
        'diff_from_target': round(target_net_earning - final_net, 2),
        'annual_taxable_income': tax_result['annual_taxable_income'],
        'effective_tax_rate': tax_result['effective_rate'],
        'tax_brackets': tax_result['brackets'],
        'personal_exemption_used': tax_result.get('personal_exemption_used', 0),
        'additional_exemption_used': tax_result.get('additional_exemption_used', 0),
        'tax_free_used': tax_result.get('tax_free_used', 0),
    }

def calculate_payroll_for_employee(employee_code, year, month, tax_law_id=None,
                                    include_onetime=True, basic_override=None, insurance_override=None):
    with get_db() as db:
        emp = db.execute("SELECT * FROM employees WHERE employee_code=? AND status='Active'", (employee_code,)).fetchone()
        if not emp:
            return None
        emp = dict(emp)

        allowances = db.execute('''SELECT * FROM employee_allowances 
            WHERE employee_code=? AND status='Active' AND (recurring='Monthly' OR (recurring='One Time' AND ?))
            AND (effective_from='' OR effective_from<=date('now','localtime'))
            AND (effective_to='' OR effective_to>=date('now','localtime'))''',
                                (employee_code, 1 if include_onetime else 0)).fetchall()

        net_allowances_total = 0
        gross_allowances_total = 0
        recurring_net = 0
        recurring_gross = 0
        onetime_net = 0
        onetime_gross = 0

        for a in allowances:
            a = dict(a)
            amt = a['amount']
            if a['payment_type'] == 'Net':
                if a['recurring'] == 'One Time':
                    onetime_net += amt
                else:
                    recurring_net += amt
                net_allowances_total += amt
            else:
                if a['recurring'] == 'One Time':
                    onetime_gross += amt
                else:
                    recurring_gross += amt
                gross_allowances_total += amt

        base_net_salary = emp['new_net_salary']
        total_net_earning = base_net_salary + net_allowances_total

        ng_result = net_to_gross(
            total_net_earning, emp, year, month, tax_law_id,
            net_allowances=net_allowances_total, gross_allowances=gross_allowances_total,
            basic_override=basic_override, insurance_override=insurance_override
        )

        allocated_gross = ng_result['estimated_gross'] + gross_allowances_total

        allocations = db.execute('''SELECT * FROM employee_project_allocations 
            WHERE employee_code=? AND status='Active'
            AND (effective_from='' OR effective_from<=date('now','localtime'))
            AND (effective_to='' OR effective_to>=date('now','localtime'))''',
                                 (employee_code,)).fetchall()

        if not allocations:
            default_proj = emp['default_project']
            if default_proj:
                allocations = [{'project_code': default_proj, 'percentage': 100, 'allocation_type': 'Percentage'}]

        total_pct = sum(a['percentage'] for a in allocations if a['allocation_type'] == 'Percentage')
        if total_pct == 0:
            total_pct = 100

        proj_allocations = []
        for a in allocations:
            a = dict(a)
            pct = a['percentage'] / total_pct if total_pct > 0 else 0
            proj_allocations.append({
                'project_code': a['project_code'],
                'percent': round(pct * 100, 2),
                'allocated_net': round(ng_result['final_net'] * pct, 2),
                'allocated_allowances': round((net_allowances_total + gross_allowances_total) * pct, 2),
                'allocated_gross': round(allocated_gross * pct, 2),
                'allocated_tax': round(ng_result['monthly_tax'] * pct, 2),
                'allocated_emp_ins': round(ng_result['employee_insurance'] * pct, 2),
                'allocated_comp_ins': round(ng_result['company_insurance'] * pct, 2),
                'allocated_cost': round(ng_result['total_company_cost'] * pct, 2),
            })

        return {
            'employee': emp,
            'base_net_salary': base_net_salary,
            'recurring_net_allowances': round(recurring_net, 2),
            'recurring_gross_allowances': round(recurring_gross, 2),
            'onetime_net_allowances': round(onetime_net, 2),
            'onetime_gross_allowances': round(onetime_gross, 2),
            'net_allowances': round(net_allowances_total, 2),
            'gross_allowances': round(gross_allowances_total, 2),
            'total_allowances': round(net_allowances_total + gross_allowances_total, 2),
            'total_net_earning': round(total_net_earning, 2),
            'estimated_gross': ng_result['estimated_gross'],
            'allocated_gross': round(allocated_gross, 2),
            'basic_salary': ng_result['basic_salary'],
            'insurance_base_before': ng_result['insurance_base_before'],
            'insurance_base_after': ng_result['insurance_base_after'],
            'employee_insurance': ng_result['employee_insurance'],
            'company_insurance': ng_result['company_insurance'],
            'taxable_amount': ng_result['annual_taxable_income'],
            'monthly_tax': ng_result['monthly_tax'],
            'annual_tax': ng_result['annual_tax'],
            'total_deductions': ng_result['total_deductions'],
            'net_transfer_amount': ng_result['final_net'],
            'total_company_cost': ng_result['total_company_cost'],
            'project_allocations': proj_allocations,
            'tax_details': {
                'annual_taxable_income': ng_result['annual_taxable_income'],
                'effective_rate': ng_result['effective_tax_rate'],
                'personal_exemption': ng_result['personal_exemption_used'],
                'additional_exemption': ng_result['additional_exemption_used'],
                'tax_free_bracket': ng_result['tax_free_used'],
            }
        }

def calculate_bonus_cost(employee_code, bonus_type, bonus_amount, year, month, tax_law_id=None):
    with get_db() as db:
        emp = db.execute("SELECT * FROM employees WHERE employee_code=? AND status='Active'", (employee_code,)).fetchone()
        if not emp:
            return None
        emp = dict(emp)

        allowances = db.execute("SELECT * FROM employee_allowances WHERE employee_code=? AND status='Active' AND recurring='Monthly'",
                                (employee_code,)).fetchall()
        net_allowances = sum(a['amount'] for a in allowances if a['payment_type'] == 'Net')
        gross_allowances = sum(a['amount'] for a in allowances if a['payment_type'] == 'Gross')
        total_net_earning = (emp['new_net_salary'] or 0) + net_allowances

        current_result = net_to_gross(total_net_earning, emp, year, month, tax_law_id,
                                       net_allowances=net_allowances, gross_allowances=gross_allowances)
        current_gross = current_result['estimated_gross']
        current_net = current_result['final_net']
        current_emp_ins = current_result['employee_insurance']
        current_comp_ins = current_result['company_insurance']
        current_comp_cost = current_result['total_company_cost']
        current_tax = current_result['monthly_tax']

        current_basic = current_result['basic_salary']
        current_ins_base = current_result['insurance_base_after']

        if bonus_type == 'Net Bonus':
            new_total_net_earning = total_net_earning + bonus_amount
            new_result = net_to_gross(new_total_net_earning, emp, year, month, tax_law_id,
                                       net_allowances=net_allowances + bonus_amount,
                                       gross_allowances=gross_allowances,
                                       basic_override=current_basic,
                                       insurance_override=current_ins_base)
            new_gross = new_result['estimated_gross']
            new_net = new_result['final_net']
            new_emp_ins = new_result['employee_insurance']
            new_comp_ins = new_result['company_insurance']
            new_comp_cost = new_result['total_company_cost']
            new_tax = new_result['monthly_tax']
            net_bonus_amt = bonus_amount
            gross_bonus_amt = new_gross - current_gross
        else:
            new_gross = current_gross + bonus_amount
            basic_salary = current_basic
            ins = calculate_insurance(emp, year, current_ins_base, basic_salary, new_gross,
                                       total_net_earning, net_allowances, gross_allowances + bonus_amount)
            annual_gross_new = new_gross * 12
            annual_ins_new = ins['employee_insurance'] * 12
            tax_res = calculate_tax(annual_gross_new, annual_ins_new, tax_law_id, year)
            new_net = new_gross - ins['employee_insurance'] - tax_res['monthly_tax']
            new_emp_ins = ins['employee_insurance']
            new_comp_ins = ins['company_insurance']
            new_comp_cost = new_gross + ins['company_insurance']
            new_tax = tax_res['monthly_tax']
            gross_bonus_amt = bonus_amount
            net_bonus_amt = new_net - current_net

        return {
            'employee_code': employee_code,
            'arabic_name': emp['arabic_name'],
            'bonus_type': bonus_type,
            'bonus_amount_entered': bonus_amount,
            'net_bonus_amount': round(net_bonus_amt, 2),
            'gross_bonus_amount': round(gross_bonus_amt, 2),
            'gross_before': round(current_gross, 2),
            'gross_after': round(new_gross, 2),
            'gross_diff': round(new_gross - current_gross, 2),
            'net_before': round(current_net, 2),
            'net_after': round(new_net, 2),
            'net_increase': round(new_net - current_net, 2),
            'tax_before': round(current_tax, 2),
            'tax_after': round(new_tax, 2),
            'tax_diff': round(new_tax - current_tax, 2),
            'emp_ins_before': round(current_emp_ins, 2),
            'emp_ins_after': round(new_emp_ins, 2),
            'emp_ins_diff': round(new_emp_ins - current_emp_ins, 2),
            'comp_ins_before': round(current_comp_ins, 2),
            'comp_ins_after': round(new_comp_ins, 2),
            'comp_ins_diff': round(new_comp_ins - current_comp_ins, 2),
            'comp_cost_before': round(current_comp_cost, 2),
            'comp_cost_after': round(new_comp_cost, 2),
            'comp_cost_diff': round(new_comp_cost - current_comp_cost, 2),
        }

def generate_payroll(year, month, project_filter=None, department_filter=None, sponsor_filter=None, tax_law_id=None):
    with get_db() as db:
        query = "SELECT * FROM employees WHERE status='Active'"
        params = []
        if project_filter:
            query += " AND default_project=?"
            params.append(project_filter)
        if department_filter:
            query += " AND department=?"
            params.append(department_filter)
        if sponsor_filter:
            query += " AND sponsor=?"
            params.append(sponsor_filter)

        employees = db.execute(query, params).fetchall()
        results = []
        existing = db.execute("SELECT employee_code FROM payroll_transactions WHERE year=? AND month=?", (year, month)).fetchall()
        existing_codes = set(e['employee_code'] for e in existing)

        run = db.execute("SELECT id FROM payroll_runs WHERE year=? AND month=?", (year, month)).fetchone()
        if not run:
            db.execute("INSERT INTO payroll_runs (year, month, status, project_filter, department_filter, sponsor_filter, created_by) VALUES (?,?,'Generated',?,?,?,?)",
                       (year, month, project_filter or '', department_filter or '', sponsor_filter or '', 'system'))
        else:
            db.execute("UPDATE payroll_runs SET status='Generated', updated_at=datetime('now','localtime') WHERE id=?", (run['id'],))

        for emp in employees:
            code = emp['employee_code']
            if code in existing_codes:
                continue
            result = calculate_payroll_for_employee(code, year, month, tax_law_id)
            if not result:
                continue
            result['employee_code'] = code
            results.append(result)
            db.execute('''INSERT OR REPLACE INTO payroll_transactions 
                (year, month, employee_code, arabic_name, organization, sponsor, position, department, section,
                 default_project, base_net_salary, recurring_net_allowances, recurring_gross_allowances,
                 onetime_net_allowances, onetime_gross_allowances, total_allowances, net_earning,
                 estimated_gross, basic_salary, insurance_base_before, insurance_base_after,
                 employee_insurance, company_insurance, taxable_amount, monthly_tax, annual_tax,
                 total_deductions, net_transfer_amount, total_company_cost, payment_status, approval_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Pending','Draft')''',
                       (year, month, code, result['employee']['arabic_name'],
                        result['employee']['organization'], result['employee']['sponsor'],
                        result['employee']['position'], result['employee']['department'],
                        result['employee']['section'], result['employee']['default_project'],
                        result['base_net_salary'], result['recurring_net_allowances'],
                        result['recurring_gross_allowances'], result['onetime_net_allowances'],
                        result['onetime_gross_allowances'], result['total_allowances'],
                        result['total_net_earning'], result['estimated_gross'], result['basic_salary'],
                        result['insurance_base_before'], result['insurance_base_after'],
                        result['employee_insurance'], result['company_insurance'],
                        result['taxable_amount'], result['monthly_tax'], result['annual_tax'],
                        result['total_deductions'], result['net_transfer_amount'],
                        result['total_company_cost']))

            pt = db.execute("SELECT id FROM payroll_transactions WHERE employee_code=? AND year=? AND month=?",
                            (code, year, month)).fetchone()
            if pt:
                for pa in result['project_allocations']:
                    db.execute('''INSERT INTO payroll_project_allocations 
                        (payroll_transaction_id, year, month, employee_code, arabic_name, department, section,
                         project_code, allocation_percent, allocated_net_salary, allocated_allowances,
                         allocated_gross, allocated_tax, allocated_employee_insurance,
                         allocated_company_insurance, allocated_total_cost)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                               (pt['id'], year, month, code, result['employee']['arabic_name'],
                                result['employee']['department'], result['employee']['section'],
                                pa['project_code'], pa['percent'], pa['allocated_net'],
                                pa['allocated_allowances'], pa['allocated_gross'],
                                pa['allocated_tax'], pa['allocated_emp_ins'],
                                pa['allocated_comp_ins'], pa['allocated_cost']))

        return results

def recalculate_payroll(year, month, employee_code=None):
    with get_db() as db:
        if employee_code:
            transactions = db.execute("SELECT id, employee_code FROM payroll_transactions WHERE year=? AND month=? AND employee_code=?",
                                      (year, month, employee_code)).fetchall()
        else:
            transactions = db.execute("SELECT id, employee_code FROM payroll_transactions WHERE year=? AND month=?",
                                      (year, month)).fetchall()
        for t in transactions:
            db.execute("DELETE FROM payroll_project_allocations WHERE payroll_transaction_id=?", (t['id'],))
            db.execute("DELETE FROM payroll_transactions WHERE id=?", (t['id'],))
    return generate_payroll(year, month)

def get_employee_allocations_summary(employee_code):
    with get_db() as db:
        allocs = db.execute('''SELECT * FROM employee_project_allocations 
            WHERE employee_code=? AND status='Active' ORDER BY is_primary DESC''', (employee_code,)).fetchall()
        return [dict(a) for a in allocs]
