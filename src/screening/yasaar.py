"""Conservative initial-entry filters; minimum amounts cannot establish a pass."""
from decimal import Decimal, InvalidOperation
from .source_facts import unique_amount

def minimum_check(components,assets,limit,inclusive=False,complete=False):
    """A lower bound can fail a ceiling; only an evidenced full total can pass.

    ``complete`` is an explicit evidence-review assertion, never inferred from
    the existence of a tag. The retained-source adapter leaves it False.
    """
    try:
        denominator=Decimal(assets['value']) if assets else Decimal('NaN')
        amounts=[Decimal(c['value']) for c in components]
        ceiling=Decimal(limit)
        valid=(denominator.is_finite() and denominator>0 and bool(amounts)
               and all(v.is_finite() and v>=0 for v in amounts)
               and ceiling.is_finite() and 0<ceiling<=1)
    except (InvalidOperation,ValueError,KeyError,TypeError):
        valid=False
    if not valid:
        return dict(status='needs_review',ratio=None,reason='Missing compatible amounts or positive assets',components=components)
    value=sum(amounts)
    ratio=value/denominator
    failed=ratio>ceiling if inclusive else ratio>=ceiling
    passed=complete is True and not failed
    return dict(status='fails_initial_filter' if failed else ('passes_filter' if passed else 'not_failed_on_available_amounts'),
        ratio=str(ratio),minimum_amount=str(value),components=components,
        completeness='complete_reviewed_total' if complete is True else 'lower_bound_only',
        reason=('Evidenced amount breaches the published limit' if failed else
                'Complete reviewed amount meets the published limit' if passed else
                'Incomplete amount cannot establish a pass'))


def debt_rule(amounts,assets,config,complete=False):
    return minimum_check(amounts,assets,config['debt_assets_limit'],complete=complete)


def cash_items_rule(amounts,assets,config,complete=False):
    return minimum_check(amounts,assets,config['cash_items_assets_limit'],complete=complete)


def receivables_cash_rule(amounts,assets,config,complete=False):
    return minimum_check(amounts,assets,config['receivables_cash_assets_limit'],complete=complete)


def income_rule(amounts,total_revenue,config,complete=False):
    return minimum_check(amounts,total_revenue,config['noncompliant_income_limit'],inclusive=True,complete=complete)


def business_revenue_rule(amounts,total_revenue,config,complete=False):
    return minimum_check(amounts,total_revenue,config['prohibited_business_revenue_limit'],inclusive=True,complete=complete)

def balance_checks(facts,end,config):
    assets=unique_amount(facts,'Assets',end)
    pick=lambda tag:unique_amount(facts,tag,end)
    debt_options=[]
    # Never sum a total and its components. Exclude mixed debt/lease tags pending mapping.
    for tag in ['DebtLongtermAndShorttermCombinedAmount','LongTermDebt','LongTermDebtNoncurrent','DebtCurrent','ShortTermBorrowings','CommercialPaper','LongTermNotesAndLoans','NotesPayableCurrent']:
        v=pick(tag)
        if v:debt_options.append([v])
    noncurrent,current=pick('LongTermDebtNoncurrent'),pick('LongTermDebtCurrent')
    if noncurrent and current:debt_options.append([noncurrent,current])
    current_all=pick('DebtCurrent')
    if noncurrent and current_all:debt_options.append([noncurrent,current_all])
    notes,notes_current=pick('LongTermNotesAndLoans'),pick('NotesPayableCurrent')
    if notes and notes_current:debt_options.append([notes,notes_current])
    # Subtract the whole issuer's finance-lease liability from a mixed subtotal.
    # This deliberately over-subtracts when the subtotal excludes current leases,
    # preserving a debt lower bound rather than treating all leases as interest debt.
    lease=pick('FinanceLeaseLiability')
    lc,ln=pick('FinanceLeaseLiabilityCurrent'),pick('FinanceLeaseLiabilityNoncurrent')
    if lease and lc and ln and Decimal(lease['value'])!=Decimal(lc['value'])+Decimal(ln['value']):
        lease=None;lc=None;ln=None
    if not lease and lc and ln:
        lease=dict(value=str(Decimal(lc['value'])+Decimal(ln['value'])),concept='FinanceLeaseLiabilityCurrentPlusNoncurrent',components=[lc,ln])
    if lease:
        for tag in ['LongTermDebtAndCapitalLeaseObligations','DebtAndCapitalLeaseObligations']:
            mixed=pick(tag)
            if mixed and Decimal(mixed['value'])>=Decimal(lease['value']):
                floor=dict(value=str(Decimal(mixed['value'])-Decimal(lease['value'])),concept='MixedDebtLessAllFinanceLeasesFloor',mixed=mixed,lease_subtraction=lease)
                debt_options.append([floor])
    debt=max(debt_options,key=lambda v:sum(Decimal(x['value']) for x in v),default=[])
    cash=pick('CashAndCashEquivalentsAtCarryingValue') or pick('Cash') or pick('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents')
    recv=pick('AccountsReceivableNetCurrent') or pick('ReceivablesNetCurrent') or pick('AccountsNotesAndLoansReceivableNetCurrent') or pick('AccountsReceivableNet') or pick('AccountsAndNotesReceivableNet')
    # Cash alone is a valid floor. Investment/receivable category completeness is not assumed.
    cash_components=[cash] if cash else []
    recv_components=[x for x in [cash,recv] if x]
    return dict(assets=assets,
        debt=debt_rule(debt,assets,config),
        cash_and_interest_items=cash_items_rule(cash_components,assets,config),
        receivables_and_cash=receivables_cash_rule(recv_components,assets,config))

def overall(checks,business,blocked=False):
    failed=[name for name,r in checks.items() if isinstance(r,dict) and r.get('status')=='fails_initial_filter']
    if business.get('status')=='fails_initial_filter':failed.append('business')
    if blocked:return 'needs_review',[]
    if failed:return 'fails_initial_filters',failed
    required=['debt','cash_and_interest_items','receivables_and_cash','income']
    if (all(checks.get(name,{}).get('status')=='passes_filter' for name in required)
            and business.get('status')=='passes_filter'):
        return 'passes_research_filters',[]
    return 'needs_review',[]
