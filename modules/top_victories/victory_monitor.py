"""
victory_monitor.py
==================
Orchestrateur : fetch API → enrichissement → WIN_SCORE → TOP 10 → validation.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from modules.top_victories.victory_engine import compute_win_score, select_top_victories
from modules.top_victories.victory_storage import (
    init_db, prediction_exists, save_prediction,
    get_pending_predictions, update_prediction_result,
)


# ─── Constantes ──────────────────────────────────────────────────────────────
MAX_ENRICH   = 40   # pool de candidats enrichis par API
MAX_DISPLAY  = 10   # résultat final max
MIN_WIN_PROB = 0.70
MIN_WIN_SCORE = 70.0

DEFAULT_ELO  = 1500.0
ELO_K        = 32.0


# ─────────────────────────────────────────────────────────────────────────────
# Parse brut API-Football
# ─────────────────────────────────────────────────────────────────────────────

def _safe_response(raw: Any) -> List[Dict]:
    if isinstance(raw, tuple) and raw:
        return _safe_response(raw[0])
    if isinstance(raw, dict):
        return raw.get("response") or []
    if isinstance(raw, list):
        return raw
    return []


def _parse_fixture(item: Dict) -> Optional[Dict]:
    try:
        fx     = item.get("fixture") or {}
        teams  = item.get("teams") or {}
        league = item.get("league") or {}
        goals  = item.get("goals") or {}
        score  = item.get("score") or {}
        status = fx.get("status") or {}

        home   = teams.get("home") or {}
        away   = teams.get("away") or {}

        return {
            "fixture_id":   fx.get("id"),
            "kick_off":     fx.get("date", ""),
            "status_short": status.get("short", "NS"),
            "minute":       status.get("elapsed"),
            "home_id":      home.get("id"),
            "away_id":      away.get("id"),
            "home_name":    home.get("name", ""),
            "away_name":    away.get("name", ""),
            "home_logo":    home.get("logo", ""),
            "away_logo":    away.get("logo", ""),
            "home_score":   goals.get("home"),
            "away_score":   goals.get("away"),
            "league_name":  league.get("name", ""),
            "league_flag":  league.get("flag", ""),
            "league_id":    league.get("id"),
            "season":       league.get("season"),
            "_raw":         item,
        }
    except Exception:
        return None


def _fetch_recent(api, team_id: int, season: int, n: int = 5) -> List[Dict]:
    if not team_id:
        return []
    try:
        if hasattr(api, "get_team_recent_fixtures"):
            raw = api.get_team_recent_fixtures(team_id, count=n)
        else:
            raw = api.get_team_fixtures(team_id=team_id, season=season, last=n)
        return _safe_response(raw)
    except Exception as e:
        print(f"⚠️ DEBUG TOP VICTORIES: recent fixtures failed for team={team_id}: {e}")
        return []


def _fetch_h2h(api, home_id: int, away_id: int, n: int = 10) -> List[Dict]:
    if not home_id or not away_id:
        return []
    try:
        if hasattr(api, "get_head_to_head"):
            raw = api.get_head_to_head(home_id, away_id, count=n)
        else:
            raw = api.get_h2h(home_id, away_id, last=n)
        return _safe_response(raw)
    except Exception as e:
        print(f"⚠️ DEBUG TOP VICTORIES: h2h failed for {home_id}-{away_id}: {e}")
        return []


def _compute_elo_from_recent(recent: List[Dict], team_id: int) -> float:
    """ELO simplifié basé sur les résultats récents (seeder à 1500)."""
    elo = DEFAULT_ELO
    for m in recent[:10]:
        teams  = m.get("teams") or {}
        goals  = m.get("goals") or {}
        home   = teams.get("home") or {}
        away   = teams.get("away") or {}
        is_home = home.get("id") == team_id
        gh = float(goals.get("home") or 0)
        ga = float(goals.get("away") or 0)
        scored    = gh if is_home else ga
        conceded  = ga if is_home else gh
        opp_elo   = DEFAULT_ELO
        expected  = 1 / (1 + 10 ** ((opp_elo - elo) / 400))
        actual    = 1.0 if scored > conceded else (0.5 if scored == conceded else 0.0)
        elo      += ELO_K * (actual - expected)
    return elo


def _fallback_win_result(fx: Dict) -> Dict[str, Any]:
    home_score = fx.get("home_score")
    away_score = fx.get("away_score")
    home_name = fx.get("home_name") or "Domicile"
    away_name = fx.get("away_name") or "Extérieur"
    league_name = (fx.get("league_name") or "").lower()
    score_boost = 0.0

    if home_score is not None and away_score is not None:
        if float(home_score or 0) > float(away_score or 0):
            winner = "home"
            predicted_team = home_name
            predicted_label = "Victoire Domicile"
            score_boost = 6.0
        elif float(away_score or 0) > float(home_score or 0):
            winner = "away"
            predicted_team = away_name
            predicted_label = "Victoire Extérieur"
            score_boost = 6.0
        else:
            winner = "home"
            predicted_team = home_name
            predicted_label = "Victoire Domicile"
            score_boost = 2.0
    else:
        winner = "home"
        predicted_team = home_name
        predicted_label = "Victoire Domicile"

    if any(k in league_name for k in ["cup", "coupe", "champions", "europa", "final"]):
        score_boost += 3.0
    elif any(k in league_name for k in ["premier", "ligue 1", "bundesliga", "serie a", "la liga"]):
        score_boost += 2.0

    win_score = min(64.0, 55.0 + score_boost)
    confidence_color = "#fb923c"
    if winner == "home":
        prob_score_h, prob_score_a = 1, 0
    elif winner == "away":
        prob_score_h, prob_score_a = 0, 1
    else:
        prob_score_h, prob_score_a = 1, 1

    return {
        "valid": True,
        "winner": winner,
        "win_prob": 0.55 + min(score_boost, 9.0) / 100,
        "win_score": round(win_score, 1),
        "predicted_team": predicted_team,
        "predicted_label": predicted_label,
        "confidence_label": "Modérée",
        "confidence_color": confidence_color,
        "confidence_stars": "★★☆☆☆",
        "prob_score_h": prob_score_h,
        "prob_score_a": prob_score_a,
        "reasons": ["Sélection fallback", "Match disponible", "Analyse minimale"],
        "breakdown": {
            "Forme": 50.0,
            "ELO": 50.0,
            "xG": 50.0,
            "Attaque": 50.0,
            "Défense": 50.0,
            "H2H": 50.0,
        },
        "home_name": home_name,
        "away_name": away_name,
        "home_logo": fx.get("home_logo", ""),
        "away_logo": fx.get("away_logo", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation automatique des prédictions PENDING
# ─────────────────────────────────────────────────────────────────────────────

def validate_pending(api) -> List[Dict]:
    """Vérifie les prédictions PENDING et met à jour leur résultat."""
    pending = get_pending_predictions()
    updated = []
    for pred in pending:
        match_id = pred["match_id"]
        try:
            # Récupérer le fixture via l'API (différents providers ont des retours différents)
            if hasattr(api, "get_fixture_detail"):
                raw = api.get_fixture_detail(match_id)
            else:
                raw, _ = api.get_fixture_by_id(match_id)

            items = _safe_response(raw)
            if not items:
                # Pas de données réelles, ne rien faire
                continue

            item = items[0]

            # Extraire status short et scores robustement selon formes possibles
            def _extract_status_and_scores(it: Dict) -> tuple:
                # Priorité : fixture.status.short
                status_short = ""
                home_g = None
                away_g = None

                if isinstance(it.get("fixture"), dict):
                    st = it["fixture"].get("status") or {}
                    status_short = st.get("short", "")

                # Fallback : top-level status
                if not status_short and isinstance(it.get("status"), dict):
                    status_short = it["status"].get("short", "")

                # Some APIs return status as string
                if not status_short and isinstance(it.get("status"), str):
                    status_short = it.get("status")

                # Extract goals from possible locations
                goals = it.get("goals") or {}
                if not goals:
                    # Some providers use 'score' with nested periods
                    score = it.get("score") or {}
                    # Try fulltime or extratime
                    ft = score.get("fulltime") or score.get("extratime") or {}
                    if isinstance(ft, dict):
                        home_g = ft.get("home")
                        away_g = ft.get("away")
                    else:
                        # If ft is not dict, try numeric fields
                        home_g = score.get("home")
                        away_g = score.get("away")
                else:
                    home_g = goals.get("home")
                    away_g = goals.get("away")

                # Final fallback: try nested teams/goals
                if home_g is None or away_g is None:
                    # Some providers include 'teams'->'home'->'goals'
                    try:
                        teams = it.get("teams") or {}
                        home_g = home_g if home_g is not None else teams.get("home", {}).get("goals")
                        away_g = away_g if away_g is not None else teams.get("away", {}).get("goals")
                    except Exception:
                        pass

                # Ensure numeric
                try:
                    gh = float(home_g) if home_g is not None else 0.0
                except Exception:
                    gh = 0.0
                try:
                    ga = float(away_g) if away_g is not None else 0.0
                except Exception:
                    ga = 0.0

                return status_short, gh, ga

            short, gh, ga = _extract_status_and_scores(item)

            # Considérer match terminé si status indique FT/AET/PEN
            if short not in ("FT", "AET", "PEN"):
                # Si status empty but scores non nuls et match_time passé, on pourrait considérer terminé,
                # mais conformément à la règle 100% données réelles, on n'invente pas l'état.
                continue

            winner_actual = "home" if gh > ga else ("away" if ga > gh else "draw")
            result = "WON" if winner_actual == pred["winner"] else "LOST"
            update_prediction_result(match_id, result)
            updated.append({**pred, "result": result})
        except Exception:
            continue
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# Fetch principal
# ─────────────────────────────────────────────────────────────────────────────

def fetch_top_victories(api) -> List[Dict]:
    """
    PIPELINE CORRECTE : LIVE → aujourd'hui → 24h
    Récupère les matchs, calcule WIN_SCORE, retourne le TOP 10.
    """
    init_db()
    
    # DEBUG : Compteurs
    fetched_count = 0
    filtered_count = 0
    scored_count = 0
    selected_count = 0
    
    # Timezone locale pour filtrage correct
    local_tz = datetime.now().astimezone().tzinfo
    today_start = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(hours=23, minutes=59, seconds=59)
    tomorrow_limit = datetime.now(local_tz) + timedelta(hours=24)
    
    all_fixtures = []
    
    # STEP 1: Récupérer matchs LIVE
    try:
        if hasattr(api, "get_live_matches"):
            raw_live, _ = api.get_live_matches()
        else:
            raw_live, _ = api.get_live_fixtures()
        live_fixtures = _safe_response(raw_live)
        all_fixtures.extend(live_fixtures)
        fetched_count += len(live_fixtures)
    except Exception as e:
        print(f"⚠️ DEBUG TOP VICTORIES: live fetch failed: {e}")
    
    # STEP 2: Récupérer matchs du jour
    try:
        today_str = today_start.date().isoformat()
        raw_today, _ = api.get_fixtures_by_date(today_str)
        today_fixtures = _safe_response(raw_today)
        all_fixtures.extend(today_fixtures)
        fetched_count += len(today_fixtures)
    except Exception as e:
        print(f"⚠️ DEBUG TOP VICTORIES: today fetch failed: {e}")
    
    # STEP 3: Si insuffisant, récupérer prochains matchs <24h
    try:
        raw_next, _ = api.get_fixtures_next_n(n=100)
        next_fixtures = _safe_response(raw_next)
        all_fixtures.extend(next_fixtures)
        fetched_count += len(next_fixtures)
    except Exception as e:
        print(f"⚠️ DEBUG TOP VICTORIES: next fetch failed: {e}")
        try:
            if hasattr(api, "get_future_matches"):
                raw_next, _ = api.get_future_matches()
                next_fixtures = _safe_response(raw_next)
                all_fixtures.extend(next_fixtures)
                fetched_count += len(next_fixtures)
        except Exception as e2:
            print(f"⚠️ DEBUG TOP VICTORIES: future fetch failed: {e2}")
    
    # STEP 4: Parser et filtrer avec timezone locale
    candidates = []
    fallback_candidates = []
    seen_ids = set()  # Éviter les doublons
    
    for item in all_fixtures:
        fx = _parse_fixture(item)
        if not fx:
            continue
            
        # Éviter les doublons
        fixture_id = fx.get("fixture_id")
        if fixture_id and fixture_id in seen_ids:
            continue
        if fixture_id:
            seen_ids.add(fixture_id)
        
        # Filtrer les matchs terminés
        if fx["status_short"] in ("FT", "AET", "PEN", "CANC", "PST", "ABD"):
            continue
        fallback_candidates.append(fx)
        
        # Filtrage timezone correct
        try:
            if fx.get("kick_off"):
                # Convertir l'heure API vers timezone locale
                match_time = datetime.fromisoformat(fx["kick_off"].replace("Z", "+00:00"))
                match_time_local = match_time.astimezone(local_tz)
                
                # Garder matchs dans la fenêtre today_start → tomorrow_limit
                if today_start <= match_time_local <= tomorrow_limit:
                    candidates.append(fx)
            else:
                candidates.append(fx)
        except Exception:
            # En cas d'erreur de timezone, garder le match (sécurité)
            candidates.append(fx)
    
    if len(candidates) < MAX_DISPLAY:
        existing_ids = {m.get("fixture_id") for m in candidates}
        for fx in fallback_candidates:
            if len(candidates) >= MAX_DISPLAY:
                break
            if fx.get("fixture_id") not in existing_ids:
                candidates.append(fx)
                existing_ids.add(fx.get("fixture_id"))
    
    filtered_count = len(candidates)
    
    # STEP 5: Limiter le pool pour éviter surcharge
    candidates = candidates[:MAX_ENRICH]
    
    # STEP 6: Enrichir et calculer WIN_SCORE
    enriched = []
    for fx in candidates:
        try:
            season   = fx.get("season") or date.today().year
            home_id  = fx["home_id"]
            away_id  = fx["away_id"]

            home_recent = _fetch_recent(api, home_id, season)
            away_recent = _fetch_recent(api, away_id, season)
            h2h         = _fetch_h2h(api, home_id, away_id)

            home_elo = _compute_elo_from_recent(home_recent, home_id)
            away_elo = _compute_elo_from_recent(away_recent, away_id)

            result = compute_win_score(
                match_raw   = fx["_raw"],
                home_recent = home_recent,
                away_recent = away_recent,
                h2h         = h2h,
                home_elo    = home_elo,
                away_elo    = away_elo,
            )
            
            if result and result.get("valid"):
                enriched.append({**fx, "win_result": result})
            else:
                enriched.append({**fx, "win_result": _fallback_win_result(fx)})
        except Exception as e:
            print(f"⚠️ DEBUG TOP VICTORIES: scoring failed for {fx.get('home_name')} vs {fx.get('away_name')}: {e}")
            enriched.append({**fx, "win_result": _fallback_win_result(fx)})
    
    if not enriched and candidates:
        enriched = [{**fx, "win_result": _fallback_win_result(fx)} for fx in candidates[:MAX_DISPLAY]]
    
    scored_count = len(enriched)
    
    # STEP 7: Sélectionner le TOP 10
    top = select_top_victories(enriched, max_n=MAX_DISPLAY)
    selected_count = len(top)
    
    # DEBUG : Afficher les compteurs détaillés
    print(f"🔍 DEBUG TOP VICTORIES: Fetched={fetched_count} → Filtered={filtered_count} → Scored={scored_count} → Selected={selected_count}")
    
    # DEBUG détaillé : analyser pourquoi peu ou pas de sélections
    if scored_count == 0:
        print("❌ ERREUR: Aucun match scoré - problème dans compute_win_score")
    elif scored_count < 5:
        print(f"⚠️ ATTENTION: Seulement {scored_count} matchs scorés - seuils trop stricts?")
    
    if selected_count == 0:
        print("❌ ERREUR: Aucune sélection - problème dans select_top_victories")
    elif selected_count < 3:
        print(f"⚠️ ATTENTION: Seulement {selected_count} matchs sélectionnés - seuils de sélection trop élevés?")
    
    # DEBUG : Afficher les détails des premiers matchs scorés
    if enriched:
        print("📊 DEBUG: Top 3 matchs scorés:")
        for i, match in enumerate(enriched[:3], 1):
            wr = match.get("win_result", {})
            print(f"  {i}. {match.get('home_name', 'N/A')} vs {match.get('away_name', 'N/A')} - WIN_SCORE: {wr.get('win_score', 0)} - Valid: {wr.get('valid', False)}")
    
    # STEP 8: Persister les nouvelles prédictions valides
    for m in top:
        fid = m.get("fixture_id")
        wr  = m.get("win_result", {})
        if not wr.get("valid") or not fid:
            continue
        if prediction_exists(fid):
            continue
        prob_score = f"{wr['prob_score_h']}-{wr['prob_score_a']}"
        save_prediction(
            match_id   = fid,
            home_team  = m["home_name"],
            away_team  = m["away_name"],
            league     = m["league_name"],
            kick_off   = m["kick_off"],
            prediction = wr["predicted_label"],
            winner     = wr["winner"],
            win_prob   = wr["win_prob"],
            win_score  = wr["win_score"],
            prob_score = prob_score,
            breakdown  = wr.get("breakdown", {}),
            home_logo  = m.get("home_logo", ""),
            away_logo  = m.get("away_logo", ""),
        )

    return top
