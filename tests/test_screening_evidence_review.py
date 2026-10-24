"""Exercise the source-review path, including genuine pass/fail and rejection cases."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from src.screening.evidence_review import (apply_evidence_review, coverage_issues,
                                         select_annual_revenue, validate_reviewed_result)
from src.screening.field_recovery import recover_income_check, income_inventory

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'configs/yasaar_research.json').read_text())


def fixture(interest='2', prohibited='1'):
    # Entirely synthetic issuer and amounts; never a real-company halal result.
    values = {'Revenues': '100', 'InterestIncomeNonOperating': interest,
              'OtherIncome': '1', 'AllowedSegment': '99', 'ProhibitedSegment': prohibited}
    html = '''<html><body><xbrli:context id="annual"><xbrli:entity>
      <xbrli:identifier>123</xbrli:identifier></xbrli:entity><xbrli:period>
      <xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate>
      </xbrli:period></xbrli:context><xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'''
    for concept, value in values.items():
        html += f'<ix:nonFraction name="us-gaap:{concept}" contextRef="annual" unitRef="usd" decimals="0">{value}</ix:nonFraction>'
    content = (html + '</body></html>').encode()
    report = dict(ticker='SYNTHETIC', cik='0000000123', accession_number='TEST-ONLY',
                  source_url='https://example.invalid/test-only', sha256=hashlib.sha256(content).hexdigest(),
                  report_date='2024-12-31', available_from_session='2025-02-03')
    def ref(concept, classification=None):
        return dict(concept=concept, expected_value=values[concept],
                    classification=classification, classification_rationale='Synthetic explicit test classification')
    common = dict(review_state='complete', reviewer='Synthetic test reviewer',
                  coverage_confirmed=True, gross_income_confirmed=True,
                  disjoint_components_confirmed=True, total_revenue_confirmed=True,
                  coverage_rationale='Synthetic full source category coverage', denominator=ref('Revenues'))
    review = {k: report[k] for k in ['ticker','cik','accession_number','source_url','available_from_session']}
    review.update(source_sha256=report['sha256'], period_start='2024-01-01', period_end='2024-12-31', checks={
        'income': dict(common, components=[ref('InterestIncomeNonOperating','noncompliant_interest'),ref('OtherIncome','noncompliant_other')]),
        'business': dict(common, components=[ref('AllowedSegment','permitted'),ref('ProhibitedSegment','prohibited')])})
    return content, report, review


def run(review, report, content, checks=None, business=None):
    return apply_evidence_review(checks or {'income': {'status':'needs_review','ratio':None}},
                                business or {'status':'needs_review'}, report, content, review, CONFIG)


def test_complete_source_review_flows_to_both_rules_and_independent_verifier():
    content, report, review = fixture()
    checks, business = run(review, report, content)
    assert checks['income']['status'] == business['status'] == 'passes_filter'
    assert checks['income']['ratio'] == '0.03'
    assert business['ratio'] == '0.01'
    assert validate_reviewed_result(checks['income'], 'income', CONFIG, '2025-12-31')
    assert validate_reviewed_result(business, 'business', CONFIG, '2025-12-31')


def test_source_review_can_fail_income_instead_of_always_needing_review():
    content, report, review = fixture(interest='6')
    assert run(review, report, content)[0]['income']['status'] == 'fails_initial_filter'


def test_reported_five_percent_with_rounding_cannot_claim_a_clear_pass_or_failure():
    content, report, review = fixture(interest='4')
    checks, _ = run(review, report, content)
    assert checks['income']['ratio'] == '0.05'
    assert checks['income']['status'] == 'needs_review'
    assert validate_reviewed_result(checks['income'], 'income', CONFIG, '2025-12-31')


def test_missing_or_draft_review_does_not_pass():
    content, report, review = fixture()
    assert run(None, report, content)[0]['income']['status'] == 'needs_review'
    review['checks']['income']['review_state'] = 'draft'
    assert run(review, report, content)[0]['income']['status'] == 'needs_review'


@pytest.mark.parametrize('field,value', [('coverage_confirmed',False),('coverage_confirmed','True'),
    ('gross_income_confirmed',False),('disjoint_components_confirmed',False),
    ('total_revenue_confirmed',False),('coverage_rationale',''),('reviewer','')])
def test_incomplete_coverage_cannot_be_signed_off(field, value):
    content, report, review = fixture()
    review['checks']['income'][field] = value
    with pytest.raises(ValueError): run(review, report, content)


@pytest.mark.parametrize('field,value', [('cik','999'),('accession_number','OTHER'),
    ('source_sha256','f'*64),('period_end','2024-09-30'),('available_from_session','2026-01-01')])
def test_wrong_source_period_or_availability_is_rejected(field, value):
    content, report, review = fixture()
    review[field] = value
    with pytest.raises(ValueError): run(review, report, content)


def test_different_original_bytes_are_rejected():
    content, report, review = fixture()
    with pytest.raises(ValueError): run(review, report, content+b'changed')


def test_unknown_zero_is_not_a_source_fact():
    content, report, review = fixture()
    review['checks']['income']['components'][0]['expected_value'] = '0'
    with pytest.raises(ValueError): run(review, report, content)


def test_duplicate_components_and_partial_business_coverage_are_rejected():
    content, report, review = fixture()
    duplicate = deepcopy(review)
    duplicate['checks']['income']['components'] *= 2
    with pytest.raises(ValueError): run(duplicate, report, content)
    review['checks']['business']['components'].pop()
    with pytest.raises(ValueError): run(review, report, content)


def test_new_pass_cannot_erase_an_established_failure():
    content, report, review = fixture()
    with pytest.raises(ValueError):
        run(review, report, content, business={'status':'fails_initial_filter'})
    with pytest.raises(ValueError):
        run(review, report, content, checks={'income':{'status':'fails_initial_filter'}})


def test_changed_saved_arithmetic_is_detected_independently():
    content, report, review = fixture()
    checks, _ = run(review, report, content)
    checks['income']['ratio'] = '0.01'
    with pytest.raises(ValueError):
        validate_reviewed_result(checks['income'], 'income', CONFIG, '2025-12-31')


def test_total_revenue_selection_repairs_sales_candidate_without_implying_clearance():
    check = dict(status='needs_review', revenue_candidate=dict(value_decimal='90',period_start='2024-01-01',period_end='2024-12-31'))
    annual = dict(report_date='2024-12-31',source_url='test',source_sha256='f'*64,accession_number='TEST',filing_date='2025-02-01',available_from_session='2025-02-03', facts=[
        dict(namespace='us-gaap',concept='Revenues',row_label='Total revenues',value='100',dimensions=[],unit='USD',period_start='2024-01-01',period_end='2024-12-31')])
    result = select_annual_revenue(check, annual)
    assert result['revenue_candidate']['value_decimal'] == '100'
    assert result['previous_revenue_candidate']['value_decimal'] == '90'
    assert result['revenue_amount_changed'] is True
    assert result['status'] == 'needs_review'
    annual['facts'][0]['dimensions'] = [{'axis':'segment','member':'part'}]
    assert select_annual_revenue(check, annual) == check


def test_ownership_interest_is_not_earned_interest_and_recovery_preserves_completed_review():
    annual = dict(report_date='2024-12-31',facts=[dict(concept='NetIncomeLossAttributableToNoncontrollingInterest',value='10',period_start='2024-01-01',period_end='2024-12-31',dimensions=[])])
    assert income_inventory(annual) == []
    check = dict(status='passes_filter',completeness='complete_reviewed_total')
    assert recover_income_check(check,annual,[])['status'] == 'passes_filter'


def test_combined_interest_is_a_review_issue_not_absent_or_pure_interest():
    income = dict(revenue_candidate={'value_decimal':'100'},recovered_interest_disclosures=[
        dict(classification='reported_combined_interest_candidate',value='3')])
    issues = coverage_issues(income, {'status':'needs_review'})
    assert issues['combined_interest_observations_found'] is True
    assert issues['gross_interest_observation_found'] is False
    assert 'interest_combined_with_other_income' in issues['issues']
