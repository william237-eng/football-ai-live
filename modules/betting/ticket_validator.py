"""
ticket_validator.py
===================
Vérifie le résultat d'un item de pari via l'API Football.
Supporte : 1X2, Double Chance, BTTS, Over/Under Buts, Score Exact,
           Prochain But (approx), Mi-temps, Corners, Cartons.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def _goals(fixture: Dict) -> Tuple[int, int]:
    goals = fixture.get("goals") or {}
    h = int(goals.get("home") or 0)
    a = int(goals.get("away") or 0)
    return h, a


def _ht_goals(fixture: Dict) -> Tuple[int, int]:
    score = fixture.get("score") or {}
    ht = score.get("halftime") or {}
    h = int(ht.get("home") or 0)
    a = int(ht.get("away") or 0)
    return h, a


def _status(fixture: Dict) -> str:
    status = fixture.get("fixture", {}).get("status", {})
    return (status.get("short") or status.get("long") or "NS").upper()


def is_finished(fixture: Dict) -> bool:
    return _status(fixture) in ("FT", "AET", "PEN", "AWD", "WO")


def check_item(
    market: str,
    prediction: str,
    fixture: Dict,
    stats: Optional[Dict] = None,
    events: Optional[list] = None,
) -> str:
    """
    Retourne 'WON', 'LOST', ou 'PENDING'.
    fixture est un dict brut d'une réponse API Football (fixture object).
    """
    if not is_finished(fixture):
        return "PENDING"

    h, a = _goals(fixture)
    total = h + a

    # ── 1X2 ──────────────────────────────────────────────────────────────────
    if market == "1X2":
        if prediction == "Domicile (1)":
            return "WON" if h > a else "LOST"
        if prediction == "Nul (X)":
            return "WON" if h == a else "LOST"
        if prediction == "Extérieur (2)":
            return "WON" if a > h else "LOST"

    # ── Double Chance ─────────────────────────────────────────────────────────
    if market == "Double Chance":
        if prediction == "1X":
            return "WON" if h >= a else "LOST"
        if prediction == "X2":
            return "WON" if a >= h else "LOST"
        if prediction == "12":
            return "WON" if h != a else "LOST"

    # ── BTTS ─────────────────────────────────────────────────────────────────
    if market == "BTTS":
        btts = h > 0 and a > 0
        if prediction == "GG Oui":
            return "WON" if btts else "LOST"
        if prediction == "GG Non":
            return "WON" if not btts else "LOST"

    # ── Over/Under Buts ──────────────────────────────────────────────────────
    if market == "Over/Under Buts":
        try:
            direction, thresh_str = prediction.split(" ", 1)
            thresh = float(thresh_str)
        except Exception:
            return "LOST"
        if direction == "Over":
            return "WON" if total > thresh else "LOST"
        if direction == "Under":
            return "WON" if total < thresh else "LOST"

    # ── Score Exact ──────────────────────────────────────────────────────────
    if market == "Score Exact":
        try:
            ph, pa = prediction.split("-")
            return "WON" if h == int(ph) and a == int(pa) else "LOST"
        except Exception:
            return "LOST"

    # ── Mi-temps ─────────────────────────────────────────────────────────────
    if market == "Mi-temps":
        hh, ha = _ht_goals(fixture)
        if prediction == "Domicile marque 1ère MT":
            return "WON" if hh > 0 else "LOST"
        if prediction == "Extérieur marque 1ère MT":
            return "WON" if ha > 0 else "LOST"
        if prediction == "Domicile marque 2ème MT":
            home_ht2 = h - hh
            return "WON" if home_ht2 > 0 else "LOST"
        if prediction == "Extérieur marque 2ème MT":
            away_ht2 = a - ha
            return "WON" if away_ht2 > 0 else "LOST"
        if prediction == "BTTS 1ère MT":
            return "WON" if hh > 0 and ha > 0 else "LOST"
        if prediction == "Over 0.5 1ère MT":
            return "WON" if hh + ha > 0 else "LOST"

    # ── Corners ──────────────────────────────────────────────────────────────
    if market == "Corners":
        total_corners = 0
        if stats:
            for side in stats:
                for row in (side.get("statistics") or []):
                    if (row.get("type") or "").lower() in ("corner kicks", "corners"):
                        try:
                            total_corners += int(str(row.get("value") or 0).replace("%", ""))
                        except Exception:
                            pass
        try:
            direction, thresh_str = prediction.split(" ", 1)
            thresh = float(thresh_str)
        except Exception:
            return "LOST"
        if direction == "Over":
            return "WON" if total_corners > thresh else "LOST"
        if direction == "Under":
            return "WON" if total_corners < thresh else "LOST"

    # ── Cartons ──────────────────────────────────────────────────────────────
    if market == "Cartons":
        total_cards = 0
        if events:
            for ev in events:
                ev_type = (ev.get("type") or "").lower()
                if "card" in ev_type:
                    total_cards += 1
        try:
            direction, thresh_str = prediction.split(" ", 1)
            thresh = float(thresh_str)
        except Exception:
            return "LOST"
        if direction == "Over":
            return "WON" if total_cards > thresh else "LOST"
        if direction == "Under":
            return "WON" if total_cards < thresh else "LOST"

    # ── Prochain But (vérification approximative) ─────────────────────────────
    if market == "Prochain But":
        if prediction == "Aucun but":
            return "WON" if total == 0 else "LOST"
        # On ne peut pas déterminer exactement le prochain but a posteriori
        # On évalue simplement qui a marqué plus
        if prediction == "Domicile":
            return "WON" if h > 0 else "LOST"
        if prediction == "Extérieur":
            return "WON" if a > 0 else "LOST"

    return "LOST"
