from decimal import Decimal
import pytest
from src.screening.source_facts import unique_amount,read_facts
from src.screening.yasaar import minimum_check,balance_checks,overall

CONFIG={'debt_assets_limit':'0.33333','cash_items_assets_limit':'0.33333','receivables_cash_assets_limit':'0.50'}
def f(tag,value,end='2025-09-30'):
    return dict(concept=tag,value=str(value),period_start=None,period_end=end,context_id='issuer',unit='USD')

@pytest.mark.parametrize('amount,status',[('33.3329','not_failed_on_available_amounts'),('33.333','fails_initial_filter'),('33.3331','fails_initial_filter')])
def test_debt_boundary_unrounded(amount,status):
    assert minimum_check([f('Debt',amount)],f('Assets',100),'0.33333')['status']==status

def test_missing_does_not_pass_and_zero_is_known():
    assert minimum_check([],f('Assets',100),'0.33333')['status']=='needs_review'
    assert minimum_check([f('Cash',0)],f('Assets',100),'0.33333')['ratio']=='0'
    assert minimum_check([f('Cash',1)],f('Assets',0),'0.33333')['status']=='needs_review'

def test_total_not_added_to_components():
    facts=[f('Assets',100),f('LongTermDebt',30),f('LongTermDebtNoncurrent',25),f('LongTermDebtCurrent',5)]
    result=balance_checks(facts,'2025-09-30',CONFIG)
    assert Decimal(result['debt']['minimum_amount'])==30
    assert result['debt']['status']=='not_failed_on_available_amounts'

def test_disjoint_longterm_components_and_overlapping_borrowing():
    facts=[f('Assets',100),f('LongTermDebtNoncurrent',30),f('LongTermDebtCurrent',4),f('DebtCurrent',7),f('CommercialPaper',3)]
    result=balance_checks(facts,'2025-09-30',CONFIG)
    assert Decimal(result['debt']['minimum_amount'])==37
    assert result['debt']['status']=='fails_initial_filter'

def test_conflicting_facts_unknown_and_other_period_not_used():
    assert unique_amount([f('Assets',100),f('Assets',101)],'Assets','2025-09-30') is None
    assert unique_amount([f('Assets',100,'2024-09-30')],'Assets','2025-09-30') is None
    assert unique_amount([f('Assets',100),f('Assets',100)],'Assets','2025-09-30')['value']=='100'

def test_no_pass_from_incomplete_evidence_and_amendment_blocks():
    checks={'debt':{'status':'not_failed_on_available_amounts'}}
    assert overall(checks,{'status':'needs_review'})[0]=='needs_review'
    checks['debt']['status']='fails_initial_filter'
    assert overall(checks,{'status':'needs_review'})[0]=='fails_initial_filters'
    assert overall(checks,{'status':'needs_review'},True)[0]=='needs_review'

