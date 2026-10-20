"""Recovery may resolve extraction gaps, never invent totals or erase ambiguity."""
import pytest

from src.screening.field_recovery import reconcile_amount,recovered_balance,recover_income_check,recover_reviewed_debt
from src.screening.yasaar import balance_checks


END='2025-09-30'
CONFIG=dict(debt_assets_limit='0.33333',cash_items_assets_limit='0.33333',receivables_cash_assets_limit='0.50')


def fact(concept,value,decimals='0',dimensions=()):
    return dict(namespace='us-gaap',concept=concept,value=str(value),period_start=None,
        period_end=END,context_id=concept+str(value),unit='USD',reported_decimals=decimals,
        row_label=concept,dimensions=list(dimensions))


def test_rounding_is_reconciled_from_declared_precision_not_a_guessed_tolerance():
    rows=[fact('AccountsReceivableNetCurrent','2093000000','-6'),
          fact('AccountsReceivableNetCurrent','2090000000','-7')]
    result=reconcile_amount(rows,'AccountsReceivableNetCurrent',END)
    assert result['value']=='2093000000'
    assert result['rounding_reconciled'] is True
    assert len(result['reported_values'])==2


def test_real_conflicts_and_unknown_precision_remain_unresolved():
    assert reconcile_amount([fact('Assets',100),fact('Assets',110)],'Assets',END) is None
    assert reconcile_amount([fact('Assets',100,None),fact('Assets',101,None)],'Assets',END) is None


def test_cash_and_securities_are_not_blindly_added():
    facts=[fact('Assets',100),fact('Cash',30),fact('AvailableForSaleSecuritiesDebtSecurities',20)]
    recovered=recovered_balance(facts,END,balance_checks(facts,END,CONFIG),CONFIG)
    assert recovered['cash_and_interest_items']['ratio']=='0.3'


def test_source_reviewed_classification_subtracts_cash_overlap():
    level2=[dict(axis='us-gaap:FairValueByFairValueHierarchyLevelAxis',member='us-gaap:FairValueInputsLevel2Member')]
    facts=[fact('Assets',100),fact('CashAndCashEquivalentsAtCarryingValue',30),
        fact('AvailableForSaleSecuritiesDebtSecurities',20,dimensions=level2),
        fact('CashAndCashEquivalentsAtCarryingValue',5,dimensions=level2)]
    config=dict(CONFIG,recover_apple_classification_table=True)
    recovered=recovered_balance(facts,END,balance_checks(facts,END,config),config)
    assert recovered['cash_and_interest_items']['minimum_amount']=='45'
    assert recovered['cash_and_interest_items']['status']=='fails_initial_filter'


def test_business_segment_debt_does_not_become_consolidated_debt():
    dims=[dict(axis='srt:ProductOrServiceAxis',member='company:FinanceSegment')]
    facts=[fact('Assets',100),fact('LongTermDebt',80,dimensions=dims)]
    recovered=recovered_balance(facts,END,balance_checks(facts,END,CONFIG),CONFIG)
    assert recovered['debt']['status']=='needs_review'


def test_instrument_component_can_establish_floor_without_summing_overlaps():
    dims=[dict(axis='us-gaap:LongtermDebtTypeAxis',member='us-gaap:UnsecuredDebtMember')]
    facts=[fact('Assets',100),fact('NotesPayable',40,dimensions=dims),fact('DebtCurrent',5)]
    recovered=recovered_balance(facts,END,balance_checks(facts,END,CONFIG),CONFIG)
    assert recovered['debt']['minimum_amount']=='40'


def test_custom_tag_with_standard_name_is_not_auto_approved():
    facts=[fact('Assets',100),dict(fact('NotesPayable',80),namespace='custom')]
    recovered=recovered_balance(facts,END,balance_checks([facts[0]],END,CONFIG),CONFIG)
    assert recovered['debt']['status']=='needs_review'


def test_net_interest_cannot_be_used_as_gross_or_clear_all_income():
    annual=dict(ticker='T',cik='1',accession_number='a',source_sha256='x',source_url='https://example.org/report',
        report_date=END,available_from_session='2025-10-01',table_rows=[],
        facts=[dict(fact('InterestIncomeExpenseNet',10),period_start='2024-10-01')])
    result=recover_income_check(dict(status='needs_review',interest_candidate=None),annual,[])
    assert result['interest_candidate'] is None
    assert result['status']=='needs_review'


def test_manual_table_review_requires_exact_original_source():
    annual=dict(ticker='T',cik='1',accession_number='a',source_sha256='x',report_date=END,facts=[],table_rows=[])
    mapping=dict(ticker='T',cik='1',accession_number='different',source_sha256='x')
    with pytest.raises(ValueError,match='filing'):
        recover_income_check(dict(status='needs_review'),annual,[mapping])


def test_reviewed_lease_footnote_removes_lease_not_future_interest_payments():
    import hashlib
    content=b'<html><body>Excludes finance lease obligations of $108 million</body></html>'
    financial=dict(ticker='T',cik='1',accession_number='a',report_date=END,
        source_sha256=hashlib.sha256(content).hexdigest(),source_url='https://example.org/original',
        facts=[fact('Assets',1000),fact('LongTermDebtAndCapitalLeaseObligationsCurrent',100),
               fact('LongTermDebtAndCapitalLeaseObligations',500)])
    mapping=dict(**{key:financial[key] for key in ['ticker','cik','accession_number','source_sha256','report_date']},
        mixed_debt_concepts=['LongTermDebtAndCapitalLeaseObligationsCurrent','LongTermDebtAndCapitalLeaseObligations'],
        finance_lease_liability_usd='108',expected_narrative='Excludes finance lease obligations of $108 million',
        interpretation='Fixture source review')
    checks=balance_checks(financial['facts'],END,CONFIG)
    result=recover_reviewed_debt(checks,financial,[mapping],content,CONFIG)
    assert result['debt']['minimum_amount']=='492'
    assert result['debt']['status']=='fails_initial_filter'
    with pytest.raises(ValueError,match='hash'):
        recover_reviewed_debt(checks,financial,[mapping],content+b'changed',CONFIG)
    mapping['expected_narrative']='lease liability is zero'
    with pytest.raises(ValueError,match='footnote'):
        recover_reviewed_debt(checks,financial,[mapping],content,CONFIG)
