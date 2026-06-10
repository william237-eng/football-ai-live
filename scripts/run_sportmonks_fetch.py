"""Small runner to test the asynchronous Sportmonks client locally.

Usage (PowerShell):

# set your API key in the current session (do NOT commit it)
$env:SPORTMONKS_API_KEY = '11IV8bGiXz2uqgj1E0JpRDQmT8TnET8xtXKd9F6aZy510DHB82vmesqHtHmS'
python .\scripts\run_sportmonks_fetch.py

Or from an already configured environment or CI where SPORTMONKS_API_KEY is set.
"""
from __future__ import annotations

import asyncio
from datetime import date
import os
import sys

from data_ingestion.sportmonks_async import fetch_fixtures_by_date, health_check


async def main() -> int:
    api_key = os.environ.get("SPORTMONKS_API_KEY")
    if not api_key:
        print("ERROR: SPORTMONKS_API_KEY not set in environment.\nSet it in PowerShell with:\n$env:SPORTMONKS_API_KEY = '11IV8bGiXz2uqgj1E0JpRDQmT8TnET8xtXKd9F6aZy510DHB82vmesqHtHmS'", file=sys.stderr)
        return 2

    today = date.today().isoformat()
    print(f"Fetching fixtures for {today}...")
    try:
        fixtures = await fetch_fixtures_by_date(today)
        print(f"Received {len(fixtures)} fixtures (raw objects).\nFirst 3 items:")
        for f in fixtures[:3]:
            print(f)
        return 0
    except Exception as exc:
        print("Fetch failed:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

