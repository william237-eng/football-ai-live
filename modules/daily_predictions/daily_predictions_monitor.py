"""
daily_predictions_monitor.py
============================
Validation automatique des prédictions "OVER 7.5 yellow cards" en attente.
Lit le registre `prediction_registry` et appelle l'API pour chaque fixture pending.
Si l'API indique un état final (FT/AET/PEN) la prédiction est mise à jour en fonction
du nombre total de cartons jaunes (seuil 8 → >=8 = VALIDATED).
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
        from modules.daily_predictions.prediction_registry import get_pending_predictions, validate_prediction
    except Exception:
        return []

    pending = get_pending_predictions()
    updated = []

    for pred in pending:
        fixture_id = pred.get("fixture_id")
        if not fixture_id:
            continue
        try:
            # Préférence : events (plus fiables pour compter cartons)
            try:
                if hasattr(api, "get_fixture_events"):
                    ev_raw = api.get_fixture_events(fixture_id)
                else:
                    ev_raw = api.get_fixture_detail(fixture_id)
            except Exception:
                ev_raw = None

            events = _safe_response(ev_raw) if ev_raw is not None else []

            # Si pas d'events, on peut tenter get_fixture_detail pour vérifier status
            # mais on ne tente pas d'inventer le nombre de cartons sans events
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

            # Si status absent mais events fournis, tenter d'extraire finalité via events 'period' 'Full Time' / etc.
            # Pour simplicité, si aucune info de status et pas d'events -> skip
            if not status and not events:
                continue

            # Compter cartes dans events
            total_cards = 0
            for ev in events:
                ev_type = (ev.get("type") or "").lower()
                if "card" in ev_type:
                    total_cards += 1

            # Si on n'a pas le status, essayer d'inférer via events (s'il y a un event de type 'final' ou minute >= 90)
            if not status:
                # tenter de trouver 'FT' dans event descriptions
                for ev in events:
                    if (ev.get("detail") or "").lower().startswith("full time"):
                        status = "FT"
                        break

            if status not in ("FT", "AET", "PEN"):
                continue

            # Seuil : >=8 cartons jaunes → VALIDATED
            res = "VALIDATED" if total_cards >= 8 else "FAILED"
            ok = validate_prediction(fixture_id, res, total_cards)
            if ok:
                updated.append({**pred, "result": res, "total_cards": total_cards})
        except Exception:
            continue

    return updated

