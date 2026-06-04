"""
over25_monitor.py
==================
Validation automatique des prédictions OVER 2.5 en attente.
Lit le registre `prediction_registry` et appelle l'API pour chaque fixture pending.
Si l'API indique un état final (FT/AET/PEN) la prédiction est mise à jour.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _safe_response(raw: Any) -> List[Dict]:
    if isinstance(raw, tuple) and raw:
        return _safe_response(raw[0])
    if isinstance(raw, dict):
        return raw.get("response") or []
    if isinstance(raw, list):
        return raw
    return []


def validate_pending(api) -> List[Dict]:
    """Vérifie les prédictions PENDING et met à jour leur statut dans le registre.

    Retourne la liste des prédictions mises à jour.
    """
    try:
        from modules.top_over25_live.prediction_registry import get_pending_predictions, validate_prediction
    except Exception:
        return []

    pending = get_pending_predictions()
    updated = []

    for pred in pending:
        fixture_id = pred.get("fixture_id") or pred.get("fixture_id")
        if not fixture_id:
            continue
        try:
            if hasattr(api, "get_fixture_detail"):
                raw = api.get_fixture_detail(fixture_id)
            else:
                raw, _ = api.get_fixture_by_id(fixture_id)
            items = _safe_response(raw)
            if not items:
                continue
            itm = items[0]

            # Extract status and scores robustly (like victory_monitor)
            def _extract_status_and_scores(it: Dict) -> tuple:
                status_short = ""
                home_g = None
                away_g = None
                if isinstance(it.get("fixture"), dict):
                    st = it["fixture"].get("status") or {}
                    status_short = st.get("short", "")
                if not status_short and isinstance(it.get("status"), dict):
                    status_short = it["status"].get("short", "")
                if not status_short and isinstance(it.get("status"), str):
                    status_short = it.get("status")

                goals = it.get("goals") or {}
                if not goals:
                    score = it.get("score") or {}
                    ft = score.get("fulltime") or score.get("extratime") or {}
                    if isinstance(ft, dict):
                        home_g = ft.get("home")
                        away_g = ft.get("away")
                    else:
                        home_g = score.get("home")
                        away_g = score.get("away")
                else:
                    home_g = goals.get("home")
                    away_g = goals.get("away")

                if home_g is None or away_g is None:
                    try:
                        teams = it.get("teams") or {}
                        home_g = home_g if home_g is not None else teams.get("home", {}).get("goals")
                        away_g = away_g if away_g is not None else teams.get("away", {}).get("goals")
                    except Exception:
                        pass
                try:
                    gh = int(home_g) if home_g is not None else 0
                except Exception:
                    try:
                        gh = int(float(home_g))
                    except Exception:
                        gh = 0
                try:
                    ga = int(away_g) if away_g is not None else 0
                except Exception:
                    try:
                        ga = int(float(away_g))
                    except Exception:
                        ga = 0
                return status_short, gh, ga

            status, gh, ga = _extract_status_and_scores(itm)
            if status not in ("FT", "AET", "PEN"):
                continue
            total = gh + ga
            if total >= 3:
                res = "VALIDATED"
            else:
                res = "FAILED"
            try:
                ok = validate_prediction(fixture_id, res, gh, ga)
                if ok:
                    updated.append({**pred, "result": res, "home_score": gh, "away_score": ga})
            except Exception:
                continue
        except Exception:
            continue
    return updated

