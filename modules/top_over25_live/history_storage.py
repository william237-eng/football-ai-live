"""
history_storage.py
==================
Stockage SQLite de l'historique des prédictions Over 2.5.
Table : over25_history
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "database", "over25_history.db"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS over25_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id      INTEGER NOT NULL,
                home_name       TEXT,
                away_name       TEXT,
                league_name     TEXT,
                league_country  TEXT,
                match_date      TEXT,
                initial_prob    REAL,
                initial_pct     REAL,
                conf_label      TEXT,
                result          TEXT,
                home_score      INTEGER,
                away_score      INTEGER,
                total_goals     INTEGER,
                validated_at    TEXT,
                created_at      TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_fid ON over25_history(fixture_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_date ON over25_history(match_date)")


def fixture_exists(fixture_id: int) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM over25_history WHERE fixture_id=?", (fixture_id,)
        ).fetchone()
    return row is not None


def save_result(match_data: Dict[str, Any]) -> None:
    """Enregistre un match terminé dans l'historique (une seule fois par fixture_id)."""
    fid = match_data.get("fixture_id")
    if not fid:
        return
    if fixture_exists(fid):
        return  # déjà enregistré

    val = match_data.get("validation") or {}
    result = val.get("result", "UNKNOWN")
    total  = match_data.get("home_score", 0) + match_data.get("away_score", 0)

    with _conn() as c:
        c.execute("""
            INSERT INTO over25_history
                (fixture_id, home_name, away_name, league_name, league_country,
                 match_date, initial_prob, initial_pct, conf_label,
                 result, home_score, away_score, total_goals,
                 validated_at, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            fid,
            match_data.get("home_name", ""),
            match_data.get("away_name", ""),
            match_data.get("league_name", ""),
            match_data.get("league_country", ""),
            match_data.get("start_date_display", ""),
            match_data.get("initial_prob", match_data.get("over25_prob", 0.0)),
            match_data.get("initial_pct",  match_data.get("over25_pct",  0.0)),
            match_data.get("conf_label", ""),
            result,
            match_data.get("home_score", 0),
            match_data.get("away_score", 0),
            total,
            _now_iso(),
            _now_iso(),
        ))


def get_history(days: int = 30) -> List[Dict]:
    """Récupère l'historique des N derniers jours."""
    init_db()
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM over25_history WHERE validated_at >= ? ORDER BY validated_at DESC",
            (cutoff,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_history() -> List[Dict]:
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM over25_history ORDER BY validated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]
