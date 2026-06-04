"""
daily_predictions_monitor_red.py
=================================
Validation automatique des prédictions "Au moins 1 carton rouge" en attente.
Lit le registre `prediction_registry_red` et appelle l'API pour chaque fixture pending.
Si l'API indique un état final (FT/AET/PEN) la prédiction est mise à jour en fonction
du nombre total de cartons rouges (seuil >=1 → VALIDATED).
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
    try:
        from modules.daily_predictions.prediction_registry_red import get_pending_predictions, validate_prediction
    except Exception:
        return []

    pending = get_pending_predictions()
    updated = []

    for pred in pending:
        fixture_id = pred.get("fixture_id")
        if not fixture_id:
            continue
        try:
            try:
                if hasattr(api, "get_fixture_events"):
                    ev_raw = api.get_fixture_events(fixture_id)
                else:
                    ev_raw = api.get_fixture_detail(fixture_id)
            except Exception:
                ev_raw = None

            events = _safe_response(ev_raw) if ev_raw is not None else []

            status = None
            if hasattr(api, "get_fixture_detail"):
                try:
                    raw = api.get_fixture_detail(fixture_id)
                    items = _safe_response(raw)
                    if items:
                        it = items[0]
                        st = it.get("fixture", {}).get("status") or it.get("status") or {}
                        status = st.get("short") if isinstance(st, dict) else st
                except Exception:
                    status = None

            if not status and not events:
                continue

            total_reds = 0
            for ev in events:
                ev_type = (ev.get("type") or "").lower()
                detail = (ev.get("detail") or "").lower()
                if "card" in ev_type:
                    # détail peut contenir 'Red' ou 'Yellow/Red'
                    if "red" in detail:
                        total_reds += 1
                # Certains endpoints fournissent 'card' events with 'color' field
                if ev.get("color") and str(ev.get("color")).lower() == "red":
                    total_reds += 1

            if not status:
                for ev in events:
                    if (ev.get("detail") or "").lower().startswith("full time"):
                        status = "FT"
                        break

            if status not in ("FT", "AET", "PEN"):
                continue

            # Seuil : >=1 carton rouge → VALIDATED
            res = "VALIDATED" if total_reds >= 1 else "FAILED"
            ok = validate_prediction(fixture_id, res, total_reds)
            if ok:
                updated.append({**pred, "result": res, "total_reds": total_reds})
        except Exception:
            continue

    return updated

