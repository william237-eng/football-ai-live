"""
ticket_storage.py
=================
Couche SQLite : initialisation schema, CRUD pour user_points, bet_tickets, bet_items.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent.parent.parent / "database" / "betting.db"

DEFAULT_USER_ID = 1  # app mono-utilisateur


# ─────────────────────────────────────────────────────────────────────────────
# Init
# ─────────────────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crée les tables si elles n'existent pas encore."""
    with _get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_points (
            user_id    INTEGER PRIMARY KEY,
            points     INTEGER DEFAULT 10,
            last_refill TEXT,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS bet_tickets (
            ticket_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER,
            fixture_ids    TEXT,
            ticket_status  TEXT DEFAULT 'ACTIVE',
            points_used    INTEGER DEFAULT 5,
            reward_points  INTEGER DEFAULT 0,
            sold_price     INTEGER DEFAULT 0,
            created_at     TEXT,
            updated_at     TEXT
        );

        CREATE TABLE IF NOT EXISTS bet_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id    INTEGER,
            fixture_id   INTEGER,
            home_team    TEXT,
            away_team    TEXT,
            market       TEXT,
            prediction   TEXT,
            result       TEXT DEFAULT 'PENDING',
            kick_off     TEXT,
            odds         REAL DEFAULT 1.0,
            live_minute  INTEGER DEFAULT 0,
            created_at   TEXT
        );
        """)
        # Migration : ajouter colonnes manquantes si DB existante
        for col, definition in [
            ("sold_price",  "INTEGER DEFAULT 0"),
            ("kick_off",    "TEXT"),
            ("odds",        "REAL DEFAULT 1.0"),
            ("live_minute", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE bet_items ADD COLUMN {col} {definition}")
            except Exception:
                pass
        try:
            conn.execute("ALTER TABLE bet_tickets ADD COLUMN sold_price INTEGER DEFAULT 0")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# user_points
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_user(user_id: int = DEFAULT_USER_ID) -> Dict[str, Any]:
    init_db()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_points WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO user_points (user_id, points, last_refill, created_at) VALUES (?,?,?,?)",
                (user_id, 10, _now(), _now()),
            )
            row = conn.execute(
                "SELECT * FROM user_points WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row)


def update_points(user_id: int, new_points: int) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE user_points SET points = ? WHERE user_id = ?",
            (new_points, user_id),
        )


def update_last_refill(user_id: int) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE user_points SET last_refill = ? WHERE user_id = ?",
            (_now(), user_id),
        )


# ─────────────────────────────────────────────────────────────────────────────
# bet_tickets
# ─────────────────────────────────────────────────────────────────────────────

def create_ticket(
    user_id: int,
    fixture_ids: List[int],
    points_used: int = 5,
) -> int:
    """Crée un ticket et retourne son ticket_id."""
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO bet_tickets
               (user_id, fixture_ids, ticket_status, points_used, reward_points, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                user_id,
                json.dumps(fixture_ids),
                "ACTIVE",
                points_used,
                0,
                _now(),
                _now(),
            ),
        )
        return cur.lastrowid


def get_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM bet_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_tickets(
    user_id: int = DEFAULT_USER_ID,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM bet_tickets WHERE user_id = ? AND ticket_status = ? ORDER BY created_at DESC",
                (user_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM bet_tickets WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def update_ticket_status(ticket_id: int, status: str, reward_points: int = 0) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE bet_tickets SET ticket_status = ?, reward_points = ?, updated_at = ? WHERE ticket_id = ?",
            (status, reward_points, _now(), ticket_id),
        )


# ─────────────────────────────────────────────────────────────────────────────
# bet_items
# ─────────────────────────────────────────────────────────────────────────────

def add_bet_item(
    ticket_id: int,
    fixture_id: int,
    home_team: str,
    away_team: str,
    market: str,
    prediction: str,
    kick_off: str = "",
    odds: float = 1.0,
    live_minute: int = 0,
) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO bet_items
               (ticket_id, fixture_id, home_team, away_team, market, prediction,
                result, kick_off, odds, live_minute, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (ticket_id, fixture_id, home_team, away_team, market, prediction,
             "PENDING", kick_off, odds, live_minute, _now()),
        )
        return cur.lastrowid


def update_item_live_minute(item_id: int, minute: int) -> None:
    """Met à jour le temps de jeu live d'un item."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE bet_items SET live_minute = ? WHERE id = ?",
            (minute, item_id),
        )


def sell_ticket(ticket_id: int, sell_price: int) -> None:
    """Marque un ticket comme vendu et enregistre le prix de vente."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE bet_tickets SET ticket_status = 'SOLD', sold_price = ?, updated_at = ? WHERE ticket_id = ?",
            (sell_price, _now(), ticket_id),
        )


def get_ticket_items(ticket_id: int) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM bet_items WHERE ticket_id = ? ORDER BY id",
            (ticket_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_item_result(item_id: int, result: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE bet_items SET result = ? WHERE id = ?",
            (result, item_id),
        )


def delete_ticket(ticket_id: int, user_id: int = DEFAULT_USER_ID) -> bool:
    """
    Supprime complètement un ticket et tous ses items.
    Retourne True si succès, False si erreur.
    """
    try:
        with _get_conn() as conn:
            # Vérifier que le ticket appartient à l'utilisateur
            ticket = conn.execute(
                "SELECT ticket_id FROM bet_tickets WHERE ticket_id = ? AND user_id = ?",
                (ticket_id, user_id)
            ).fetchone()
            
            if not ticket:
                return False
            
            # Supprimer d'abord les items du ticket
            conn.execute(
                "DELETE FROM bet_items WHERE ticket_id = ?",
                (ticket_id,)
            )
            
            # Supprimer le ticket lui-même
            conn.execute(
                "DELETE FROM bet_tickets WHERE ticket_id = ? AND user_id = ?",
                (ticket_id, user_id)
            )
            
            return True
    except Exception:
        return False


def has_duplicate_ticket(user_id: int, fixture_ids: List[int], predictions: List[str]) -> bool:
    """Vérifie si un ticket identique (mêmes fixtures + prédictions) existe déjà ACTIVE."""
    tickets = get_user_tickets(user_id, status="ACTIVE")
    key = json.dumps(sorted(fixture_ids)) + "|" + "|".join(sorted(predictions))
    for t in tickets:
        items = get_ticket_items(t["ticket_id"])
        t_fids = sorted([i["fixture_id"] for i in items])
        t_preds = sorted([i["prediction"] for i in items])
        t_key = json.dumps(t_fids) + "|" + "|".join(t_preds)
        if t_key == key:
            return True
    return False
