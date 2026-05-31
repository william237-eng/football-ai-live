"""
under25_engine.py
=================
Calcule la probabilité Under 2.5 buts pour un match donné.
Sources : forme récente (attaque/défense), H2H, stats live.
Under 2.5 = P(total buts <= 2) via Poisson.
"""
from __future__ import annotations

import math
import datetime as _dt
from typing import Any, Dict, List, Optional

from modules.top_over25_live.league_blacklist import is_blacklisted
from modules.top_over25_live.top_over25_engine import get_continent


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(v, default=0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _poisson_under(lam: float, threshold: int = 3) -> float:
    """P(goals < threshold) = P(goals <= threshold-1) via Poisson(lambda)."""
    if lam <= 0:
        return 1.0
    prob_under = sum(
        math.exp(-lam) * (lam ** k) / math.factorial(k)
        for k in range(threshold)
    )
    return max(0.0, min(1.0, prob_under))


def _team_attack_defense(fixtures: List[Dict], team_id: int, last: int = 6):
    scored = conceded = count = 0.0
    recent = fixtures[-last:] if len(fixtures) >= last else fixtures
    for fx in recent:
        try:
            teams  = fx.get("teams", {})
            goals  = fx.get("goals", {})
            hid    = (teams.get("home") or {}).get("id")
            home_g = _safe(goals.get("home"))
            away_g = _safe(goals.get("away"))
            if hid == team_id:
                scored += home_g; conceded += away_g
            else:
                scored += away_g; conceded += home_g
            count += 1
        except Exception:
            continue
    if count == 0:
        return 1.1, 1.0   # équipes défensives par défaut pour Under
    return round(scored / count, 3), round(conceded / count, 3)


def _h2h_avg_goals(h2h_fixtures: List[Dict]) -> float:
    if not h2h_fixtures:
        return 2.5
    total = count = 0.0
    for fx in h2h_fixtures[-5:]:
        try:
            goals = fx.get("goals", {})
            total += _safe(goals.get("home")) + _safe(goals.get("away"))
            count += 1
        except Exception:
            continue
    return total / count if count > 0 else 2.5


# ─────────────────────────────────────────────────────────────────────────────
# Moteur principal
# ─────────────────────────────────────────────────────────────────────────────

MIN_UNDER_PROB = 0.60   # Seuil minimum pour afficher


def compute_under25_probability(
    fixture_raw: Dict[str, Any],
    home_recent: Optional[List[Dict]] = None,
    away_recent: Optional[List[Dict]] = None,
    h2h_fixtures: Optional[List[Dict]] = None,
    live_stats: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    teams   = fixture_raw.get("teams", {})
    goals   = fixture_raw.get("goals", {})
    fixture = fixture_raw.get("fixture", {})
    league  = fixture_raw.get("league", {})
    status_info = fixture.get("status", {})

    home_id   = (teams.get("home") or {}).get("id")
    away_id   = (teams.get("away") or {}).get("id")
    home_name = (teams.get("home") or {}).get("name", "—")
    away_name = (teams.get("away") or {}).get("name", "—")
    home_logo = (teams.get("home") or {}).get("logo", "")
    away_logo = (teams.get("away") or {}).get("logo", "")

    home_score   = _safe(goals.get("home"), 0)
    away_score   = _safe(goals.get("away"), 0)
    minute       = _safe(status_info.get("elapsed"), 0)
    status_short = status_info.get("short", "NS")
    status_long  = status_info.get("long", "Not Started")
    fixture_id   = fixture.get("id")

    league_name    = league.get("name", "—")
    league_country = league.get("country", "—")
    league_flag    = league.get("flag", "")
    league_id      = league.get("id")
    season         = league.get("season")

    raw_date = fixture.get("date", "")
    start_time = start_date_display = "—"
    try:
        if raw_date:
            if raw_date.endswith("Z"):
                raw_date = raw_date[:-1] + "+00:00"
            dtobj = _dt.datetime.fromisoformat(raw_date).astimezone()
            start_time         = dtobj.strftime("%H:%M")
            start_date_display = dtobj.strftime("%d/%m/%Y")
    except Exception:
        pass

    is_live     = status_short in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE")
    is_finished = status_short in ("FT", "AET", "PEN")
    total_goals = int(home_score + away_score)

    _has_real_data = bool(home_recent) or bool(away_recent)

    home_atk, home_def = _team_attack_defense(home_recent or [], home_id or 0)
    away_atk, away_def = _team_attack_defense(away_recent or [], away_id or 0)

    LEAGUE_AVG = 1.25
    lambda_home = home_atk * (away_def / LEAGUE_AVG) if away_def > 0 else home_atk
    lambda_away = away_atk * (home_def / LEAGUE_AVG) if home_def > 0 else away_atk
    lambda_base = lambda_home + lambda_away

    h2h_avg = _h2h_avg_goals(h2h_fixtures or [])
    if h2h_avg != 2.5:
        lambda_base = lambda_base * 0.65 + h2h_avg * 0.35

    # xG live
    home_xg = away_xg = 0.0
    if live_stats:
        for ts in live_stats:
            sid = (ts.get("team") or {}).get("id")
            for s in (ts.get("statistics") or []):
                if "xG" in (s.get("type") or ""):
                    try:
                        v = float(s.get("value") or 0)
                        if sid == home_id:
                            home_xg = v
                        elif sid == away_id:
                            away_xg = v
                    except Exception:
                        pass
    if home_xg + away_xg > 0:
        lambda_base = lambda_base * 0.55 + (home_xg + away_xg) * 0.45

    # ── Cas live ──────────────────────────────────────────────────────────
    if is_live and minute > 0:
        # Si déjà 3+ buts → Under 2.5 impossible
        if total_goals >= 3:
            return _build_result(
                fixture_id, home_name, away_name, home_logo, away_logo,
                home_score, away_score, minute, status_short, status_long,
                league_name, league_country, league_flag, league_id, season,
                start_time, start_date_display, is_live, is_finished,
                prob=0.0, lambda_val=lambda_base,
                home_xg=home_xg, away_xg=away_xg,
                locked=True, locked_reason=f"Déjà {total_goals} buts → Under impossible",
                continent=get_continent(league_country),
                has_real_data=_has_real_data,
            )
        remaining = max(1, 90 - minute)
        goals_allowed = 2 - total_goals  # buts encore tolérés
        lambda_residual = lambda_base * (remaining / 90.0)
        # P(buts restants <= goals_allowed)
        prob = _poisson_under(lambda_residual, threshold=goals_allowed + 1)
    else:
        prob = _poisson_under(lambda_base, threshold=3)

    prob = min(0.95, max(0.0, prob))

    return _build_result(
        fixture_id, home_name, away_name, home_logo, away_logo,
        home_score, away_score, minute, status_short, status_long,
        league_name, league_country, league_flag, league_id, season,
        start_time, start_date_display, is_live, is_finished,
        prob=prob, lambda_val=lambda_base,
        home_xg=home_xg, away_xg=away_xg,
        locked=False, locked_reason="",
        continent=get_continent(league_country),
        has_real_data=_has_real_data,
    )


def _build_result(
    fixture_id, home_name, away_name, home_logo, away_logo,
    home_score, away_score, minute, status_short, status_long,
    league_name, league_country, league_flag, league_id, season,
    start_time, start_date_display,
    is_live, is_finished,
    prob, lambda_val, home_xg, away_xg,
    locked, locked_reason, continent,
    has_real_data: bool = False,
) -> Dict[str, Any]:

    if prob >= 0.80:
        conf_label, conf_color = "Très élevée", "#22c55e"
    elif prob >= 0.70:
        conf_label, conf_color = "Élevée", "#84cc16"
    elif prob >= 0.60:
        conf_label, conf_color = "Modérée", "#f59e0b"
    else:
        conf_label, conf_color = "Faible", "#ef4444"

    return {
        "fixture_id":         fixture_id,
        "home_name":          home_name,
        "away_name":          away_name,
        "home_logo":          home_logo,
        "away_logo":          away_logo,
        "home_score":         int(home_score),
        "away_score":         int(away_score),
        "minute":             int(minute),
        "status_short":       status_short,
        "status_long":        status_long,
        "league_name":        league_name,
        "league_country":     league_country,
        "league_flag":        league_flag,
        "league_id":          league_id,
        "season":             season,
        "start_time":         start_time,
        "start_date_display": start_date_display,
        "is_live":            is_live,
        "is_finished":        is_finished,
        "under25_prob":       round(prob, 4),
        "under25_pct":        round(prob * 100, 1),
        "initial_prob":       round(prob, 4),
        "initial_pct":        round(prob * 100, 1),
        "lambda_val":         round(lambda_val, 2),
        "home_xg":            round(home_xg, 2),
        "away_xg":            round(away_xg, 2),
        "locked":             locked,
        "locked_reason":      locked_reason,
        "conf_label":         conf_label,
        "conf_color":         conf_color,
        "continent":          continent,
        "validation":         None,
        "data_source":        "real" if has_real_data else "estimated",
    }
