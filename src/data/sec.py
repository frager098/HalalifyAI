"""SEC collection, candidate extraction and original-filing cross-check commands.

Current CompanyFacts snapshots never replace original historical filing facts.
Downloads are explicit commands; importing this module never fetches data.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import pandas as pd
from .reconciliation import COMPANY_SYMBOLS, save_json, sha256

CONCEPTS = {
    "total_assets": [
        "Assets"
    ],

    "total_debt": [
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent"
    ],

    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    ],

    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet"
    ],

    "accounts_receivable": [
        "AccountsReceivableNetCurrent"
    ]
}

def download_companyfacts(output_folder, user_agent=None):
    """Retain the original downloader's content in an explicitly new raw folder."""
    output_folder = Path(output_folder)
    if output_folder.exists() and any(output_folder.iterdir()):
        raise FileExistsError('Use a new raw folder; existing downloads are immutable')
    import requests
    SYMBOLS = COMPANY_SYMBOLS
    HEADERS = {'User-Agent': user_agent or os.environ.get('SEC_USER_AGENT', 'HalalifyAI.edu.@gmail.com'),
               'Accept-Encoding': 'gzip, deflate'}
    OUTPUT_FOLDER = str(output_folder)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print("Downloading SEC ticker-to-CIK mapping...")

    mapping_url = "https://www.sec.gov/files/company_tickers.json"

    response = requests.get(
        mapping_url,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    mapping_data = response.json()

    ticker_to_cik = {}

    for item in mapping_data.values():

        ticker = item["ticker"].upper()

        cik = str(item["cik_str"]).zfill(10)

        ticker_to_cik[ticker] = cik

    print("Ticker mapping downloaded successfully.")
    print()

    successful = []
    failed = []

    for number, ticker in enumerate(SYMBOLS, start=1):

        print(
            f"[{number}/{len(SYMBOLS)}] Downloading {ticker}..."
        )

        cik = ticker_to_cik.get(ticker)

        if not cik:

            print(f"   CIK not found for {ticker}")

            failed.append({
                "ticker": ticker,
                "reason": "CIK not found"
            })

            continue

        company_url = (
            f"https://data.sec.gov/api/xbrl/"
            f"companyfacts/CIK{cik}.json"
        )

        try:

            response = requests.get(
                company_url,
                headers=HEADERS,
                timeout=60
            )

            response.raise_for_status()

            company_data = response.json()

            output_file = os.path.join(
                OUTPUT_FOLDER,
                f"{ticker}_companyfacts.json"
            )

            with open(
                output_file,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    company_data,
                    file,
                    indent=2
                )

            company_name = company_data.get(
                "entityName",
                "Unknown"
            )

            concepts = (
                company_data
                .get("facts", {})
                .get("us-gaap", {})
            )

            concept_count = len(concepts)

            successful.append({
                "ticker": ticker,
                "company": company_name,
                "cik": cik,
                "concepts": concept_count
            })

            print(
                f"   Success: {company_name} "
                f"({concept_count} concepts)"
            )

        except Exception as error:

            print(f"   FAILED: {error}")

            failed.append({
                "ticker": ticker,
                "reason": str(error)
            })

        time.sleep(0.2)

    summary_file = os.path.join(
        OUTPUT_FOLDER,
        "sec_download_summary.json"
    )

    summary = {
        "requested_companies": len(SYMBOLS),
        "successful_downloads": len(successful),
        "failed_downloads": len(failed),
        "successful": successful,
        "failed": failed
    }

    with open(
        summary_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=2
        )

    print()
    print("---------------------------------------")
    print("SEC DOWNLOAD COMPLETED")
    print("---------------------------------------")

    print("Companies requested :", len(SYMBOLS))
    print("Successful downloads:", len(successful))
    print("Failed downloads    :", len(failed))

    print()
    print("Raw files saved in:")
    print(OUTPUT_FOLDER)

    if failed:

        print()
        print("FAILED COMPANIES:")

        for item in failed:
            print(
                item["ticker"],
                "->",
                item["reason"]
            )

    else:

        print()
        print("All 50 companies downloaded successfully.")

def extract_fundamentals(input_folder, output_folder):
    """Extract the original long-format candidates; these are not approved totals."""
    INPUT_FOLDER, OUTPUT_FOLDER = str(input_folder), str(output_folder)
    target = Path(OUTPUT_FOLDER) / 'sec_historical_fundamentals_long.csv'
    if target.exists():
        raise FileExistsError('Use a new intermediate folder; previous extracts are preserved')
    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)
    rows = []

    for filename in os.listdir(INPUT_FOLDER):

        if not filename.endswith("_companyfacts.json"):
            continue

        filepath = os.path.join(INPUT_FOLDER, filename)

        ticker = filename.replace("_companyfacts.json", "")

        print(f"Extracting {ticker}...")

        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)

        company_name = data.get("entityName", "")

        us_gaap = (
            data
            .get("facts", {})
            .get("us-gaap", {})
        )

        for field_name, possible_concepts in CONCEPTS.items():

            for concept_name in possible_concepts:

                concept = us_gaap.get(concept_name)

                if not concept:
                    continue

                units = concept.get("units", {})

                for unit_name, observations in units.items():

                    for observation in observations:

                        form = observation.get("form")

                        if form not in ["10-K", "10-Q"]:
                            continue

                        rows.append({
                            "ticker": ticker,
                            "company_name": company_name,
                            "field": field_name,
                            "sec_concept": concept_name,
                            "value": observation.get("val"),
                            "unit": unit_name,
                            "period_start": observation.get("start"),
                            "period_end": observation.get("end"),
                            "filing_date": observation.get("filed"),
                            "form": form,
                            "fiscal_year": observation.get("fy"),
                            "fiscal_period": observation.get("fp"),
                            "accession_number": observation.get("accn")
                        })

    df = pd.DataFrame(rows)

    if df.empty:

        print("No financial data was extracted.")

    else:

        df["period_start"] = pd.to_datetime(
            df["period_start"],
            errors="coerce"
        )

        df["period_end"] = pd.to_datetime(
            df["period_end"],
            errors="coerce"
        )

        df["filing_date"] = pd.to_datetime(
            df["filing_date"],
            errors="coerce"
        )

        df = df.sort_values(
            ["ticker", "filing_date", "field"]
        )

        df = df.drop_duplicates(
            subset=[
                "ticker",
                "field",
                "sec_concept",
                "period_start",
                "period_end",
                "filing_date",
                "value"
            ]
        )

        output_file = os.path.join(
            OUTPUT_FOLDER,
            "sec_historical_fundamentals_long.csv"
        )

        df.to_csv(
            output_file,
            index=False
        )

        print()
        print("Extraction completed.")
        print("Total rows:", len(df))
        print("Companies:", df["ticker"].nunique())
        print("First filing date:", df["filing_date"].min())
        print("Last filing date:", df["filing_date"].max())
        print()
        print("Saved to:")
        print(output_file)

