from copy import deepcopy
from decimal import Decimal
import pytest
from src.screening.accounting_bounds import (apply_accounting_bounds,financial_asset_envelope,
    liability_envelope,validate_upper_proof)
from src.screening.yasaar import balance_checks,overall

END='2025-09-30'
CONFIG=dict(debt_assets_limit='0.33333',cash_items_assets_limit='0.33333',receivables_cash_assets_limit='0.50')


def fact(tag,value,**extra):
    return dict(concept=tag,value=str(value),namespace='us-gaap',unit='USD',period_end=END,
        period_start=None,dimensions=[],reported_decimals='INF',context_id=tag,row_label=tag,**extra)


def fixture():
    return [fact('Assets',100),fact('Liabilities',20),fact('LongTermDebt',10),
        fact('CashAndCashEquivalentsAtCarryingValue',5),fact('AccountsReceivableNetCurrent',3),
        fact('PropertyPlantAndEquipmentNet',40),fact('Goodwill',15),fact('InventoryNet',5),
        fact('IntangibleAssetsNetExcludingGoodwill',10)]


def test_safe_upper_bounds_clear_financial_rules_without_zero_filling_income():
    facts=fixture();original=balance_checks(facts,END,CONFIG)
    checks=apply_accounting_bounds(original,facts,END,CONFIG)
    assert checks['debt']['status']=='passes_filter'
    assert checks['debt']['minimum_amount']=='10'
    assert checks['debt']['maximum_amount']=='20'
    assert checks['cash_and_interest_items']['maximum_amount']=='30'
    assert checks['cash_and_interest_items']['status']=='passes_filter'
    assert checks['receivables_and_cash']['status']=='passes_filter'
    assert original['debt']['status']!='passes_filter'
    checks['income']=dict(status='needs_review')
    assert overall(checks,dict(status='needs_review'))[0]=='needs_review'


def test_combined_intangible_and_ppe_alternatives_are_never_double_counted():
    facts=fixture()+[fact('GoodwillAndIntangibleAssetsNet',25),
        fact('FiniteLivedIntangibleAssetsNet',8),
        fact('PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization',45)]
    proof=financial_asset_envelope(facts,END)
    assert proof['numerator_upper']=='25'
    assert len(proof['nonfinancial_groups'])==3


def test_declared_rounding_uses_worst_case_bounds_and_exclusive_limit():
    facts=[fact('Assets',100),fact('CashAndCashEquivalentsAtCarryingValue',1),
        fact('PropertyPlantAndEquipmentNet','66.667')]
    checks=apply_accounting_bounds(balance_checks(facts,END,CONFIG),facts,END,CONFIG)
    assert checks['cash_and_interest_items']['maximum_ratio']=='0.33333'
    assert checks['cash_and_interest_items']['status']!='passes_filter'
    facts[0]['reported_decimals']='0'
    rounded=financial_asset_envelope(facts,END)
    assert Decimal(rounded['numerator_upper'])==Decimal('33.833')
    assert Decimal(rounded['denominator_lower'])==Decimal('99.5')


def test_nonconsolidated_custom_currency_or_other_period_cannot_prove_clearance():
    for edit in [dict(namespace='custom'),dict(unit='EUR'),dict(period_end='2025-06-30'),
                 dict(dimensions=[dict(axis='ProductAxis',member='SegmentMember')])]:
        facts=[fact('Assets',100),{**fact('PropertyPlantAndEquipmentNet',90),**edit}]
        assert financial_asset_envelope(facts,END) is None
    assert liability_envelope([fact('Assets',100),fact('StockholdersEquity',90)],END) is None


def test_forged_upper_bound_arithmetic_is_rejected():
    facts=fixture();checks=apply_accounting_bounds(balance_checks(facts,END,CONFIG),facts,END,CONFIG)
    assert validate_upper_proof(checks['cash_and_interest_items'],CONFIG['cash_items_assets_limit'])
    broken=deepcopy(checks['cash_and_interest_items']);broken['maximum_amount']='1'
    with pytest.raises(ValueError,match='arithmetic'):
        validate_upper_proof(broken,CONFIG['cash_items_assets_limit'])


def test_conflicting_envelope_does_not_erase_an_existing_failure():
    facts=fixture();facts.append(fact('AvailableForSaleSecuritiesDebtSecurities',70))
    checks=balance_checks(facts,END,CONFIG)
    checks['cash_and_interest_items']=dict(status='fails_initial_filter',minimum_amount='70',ratio='.7')
    result=apply_accounting_bounds(checks,facts,END,CONFIG)
    assert result['cash_and_interest_items']['status']=='fails_initial_filter'
    assert 'upper_bound_diagnostic' in result['cash_and_interest_items']


def test_missing_precision_cannot_claim_exact_upper_bound():
    facts=[fact('Assets',100),dict(fact('PropertyPlantAndEquipmentNet',99),reported_decimals=None)]
    assert financial_asset_envelope(facts,END) is None


def test_saved_proof_rejects_wrong_period_or_overlapping_alternatives():
    facts=fixture();check=apply_accounting_bounds(balance_checks(facts,END,CONFIG),facts,END,CONFIG)['cash_and_interest_items']
    with pytest.raises(ValueError,match='period'):
        validate_upper_proof(check,'.33333','2020-01-01')
    duplicate=deepcopy(check)
    group=duplicate['upper_bound_proof']['nonfinancial_groups'][0]
    group['facts'].append(deepcopy(group['facts'][0]))
    with pytest.raises(ValueError,match='class'):
        validate_upper_proof(duplicate,'.33333')
