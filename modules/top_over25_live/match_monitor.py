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


def _safe_response(raw: Any) -> List[Dict]:
    """Extrait response[] depuis un dict API ou retourne []."""
    if isinstance(raw, dict):
        return raw.get("response") or []
    if isinstance(raw, list):
        return raw
    return []


def _fetch_real_stats(api, fx: Dict) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Récupère les vraies données pour un match :
      - home_recent : 6 derniers matchs de l'équipe domicile
      - away_recent : 6 derniers matchs de l'équipe extérieure
      - h2h         : 5 derniers H2H
    En cas d'erreur API sur un élément, retourne [] pour cet élément.
    """
    teams    = fx.get("teams") or {}
    home_id  = (teams.get("home") or {}).get("id")
    away_id  = (teams.get("away") or {}).get("id")

    home_recent: List[Dict] = []
    away_recent: List[Dict] = []
    h2h:         List[Dict] = []

    if home_id:
        try:
            raw = api.get_team_recent_fixtures(home_id, count=6)
            home_recent = _safe_response(raw)
        except Exception:
            pass

    if away_id:
        try:
            raw = api.get_team_recent_fixtures(away_id, count=6)
            away_recent = _safe_response(raw)
        except Exception:
            pass

    if home_id and away_id:
        try:
            raw = api.get_head_to_head(home_id, away_id, count=5)
            h2h = _safe_response(raw)
        except Exception:
            pass

    return home_recent, away_recent, h2h


# ─────────────────────────────────────────────────────────────────────────────
# Fetch et calcul initial du TOP Over 2.5 du jour
# ─────────────────────────────────────────────────────────────────────────────

MAX_ENRICH      = 15   # Nombre max de matchs à enrichir avec données API réelles


def fetch_top_over25(api, continent_filter: str = "Tous") -> List[Dict[str, Any]]:
    """
    Récupère les fixtures du jour + live, calcule over25_probability.
    Stratégie en 2 passes pour éviter les centaines d'appels API :
      PASSE 1 : calcul rapide (sans données externes) sur tous les matchs
               → pré-sélection des TOP MAX_ENRICH candidats
      PASSE 2 : enrichissement API réel (forme récente + H2H + stats live)
               uniquement sur les candidats retenus
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

    # ══════════════════════════════════════════════════════════════════════
    # PASSE 1 — Calcul rapide (sans appels API externes) pour pré-filtrer
    # ══════════════════════════════════════════════════════════════════════
    prefiltered_active:   List[tuple] = []   # (prob, fx, status_short)
    prefiltered_resolved: List[tuple] = []

    for fx in raw_items:
        status_short = (fx.get("fixture") or {}).get("status", {}).get("short", "NS")
        if status_short in ("CANC", "ABD", "AWD", "WO", "TBD"):
            continue
        if is_blacklisted(fx):
            continue

        try:
            quick = compute_over25_probability(
                fixture_raw=fx,
                home_recent=None,
                away_recent=None,
                h2h_fixtures=None,
                live_stats=None,
            )
        except Exception:
            continue

        if continent_filter != "Tous" and quick["continent"] != continent_filter:
            continue

        is_fin  = quick["is_finished"]
        minute  = quick["minute"]
        total_g = quick["home_score"] + quick["away_score"]
        prob    = quick["over25_prob"]

        if is_fin:
            if prob >= MIN_PROBABILITY or total_g >= 3:
                prefiltered_resolved.append((prob, fx, status_short, quick))
        elif total_g >= 3:
            prefiltered_resolved.append((1.0, fx, status_short, quick))
        elif total_g < 3 and minute <= 70 and prob >= MIN_PROBABILITY:
            prefiltered_active.append((prob, fx, status_short, quick))
        elif minute > 70 and total_g < 3 and prob >= MIN_PROBABILITY:
            prefiltered_active.append((prob, fx, status_short, quick))

    # Trier par prob desc et ne retenir que les meilleurs candidats à enrichir
    prefiltered_active.sort(key=lambda x: x[0], reverse=True)
    top_active_to_enrich   = prefiltered_active[:MAX_ENRICH]
    top_resolved_to_enrich = prefiltered_resolved[:MAX_RESOLVED]

    # ══════════════════════════════════════════════════════════════════════
    # PASSE 2 — Enrichissement API réel uniquement sur les candidats retenus
    # ══════════════════════════════════════════════════════════════════════
    active_candidates:   List[Dict[str, Any]] = []
    resolved_candidates: List[Dict[str, Any]] = []

    for (_, fx, status_short, _quick) in top_active_to_enrich + top_resolved_to_enrich:
        # Récupérer les vraies données API
        home_recent, away_recent, h2h_fixtures = _fetch_real_stats(api, fx)

        # Stats live si match en cours
        live_stats = None
        fid = (fx.get("fixture") or {}).get("id")
        if status_short in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE") and fid:
            try:
                raw_stats = api.get_fixture_statistics(fid)
                live_stats = _safe_response(raw_stats) or None
            except Exception:
                pass

        try:
            match_data = compute_over25_probability(
                fixture_raw=fx,
                home_recent=home_recent or None,
                away_recent=away_recent or None,
                h2h_fixtures=h2h_fixtures or None,
                live_stats=live_stats,
            )
            match_data["_home_recent"] = home_recent
            match_data["_away_recent"] = away_recent
            match_data["_h2h"]         = h2h_fixtures
        except Exception:
            continue

        is_fin  = match_data["is_finished"]
        minute  = match_data["minute"]
        total_g = match_data["home_score"] + match_data["away_score"]
        prob    = match_data["over25_prob"]

        # Classement final dans les bons buckets
        if is_fin:
            match_data = validate_over25(match_data)
            if prob >= MIN_PROBABILITY or total_g >= 3:
                resolved_candidates.append(match_data)
        elif total_g >= 3:
            resolved_candidates.append(match_data)
        else:
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
    Met à jour score/minute/statut/probabilité pour chaque match en cours.
    Recalcule la probabilité Over 2.5 avec les vraies données API actualisées.
    N'appelle l'API que pour les matchs non terminés.
    """
    updated = []
    for m in current_matches:
        fid = m.get("fixture_id")
        if not fid or m.get("is_finished"):
            updated.append(m)
            continue

        try:
            raw = api.get_fixture_detail(fid)
            items = _parse_raw_fixtures(raw)
            if not items:
                updated.append(m)
                continue

            fresh_fx = items[0]

            # Stats live
            live_stats = None
            try:
                raw_stats = api.get_fixture_statistics(fid)
                live_stats = _safe_response(raw_stats) or None
            except Exception:
                pass

            # Récupérer la forme récente si pas encore en cache sur le match
            home_recent = m.get("_home_recent") or []
            away_recent = m.get("_away_recent") or []
            h2h_fixtures = m.get("_h2h") or []

            if not home_recent and not away_recent:
                home_recent, away_recent, h2h_fixtures = _fetch_real_stats(api, fresh_fx)

            # Recalcul complet avec données réelles
            try:
                refreshed = compute_over25_probability(
                    fixture_raw=fresh_fx,
                    home_recent=home_recent or None,
                    away_recent=away_recent or None,
                    h2h_fixtures=h2h_fixtures or None,
                    live_stats=live_stats,
                )
                # Conserver la prob initiale et les données cachées
                refreshed["initial_prob"] = m.get("initial_prob", refreshed["over25_prob"])
                refreshed["initial_pct"]  = m.get("initial_pct",  refreshed["over25_pct"])
                refreshed["_home_recent"] = home_recent
                refreshed["_away_recent"] = away_recent
                refreshed["_h2h"]         = h2h_fixtures
                m = refreshed
            except Exception:
                m = update_match_state(m, fresh_fx, live_stats)

        except Exception:
            pass

        updated.append(m)

    return updated
