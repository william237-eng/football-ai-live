"""Synchronous helpers to read migrated predictions from the local SQLite DB.

This module is intentionally synchronous so it can be used from Streamlit UI
without extra async plumbing.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Any


def _get_db_path() -> str:
    dsn = os.getenv("QL_DB_DSN", "sqlite:///./quant_engine.db")
    return dsn.replace("sqlite:///", "")


def get_todays_predictions(limit: int = 50) -> List[Dict[str, Any]]:
    """Return up to `limit` predictions whose timestamp_prediction is today.

    Converts DB rows to a normalized dict used by the UI rendering functions.
    """
    db = _get_db_path()
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    today = datetime.utcnow().date().isoformat()
    # match timestamp_prediction starting with today's date
    like = today + "%"
    rows = cur.execute(
        "SELECT fixture_id, market, probability, probability_pct, confidence, raw FROM predictions WHERE timestamp_prediction LIKE ? ORDER BY timestamp_prediction DESC LIMIT ?",
        (like, limit),
    ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        raw = {}
        try:
            raw = json.loads(r["raw"]) if r["raw"] else {}
        except Exception:
            raw = {}

        item = {
            "fixture_id": r["fixture_id"],
            "home_name": raw.get("home_name") or raw.get("home") or raw.get("home_team") or "—",
            "away_name": raw.get("away_name") or raw.get("away") or raw.get("away_team") or "—",
            "league_name": raw.get("league_name") or raw.get("league") or "—",
            "league_country": raw.get("league_country") or raw.get("league_country") or "—",
            "start_time": raw.get("start_time") or raw.get("start_date_display") or "—",
            "market": r["market"],
            "prediction": raw.get("prediction") or r["market"],
            "probability": r["probability"] or 0.0,
            "probability_pct": r["probability_pct"] or 0.0,
            "confidence": r["confidence"] or raw.get("confidence") or "—",
            "raw": raw,
        }
        out.append(item)

    conn.close()
    return out

