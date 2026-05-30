"""
performance_tracker.py
======================
Enregistre automatiquement les matchs terminés dans l'historique.
Appelé après chaque refresh des matchs.
"""
from __future__ import annotations

from typing import Any, Dict, List

from modules.top_over25_live.history_storage import init_db, save_result


def track_resolved_matches(matches: List[Dict[str, Any]]) -> int:
    """
    Pour chaque match terminé avec validation, l'enregistre dans l'historique.
    Retourne le nombre de nouveaux enregistrements.
    """
    init_db()
    saved = 0
    for m in matches:
        # Uniquement les matchs réellement terminés (FT/AET/PEN), pas les locked live
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
        try:
            save_result(m)
            saved += 1
        except Exception:
            pass
    return saved
