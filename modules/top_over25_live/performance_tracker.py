"""
performance_tracker.py
======================
Enregistre dans l'historique SQLite UNIQUEMENT les matchs
qui ont été réellement prédits (présents dans le registre).
"""
from __future__ import annotations

from typing import Any, Dict, List

from modules.top_over25_live.history_storage import init_db, save_result
from modules.top_over25_live.prediction_registry import prediction_exists


def track_resolved_matches(matches: List[Dict[str, Any]]) -> int:
    """
    Pour chaque match terminé avec validation,
    l'enregistre dans l'historique SEULEMENT s'il était prédit.
    Retourne le nombre de nouveaux enregistrements.
    """
    init_db()
    saved = 0
    for m in matches:
        if not m.get("is_finished"):
            continue
        status = m.get("status_short", "")
        if status not in ("FT", "AET", "PEN"):
            continue
        val = m.get("validation")
        if not val:
            continue
        result = val.get("result")
        if result not in ("VALIDATED", "FAILED"):
            continue
        fid = m.get("fixture_id")
        if not fid or not prediction_exists(fid):
            continue  # non prédit → ne jamais enregistrer
        try:
            save_result(m)
            saved += 1
        except Exception:
            pass
    return saved
