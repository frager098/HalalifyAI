import os
import json
import pandas as pd


INPUT_FOLDER = "data/raw/sec"
OUTPUT_FOLDER = "data/processed"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


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