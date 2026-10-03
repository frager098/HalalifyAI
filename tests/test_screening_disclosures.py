from pathlib import Path
import json
import pandas as pd
import pytest
import exchange_calendars as xcals
from src.data.screening_disclosures import numeric_value,concept_kind,business_section,next_session,parse_report,parse_instance,interest_row_kind
from src.data.extract_screening_reports import usable_candidate,original_fact_key
from src.data.collect_screening_reports import filing_rows,Collector
from src.data.evidence_archive import archive_runs,evidence_sha256
from src.data.clean_screening_candidates import retain_candidate,main as clean_main
from zipfile import ZipFile


@pytest.fixture
def calendar():
    return xcals.get_calendar('XNYS',start='2015-01-01',end='2026-12-31').sessions


@pytest.fixture
def filing():
    return dict(ticker='AAPL',cik='0000320193',accession_number='0000320193-25-000079',form='10-K',
        filing_date='2025-10-31',source_url='https://www.sec.gov/example',sha256='fixture',
        instance_url='https://www.sec.gov/example.xml',instance_sha256='xml-fixture')


def test_numeric_scale_sign_and_regional_decimal():
    assert numeric_value('1,234','6','-','ixt:num-dot-decimal')==('-1234000000','parsed')
    assert numeric_value('1.234,50','0',None,'ixt:num-comma-decimal')==('1234.50','parsed')
    assert numeric_value('(12)')==('-12','parsed')


def test_missing_and_unsupported_values_do_not_become_zero():
    assert numeric_value('-')[0] is None
    assert numeric_value('12',format_name='ixt:unknown')[0] is None
    assert numeric_value('-',format_name='ixt:zerodash')==('0','parsed')
    assert numeric_value('\u2014',format_name='ixt:fixed-zero')==('0','parsed')


def test_income_row_labels_keep_combined_and_net_amounts_separate():
    assert interest_row_kind('Interest income')=='gross_interest_income_candidate'
    assert interest_row_kind('Interest and dividend income')=='combined_interest_dividend_candidate'
    assert interest_row_kind('Net interest income')=='net_interest_or_income_expense_candidate'
    assert interest_row_kind('Income attributable to noncontrolling interests') is None


def test_net_combined_and_expense_are_not_gross_interest_income():
    assert concept_kind('us-gaap:InterestIncomeNonoperating')=='gross_interest_income_candidate'
    assert concept_kind('us-gaap:InterestIncomeExpenseNonoperatingNet')=='net_interest_or_income_expense_candidate'
    assert concept_kind('us-gaap:InvestmentIncomeInterestAndDividend')=='combined_interest_dividend_candidate'
    assert concept_kind('us-gaap:InterestExpense') is None
    assert concept_kind('us-gaap:RevenuesNetOfInterestExpense')=='net_revenue_candidate'
    assert concept_kind('us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments') is None
    assert concept_kind('us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest') is None
    assert concept_kind('us-gaap:InterestAndFeeIncomeLoans')=='combined_interest_fee_candidate'


def test_security_balances_and_sale_proceeds_are_not_revenue_candidates():
    row=dict(evidence_kind='other_revenue_related_candidate')
    assert not retain_candidate(dict(row,source_concept='us-gaap:AvailableForSaleSecurities'))
    assert not retain_candidate(dict(row,source_concept='us-gaap:ProceedsFromSalesOfBusinesses'))
    assert retain_candidate(dict(row,source_concept='issuer:ProductSales'))
    assert retain_candidate(dict(row,source_concept='issuer:OtherRevenues'))


