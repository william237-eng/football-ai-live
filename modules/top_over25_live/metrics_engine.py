"""
metrics_engine.py
=================
Calcule les métriques de performance du moteur Over 2.5 :
- Winrate (%)
- ROI simulé (cote fixe 1.85 standard Over 2.5)
- Breakdown par période (aujourd'hui / 7j / 30j)
"""
from __future__ import annotations

from typing import Any, Dict, List

from modules.top_over25_live.history_storage import get_history, init_db

# Cote fixe simulée pour Over 2.5 (marché standard bookmaker)
SIMULATED_ODD = 1.85
STAKE_PER_BET = 1.0  # unité normalisée


def compute_metrics(days: int = 7) -> Dict[str, Any]:
    """
    Calcule les métriques sur les `days` derniers jours.
    Retourne un dict avec : total, won, lost, winrate, roi, profit.
    """
    init_db()
    history = get_history(days=days)

    total = len(history)
    won   = sum(1 for r in history if r.get("result") == "VALIDATED")
    lost  = sum(1 for r in history if r.get("result") == "FAILED")

    winrate = round(won / total * 100, 1) if total > 0 else 0.0

    # ROI simulé : chaque pari = 1 unité à cote 1.85
    total_staked = total * STAKE_PER_BET
    total_return = won * SIMULATED_ODD * STAKE_PER_BET
    profit = round(total_return - total_staked, 2)
    roi    = round((profit / total_staked) * 100, 1) if total_staked > 0 else 0.0

    return {
        "days":       days,
        "total":      total,
        "won":        won,
        "lost":       lost,
        "winrate":    winrate,
        "profit":     profit,
        "roi":        roi,
        "odd_used":   SIMULATED_ODD,
    }


def compute_all_periods() -> Dict[str, Dict[str, Any]]:
    """Retourne les métriques pour aujourd'hui (1j), 7j et 30j."""
    return {
        "today":   compute_metrics(days=1),
        "week":    compute_metrics(days=7),
        "month":   compute_metrics(days=30),
    }