def collect_companyfacts(args):
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

def check_companyfacts(args):
    api_manifest=json.loads((args.api/'metadata.json').read_text())
    note_manifest=json.loads((args.notes/'manifest.json').read_text())
    if api_manifest.get('status')!='complete' or api_manifest.get('downloaded')!=50:
        raise ValueError('SEC API collection is not complete')
    cutoff=note_manifest['as_of_date'];companies=[]
    for ticker,entry in note_manifest['companies'].items():
        api_entry=api_manifest['files'][ticker];api_path=args.api/f'{ticker}_companyfacts.json'
        note_path=args.notes/entry['file']
        if sha256(api_path)!=api_entry['sha256'] or sha256(note_path)!=entry['sha256']:
            raise ValueError('Supplementary evidence hash changed')
        api=json.loads(api_path.read_text());notes=json.loads(note_path.read_text())
        if int(api['cik'])!=int(notes['financial']['cik']):raise ValueError('Issuer mismatch')
        index=set();future=0;historical=0
        for concept,data in api.get('facts',{}).get('us-gaap',{}).items():
            for row in data.get('units',{}).get('USD',[]):
                if row.get('filed','9999')>cutoff or row.get('end','9999')>cutoff:
                    future+=1;continue
                historical+=1
                index.add((concept,row.get('start'),row.get('end'),Decimal(str(row['val'])),row.get('accn')))
        per_role={}
        for role,source in notes.items():
            found=set();missed=set()
            for fact in source['facts']:
                if fact.get('dimensions') or 'us-gaap' not in fact['namespace']:continue
                if fact['period_end']!=source['report_date']:continue
                key=(fact['concept'],fact['period_start'],fact['period_end'],Decimal(fact['value']),source['accession_number'])
                (found if key in index else missed).add(key)
            per_role[role]=dict(exact_original_fact_matches=len(found),not_in_current_api=len(missed),
                accession_number=source['accession_number'],original_source=source['source_url'])
        companies.append(dict(ticker=ticker,api_sha256=api_entry['sha256'],api_url=api_entry['url'],
            api_observations_after_cutoff_excluded=future,eligible_historical_api_observations=historical,
            roles=per_role,decision_source='original eligible filings, never latest API values'))
    save_json(args.out,dict(cutoff=cutoff,companies=companies,api_files=50,
        api_manifest_sha256=sha256(args.api/'metadata.json'),notes_manifest_sha256=sha256(args.notes/'manifest.json'),
        current_api_used_as_historical_truth=False,
        exact_original_fact_matches=sum(r['roles'][role]['exact_original_fact_matches'] for r in companies for role in r['roles'])))
    print('All 50 SEC API snapshots checked against original filing contexts.')

def collect_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--user-agent', default=os.environ.get('SEC_USER_AGENT',
        'HalalifyAI Academic Research HalalifyAI.edu.@gmail.com'))
    args = parser.parse_args(argv)
    return collect_companyfacts(args)

def check_main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api',type=Path,required=True)
    parser.add_argument('--notes',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    return check_companyfacts(args)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    download = commands.add_parser('download', help='Download the registered company facts to a new raw folder')
    download.add_argument('--out', type=Path, required=True)
    download.add_argument('--user-agent')
    extract = commands.add_parser('extract', help='Extract existing CompanyFacts to a new intermediate folder')
    extract.add_argument('--input', type=Path, required=True)
    extract.add_argument('--out', type=Path, required=True)
    collect = commands.add_parser('collect', help='Collect supplementary screening snapshots')
    collect.add_argument('--repo', type=Path, default=Path.cwd())
    collect.add_argument('--out', type=Path, required=True)
    collect.add_argument('--user-agent', default=os.environ.get('SEC_USER_AGENT',
        'HalalifyAI Academic Research HalalifyAI.edu.@gmail.com'))
    check = commands.add_parser('check', help='Cross-check saved snapshots against original filings')
    check.add_argument('--api', type=Path, required=True)
    check.add_argument('--notes', type=Path, required=True)
    check.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'download':
        return download_companyfacts(args.out, args.user_agent)
    if args.command == 'extract':
        return extract_fundamentals(args.input, args.out)
    if args.command == 'collect':
        return collect_companyfacts(args)
    return check_companyfacts(args)

if __name__ == '__main__':
    main()