def test_cleanup_updates_handoff_coverage_without_approving_income(tmp_path,monkeypatch):
    folder=tmp_path/'data/interim/screening_evidence/sec_2015_2025_v2';folder.mkdir(parents=True)
    report=tmp_path/'reports/validation/screening_evidence/sec_2015_2025_v2/coverage.json';report.parent.mkdir(parents=True)
    report.write_text(json.dumps(dict(as_of_date='2025-12-31',companies=[dict(ticker='AAPL',approved_interest_income=None)])))
    (folder/'screening_review_packets.json').write_text(json.dumps(dict(companies=[])))
    row=dict(ticker='AAPL',cik='0000320193',accession_number='fixture',source_kind='inline_xbrl',evidence_kind='other_revenue_related_candidate',
        unit='USD',value_decimal='100',period_start='2024-01-01',period_end='2024-12-31',filing_date='2025-02-01',
        available_from_session='2025-02-03',numeric_parse_status='parsed',issuer_context_matches=True,dimensions=[])
    retained=dict(row,source_concept='issuer:ProductSales')
    (folder/'numeric_candidates.jsonl').write_text('\n'.join(json.dumps(dict(row,source_concept=c)) for c in ['issuer:ProductSales','us-gaap:AvailableForSaleSecurities','us-gaap:ProceedsFromSalesOfBusinesses'])+'\n')
    monkeypatch.setattr('sys.argv',['clean','--repo',str(tmp_path)])
    clean_main();clean_main()
    coverage=json.loads(report.read_text())
    assert coverage['total_numeric_candidates']==1 and coverage['lexical_revenue_cleanup']['removed_records']==2
    assert coverage['companies'][0]['usable_usd_candidates']==1
    assert coverage['companies'][0]['approved_interest_income'] is None
    assert json.loads((folder/'numeric_candidates.jsonl').read_text())==retained
    assert json.loads((folder/'screening_review_packets.json').read_text())['companies']==coverage['companies']


def test_business_section_ignores_short_contents_match():
    text='Item 1. Business 5 Item 1A. Risk Factors 6 '+('intro '*30)+'Item 1. Business '+('We make products. '*100)+'Item 1A. Risk Factors'
    result=business_section(text)
    assert result['status']=='extracted_requires_review'
    assert 'We make products.' in result['text'] and 'Business 5' not in result['text']
    assert business_section('Business activities unavailable')['text'] is None


def test_reorganized_business_and_unicode_heading_boundaries(calendar,filing):
    text='Item 1\u2014Business\n'+('We sell goods. '*100)+'\nItem 1A\u2014Risk Factors'
    assert business_section(text)['text'].startswith('Item 1\u2014Business')
    text='BUSINESS SUMMARY\n'+('We operate restaurants. '*100)+"\nMANAGEMENT'S DISCUSSION AND ANALYSIS\nFinances"
    result=business_section(text,'MCD')
    assert result['text'] and 'Finances' not in result['text']
    html=('<html><header>Item 1.</header><p>Note about forward-looking statements.</p><p><span>Busi</span><span>ness</span></p><p>'+
          'We sell goods. '*100+'</p><p>Item 1A. Risk Factors</p></html>').encode()
    record,_=parse_report(html,filing,calendar)
    assert record['text'] and 'Business' in record['text']
    text='Item 1. Business\n'+('We make goods. '*100)+'See Item 1A-Risk Factors for details.\n'+('More business information. '*100)+'\nItem 1A. Risk Factors'
    assert 'More business information.' in business_section(text)['text']


def test_archive_preserves_exact_bytes_without_unpacking(tmp_path):
    path=tmp_path/'sources.zip';payload=b'{"original":true}'
    with ZipFile(path,'w') as archive:
        archive.writestr('archive_manifest.json',json.dumps(dict(run_prefixes=['run'])))
        archive.writestr('run/metadata.json',payload)
    archive,runs=archive_runs(path)
    try:
        file=runs[0]/'metadata.json'
        assert file.read_bytes()==payload
        assert json.loads(file.read_text())['original'] is True
        assert evidence_sha256(file)==__import__('hashlib').sha256(payload).hexdigest()
        assert not (tmp_path/'run').exists()
    finally:archive.close()


def test_information_starts_next_exchange_session(calendar):
    assert next_session('2025-10-31',calendar)=='2025-11-03'
    assert next_session('2025-01-08',calendar)=='2025-01-10'
    assert next_session('2025-10-31',calendar,'2025-11-03T18:00:00Z')=='2025-11-04'