def test_inline_identity_scope_scale_and_footnote():
    content=b'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
    <xbrli:context id="a"><xbrli:entity><xbrli:identifier>123</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-09-30</xbrli:instant></xbrli:period></xbrli:context>
    <xbrli:context id="foreign"><xbrli:entity><xbrli:identifier>999</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-09-30</xbrli:instant></xbrli:period></xbrli:context>
    <xbrli:context id="segment"><xbrli:entity><xbrli:identifier>123</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="ProductAxis">Phone</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2025-09-30</xbrli:instant></xbrli:period></xbrli:context>
    <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
    <ix:nonFraction name="us-gaap:Assets" contextRef="a" unitRef="usd" scale="6">100<ix:exclude>*</ix:exclude></ix:nonFraction>
    <ix:nonFraction name="us-gaap:Assets" contextRef="foreign" unitRef="usd">900</ix:nonFraction>
    <ix:nonFraction name="us-gaap:Assets" contextRef="segment" unitRef="usd">800</ix:nonFraction>
    <ix:nonFraction name="custom:Assets" contextRef="a" unitRef="usd">700</ix:nonFraction>
    </body></html>'''
    rows=read_facts(content,'0000000123')
    assert len(rows)==1 and Decimal(rows[0]['value'])==100000000

def test_xml_entity_and_dimension():
    content=b'''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2025">
    <xbrli:context id="a"><xbrli:entity><xbrli:identifier>123</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-09-30</xbrli:instant></xbrli:period></xbrli:context>
    <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><us-gaap:Assets contextRef="a" unitRef="usd">100</us-gaap:Assets></xbrli:xbrl>'''
    assert read_facts(content,'123',True)[0]['value']=='100'
    assert read_facts(content,'456',True)==[]

def test_income_inclusive_boundary():
    assert minimum_check([f('Income',5)],f('Revenue',100),'0.05',True)['status']=='not_failed_on_available_amounts'
    assert minimum_check([f('Income',5.0001)],f('Revenue',100),'0.05',True)['status']=='fails_initial_filter'

def test_selection_respects_next_session_and_keeps_amendments():
    import pandas as pd
    from src.screening.run_yasaar import select_latest
    sessions=pd.DatetimeIndex(['2025-12-30','2025-12-31','2026-01-02'])
    base=dict(ticker='A',status='downloaded',form='10-Q',report_date='2025-09-30',filing_date='2025-12-30',accession_number='old')
    future=dict(base,report_date='2025-12-31',filing_date='2025-12-31',accession_number='future')
    amended=dict(base,form='10-Q/A',accession_number='amended')
    selected,amends=select_latest([('p',base),('p',future),('p',amended)],'2025-12-31',sessions)
    assert selected['A'][1]['accession_number']=='old'
    assert len(amends)==1

def test_acceptance_date_can_delay_availability():
    import pandas as pd
    from src.screening.run_yasaar import select_latest
    sessions=pd.DatetimeIndex(['2025-12-30','2025-12-31','2026-01-02'])
    row=dict(ticker='A',status='downloaded',form='10-Q',report_date='2025-09-30',filing_date='2025-12-30',acceptance_datetime='2026-01-01T02:00:00Z',accession_number='late')
    selected,_=select_latest([('p',row)],'2025-12-31',sessions)
    assert not selected


def test_recovery_aliases_and_disjoint_current_debt():
    facts=[f('Assets',100),f('LongTermDebtNoncurrent',30),f('DebtCurrent',7),f('Cash',4),f('ReceivablesNetCurrent',8)]
    r=balance_checks(facts,'2025-09-30',CONFIG)
    assert Decimal(r['debt']['minimum_amount'])==37
    assert Decimal(r['receivables_and_cash']['minimum_amount'])==12

def test_mixed_lease_debt_is_not_automatically_interest_debt():
    r=balance_checks([f('Assets',100),f('LongTermDebtAndCapitalLeaseObligations',60)],'2025-09-30',CONFIG)
    assert r['debt']['status']=='needs_review'


def test_mixed_debt_subtracts_all_issuer_finance_leases_for_safe_floor():
    facts=[f('Assets',100),f('LongTermDebtAndCapitalLeaseObligations',40),f('FinanceLeaseLiabilityCurrent',2),f('FinanceLeaseLiabilityNoncurrent',3)]
    r=balance_checks(facts,'2025-09-30',CONFIG)
    assert Decimal(r['debt']['minimum_amount'])==35
    assert r['debt']['status']=='fails_initial_filter'

def test_notes_current_noncurrent_and_restricted_cash_fallback():
    facts=[f('Assets',100),f('LongTermNotesAndLoans',40),f('NotesPayableCurrent',5),f('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',4)]
    r=balance_checks(facts,'2025-09-30',CONFIG)
    assert Decimal(r['debt']['minimum_amount'])==45
    assert Decimal(r['cash_and_interest_items']['minimum_amount'])==4


def test_conflicting_lease_reconciliation_does_not_generate_debt_failure():
    facts=[f('Assets',100),f('LongTermDebtAndCapitalLeaseObligations',50),f('FinanceLeaseLiability',5),f('FinanceLeaseLiabilityCurrent',4),f('FinanceLeaseLiabilityNoncurrent',6)]
    assert balance_checks(facts,'2025-09-30',CONFIG)['debt']['status']=='needs_review'


def test_custom_mapping_requires_exact_ticker_issuer_namespace_and_concept():
    from src.screening.source_facts import mapped_research_facts
    mapping=dict(ticker='DE',cik='123',namespace='de',concept='Borrowings',maps_to='LongTermDebtAndCapitalLeaseObligations',basis='research')
    fact=dict(f('Borrowings',40),namespace='de')
    assert mapped_research_facts([], [fact], 'OTHER','123',[mapping])==[]
    assert mapped_research_facts([], [fact], 'DE','456',[mapping])==[]
    assert mapped_research_facts([], [dict(fact,namespace='other')], 'DE','123',[mapping])==[]
    r=mapped_research_facts([], [fact], 'DE','123',[mapping])
    assert r[0]['source_concept']=='Borrowings' and r[0]['mapping_basis']=='research'
