"""
over25_tracker.py
=================
Suit en temps réel l'évolution des matchs sélectionnés :
met à jour score, minute, statut et déclenche la validation si terminé.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from modules.top_over25_live.over25_validator import validate_over25


def update_match_state(
    match_data: Dict[str, Any],
    fresh_fixture: Dict[str, Any],
    fresh_live_stats: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Met à jour les champs live d'un match_data depuis la réponse API fraîche.
    """
    fixture_info = fresh_fixture.get("fixture", {})
    goals        = fresh_fixture.get("goals", {})
    status_info  = fixture_info.get("status", {})

    home_score   = goals.get("home") or 0
    away_score   = goals.get("away") or 0
    minute       = status_info.get("elapsed") or 0
    status_short = status_info.get("short", match_data.get("status_short", "NS"))
    status_long  = status_info.get("long",  match_data.get("status_long",  "Not Started"))

    match_data["home_score"]   = int(home_score)
    match_data["away_score"]   = int(away_score)
    match_data["minute"]       = int(minute)
    match_data["status_short"] = status_short
    match_data["status_long"]  = status_long

    is_live = status_short in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE")
    is_finished = status_short in ("FT", "AET", "PEN")
    match_data["is_live"]     = is_live
    match_data["is_finished"] = is_finished

    # xG live si dispo
    if fresh_live_stats:
        home_id = None
        away_id = None
        teams = fresh_fixture.get("teams", {})
        home_id = (teams.get("home") or {}).get("id")
        away_id = (teams.get("away") or {}).get("id")
        for team_stat in fresh_live_stats:
            tid   = (team_stat.get("team") or {}).get("id")
            stats = team_stat.get("statistics") or []
            for s in stats:
                if "xG" in (s.get("type") or ""):
                    try:
                        xg = float(s.get("value") or 0)
                        if tid == home_id:
                            match_data["home_xg"] = round(xg, 2)
                        elif tid == away_id:
                            match_data["away_xg"] = round(xg, 2)
                    except Exception:
                        pass

    # Verrouiller si Over 2.5 déjà atteint
    total = match_data["home_score"] + match_data["away_score"]
    if total >= 3 and not is_finished:
        match_data["locked"] = True
        match_data["locked_reason"] = f"Déjà {total} buts"
        match_data["over25_prob"] = 1.0
        match_data["over25_pct"]  = 100.0

    # Valider si terminé
    if is_finished:
        match_data = validate_over25(match_data)

    return match_data
