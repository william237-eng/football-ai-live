"""
victory_storage.py
==================
Persistance SQLite pour l'historique des prédictions TOP VICTOIRES IA.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent.parent.parent / "database" / "victory_predictions.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS victory_predictions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id    INTEGER NOT NULL,
                home_team   TEXT,
                away_team   TEXT,
                league      TEXT,
                kick_off    TEXT,
                prediction  TEXT,
                winner      TEXT,
                win_prob    REAL,
                win_score   REAL,
                prob_score  TEXT,
                status      TEXT DEFAULT 'PENDING',
                result      TEXT,
                timestamp   TEXT,
                breakdown   TEXT
            )
        """)
        # Migration : ajouter colonnes manquantes si vieille DB
        existing = {row[1] for row in con.execute("PRAGMA table_info(victory_predictions)")}
        for col, defn in [
            ("home_logo", "TEXT"),
            ("away_logo", "TEXT"),
        ]:
            if col not in existing:
                con.execute(f"ALTER TABLE victory_predictions ADD COLUMN {col} {defn}")
        con.commit()


def prediction_exists(match_id: int) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM victory_predictions WHERE match_id=? AND status='PENDING'",
            (match_id,)
        ).fetchone()
        return row is not None


def save_prediction(
    match_id: int,
    home_team: str,
    away_team: str,
    league: str,
    kick_off: str,
    prediction: str,
    winner: str,
    win_prob: float,
    win_score: float,
    prob_score: str,
    breakdown: Dict,
    home_logo: str = "",
    away_logo: str = "",
) -> int:
    with _conn() as con:
        cur = con.execute("""
            INSERT INTO victory_predictions
            (match_id, home_team, away_team, league, kick_off, prediction,
             winner, win_prob, win_score, prob_score, status, timestamp, breakdown,
             home_logo, away_logo)
            VALUES (?,?,?,?,?,?,?,?,?,?,'PENDING',?,?,?,?)
        """, (
            match_id, home_team, away_team, league, kick_off, prediction,
            winner, win_prob, win_score, prob_score,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(breakdown),
            home_logo, away_logo,
        ))
        con.commit()
        return cur.lastrowid


def update_prediction_result(match_id: int, result: str) -> None:
    """result: 'WON' | 'LOST'"""
    status = "WON" if result == "WON" else "LOST"
    with _conn() as con:
        con.execute(
            "UPDATE victory_predictions SET status=?, result=? WHERE match_id=? AND status='PENDING'",
            (status, result, match_id)
        )
        con.commit()


def get_all_predictions(limit: int = 100) -> List[Dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM victory_predictions ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_pending_predictions() -> List[Dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM victory_predictions WHERE status='PENDING' ORDER BY timestamp DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> Dict[str, Any]:
    with _conn() as con:
        total = con.execute("SELECT COUNT(*) FROM victory_predictions").fetchone()[0]
        won   = con.execute("SELECT COUNT(*) FROM victory_predictions WHERE status='WON'").fetchone()[0]
        lost  = con.execute("SELECT COUNT(*) FROM victory_predictions WHERE status='LOST'").fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM victory_predictions WHERE status='PENDING'").fetchone()[0]
    resolved = won + lost
    winrate  = round(won / resolved * 100, 1) if resolved > 0 else 0.0
    return {
        "total":    total,
        "won":      won,
        "lost":     lost,
        "pending":  pending,
        "resolved": resolved,
        "winrate":  winrate,
    }


def get_daily_stats() -> Dict[str, Any]:
    """Statistiques journalières avec winrate, ROI et profit."""
    today = datetime.now(timezone.utc).date().isoformat()
    
    with _conn() as con:
        # Prédictions du jour
        daily = con.execute("""
            SELECT * FROM victory_predictions 
            WHERE DATE(timestamp) = ?
            ORDER BY timestamp DESC
        """, (today,)).fetchall()
        
        if not daily:
            return {
                "date": today,
                "selected": 0,
                "won": 0,
                "lost": 0,
                "pending": 0,
                "winrate": 0.0,
                "roi": 0.0,
                "profit": 0.0,
                "predictions": []
            }
        
        # Compter les résultats
        selected = len(daily)
        won = sum(1 for d in daily if d["status"] == "WON")
        lost = sum(1 for d in daily if d["status"] == "LOST")
        pending = sum(1 for d in daily if d["status"] == "PENDING")
        
        resolved = won + lost
        winrate = round(won / resolved * 100, 1) if resolved > 0 else 0.0
        
        # Calcul ROI et profit (simulation : 1 unité par prédiction gagnante = +0.8, perdue = -1)
        profit = (won * 0.8) - (lost * 1.0)
        roi = round((profit / selected) * 100, 1) if selected > 0 else 0.0
        
        return {
            "date": today,
            "selected": selected,
            "won": won,
            "lost": lost,
            "pending": pending,
            "winrate": winrate,
            "roi": roi,
            "profit": round(profit, 2),
            "predictions": [dict(d) for d in daily]
        }


def get_prediction_history(limit: int = 50) -> List[Dict]:
    """Historique complet des prédictions avec détails."""
    with _conn() as con:
        rows = con.execute("""
            SELECT * FROM victory_predictions 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,)).fetchall()
        
        history = []
        for row in rows:
            pred = dict(row)
            # Ajouter le score réel si disponible
            if pred["status"] in ("WON", "LOST"):
                pred["status_display"] = "✅ GAGNÉ" if pred["status"] == "WON" else "❌ PERDU"
            else:
                pred["status_display"] = "⏳ Attente"
            history.append(pred)
        
        return history
