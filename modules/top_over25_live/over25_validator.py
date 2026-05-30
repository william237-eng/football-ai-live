"""
over25_validator.py
===================
Validation automatique : si le match est terminé, détermine si l'Over 2.5 est validé.
"""
from __future__ import annotations
from typing import Any, Dict


def validate_over25(match_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vérifie le résultat final Over 2.5.
    Retourne le match_data enrichi avec le champ 'validation'.
    """
    is_finished = match_data.get("is_finished", False)
    home_score  = match_data.get("home_score", 0)
    away_score  = match_data.get("away_score", 0)
    total       = home_score + away_score

    if not is_finished:
        match_data["validation"] = None
        return match_data

    if total >= 3:
        match_data["validation"] = {
            "result":  "VALIDATED",
            "label":   "✅ VALIDÉ",
            "reason":  f"Total buts : {total} ≥ 3",
            "color":   "#22c55e",
            "bg":      "rgba(34,197,94,0.12)",
            "border":  "#22c55e",
        }
    else:
        match_data["validation"] = {
            "result":  "FAILED",
            "label":   "❌ ÉCHOUÉ",
            "reason":  f"Total buts : {total} < 3",
            "color":   "#ef4444",
            "bg":      "rgba(239,68,68,0.12)",
            "border":  "#ef4444",
        }

    return match_data
