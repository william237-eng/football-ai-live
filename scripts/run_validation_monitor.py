"""Run a validation monitor that checks pending predictions and marks them VALIDATED/FAILED.

This script:
 - connects to the AsyncDB wrapper
 - selects predictions with status='pending'
 - for each prediction it queries Sportmonks events and fixture detail
 - counts cards and marks result according to market thresholds

Usage (PowerShell):
 $env:SPORTMONKS_API_KEY = '11IV8bGiXz2uqgj1E0JpRDQmT8TnET8xtXKd9F6aZy510DHB82vmesqHtHmS'
 $env:QL_DB_DSN = 'sqlite:///./quant_engine.db'
 $env:PYTHONPATH = '<repo_root>'
 python .\scripts\run_validation_monitor.py
"""
import asyncio
import os
from datetime import datetime

from storage.db import AsyncDB
from data_ingestion.sportmonks_async import fetch_fixture_events, fetch_fixture_detail


MARKET_THRESHOLDS = {
    "OVER_3.5_YELLOWS": 4,
    "OVER_7.5_YELLOWS": 8,
    "OVER_2.5": None,  # goals market handled elsewhere
}


async def validate_pending_once(db: AsyncDB) -> None:
    rows = await db.fetchall("SELECT id, fixture_id, market, raw FROM predictions WHERE status='pending'")
    if not rows:
        print("No pending predictions found.")
        return
    print(f"Found {len(rows)} pending predictions")

    for r in rows:
        pred_id = r.get("id")
        fixture_id = r.get("fixture_id")
        market = (r.get("market") or "").upper()
        print(f"Checking prediction id={pred_id} fixture={fixture_id} market={market}")

        events = []
        try:
            # guard per-fixture to avoid long hangs
            events = await asyncio.wait_for(fetch_fixture_events(int(fixture_id)), timeout=12)
        except asyncio.TimeoutError:
            print(f"  Timeout fetching events for {fixture_id}; skipping")
            events = []
        except Exception as e:
            print(f"  Error fetching events for {fixture_id}: {e}")
            events = []

        # If no events, try fixture detail to see if match is finished
        finished = False
        try:
            detail = await fetch_fixture_detail(int(fixture_id))
            status = detail.get("status") or detail.get("fixture_status") or {}
            # try common keys
            if isinstance(status, dict):
                short = status.get("short") or status.get("long") or ""
                if str(short).lower() in ("ft", "fulltime", "finished", "finished"):
                    finished = True
            else:
                if str(status).lower() in ("ft", "fulltime", "finished"):
                    finished = True
        except Exception:
            detail = {}

        if not events and not finished:
            print(f"  No events and match not finished; skipping id={pred_id}")
            continue

        # count card-like events
        total_cards = 0
        for ev in events:
            # support multiple shapes
            typ = ""
            if isinstance(ev, dict):
                typ = (ev.get("type") or ev.get("event") or ev.get("detail") or "").lower()
            else:
                typ = str(ev).lower()
            if "card" in typ or "yellow" in typ or "red" in typ:
                total_cards += 1

        print(f"  total_cards observed={total_cards}")

        threshold = MARKET_THRESHOLDS.get(market)
        if threshold is None:
            # Not a cards market we validate here; mark skipped
            print(f"  Market {market} not handled by this monitor; skipping")
            continue

        result = "FAILED"
        if total_cards >= threshold:
            result = "VALIDATED"

        ts_valid = datetime.utcnow().isoformat() + "Z"
        # update DB: set status to 'validated' and result to VALIDATED/FAILED
        await db.execute(
            "UPDATE predictions SET status=?, result=?, total_cards_final=?, timestamp_validated=? WHERE id=?",
            ("validated", result, total_cards, ts_valid, pred_id),
        )
        print(f"  prediction id={pred_id} -> {result}")


async def main() -> int:
    db_dsn = os.getenv("QL_DB_DSN", "sqlite:///./quant_engine.db")
    db = AsyncDB(dsn=db_dsn)
    await db.connect()
    await db.ensure_schema()
    await validate_pending_once(db)
    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

