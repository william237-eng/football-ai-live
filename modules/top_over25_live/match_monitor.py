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
from modules.top_over25_live.prediction_registry import (
    register_prediction, prediction_exists, validate_prediction
)

# ── Critères LIVE ───────────────────────────────────────────────────────────────
LIVE_MIN_MINUTE     = 5      # minute minimale
LIVE_MAX_MINUTE     = 70     # minute maximale
LIVE_MIN_PROB       = 0.45   # probabilité Over 2.5 minimale
LIVE_MIN_OVER_SCORE = 45.0   # over_score minimal
LIVE_MIN_SHOTS      = 3      # tirs totaux minimaux
LIVE_MIN_CORNERS    = 1      # corners minimaux
LIVE_MAX_RED_CARDS  = 1      # cartons rouges tolérés
MAX_LIVE            = 5      # jamais plus de 5 matchs live

# ── Critères FUTURS ───────────────────────────────────────────────────────────────
# Paliers adaptatifs (3 passes), objectif 2–5 matchs
_FUT_TIERS = [
    # (prob, over_score, exp_goals, avg_goals, btts)  ← du plus strict au plus souple
    (0.60, 50.0, 2.4, 2.3, 0.45),
    (0.55, 45.0, 2.2, 2.0, 0.40),
    (0.50, 40.0, 2.0, 1.8, 0.35),
]
FUT_MIN_DISPLAY     = 2      # minimum souhaitable de matchs futurs
MAX_FUTURE          = 5      # jamais plus de 5 matchs futurs

MAX_RESOLVED        = 8      # historique terminés
MAX_ENRICH_LIVE     = 10     # candidats à enrichir live
MAX_ENRICH_FUTURE   = 15     # pool large pour les passes adaptatives

# Scores probables absurdes → toujours rejeter
_REJECT_FUTURE_SCORES = {(0, 0)}


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

def _has_red_card(live_stats: Optional[List[Dict]]) -> bool:
    """Retourne True si un carton rouge précoce est détecté dans les stats live."""
    for ts in (live_stats or []):
        for s in (ts.get("statistics") or []):
            t = (s.get("type") or "").lower()
            if "red card" in t:
                try:
                    if int(s.get("value") or 0) >= 1:
                        return True
                except (TypeError, ValueError):
                    pass
    return False


def _count_red_cards(live_stats: Optional[List[Dict]]) -> int:
    """Compte le total de cartons rouges dans les stats live (toutes équipes)."""
    total = 0
    for ts in (live_stats or []):
        for s in (ts.get("statistics") or []):
            t = (s.get("type") or "").lower()
            if "red card" in t:
                try:
                    total += int(s.get("value") or 0)
                except (TypeError, ValueError):
                    pass
    return total


def _is_today(fixture_raw: Dict) -> bool:
    """Vérifie si le match est aujourd'hui (UTC local)."""
    raw_date = (fixture_raw.get("fixture") or {}).get("date", "")
    if not raw_date:
        return False
    try:
        if raw_date.endswith("Z"):
            raw_date = raw_date[:-1] + "+00:00"
        dtobj = datetime.fromisoformat(raw_date).astimezone()
        return dtobj.date() == date.today()
    except Exception:
        return False


