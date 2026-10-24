"""Preserve public candidate sources for review; never join their current ratios.

These are discovery/comparison inputs, not approved historical screening facts.
No account, payment, credential or commercial API is used.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from ..reconciliation import save_json, sha256


SOURCES = {
    'halalwallet_screening': 'https://www.halalwallet.us/api/data/halal-stock-screening-data-us.json',
    'halalwallet_standard_comparison': 'https://www.halalwallet.us/api/data/halal-screening-standard-divergence-us.json',
    'kaggle_fundamentals_search': 'https://www.kaggle.com/api/v1/datasets/list?' + urlencode({'search': 'US financial statements 2025', 'pageSize': 12}),
    'kaggle_us_fundamentals': 'https://www.kaggle.com/api/v1/datasets/list?' + urlencode({'search': 'US stocks fundamentals', 'pageSize': 12}),
    'kaggle_financial_statements': 'https://www.kaggle.com/api/v1/datasets/list?' + urlencode({'search': 'financial statements', 'pageSize': 12}),
}


def collect(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    records = {}
    for name, url in SOURCES.items():
        entry = dict(url=url, retrieved_at_utc=datetime.now(timezone.utc).isoformat())
        try:
            request = Request(url, headers={'User-Agent': 'HalalifyAI academic data review', 'Accept': 'application/json'})
            with urlopen(request, timeout=45) as response:
                payload = response.read()
                entry.update(http_status=response.status, content_type=response.headers.get('Content-Type'))
            path = folder/(name+'.json')
            path.write_bytes(payload)
            entry.update(file=path.name, sha256=sha256(path), bytes=len(payload))
            data = json.loads(payload)
            entry['status'] = 'downloaded_candidate_not_approved'
            if isinstance(data, dict):
                entry['publisher_metadata'] = data.get('_meta')
                entry['record_count'] = len(data.get('records', []))
            elif isinstance(data, list):
                entry['datasets'] = [dict(ref=r.get('ref'), title=r.get('title'), url=r.get('url'),
                    last_updated=r.get('lastUpdated'), total_bytes=r.get('totalBytes')) for r in data]
        except Exception as error:
            entry.update(status='unavailable_or_not_json', error=str(error))
        records[name] = entry
        save_json(folder/'metadata.json', dict(sources=records, decision_use='none_without_company_date_and_definition_validation'))
        print(name, entry['status'], flush=True)
    return records


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    collect(p.parse_args().out)
