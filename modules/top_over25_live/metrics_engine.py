"""
metrics_engine.py
=================
Calcule les métriques de performance RÉELLES du moteur Over 2.5.
Source : prediction_registry (prédictions réellement émises).
Jamais depuis l'historique brut — jamais de 100% artificiel.
"""
from __future__ import annotations

from typing import Any, Dict

from modules.top_over25_live.prediction_registry import compute_real_stats


def compute_metrics(days: int = 7) -> Dict[str, Any]:
    """
    Calcule les métriques sur les `days` derniers jours
    en se basant UNIQUEMENT sur les prédictions du registre.
    """
    return compute_real_stats(days=days)


def compute_all_periods() -> Dict[str, Dict[str, Any]]:
    """Retourne les métriques pour aujourd'hui (1j), 7j et 30j."""
    return {
        "today": compute_real_stats(days=1),
        "week":  compute_real_stats(days=7),
        "month": compute_real_stats(days=30),
    }
