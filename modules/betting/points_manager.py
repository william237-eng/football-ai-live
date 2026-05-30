"""
points_manager.py
=================
Gestion des points utilisateur : débit, crédit, recharge automatique 12h.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple

from modules.betting.ticket_storage import (
    get_user,
    update_points,
    update_last_refill,
    DEFAULT_USER_ID,
    init_db,
)

TICKET_COST   = 5
REFILL_AMOUNT = 5
REFILL_HOURS  = 12


def _parse_dt(iso: str) -> datetime:
    try:
        return datetime.fromisoformat(iso)
    except Exception:
        return datetime.now(timezone.utc) - timedelta(hours=25)


def get_points_info(user_id: int = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Retourne les infos de points + refill_in si applicable."""
    init_db()
    user = get_user(user_id)
    points = user["points"]
    last_refill = _parse_dt(user.get("last_refill") or "")
    now = datetime.now(timezone.utc)

    # Refill automatique si 0 points et 12h écoulées
    elapsed = now - last_refill.astimezone(timezone.utc)
    refill_in_seconds = max(0, REFILL_HOURS * 3600 - elapsed.total_seconds())

    if points == 0 and elapsed.total_seconds() >= REFILL_HOURS * 3600:
        points += REFILL_AMOUNT
        update_points(user_id, points)
        update_last_refill(user_id)
        refill_in_seconds = REFILL_HOURS * 3600

    return {
        "points": points,
        "can_bet": points >= TICKET_COST,
        "refill_in_seconds": int(refill_in_seconds),
        "refill_in_label": _format_refill(refill_in_seconds) if points == 0 else None,
    }


def _format_refill(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h{m:02d}m"


def deduct_points(user_id: int = DEFAULT_USER_ID, amount: int = TICKET_COST) -> Tuple[bool, str]:
    """Déduit les points si suffisants. Retourne (succès, message)."""
    user = get_user(user_id)
    points = user["points"]
    if points < amount:
        return False, f"Points insuffisants ({points} ⭐ disponibles, {amount} ⭐ requis)"
    update_points(user_id, points - amount)
    return True, f"{amount} ⭐ débités. Solde : {points - amount} ⭐"


def credit_points(user_id: int = DEFAULT_USER_ID, amount: int = 0) -> None:
    """Crédite des points de récompense."""
    user = get_user(user_id)
    update_points(user_id, user["points"] + amount)
