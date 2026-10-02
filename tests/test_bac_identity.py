"""Tests for identity, consolidated context and original-source safeguards."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import csv
import json

spec = importlib.util.spec_from_file_location('verify_bac_identity',
    Path(__file__).resolve().parents[1] / 'src/data/verify_bac_identity.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def instance(name='Bank of America Corporation', cik='0000070858', dimension='', value='100'):
    return f'''<xbrl xmlns="http://www.xbrl.org/2003/instance"
        xmlns:dei="http://xbrl.sec.gov/dei/2024"
        xmlns:gaap="http://fasb.org/us-gaap/2024"
        xmlns:dim="http://xbrl.org/2006/xbrldi">
      <context id="c"><entity><identifier scheme="http://www.sec.gov/CIK">{cik}</identifier>{dimension}</entity>
        <period><instant>2024-12-31</instant></period></context>
      <unit id="usd"><measure>iso4217:USD</measure></unit>
      <dei:EntityRegistrantName contextRef="c">{name}</dei:EntityRegistrantName>
      <dei:EntityCentralIndexKey contextRef="c">{cik}</dei:EntityCentralIndexKey>
      <dei:DocumentType contextRef="c">10-K</dei:DocumentType>
      <gaap:Assets contextRef="c" unitRef="usd">{value}</gaap:Assets>
    </xbrl>'''


class IdentityTests(unittest.TestCase):
    def parse(self, xml):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixture.xml'
            path.write_text(xml, encoding='utf-8')
            return module.parse_instance(path)

    def test_original_consolidated_fact_matches(self):
        identity, _, facts = self.parse(instance())
        self.assertTrue(identity)
        self.assertIn(('Assets', None, '2024-12-31', 'USD', module.Decimal('100')), facts)

    def test_historical_sec_legal_name(self):
        self.assertTrue(self.parse(instance('BANK OF AMERICA CORP /DE/'))[0])

    def test_subsidiary_name_does_not_pass(self):
        self.assertFalse(self.parse(instance('BofA Finance LLC'))[0])

    def test_wrong_cik_rejected(self):
        identity, _, facts = self.parse(instance(cik='0001682472'))
        self.assertFalse(identity)
        self.assertFalse(facts)

    def test_segment_fact_cannot_match_consolidated_amount(self):
        dimension = '<segment><dim:explicitMember dimension="gaap:SomeAxis">gaap:Subsidiary</dim:explicitMember></segment>'
        identity, _, facts = self.parse(instance(dimension=dimension))
        self.assertTrue(identity)
        self.assertFalse(facts)

    def test_invalid_and_nonfinite_values_not_accepted(self):
        for value in ['', 'NaN', 'Infinity']:
            self.assertFalse(self.parse(instance(value=value))[2])

    def test_xml_selection_uses_instance_not_linkbase(self):
        html = '<tr><td>EX-101.CAL</td><td><a href="cal.xml">cal</a></td></tr><tr><td><b>EXTRACTED</b> XBRL INSTANCE DOCUMENT</td><td><a href="bac_htm.xml">instance</a></td></tr>'
        self.assertEqual(module.find_instance_url(html, 'https://www.sec.gov/Archives/edgar/data/70858/abc/index.htm'),
                         'https://www.sec.gov/Archives/edgar/data/70858/abc/bac_htm.xml')

    def test_untrusted_instance_link_rejected(self):
        html = '<tr><td>EX-101.INS</td><td><a href="https://example.com/x.xml">instance</a></td></tr>'
        with self.assertRaises(ValueError):
            module.find_instance_url(html, 'https://www.sec.gov/Archives/edgar/data/70858/abc/index.htm')

    def test_normalization_preserves_raw_name_values_dates_and_mapping_review(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            cf, sub, source = [repo / name for name in ['cf.json', 'sub.json', 'facts.csv']]
            obs = dict(end='2024-12-31', val=100, accn='0000070858-25-000139',
                       form='10-K', filed='2025-02-25')
            cf.write_text(json.dumps(dict(cik=70858, entityName='BofA Finance LLC',
                facts={'us-gaap': {'Assets': {'units': {'USD': [obs]}}}})))
            sub.write_text(json.dumps(dict(cik='0000070858', tickers=['BAC'], name='BANK OF AMERICA CORP /DE/')))
            row = dict(ticker='BAC', cik='0000070858', company_name='BofA Finance LLC',
                accession_number=obs['accn'], source_tag='Assets', period_start='',
                period_end=obs['end'], value='100', unit='USD', form_type='10-K',
                filed_date=obs['filed'], available_from_session='2025-02-26',
                review_status='unreviewed', statement_scope='unverified')
            other_company = dict(row, ticker='MSFT', company_name='Microsoft')
            module.write_csv(source, [row, dict(row, value='999'), other_company], list(row))
            hashes = [module.digest(p) for p in [cf, sub, source]]
            def fake_fetch(url, path, user_agent):
                path.write_text(instance() if path.suffix == '.xml' else
                    '<tr><td>EX-101.INS</td><td><a href="instance.xml">instance</a></td></tr>')
            with patch.object(module, 'fetch', side_effect=fake_fetch):
                result, interim, _ = module.verify(cf, sub, source, repo, 'test contact', 'test_run')
            self.assertEqual(result['verified_rows'], 1)
            self.assertEqual(result['needs_review_rows'], 1)
            self.assertEqual(hashes, [module.digest(p) for p in [cf, sub, source]])
            with (interim / 'BAC_identity_verified_financial_facts.csv').open(newline='') as stream:
                corrected = next(csv.DictReader(stream))
            self.assertEqual(corrected['company_name'], 'Bank of America Corporation')
            self.assertEqual(corrected['source_company_name'], 'BofA Finance LLC')
            for key in ['value', 'filed_date', 'available_from_session', 'review_status']:
                self.assertEqual(corrected[key], row[key])
            with (interim / 'financial_facts_identity_updated.csv').open(newline='') as stream:
                combined = list(csv.DictReader(stream))
            self.assertEqual(len(combined), 3)
            self.assertEqual({key: combined[2][key] for key in row}, other_company)


if __name__ == '__main__':
    unittest.main()