def fetch_top_over25(api, continent_filter: str = "Tous") -> Dict[str, List[Dict[str, Any]]]:
    """
    Retourne un dict {
      'live'    : [5 max — matchs live sélectionnés],
      'future'  : [5 max — matchs du jour pas encore commencés],
      'resolved': [15 max — matchs terminés aujourd'hui],
    }
    Stratégie 2 passes : pré-filtre rapide → enrichissement API sur les meilleurs.
    """
    today_str  = date.today().isoformat()
    seen_ids: set = set()
    live_raw:   List[Dict] = []
    future_raw: List[Dict] = []
    resolved_raw: List[Dict] = []

    # ── 1. Fixtures live ───────────────────────────────────────────────────
    try:
        raw_live, _ = api.get_live_matches()
        for fx in _parse_raw_fixtures(raw_live):
            fid = (fx.get("fixture") or {}).get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                live_raw.append(fx)
    except Exception:
        pass

    # ── 2. Fixtures du jour (all statuses) ────────────────────────────────
    try:
        raw_today, _ = api.get_fixtures_by_date(today_str)
        for fx in _parse_raw_fixtures(raw_today):
            fid = (fx.get("fixture") or {}).get("id")
            if not fid or fid in seen_ids:
                continue
            seen_ids.add(fid)
            st = (fx.get("fixture") or {}).get("status", {}).get("short", "NS")
            if st in ("CANC", "ABD", "AWD", "WO", "TBD"):
                continue
            if st in ("FT", "AET", "PEN"):
                resolved_raw.append(fx)
            elif st == "NS":
                future_raw.append(fx)
            else:
                live_raw.append(fx)
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════
    # PASSE 1 — Pré-filtrage rapide (sans appels API externes)
    # ══════════════════════════════════════════════════════════════════════

    def _quick_score(fx):
        try:
            return compute_over25_probability(fixture_raw=fx)
        except Exception:
            return None

    # — LIVE : pré-filtre QUALITÉ > QUANTITÉ (seuils assouplis, rejets absurdes uniquement)
    live_candidates: List[tuple] = []
    for fx in live_raw:
        if is_blacklisted(fx):
            continue
        q = _quick_score(fx)
        if q is None:
            continue
        if continent_filter != "Tous" and q["continent"] != continent_filter:
            continue
        minute  = q["minute"]
        total_g = q["home_score"] + q["away_score"]
        # Rejets absolus
        if minute < LIVE_MIN_MINUTE or minute > LIVE_MAX_MINUTE:
            continue
        if total_g >= 3:
            continue
        # 0-0 après 70' → inutile
        if total_g == 0 and minute > 70:
            continue
        if q["over25_prob"] < LIVE_MIN_PROB:
            continue
        if q["over_score"] < LIVE_MIN_OVER_SCORE:
            continue
        live_candidates.append((q["final_live_score"], q["over25_prob"], fx, q))

    live_candidates.sort(key=lambda x: x[0], reverse=True)
    live_to_enrich = live_candidates[:MAX_ENRICH_LIVE]

    # — FUTURS : pool complet pré-trié (les passes adaptatives filtrent ensuite)
    future_pool: List[tuple] = []
    for fx in future_raw:
        if is_blacklisted(fx):
            continue
        q = _quick_score(fx)
        if q is None:
            continue
        if continent_filter != "Tous" and q["continent"] != continent_filter:
            continue
        # Rejeter uniquement les cas absurdes : prob<35% ou score probable 0-0
        if q["over25_prob"] < 0.35:
            continue
        ps = q.get("probable_score", (1, 1))
        if tuple(ps) in _REJECT_FUTURE_SCORES:
            continue
        future_pool.append((q["over_score"], q["over25_prob"], fx, q))

    future_pool.sort(key=lambda x: x[0], reverse=True)
    # Pool large pour les passes adaptatives
    future_to_enrich = future_pool[:MAX_ENRICH_FUTURE]

    # — RESOLUS : UNIQUEMENT les matchs qui sont dans le registre de prédictions
    resolved_candidates_raw: List[tuple] = []
    for fx in resolved_raw:
        if is_blacklisted(fx):
            continue
        fid_r = (fx.get("fixture") or {}).get("id")
        if not fid_r or not prediction_exists(fid_r):
            continue  # jamais prédit → ne pas afficher
        q = _quick_score(fx)
        if q is None:
            continue
        resolved_candidates_raw.append((q["over25_prob"], fx, q))

    resolved_candidates_raw.sort(key=lambda x: x[0], reverse=True)
    resolved_to_enrich = resolved_candidates_raw[:MAX_RESOLVED]

    # ══════════════════════════════════════════════════════════════════════
    # PASSE 2 — Enrichissement API réel sur les candidats retenus
    # ══════════════════════════════════════════════════════════════════════

    def _enrich(fx, status_short, is_live_match=False):
        home_recent, away_recent, h2h_fixtures = _fetch_real_stats(api, fx)
        live_stats = None
        fid = (fx.get("fixture") or {}).get("id")
        if is_live_match and fid:
            try:
                raw_stats = api.get_fixture_statistics(fid)
                live_stats = _safe_response(raw_stats) or None
            except Exception:
                pass
        try:
            md = compute_over25_probability(
                fixture_raw=fx,
                home_recent=home_recent or None,
                away_recent=away_recent or None,
                h2h_fixtures=h2h_fixtures or None,
                live_stats=live_stats,
            )
            md["_home_recent"] = home_recent
            md["_away_recent"] = away_recent
            md["_h2h"]         = h2h_fixtures
            md["_live_stats"]   = live_stats
            return md, live_stats
        except Exception:
            return None, live_stats

    # — LIVE enrichi : vérification post-enrichissement
    _live_enriched_seen: set = set()
    live_final: List[Dict[str, Any]] = []

    for t in live_to_enrich:
        fx = t[2]
        fid_e = (fx.get("fixture") or {}).get("id")
        if fid_e in _live_enriched_seen:
            continue
        _live_enriched_seen.add(fid_e)
        st = (fx.get("fixture") or {}).get("status", {}).get("short", "NS")
        md, live_stats = _enrich(fx, st, is_live_match=True)
        if md is None:
            continue

        minute  = md["minute"]
        total_g = md["home_score"] + md["away_score"]

        # Rejets absolus post-enrichissement
        if minute < LIVE_MIN_MINUTE or minute > LIVE_MAX_MINUTE:
            continue
        if total_g >= 3:
            continue
        if total_g == 0 and minute > 70:
            continue
        if md["over25_prob"] < LIVE_MIN_PROB:
            continue
        if md["over_score"] < LIVE_MIN_OVER_SCORE:
            continue
        # Tirs et corners minimaux
        if md.get("shots_total", 0) < LIVE_MIN_SHOTS:
            continue
        if md.get("corners", 0) < LIVE_MIN_CORNERS:
            continue
        # Cartons rouges : tolérer jusqu'à LIVE_MAX_RED_CARDS
        red_count = _count_red_cards(live_stats)
        if red_count > LIVE_MAX_RED_CARDS:
            continue

        md["match_type"] = "live"
        live_final.append(md)

    live_final.sort(key=lambda x: x.get("final_live_score", x["over_score"]), reverse=True)
    live_top = live_final[:MAX_LIVE]

    # Enregistrer les prédictions live dans le registre
    for md in live_top:
        try:
            register_prediction(md)
        except Exception:
            pass

    # — FUTURS enrichis : enrichir le pool une seule fois
    _future_enriched_seen: set = set()
    _future_enriched_pool: List[Dict[str, Any]] = []

    for t in future_to_enrich:
        fx = t[2]
        fid_e = (fx.get("fixture") or {}).get("id")
        if fid_e in _future_enriched_seen:
            continue
        _future_enriched_seen.add(fid_e)
        md, _ = _enrich(fx, "NS", is_live_match=False)
        if md is None:
            continue
        # Rejet absolu : score probable 0-0
        ps = md.get("probable_score", (1, 1))
        if tuple(ps) in _REJECT_FUTURE_SCORES:
            continue
        _future_enriched_pool.append(md)

    _future_enriched_pool.sort(key=lambda x: x["over_score"], reverse=True)

    # Passes adaptatives : appliquer les seuils du plus strict au plus souple
    future_final: List[Dict[str, Any]] = []
    future_criteria_adapted = False

    for tier_idx, (p_min, s_min, eg_min, ag_min, btts_min) in enumerate(_FUT_TIERS):
        candidates: List[Dict[str, Any]] = []
        for md in _future_enriched_pool:
            if md["over25_prob"] < p_min:
                continue
            if md["over_score"] < s_min:
                continue
            if md["expected_goals"] < eg_min:
                continue
            if md["avg_goals_last5"] < ag_min:
                continue
            if md["btts_prob"] < btts_min:
                continue
            candidates.append(md)
        if len(candidates) >= FUT_MIN_DISPLAY or tier_idx == len(_FUT_TIERS) - 1:
            future_final = candidates
            if tier_idx > 0:
                future_criteria_adapted = True
            break

    for md in future_final:
        md["match_type"] = "future"
        md["criteria_adapted"] = future_criteria_adapted

    future_final.sort(key=lambda x: x["over_score"], reverse=True)
    future_top = future_final[:MAX_FUTURE]

    # Enregistrer les prédictions futures dans le registre
    for md in future_top:
        try:
            register_prediction(md)
        except Exception:
            pass

    # — RESOLUS enrichis + validation (uniquement prédictions du registre)
    resolved_final: List[Dict[str, Any]] = []
    for (_, fx, _q) in resolved_to_enrich:
        st = (fx.get("fixture") or {}).get("status", {}).get("short", "FT")
        md, _ = _enrich(fx, st, is_live_match=False)
        if md is None:
            continue
        md = validate_over25(md)
        md["match_type"] = "finished"
        # Mettre à jour le résultat dans le registre
        fid_r = md.get("fixture_id")
        val_r = md.get("validation") or {}
        if fid_r and val_r.get("result") in ("VALIDATED", "FAILED"):
            try:
                validate_prediction(
                    fid_r, val_r["result"],
                    md.get("home_score", 0), md.get("away_score", 0)
                )
            except Exception:
                pass
        resolved_final.append(md)

    resolved_final.sort(
        key=lambda x: (
            1 if (x.get("validation") or {}).get("result") == "VALIDATED" else 0,
            x["home_score"] + x["away_score"],
        ),
        reverse=True,
    )
    resolved_top = resolved_final[:MAX_RESOLVED]

    # Enregistrement automatique historique
    try:
        track_resolved_matches(resolved_top)
    except Exception:
        pass

    return {
        "live":     live_top,
        "future":   future_top,
        "resolved": resolved_top,
    }


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
    current_data: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Rafraîchit uniquement les matchs live dans le dict structuré.
    N'appelle l'API que pour les matchs non terminés.
    """
    live_matches = current_data.get("live") or []
    updated_live = []

    for m in live_matches:
        fid = m.get("fixture_id")
        if not fid or m.get("is_finished"):
            updated_live.append(m)
            continue
        try:
            raw = api.get_fixture_detail(fid)
            items = _parse_raw_fixtures(raw)
            if not items:
                updated_live.append(m)
                continue
            fresh_fx = items[0]
            live_stats = None
            try:
                raw_stats = api.get_fixture_statistics(fid)
                live_stats = _safe_response(raw_stats) or None
            except Exception:
                pass
            home_recent  = m.get("_home_recent") or []
            away_recent  = m.get("_away_recent") or []
            h2h_fixtures = m.get("_h2h") or []
            if not home_recent and not away_recent:
                home_recent, away_recent, h2h_fixtures = _fetch_real_stats(api, fresh_fx)
            try:
                refreshed = compute_over25_probability(
                    fixture_raw=fresh_fx,
                    home_recent=home_recent or None,
                    away_recent=away_recent or None,
                    h2h_fixtures=h2h_fixtures or None,
                    live_stats=live_stats,
                )
                refreshed["initial_prob"]  = m.get("initial_prob", refreshed["over25_prob"])
                refreshed["initial_pct"]   = m.get("initial_pct",  refreshed["over25_pct"])
                refreshed["_home_recent"]  = home_recent
                refreshed["_away_recent"]  = away_recent
                refreshed["_h2h"]          = h2h_fixtures
                refreshed["match_type"]    = "live"
                m = refreshed
            except Exception:
                m = update_match_state(m, fresh_fx, live_stats)
        except Exception:
            pass
        updated_live.append(m)

    return {
        "live":     updated_live,
        "future":   current_data.get("future") or [],
        "resolved": current_data.get("resolved") or [],
    }
