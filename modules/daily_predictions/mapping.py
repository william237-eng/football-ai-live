"""Mapping des marchés vers les rubriques UI.
la logique qui décide dans quelle rubrique (wins, double_chance, btts,
corners_cards) classer une prédiction selon la valeur de `market` provenant de la DB.
"""
from __future__ import annotations

from typing import Literal


Bucket = Literal["wins", "double_chance", "btts", "corners_cards"]


def map_market_to_bucket(market: str) -> Bucket:
    m = (market or "").upper()

    # Corners + cards
    if any(k in m for k in ("YELLOW", "CARTON", "CARTONS", "CORNERS")):
        return "corners_cards"

    # Double chance explicit
    if "DOUBLE" in m or "DC" in m or "1X" in m or "X2" in m or "12" in m:
        return "double_chance"

    # BTTS / GG
    if any(k in m for k in ("BTTS", "GG", "BOTH")):
        return "btts"

    # Victory markets
    if any(k in m for k in ("WIN", "VICT", "MATCH")) or "1" in m or "2" in m:
        return "wins"

    # Fallback conservative: BTTS
    return "btts"

