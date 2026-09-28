import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

# Alpaca


# 1. LOAD ALPACA API KEYS


load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    raise ValueError(
        "Alpaca API keys were not found. Check your .env file."
    )


# 2. STOCKS FOR OUR HALALIFY PROTOTYPE

# 50 large U.S.-listed stocks across multiple sectors.
# This is an initial research universe; it is NOT the
# result of Shariah screening.

SYMBOLS = [
    # Technology
    "AAPL", "MSFT", "NVDA", "AMD", "AVGO",
    "ORCL", "ADBE", "CRM", "CSCO", "INTC",

    # Communication / Internet
    "GOOGL", "META", "NFLX",

    # Consumer
    "AMZN", "TSLA", "HD", "LOW", "NKE",
    "SBUX", "MCD", "COST", "WMT",

    # Healthcare
    "JNJ", "LLY", "ABBV", "MRK", "TMO",
    "ABT", "DHR",

    # Industrials
    "CAT", "DE", "HON", "UPS", "UNP",
    "GE",

    # Energy
    "XOM", "CVX", "COP", "SLB",

    # Financial
    "JPM", "BAC", "GS", "MS", "V",
    "MA",

    # Other large companies
    "PG", "KO", "PEP", "LIN", "NEE"
]


# --------------------------------------------------
# 3. DATE RANGE
# --------------------------------------------------

START_DATE = "2016-01-01"
END_DATE = "2026-09-28"

URL = "https://data.alpaca.markets/v2/stocks/bars"

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}



# 4. DOWNLOAD FUNCTION


def download_stock_data(symbols):

    params = {
        "symbols": ",".join(symbols),
        "timeframe": "1Day",
        "start": START_DATE,
        "end": END_DATE,

        # Maximum records Alpaca allows per page
        "limit": 10000,

        # Free Alpaca stock feed
        "feed": "iex",

        # Adjust historical prices for corporate actions
        "adjustment": "all",

        # Oldest data first
        "sort": "asc"
    }

    all_rows = []
    page_number = 1

    while True:

        print(f"Downloading page {page_number}...")

        response = requests.get(
            URL,
            headers=HEADERS,
            params=params,
            timeout=60
        )

        # Stop if Alpaca returns an error
        response.raise_for_status()

        data = response.json()

        bars_by_symbol = data.get("bars", {})

        # Extract every stock and every daily bar
        for ticker, bars in bars_by_symbol.items():

            for bar in bars:

                all_rows.append({
                    "date": bar["t"],
                    "ticker": ticker,
                    "open": bar["o"],
                    "high": bar["h"],
                    "low": bar["l"],
                    "close": bar["c"],
                    "volume": bar["v"]
                })

        # Alpaca pagination
        next_token = data.get("next_page_token")

        if not next_token:
            break

        params["page_token"] = next_token

        page_number += 1

        # Small pause between requests
        time.sleep(0.2)

    return pd.DataFrame(all_rows)


# --------------------------------------------------
# 5. DOWNLOAD
# --------------------------------------------------

print("---------------------------------------")
print("HALALIFY HISTORICAL DATA DOWNLOADER")
print("---------------------------------------")

print(f"Requested stocks: {len(SYMBOLS)}")
print(f"Requested period: {START_DATE} to {END_DATE}")
print()

df = download_stock_data(SYMBOLS)


# 6. CHECK THAT DATA EXISTS


if df.empty:
    raise ValueError("Alpaca returned no historical data.")


# 7. CLEAN BASIC FORMAT


df["date"] = pd.to_datetime(df["date"]).dt.date

df = df.sort_values(
    ["ticker", "date"]
).reset_index(drop=True)


# 8. REMOVE DUPLICATES


before = len(df)

df = df.drop_duplicates(
    subset=["ticker", "date"]
)

duplicates_removed = before - len(df)


# 9. SAVE RAW DATA


os.makedirs("data/raw", exist_ok=True)

output_file = "data/raw/alpaca_historical_prices.csv"

df.to_csv(
    output_file,
    index=False
)

# 10. CREATE SUMMARY FOR EACH STOCK


summary = (
    df.groupby("ticker")
    .agg(
        rows=("date", "count"),
        first_date=("date", "min"),
        last_date=("date", "max")
    )
    .reset_index()
)

summary_file = "data/raw/alpaca_data_summary.csv"

summary.to_csv(
    summary_file,
    index=False
)


# 11. FINAL REPORT


print()
print("---------------------------------------")
print("DOWNLOAD COMPLETED")
print("---------------------------------------")

print(f"Requested stocks : {len(SYMBOLS)}")
print(f"Stocks received  : {df['ticker'].nunique()}")
print(f"Total rows       : {len(df):,}")
print(f"Duplicates removed: {duplicates_removed}")

print()
print("Actual dataset period:")
print("From:", df["date"].min())
print("To  :", df["date"].max())

print()
print("Files created:")
print(output_file)
print(summary_file)

print()
print("STOCK-BY-STOCK SUMMARY")
print(summary.to_string(index=False))



# 12. CHECK FOR MISSING STOCKS


received = set(df["ticker"].unique())

missing = sorted(set(SYMBOLS) - received)

if missing:
    print()
    print("WARNING - No data returned for:")
    print(missing)
else:
    print()
    print("All requested stocks returned data.")