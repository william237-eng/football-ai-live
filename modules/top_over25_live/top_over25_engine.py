"""
top_over25_engine.py
====================
Calcule la probabilité Over 2.5 buts pour un match donné.
Sources : forme récente, xG, H2H, ELO, classement, rythme offensif, stats live.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(v, default=0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _poisson_over(lam: float, threshold: int = 3) -> float:
    """P(goals >= threshold) via Poisson(lambda)."""
    if lam <= 0:
        return 0.0
    prob_under = sum(
        math.exp(-lam) * (lam ** k) / math.factorial(k)
        for k in range(threshold)
    )
    return max(0.0, min(1.0, 1.0 - prob_under))


def _team_attack_defense(
    fixtures: List[Dict], team_id: int, last: int = 6
) -> tuple[float, float]:
    """
    Retourne (avg_scored, avg_conceded) pour une équipe sur ses N derniers matchs.
    Distingue les buts marqués et encaissés selon le rôle (home/away).
    """
    scored    = 0.0
    conceded  = 0.0
    count     = 0
    recent = fixtures[-last:] if len(fixtures) >= last else fixtures
    for fx in recent:
        try:
            teams  = fx.get("teams", {})
            goals  = fx.get("goals", {})
            hid    = (teams.get("home") or {}).get("id")
            home_g = _safe(goals.get("home"))
            away_g = _safe(goals.get("away"))
            if hid == team_id:
                scored   += home_g
                conceded += away_g
            else:
                scored   += away_g
                conceded += home_g
            count += 1
        except Exception:
            continue
    if count == 0:
        return 1.35, 1.15   # moyennes league-average par défaut
    return round(scored / count, 3), round(conceded / count, 3)


def _elo_lambda_boost(home_elo: float, away_elo: float) -> float:
    """Petit boost lambda basé sur l'équilibre ELO (matchs serrés → plus de buts)."""
    diff = abs(home_elo - away_elo)
    # Matchs très serrés (diff < 50) → légèrement plus de buts
    if diff < 50:
        return 0.15
    elif diff < 150:
        return 0.05
    elif diff > 300:
        return -0.10
    return 0.0


def _h2h_avg_goals(h2h_fixtures: List[Dict]) -> float:
    if not h2h_fixtures:
        return 2.5
    total = 0.0
    count = 0
    for fx in h2h_fixtures[-5:]:
        try:
            goals = fx.get("goals", {})
            total += _safe(goals.get("home")) + _safe(goals.get("away"))
            count += 1
        except Exception:
            continue
    return total / count if count > 0 else 2.5


def _live_goals_rate(home_score: int, away_score: int, minute: int) -> float:
    """Extrapole le rythme live vers 90 minutes."""
    if minute <= 0:
        return 0.0
    total_now = home_score + away_score
    projected = total_now * (90.0 / minute)
    return projected


# ─────────────────────────────────────────────────────────────────────────────
# Moteur principal
# ─────────────────────────────────────────────────────────────────────────────

CONTINENT_MAP = {
    "Europe":  ["France", "Spain", "England", "Germany", "Italy", "Portugal",
                "Netherlands", "Belgium", "Turkey", "Greece", "Scotland",
                "Russia", "Ukraine", "Poland", "Switzerland", "Austria",
                "Czech Republic", "Croatia", "Serbia", "Romania", "Sweden",
                "Denmark", "Norway", "World"],
    "Afrique": ["Nigeria", "Senegal", "Ghana", "Morocco", "Egypt", "Cameroon",
                "Ivory Coast", "South Africa", "Tunisia", "Algeria",
                "Congo", "Ethiopia", "Kenya", "Tanzania", "Uganda"],
    "Asie":    ["Japan", "South Korea", "China", "Saudi Arabia", "Iran",
                "UAE", "Qatar", "India", "Indonesia", "Australia",
                "Vietnam", "Thailand", "Malaysia"],
    "Amériques": ["Brazil", "Argentina", "Colombia", "Chile", "Mexico",
                  "USA", "Uruguay", "Peru", "Ecuador", "Paraguay",
                  "Venezuela", "Costa Rica"],
}


def get_continent(country: str) -> str:
    for cont, countries in CONTINENT_MAP.items():
        if country in countries:
            return cont
    return "Autre"


