import os
import json
import time
import requests


SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMD", "AVGO",
    "ORCL", "ADBE", "CRM", "CSCO", "INTC",

    "GOOGL", "META", "NFLX",

    "AMZN", "TSLA", "HD", "LOW", "NKE",
    "SBUX", "MCD", "COST", "WMT",

    "JNJ", "LLY", "ABBV", "MRK", "TMO",
    "ABT", "DHR",

    "CAT", "DE", "HON", "UPS", "UNP", "GE",

    "XOM", "CVX", "COP", "SLB",

    "JPM", "BAC", "GS", "MS", "V", "MA",

    "PG", "KO", "PEP", "LIN", "NEE"
]


HEADERS = {
    "User-Agent": "HalalifyAI.edu.@gmail.com",
    "Accept-Encoding": "gzip, deflate"
}


OUTPUT_FOLDER = "data/raw/sec"

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