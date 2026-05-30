"""
match_monitor.py
================
Orchestrateur : fetch API → calcul Over 2.5 → sélection TOP 10 → tracking live.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from modules.top_over25_live.top_over25_engine import compute_over25_probability
from modules.top_over25_live.over25_tracker import update_match_state
from modules.top_over25_live.over25_validator import validate_over25
from modules.top_over25_live.league_blacklist import is_blacklisted
from modules.top_over25_live.performance_tracker import track_resolved_matches

MIN_PROBABILITY  = 0.65
MAX_ACTIVE       = 10   # TOP 10 prédictions actives
MAX_RESOLVED     = 20   # garder jusqu'à 20 résultats terminés


# ─────────────────────────────────────────────────────────────────────────────
# Parse brut d'un fixture API-Football
# ─────────────────────────────────────────────────────────────────────────────

def _parse_raw_fixtures(payload: Any) -> List[Dict]:
    if isinstance(payload, dict) and "response" in payload:
        return payload.get("response") or []
    if isinstance(payload, list):
        return payload
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Fetch et calcul initial du TOP Over 2.5 du jour
# ─────────────────────────────────────────────────────────────────────────────

def fetch_top_over25(api, continent_filter: str = "Tous") -> List[Dict[str, Any]]:
    """
    Récupère les fixtures du jour + live, calcule over25_probability.
    - Actifs (minute <= 70, total buts < 3, non terminé) : filtre >= MIN_PROBABILITY, TOP MAX_ACTIVE
    - Terminés : tous ceux qui avaient passé le seuil initial, validés/échoués
    Retourne la liste complète (catégorisation faite par categorize_matches).
    """
    today_str = date.today().isoformat()
    raw_items: List[Dict] = []
    seen_ids: set = set()

    # 1. Fixtures du jour
    try:
        raw_today, _ = api.get_fixtures_by_date(today_str)
        for fx in _parse_raw_fixtures(raw_today):
            fid = (fx.get("fixture") or {}).get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                raw_items.append(fx)
    except Exception:
        pass

    # 2. Fixtures live
    try:
        raw_live, _ = api.get_live_matches()
        for fx in _parse_raw_fixtures(raw_live):
            fid = (fx.get("fixture") or {}).get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                raw_items.append(fx)
    except Exception:
        pass

    if not raw_items:
        return []

    active_candidates: List[Dict[str, Any]]   = []
    resolved_candidates: List[Dict[str, Any]] = []

    for fx in raw_items:
        status_short = (fx.get("fixture") or {}).get("status", {}).get("short", "NS")
        if status_short in ("CANC", "ABD", "AWD", "WO", "TBD"):
            continue

        # Exclure U20/U21/Women/Réserves/Ligues mineures
        if is_blacklisted(fx):
            continue

        try:
            match_data = compute_over25_probability(
                fixture_raw=fx,
                home_recent=None,
                away_recent=None,
                h2h_fixtures=None,
            )
        except Exception:
            continue

        # Filtre continent
        if continent_filter != "Tous" and match_data["continent"] != continent_filter:
            continue

        is_fin   = match_data["is_finished"]
        minute   = match_data["minute"]
        total_g  = match_data["home_score"] + match_data["away_score"]
        prob     = match_data["over25_prob"]

        # Cas terminé → valider et mettre dans resolved si prob initiale >= seuil
        if is_fin:
            match_data = validate_over25(match_data)
            # On inclut les terminés seulement si prob était significative
            if prob >= MIN_PROBABILITY or total_g >= 3:
                resolved_candidates.append(match_data)
            continue

        # Cas actif : total < 3, minute <= 70
        if total_g < 3 and minute <= 70:
            if prob >= MIN_PROBABILITY:
                active_candidates.append(match_data)
        elif total_g >= 3:
            # Déjà Over 2.5 en cours → verrouillé, passe en resolved
            resolved_candidates.append(match_data)
        elif minute > 70 and total_g < 3:
            # Minute > 70 et pas encore Over → probabilité résiduelle faible
            # Garder uniquement si prob résiduelle encore >= 65%
            if prob >= MIN_PROBABILITY:
                active_candidates.append(match_data)

    # Trier actifs par probabilité décroissante → vraies opportunités en premier
    active_candidates.sort(key=lambda x: x["over25_prob"], reverse=True)
    active_top = active_candidates[:MAX_ACTIVE]

    # Trier resolved : validés d'abord, puis par total buts desc
    resolved_candidates.sort(
        key=lambda x: (
            1 if (x.get("validation") or {}).get("result") == "VALIDATED" else 0,
            x["home_score"] + x["away_score"],
        ),
        reverse=True,
    )
    resolved_top = resolved_candidates[:MAX_RESOLVED]

    # Enregistrer automatiquement les terminés dans l'historique
    try:
        track_resolved_matches(resolved_top)
    except Exception:
        pass

    return active_top + resolved_top


# ─────────────────────────────────────────────────────────────────────────────
# Catégorisation
# ─────────────────────────────────────────────────────────────────────────────

def categorize_matches(matches: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Sépare la liste en 3 catégories :
      - active   : prédictions actives (minute <= 70, total buts < 3, non terminé)
      - validated: matchs terminés avec total buts >= 3 (✅)
      - failed   : matchs terminés avec total buts < 3 OU minute > 85 + faible proba (❌)
    """
    active    = []
    validated = []
    failed    = []

    for m in matches:
        is_fin  = m.get("is_finished", False)
        minute  = m.get("minute", 0)
        total_g = m.get("home_score", 0) + m.get("away_score", 0)
        locked  = m.get("locked", False)
        val     = m.get("validation") or {}

        if is_fin:
            if val.get("result") == "VALIDATED":
                validated.append(m)
            else:
                failed.append(m)
        elif locked and total_g >= 3:
            # Live mais déjà Over 2.5 → classé validé (en cours)
            validated.append(m)
        elif minute > 85 and total_g < 3 and m.get("over25_prob", 1.0) < 0.30:
            # 85+ min, score serré, proba résiduelle très faible → probable échec
            failed.append(m)
        else:
            active.append(m)

    return {"active": active, "validated": validated, "failed": failed}


# ─────────────────────────────────────────────────────────────────────────────
# Refresh live des matchs déjà sélectionnés
# ─────────────────────────────────────────────────────────────────────────────

def refresh_live_matches(
    api,
    current_matches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Met à jour score/minute/statut pour chaque match en cours.
    N'appelle l'API que pour les matchs non terminés.
    """
    updated = []
    for m in current_matches:
        fid = m.get("fixture_id")
        if not fid or m.get("is_finished"):
            # Déjà terminé : pas besoin de refresh
            updated.append(m)
            continue

        try:
            raw = api.get_fixture_detail(fid)
            items = _parse_raw_fixtures(raw)
            if not items:
                updated.append(m)
                continue

            fresh_fx = items[0]

            # Stats live optionnelles
            live_stats = None
            try:
                raw_stats = api.get_fixture_statistics(fid)
                live_stats = (raw_stats or {}).get("response") or None
            except Exception:
                pass

            m = update_match_state(m, fresh_fx, live_stats)
        except Exception:
            pass

        updated.append(m)

    return updated
