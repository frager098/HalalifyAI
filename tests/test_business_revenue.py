from copy import deepcopy
import hashlib
import pytest
from src.screening.business_revenue import reviewed_revenue_failure,validate_business_revenue


def fixture(numerator='10'):
    content=f'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
    <xbrli:context id="annual"><xbrli:entity><xbrli:identifier>123</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
    <p>Reviewed conventional insurance business.</p>
    <ix:nonFraction name="us-gaap:InsuranceServicesRevenue" contextRef="annual" unitRef="usd" decimals="INF">{numerator}</ix:nonFraction>
    <ix:nonFraction name="us-gaap:Revenues" contextRef="annual" unitRef="usd" decimals="INF">100</ix:nonFraction></html>'''.encode()
    source_hash=hashlib.sha256(content).hexdigest()
    report=dict(cik='123',accession_number='source1',source_url='https://example.org/original',
                sha256=source_hash,report_date='2024-12-31',filing_date='2025-02-01')
    review=dict(cik='123',accession_number='source1',source_url=report['source_url'],source_sha256=source_hash,
        period_start='2024-01-01',period_end='2024-12-31',category='conventional_insurance',
        required_source_markers=['Reviewed conventional insurance business'],
        numerator=dict(concept='InsuranceServicesRevenue',expected_value=numerator),
        denominator=dict(concept='Revenues',expected_value='100'),reason='Reviewed category exceeds ceiling')
    return content,report,review


def test_business_failure_requires_source_bound_annual_revenue_and_classification():
    content,report,review=fixture()
    result=reviewed_revenue_failure(dict(status='needs_review'),report,content,review,'.05')
    assert result['status']=='fails_initial_filter'
    assert result['prohibited_revenue_minimum_ratio']=='0.1'
    assert result['prohibited_revenue_percentage'] is None
    assert validate_business_revenue(result,'.05')


def test_business_failure_cannot_transfer_to_other_source_or_period():
    content,report,review=fixture()
    for edit in [dict(cik='999'),dict(accession_number='another'),dict(sha256='a'*64),dict(report_date='2025-12-31')]:
        with pytest.raises(ValueError):
            reviewed_revenue_failure({},dict(report,**edit),content,review,'.05')
    for edit in [dict(period_start='2023-01-01'),dict(required_source_markers=['not present'])]:
        with pytest.raises(ValueError):
            reviewed_revenue_failure({},report,content,dict(review,**edit),'.05')


def test_low_category_does_not_clear_unknown_other_income_and_tampering_fails():
    content,report,review=fixture('5')
    with pytest.raises(ValueError,match='does not prove'):
        reviewed_revenue_failure({},report,content,review,'.05')
    content,report,review=fixture()
    result=reviewed_revenue_failure({},report,content,review,'.05')
    broken=deepcopy(result);broken['denominator']['period_end']='2023-12-31'
    with pytest.raises(ValueError,match='periods'):
        validate_business_revenue(broken,'.05')