def compute_over25_probability(
    fixture_raw: Dict[str, Any],
    home_recent: Optional[List[Dict]] = None,
    away_recent: Optional[List[Dict]] = None,
    h2h_fixtures: Optional[List[Dict]] = None,
    home_elo: float = 1500.0,
    away_elo: float = 1500.0,
    home_stats: Optional[Dict] = None,
    away_stats: Optional[Dict] = None,
    live_stats: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Calcule la probabilité Over 2.5 buts estimée.
    Retourne un dict enrichi prêt pour l'affichage.
    """
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

    home_score = _safe(goals.get("home"), 0)
    away_score = _safe(goals.get("away"), 0)
    minute     = _safe(status_info.get("elapsed"), 0)
    status_short = status_info.get("short", "NS")
    status_long  = status_info.get("long", "Not Started")
    fixture_id   = fixture.get("id")

    league_name    = league.get("name", "—")
    league_country = league.get("country", "—")
    league_flag    = league.get("flag", "")
    league_id      = league.get("id")
    season         = league.get("season")

    # Heure locale
    import datetime as _dt
    raw_date = fixture.get("date", "")
    start_time = "—"
    start_date_display = "—"
    try:
        if raw_date:
            if raw_date.endswith("Z"):
                raw_date = raw_date[:-1] + "+00:00"
            dtobj = _dt.datetime.fromisoformat(raw_date).astimezone()
            start_time = dtobj.strftime("%H:%M")
            start_date_display = dtobj.strftime("%d/%m/%Y")
    except Exception:
        pass

    is_live = status_short in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE")
    is_finished = status_short in ("FT", "AET", "PEN")
    total_goals = int(home_score + away_score)

    # ── Lambda différencié attaque/défense home × away ────────────────────
    # home_atk = buts marqués par home en moyenne
    # home_def = buts encaissés par home en moyenne
    # away_atk = buts marqués par away en moyenne
    # away_def = buts encaissés par away en moyenne
    home_atk, home_def = _team_attack_defense(home_recent or [], home_id or 0)
    away_atk, away_def = _team_attack_defense(away_recent or [], away_id or 0)

    # Lambda home = attaque home × défense away (buts que home va marquer)
    # Lambda away = attaque away × défense home (buts que away va marquer)
    # Normalisation : moyenne league-average = 1.25 buts par équipe
    LEAGUE_AVG = 1.25
    lambda_home = home_atk * (away_def / LEAGUE_AVG) if away_def > 0 else home_atk
    lambda_away = away_atk * (home_def / LEAGUE_AVG) if home_def > 0 else away_atk
    lambda_base = lambda_home + lambda_away

    # Intégrer H2H
    h2h_avg = _h2h_avg_goals(h2h_fixtures or [])
    if h2h_avg != 2.5:  # H2H disponible → pondération 35%
        lambda_base = lambda_base * 0.65 + h2h_avg * 0.35

    # ── Boost ELO ─────────────────────────────────────────────────────────
    elo_boost = _elo_lambda_boost(home_elo, away_elo)
    lambda_base += elo_boost

    # ── xG depuis stats live ──────────────────────────────────────────────
    home_xg = 0.0
    away_xg = 0.0
    if live_stats:
        for team_stat in live_stats:
            stat_team_id = (team_stat.get("team") or {}).get("id")
            stats_list   = team_stat.get("statistics") or []
            xg_val = 0.0
            for s in stats_list:
                if "xG" in (s.get("type") or ""):
                    try:
                        xg_val = float(s.get("value") or 0)
                    except Exception:
                        pass
            if stat_team_id == home_id:
                home_xg = xg_val
            elif stat_team_id == away_id:
                away_xg = xg_val

    if home_xg + away_xg > 0:
        lambda_xg = home_xg + away_xg
        lambda_base = lambda_base * 0.55 + lambda_xg * 0.45

    # ── Ajustement live ────────────────────────────────────────────────────
    if is_live and minute > 0:
        remaining = max(1, 90 - minute)
        goals_remaining_needed = max(0, 3 - total_goals)

        # Buts déjà marqués raccourcissent l'analyse
        if total_goals >= 3:
            # Déjà Over 2.5 → probabilité verrouillée
            return _build_result(
                fixture_id, home_name, away_name, home_logo, away_logo,
                home_score, away_score, minute, status_short, status_long,
                league_name, league_country, league_flag, league_id, season,
                start_time, start_date_display, is_live, is_finished,
                prob=1.0, lambda_val=lambda_base,
                home_xg=home_xg, away_xg=away_xg,
                locked=True, locked_reason=f"Déjà {total_goals} buts",
                continent=get_continent(league_country),
            )

        # Lambda résiduel pour les buts restants
        lambda_residual = lambda_base * (remaining / 90.0)
        prob = _poisson_over(lambda_residual, threshold=goals_remaining_needed)

        # Légère prime si rythme live élevé
        live_rate = _live_goals_rate(int(home_score), int(away_score), int(minute))
        if live_rate > 3.0:
            prob = min(1.0, prob * 1.12)
    else:
        # Match pas encore commencé
        prob = _poisson_over(lambda_base, threshold=3)

    # Plafonner à 0.95 (pas de certitude absolue)
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
    )


def _build_result(
    fixture_id, home_name, away_name, home_logo, away_logo,
    home_score, away_score, minute, status_short, status_long,
    league_name, league_country, league_flag, league_id, season,
    start_time, start_date_display,
    is_live, is_finished,
    prob, lambda_val, home_xg, away_xg,
    locked, locked_reason, continent,
) -> Dict[str, Any]:

    # Confiance
    if prob >= 0.80:
        conf_label, conf_color = "Très élevée", "#22c55e"
    elif prob >= 0.70:
        conf_label, conf_color = "Élevée", "#84cc16"
    elif prob >= 0.60:
        conf_label, conf_color = "Modérée", "#f59e0b"
    else:
        conf_label, conf_color = "Faible", "#ef4444"

    return {
        "fixture_id":        fixture_id,
        "home_name":         home_name,
        "away_name":         away_name,
        "home_logo":         home_logo,
        "away_logo":         away_logo,
        "home_score":        int(home_score),
        "away_score":        int(away_score),
        "minute":            int(minute),
        "status_short":      status_short,
        "status_long":       status_long,
        "league_name":       league_name,
        "league_country":    league_country,
        "league_flag":       league_flag,
        "league_id":         league_id,
        "season":            season,
        "start_time":        start_time,
        "start_date_display": start_date_display,
        "is_live":           is_live,
        "is_finished":       is_finished,
        "over25_prob":       round(prob, 4),
        "over25_pct":        round(prob * 100, 1),
        "initial_prob":      round(prob, 4),   # conservé pour affichage post-match
        "initial_pct":       round(prob * 100, 1),
        "lambda_val":        round(lambda_val, 2),
        "home_xg":           round(home_xg, 2),
        "away_xg":           round(away_xg, 2),
        "locked":            locked,
        "locked_reason":     locked_reason,
        "conf_label":        conf_label,
        "conf_color":        conf_color,
        "continent":         continent,
        "validation":        None,  # Sera rempli par le validator
    }