def report_fixture(identifier='0000320193'):
    return f'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
    <ix:header><ix:resources><xbrli:context id="c1"><xbrli:entity><xbrli:identifier>{identifier}</xbrli:identifier>
    <xbrli:segment><xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">aapl:ProductsMember</xbrldi:explicitMember></xbrli:segment>
    </xbrli:entity><xbrli:period><xbrli:startDate>2024-09-29</xbrli:startDate><xbrli:endDate>2025-09-27</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit></ix:resources></ix:header>
    <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" contextRef="c1" unitRef="usd" scale="6" format="ixt:num-dot-decimal">123<ix:exclude>Footnote 9</ix:exclude></ix:nonFraction>
    <p>Item 1. Business</p><p>{'We sell products. '*100}</p><p>Item 1A. Risk Factors</p></html>'''.encode()


def test_inline_preserves_dimension_currency_amount_and_source(calendar,filing):
    business,rows=parse_report(report_fixture(),filing,calendar)
    row=rows[0]
    assert row['value_decimal']=='123000000' and row['unit']=='USD'
    assert row['dimensions'][0]['member']=='aapl:ProductsMember'
    assert row['business_dimension_candidate'] and row['issuer_context_matches']
    assert 'Footnote' not in row['displayed_value']
    assert row['available_from_session']=='2025-11-03'
    assert business['text'] and row['review_status']=='candidate_not_approved'
    assert original_fact_key(row) is None # Never equate a segment figure with a whole-entity fact.


def test_wrong_issuer_or_future_availability_blocks_source_number(calendar,filing):
    _,rows=parse_report(report_fixture('0000070858'),filing,calendar)
    assert not usable_candidate(rows[0],'2025-12-31')
    _,rows=parse_report(report_fixture(),filing,calendar)
    assert not usable_candidate(rows[0],'2025-10-31')


def test_quarterly_financial_item_one_is_not_business_description(calendar,filing):
    business,_=parse_report(report_fixture(),dict(filing,form='10-Q'),calendar)
    assert business['text'] is None
    assert business['status']=='quarterly_report_requires_business_update_review'


def test_separate_xbrl_uses_actual_value_not_display_scale(calendar,filing):
    xml=b'''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2025">
    <xbrli:context id="c"><xbrli:entity><xbrli:identifier>0000320193</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
    <us-gaap:InterestIncomeNonoperating contextRef="c" unitRef="usd" decimals="-6">123000000</us-gaap:InterestIncomeNonoperating></xbrli:xbrl>'''
    row=parse_instance(xml,filing,calendar)[0]
    assert row['value_decimal']=='123000000' and row['source_kind']=='xbrl_instance'
    assert row['issuer_context_matches'] and usable_candidate(row,'2025-12-31')
    assert not usable_candidate(dict(row,period_start=None),'2025-12-31')
    assert not usable_candidate(dict(row,period_start='2025-12-31'),'2025-12-31')


def test_original_fact_match_requires_same_period_and_amount():
    row=dict(ticker='AAPL',cik='0000320193',accession_number='a',source_concept='us-gaap:Revenues',
        period_start='2024-01-01',period_end='2024-12-31',unit='USD',value_decimal='123.0',dimensions=[])
    key=original_fact_key(row)
    assert key==original_fact_key(dict(row,value_decimal='123'))
    assert key!=original_fact_key(dict(row,value_decimal='124'))
    assert key!=original_fact_key(dict(row,period_start='2024-10-01'))


def test_unequal_submission_columns_fail():
    with pytest.raises(ValueError):filing_rows(dict(accessionNumber=['a','b'],form=['10-K']))


def test_saved_raw_evidence_cannot_be_silently_modified(tmp_path):
    path=tmp_path/'saved.json';path.write_text('{}')
    metadata=dict(files={'saved.json':dict(url='https://example.invalid',sha256='wrong')},companies={},failures=[])
    (tmp_path/'metadata.json').write_text(json.dumps(metadata))
    collector=Collector(tmp_path,'Project contact@example.invalid')
    with pytest.raises(ValueError,match='changed'):collector.get('https://example.invalid','saved.json')
