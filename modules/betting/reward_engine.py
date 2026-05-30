"""
reward_engine.py
================
Calcule les récompenses selon nombre de sélections gagnées.
"""
from __future__ import annotations

from typing import Dict, Any


# Barème de récompense : nb_sélections → multiplicateur
_REWARD_TABLE = {
    1: 1,    # 1 sél  → x1  = 5⭐ remboursé
    2: 2,    # 2 sél  → x2  = 10⭐
    3: 4,    # 3 sél  → x4  = 20⭐
    4: 7,    # 4 sél  → x7  = 35⭐
    5: 12,   # 5 sél  → x12 = 60⭐
    6: 20,   # 6 sél  → x20 = 100⭐
}
_DEFAULT_MULTIPLIER = 30  # 7+ sélections


def compute_reward(points_used: int, nb_selections: int) -> Dict[str, Any]:
    """
    Calcule la récompense pour un ticket gagnant.
    Returns dict avec multiplier, reward_points, label.
    """
    mult = _REWARD_TABLE.get(nb_selections, _DEFAULT_MULTIPLIER)
    reward = points_used * mult
    return {
        "multiplier": mult,
        "reward_points": reward,
        "label": f"+{reward} ⭐ (×{mult})",
    }
