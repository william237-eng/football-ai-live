"""
profile_manager.py
==================
Gestion du profil utilisateur : nom, photo de profil.
Stockage persistant SQLite dans database/user_profile.db
"""
from __future__ import annotations

import base64
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

DB_PATH = Path(__file__).parent.parent / "database" / "user_profile.db"

DEFAULT_USERNAME = "Utilisateur"
DEFAULT_AVATAR_EMOJI = "👤"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id       INTEGER PRIMARY KEY DEFAULT 1,
                username TEXT    DEFAULT 'Utilisateur',
                photo    BLOB    DEFAULT NULL
            )
        """)
        row = conn.execute("SELECT id FROM user_profile WHERE id = 1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO user_profile (id, username, photo) VALUES (1, ?, NULL)",
                (DEFAULT_USERNAME,),
            )


def get_profile() -> Tuple[str, Optional[bytes]]:
    """Retourne (username, photo_bytes_or_None)."""
    _init_db()
    with _get_conn() as conn:
        row = conn.execute("SELECT username, photo FROM user_profile WHERE id = 1").fetchone()
        if row:
            return row["username"], row["photo"]
    return DEFAULT_USERNAME, None


def save_profile(username: str, photo_bytes: Optional[bytes] = None) -> None:
    """Enregistre le nom et/ou la photo."""
    _init_db()
    with _get_conn() as conn:
        if photo_bytes is not None:
            conn.execute(
                "UPDATE user_profile SET username = ?, photo = ? WHERE id = 1",
                (username.strip() or DEFAULT_USERNAME, photo_bytes),
            )
        else:
            conn.execute(
                "UPDATE user_profile SET username = ? WHERE id = 1",
                (username.strip() or DEFAULT_USERNAME,),
            )


def photo_to_base64(photo_bytes: bytes) -> str:
    """Convertit les bytes de l'image en base64 pour l'affichage HTML."""
    return base64.b64encode(photo_bytes).decode("utf-8")


def get_avatar_html(size: int = 36, border_color: str = "#00d4ff") -> str:
    """Retourne le HTML de l'avatar (photo ou initiale) pour affichage inline."""
    username, photo = get_profile()
    initiale = (username[0].upper()) if username else "U"

    if photo:
        b64 = photo_to_base64(photo)
        return (
            f"<img src='data:image/png;base64,{b64}' "
            f"style='width:{size}px;height:{size}px;border-radius:50%;"
            f"border:2px solid {border_color};object-fit:cover;"
            f"vertical-align:middle;' />"
        )
    else:
        return (
            f"<div style='width:{size}px;height:{size}px;border-radius:50%;"
            f"background:linear-gradient(135deg,#00d4ff,#7c3aed);"
            f"border:2px solid {border_color};display:inline-flex;"
            f"align-items:center;justify-content:center;"
            f"font-weight:800;font-size:{size // 2.5:.0f}px;color:#fff;"
            f"vertical-align:middle;'>{initiale}</div>"
        )
