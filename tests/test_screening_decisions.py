"""Public-rule boundaries, missing evidence and a strictly synthetic complete case."""
import json
from pathlib import Path

import pytest

from src.screening.yasaar import (debt_rule, cash_items_rule, receivables_cash_rule,
                                 income_rule, business_revenue_rule, overall)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'configs/yasaar_research.json').read_text())


def amount(value):
    return dict(value=value, concept='TEST_ONLY')


@pytest.mark.parametrize('rule,at_limit,above', [
    (debt_rule, '33.333', '33.334'),
    (cash_items_rule, '33.333', '33.334'),
    (receivables_cash_rule, '50', '50.001')])
def test_exclusive_public_limits(rule, at_limit, above):
    assert rule([amount(at_limit)], amount('100'), CONFIG)['status'] == 'fails_initial_filter'
    assert rule([amount(above)], amount('100'), CONFIG)['status'] == 'fails_initial_filter'
    assert rule([amount('1')], amount('100'), CONFIG, complete=True)['status'] == 'passes_filter'


@pytest.mark.parametrize('rule', [income_rule, business_revenue_rule])
def test_inclusive_five_percent_and_gross_total_completeness(rule):
    assert rule([amount('5')], amount('100'), CONFIG, complete=True)['status'] == 'passes_filter'
    assert rule([amount('5.0001')], amount('100'), CONFIG)['status'] == 'fails_initial_filter'
    assert rule([amount('0')], amount('100'), CONFIG)['status'] == 'not_failed_on_available_amounts'
    assert rule([], amount('100'), CONFIG)['status'] == 'needs_review'


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '', None])
def test_bad_amount_cannot_become_a_pass(value):
    assert debt_rule([amount(value)], amount('100'), CONFIG, complete=True)['status'] == 'needs_review'


def test_complete_synthetic_packet_can_pass_but_missing_rule_cannot():
    fixture = json.loads((ROOT/'data/samples/screening/complete_synthetic.json').read_text())
    assets, revenue = amount(fixture['assets']), amount(fixture['total_revenue'])
    def check(rule, key, denominator):
        return rule([amount(fixture[key])], denominator, CONFIG, complete=True)
    checks = {'debt': check(debt_rule, 'debt', assets),
              'cash_and_interest_items': check(cash_items_rule, 'cash_and_interest_items', assets),
              'receivables_and_cash': check(receivables_cash_rule, 'receivables_and_cash', assets),
              'income': check(income_rule, 'gross_interest_plus_noncompliant_income', revenue)}
    business = check(business_revenue_rule, 'prohibited_business_revenue', revenue)
    assert overall(checks, business)[0] == 'passes_research_filters'
    assert overall(checks, business, blocked=True)[0] == 'needs_review'
    del checks['income']
    assert overall(checks, business)[0] == 'needs_review'


def test_string_true_never_certifies_completeness():
    assert debt_rule([amount('1')], amount('100'), CONFIG, complete='True')['status'] != 'passes_filter'


def test_prohibited_word_alone_cannot_exclude_unrelated_business():
    from src.screening.run_yasaar import business_review
    result = business_review(dict(ticker='AAPL', text='We have insurance policies and avoid alcohol.'))
    assert result['status'] == 'needs_review'


def test_registered_universe_is_exact_and_excludes_benchmark():
    universe = json.loads((ROOT/'configs/screening_universe.json').read_text())['company_tickers']
    assert len(universe) == len(set(universe)) == 50
    assert 'SPY' not in universe


def test_activity_assessment_cannot_transfer_to_another_filing_or_issuer():
    from src.screening.run_yasaar import business_review
    review=json.loads((ROOT/'configs/business_research_assessments.json').read_text())['reviews']['BAC']
    evidence={**review, 'text':'The bank holding company provides conventional financial services.'}
    assert business_review(evidence, {'BAC':review})['status']=='fails_initial_filter'
    assert business_review({**evidence,'source_sha256':'different'}, {'BAC':review})['status']=='needs_review'
    assert business_review({**evidence,'cik':'999'}, {'BAC':review})['status']=='needs_review'
    assert business_review(evidence)['status']=='needs_review'
