"""Collect CompanyFacts as supplementary evidence, never as point-in-time truth.

Current API responses are versioned raw inputs. Screening must match each used
observation to an original eligible filing; future/restated API data is not a
historical replacement. No credentials are required by this SEC endpoint.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from .reconciliation import save_json, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--user-agent', default=os.environ.get('SEC_USER_AGENT',
        'HalalifyAI Academic Research HalalifyAI.edu.@gmail.com'))
    args = parser.parse_args()
    results = json.loads((args.repo/'reports/screening/ftse_yasaar_2025/results.json').read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out/'metadata.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(
        started_at_utc=datetime.now(timezone.utc).isoformat(), provider='SEC CompanyFacts',
        use='Supplementary current snapshot; original-filings match required', files={})
    if manifest.get('status')=='complete':
        expected={r['ticker']:r['cik'] for r in results['companies']}
        if len(expected)!=50 or set(manifest['files'])!=set(expected):
            raise ValueError('Cached API collection differs from the registered companies')
        for ticker,record in manifest['files'].items():
            if record['status']!='downloaded' or record['cik']!=expected[ticker]:
                raise ValueError('Cached API identity or status changed')
            if sha256(args.out/f'{ticker}_companyfacts.json')!=record['sha256']:
                raise ValueError('Cached API bytes changed')
        print('All 50 retained API files verified; completed metadata remains unchanged.')
        return
    for company in results['companies']:
        ticker, cik = company['ticker'], company['cik']
        path = args.out/f'{ticker}_companyfacts.json'
        previous = manifest['files'].get(ticker)
        if previous and previous['status'] == 'downloaded':
            if not path.exists() or sha256(path) != previous['sha256']:
                raise ValueError('Retained API evidence changed: '+ticker)
            continue
        if path.exists():
            raise ValueError('Unregistered raw API file: '+str(path))
        url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
        record = dict(ticker=ticker, cik=cik, url=url)
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={
                    'User-Agent': args.user_agent, 'Accept-Encoding': 'identity'})
                with urllib.request.urlopen(request, timeout=45) as response:
                    data, status = response.read(), response.status
                payload = json.loads(data)
                if int(payload.get('cik', -1)) != int(cik):
                    raise ValueError('SEC API issuer differs from requested CIK')
                path.write_bytes(data)
                record.update(status='downloaded', http_status=status, bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    retrieved_at_utc=datetime.now(timezone.utc).isoformat())
                break
            except (urllib.error.URLError, ValueError, TimeoutError) as exc:
                record.update(status='failed', error=str(exc))
                if attempt < 2:
                    time.sleep(2 ** attempt)
        manifest['files'][ticker] = record
        save_json(manifest_path, manifest)
        print(ticker, record['status'], flush=True)
        time.sleep(0.4)
    manifest['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    manifest['downloaded'] = sum(v['status']=='downloaded' for v in manifest['files'].values())
    manifest['failed'] = len(manifest['files'])-manifest['downloaded']
    manifest['status'] = 'complete' if manifest['downloaded']==50 else 'incomplete'
    save_json(manifest_path, manifest)
    print(manifest['downloaded'], 'downloaded;', manifest['failed'], 'failed')


if __name__ == '__main__':
    main()
