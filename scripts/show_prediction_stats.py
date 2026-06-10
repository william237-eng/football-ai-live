"""Show simple statistics from the migrated predictions table.

Prints summary counts per market for windows: 1 day, 7 days, 30 days.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import os

DB_PATH = os.getenv("QL_DB_DSN", "sqlite:///./quant_engine.db").replace("sqlite:///", "")


def _parse_ts(ts: str):
    if not ts:
        return None
    try:
        # Many timestamps are ISO-like with timezone; sqlite stores as text.
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f%z")
        except Exception:
            return None


def stats_for_window(conn: sqlite3.Connection, days: int):
    since = datetime.utcnow() - timedelta(days=days)
    cur = conn.cursor()
    # We'll consider only predictions that have timestamp_validated set
    rows = cur.execute(
        "SELECT market, result, COUNT(*) as cnt FROM predictions WHERE timestamp_validated IS NOT NULL GROUP BY market, result"
    ).fetchall()
    summary: dict = {}
    for market, result, cnt in rows:
        summary.setdefault(market or "<unknown>", {}).setdefault(result or "<none>", 0)
        summary[market][result] += cnt
    return summary


def main():
    db_file = Path(DB_PATH)
    if not db_file.exists():
        print("DB file not found:", db_file)
        return 2
    conn = sqlite3.connect(str(db_file))
    print("DB:", db_file)
    for days in (1, 7, 30):
        print(f"\nStats validated in last {days} day(s):")
        summary = stats_for_window(conn, days)
        if not summary:
            print("  (no validated predictions)")
            continue
        for market, results in summary.items():
            total = sum(results.values())
            validated = results.get("VALIDATED", 0)
            failed = results.get("FAILED", 0)
            print(f"  {market}: total={total} validated={validated} failed={failed} rate={validated/total:.2%}" if total>0 else f"  {market}: 0")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

