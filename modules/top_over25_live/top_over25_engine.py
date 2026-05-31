"""
top_over25_engine.py
====================
Calcule la probabilité Over 2.5 buts + OVER_SCORE composite pour un match.
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


def _btts_probability(
    home_recent: List[Dict], away_recent: List[Dict],
    home_id: int, away_id: int, last: int = 6
) -> float:
    """Estime la probabilité BTTS basée sur la forme récente."""
    def btts_rate(fixtures, tid):
        count = scored = 0
        recent = fixtures[-last:] if len(fixtures) >= last else fixtures
        for fx in recent:
            try:
                teams = fx.get("teams", {})
                goals = fx.get("goals", {})
                hid   = (teams.get("home") or {}).get("id")
                hg    = _safe(goals.get("home"))
                ag    = _safe(goals.get("away"))
                is_home = hid == tid
                my_goals  = hg if is_home else ag
                opp_goals = ag if is_home else hg
                if my_goals > 0 and opp_goals > 0:
                    scored += 1
                count += 1
            except Exception:
                continue
        return scored / count if count > 0 else 0.5
    r_home = btts_rate(home_recent, home_id)
    r_away = btts_rate(away_recent, away_id)
    return round((r_home + r_away) / 2, 3)


def _h2h_over25_rate(h2h_fixtures: List[Dict]) -> float:
    """Taux de matchs Over 2.5 dans les H2H récents."""
    if not h2h_fixtures:
        return 0.5
    count = over = 0
    for fx in h2h_fixtures[-6:]:
        try:
            goals = fx.get("goals", {})
            total = _safe(goals.get("home")) + _safe(goals.get("away"))
            if total >= 3:
                over += 1
            count += 1
        except Exception:
            continue
    return over / count if count > 0 else 0.5


def _extract_live_shots(
    live_stats: List[Dict], home_id: int, away_id: int
) -> Tuple[float, float, float, float]:
    """Extrait (shots_home, shots_on_home, shots_away, shots_on_away) des stats live."""
    sh = son_h = sa = son_a = 0.0
    for ts in (live_stats or []):
        tid  = (ts.get("team") or {}).get("id")
        stats = ts.get("statistics") or []
        for s in stats:
            t = (s.get("type") or "").lower()
            v = _safe(s.get("value"))
            if tid == home_id:
                if "total shots" in t or "shots total" in t:
                    sh = v
                elif "shots on" in t or "shots on goal" in t:
                    son_h = v
            elif tid == away_id:
                if "total shots" in t or "shots total" in t:
                    sa = v
                elif "shots on" in t or "shots on goal" in t:
                    son_a = v
    return sh, son_h, sa, son_a


def _extract_live_corners(
    live_stats: List[Dict], home_id: int, away_id: int
) -> float:
    """Extrait le total de corners."""
    total = 0.0
    for ts in (live_stats or []):
        tid   = (ts.get("team") or {}).get("id")
        stats = ts.get("statistics") or []
        for s in stats:
            if "corner" in (s.get("type") or "").lower():
                total += _safe(s.get("value"))
    return total


def _probable_score(
    lambda_home: float, lambda_away: float
) -> Tuple[int, int]:
    """Score le plus probable selon Poisson."""
    best_p  = -1.0
    best_h  = 1
    best_a  = 1
    for h in range(8):
        for a in range(8):
            p = (math.exp(-lambda_home) * lambda_home**h / math.factorial(h) *
                 math.exp(-lambda_away) * lambda_away**a / math.factorial(a))
            if p > best_p:
                best_p = p
                best_h, best_a = h, a
    return best_h, best_a


def _compute_over_score(
    lambda_home: float, lambda_away: float,
    h2h_over_rate: float, btts_rate: float,
    home_atk: float, away_atk: float,
    home_def: float, away_def: float,
    shots_total: float, shots_on: float, corners: float,
    home_xg: float, away_xg: float,
    is_live: bool, minute: float,
    prob: float,
    goals_per_match_home: float = 0.0,
    goals_per_match_away: float = 0.0,
) -> Tuple[float, List[str], Dict[str, float]]:
    """
    OVER_SCORE = attack_strength*30 + defense_weakness*25
                + form_score*20 + h2h_over25*15 + btts_score*10
    Normalisé dans [0, 100].
    """
    reasons: List[str] = []
    breakdown: Dict[str, float] = {}

    # 1. Attack strength (max 30)
    # Intensité offensive : lambda combiné normalisé sur 4.0 buts attendus
    avg_home  = goals_per_match_home if goals_per_match_home > 0 else home_atk
    avg_away  = goals_per_match_away if goals_per_match_away > 0 else away_atk
    avg_total = avg_home + avg_away
    atk_raw   = min(1.0, (lambda_home + lambda_away) / 4.0)
    atk_pts   = round(atk_raw * 30, 1)
    breakdown["Attack"] = atk_pts
    if avg_total >= 3.5:
        reasons.append(f"✓ {avg_home:.1f} + {avg_away:.1f} = {avg_total:.1f} buts/match (forme récente)")
    elif avg_total >= 2.8:
        reasons.append(f"✓ {avg_total:.1f} buts/match en moyenne (forme)")
    else:
        reasons.append(f"■ {avg_total:.1f} buts/match moyenne (forme limitée)")

    # 2. Defense weakness (max 25)
    def_gap   = (home_def + away_def) / 2
    def_raw   = min(1.0, def_gap / 2.5)
    def_pts   = round(def_raw * 25, 1)
    breakdown["Defense"] = def_pts
    if home_def >= 1.5 and away_def >= 1.5:
        reasons.append(f"✓ Défenses faibles : {home_def:.1f} + {away_def:.1f} encaissés/match")
    elif def_gap >= 1.3:
        reasons.append(f"✓ Défenses vulnérables ({def_gap:.1f} moy.)")
    else:
        reasons.append(f"■ Défenses correctes ({def_gap:.1f} moy.)")

    # 3. Form score (max 20) — basé sur la prob Poisson (reflet de la forme combinée)
    form_pts  = round(min(1.0, prob / 0.95) * 20, 1)
    breakdown["Form"] = form_pts
    if prob >= 0.75:
        reasons.append(f"✓ Probabilité Poisson élevée ({round(prob*100,1)}%)")
    elif prob >= 0.60:
        reasons.append(f"✓ Probabilité Poisson modérée ({round(prob*100,1)}%)")
    else:
        reasons.append(f"■ Probabilité Poisson faible ({round(prob*100,1)}%)")

    # 4. H2H Over 2.5 (max 15)
    h2h_pts   = round(h2h_over_rate * 15, 1)
    breakdown["H2H"] = h2h_pts
    h2h_pct = round(h2h_over_rate * 100)
    if h2h_over_rate >= 0.60:
        reasons.append(f"✓ H2H Over 2.5 : {h2h_pct}% des confrontations")
    elif h2h_over_rate >= 0.40:
        reasons.append(f"■ H2H Over 2.5 : {h2h_pct}% (neutre)")
    else:
        reasons.append(f"■ H2H Over 2.5 : {h2h_pct}% (défavorable)")

    # 5. BTTS score (max 10)
    btts_pts  = round(btts_rate * 10, 1)
    breakdown["BTTS"] = btts_pts
    btts_pct = round(btts_rate * 100)
    if btts_rate >= 0.60:
        reasons.append(f"✓ BTTS : {btts_pct}% (les deux équipes marquent)")
    elif btts_rate >= 0.55:
        reasons.append(f"✓ BTTS : {btts_pct}%")
    else:
        reasons.append(f"■ BTTS : {btts_pct}%")

    # Sous-total base
    base_score = atk_pts + def_pts + form_pts + h2h_pts + btts_pts

    # Bonus live : tirs + corners + xG (peuvent ajouter jusqu'à 15 pts)
    live_bonus = 0.0
    if is_live:
        shots_score   = min(1.0, shots_total / 14.0) * 7
        shots_on_sc   = min(1.0, shots_on   / 6.0)  * 4
        corners_score = min(1.0, corners    / 8.0)  * 4
        live_bonus    = round(shots_score + shots_on_sc + corners_score, 1)
        breakdown["Live pressure"] = live_bonus
        if shots_total >= 8:
            reasons.append(f"✓ {int(shots_total)} tirs ({int(shots_on)} cadrés) à la {int(minute)}'")
        elif shots_total >= 5:
            reasons.append(f"✓ {int(shots_total)} tirs à la {int(minute)}'")
        if corners >= 4:
            reasons.append(f"✓ {int(corners)} corners (pression soutenue)")
    else:
        breakdown["Live pressure"] = 0.0

    xg_bonus = 0.0
    xg_total = home_xg + away_xg
    if xg_total > 0:
        xg_bonus = round(min(1.0, xg_total / 3.0) * 10, 1)
        breakdown["xG"] = xg_bonus
        reasons.append(f"✓ xG cumulé : {home_xg:.2f} + {away_xg:.2f} = {xg_total:.2f}")
    else:
        breakdown["xG"] = 0.0

    total = round(min(100.0, max(0.0, base_score + live_bonus + xg_bonus)), 1)
    breakdown["Total"] = total
    return total, reasons, breakdown


def _urgency_score(
    home_atk: float, away_atk: float,
    shots_total: float, corners: float,
    btts_rate: float, prob: float,
    is_live: bool, minute: float,
) -> float:
    """
    urgency_score (0-100) pour les matchs live :
    attack_pressure*0.30 + shots_factor*0.20 + corners_factor*0.15
    + form_factor*0.15 + elo_factor*0.10 + btts_factor*0.10
    """
    if not is_live:
        return 0.0
    attack_pressure = min(1.0, (home_atk + away_atk) / 4.0)
    shots_factor    = min(1.0, shots_total / 14.0)
    corners_factor  = min(1.0, corners / 8.0)
    form_factor     = min(1.0, prob / 0.95)
    # elo_factor : on approx. via intensité temporelle (urgence croissante avec la minute)
    remaining = max(1, 90 - minute)
    elo_factor      = min(1.0, (90 - remaining) / 65.0)  # max atteint à 65'
    btts_factor     = min(1.0, btts_rate)
    raw = (
        attack_pressure * 0.30
        + shots_factor  * 0.20
        + corners_factor* 0.15
        + form_factor   * 0.15
        + elo_factor    * 0.10
        + btts_factor   * 0.10
    )
    return round(raw * 100, 1)


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
    _has_real_data = bool(home_recent) or bool(away_recent)

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
                has_real_data=_has_real_data,
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

    # ── Tirs / corners depuis stats live ───────────────────────────────────
    shots_home, shots_on_home, shots_away, shots_on_away = _extract_live_shots(
        live_stats or [], home_id or 0, away_id or 0
    )
    shots_total = shots_home + shots_away
    shots_on    = shots_on_home + shots_on_away
    corners     = _extract_live_corners(live_stats or [], home_id or 0, away_id or 0)

    # ── H2H Over 2.5 rate + BTTS ────────────────────────────────────────────
    h2h_over_rate = _h2h_over25_rate(h2h_fixtures or [])
    btts_rate_val = _btts_probability(
        home_recent or [], away_recent or [], home_id or 0, away_id or 0
    )

    # ── Score probable ──────────────────────────────────────────────────────
    prob_score_h, prob_score_a = _probable_score(lambda_home, lambda_away)

    # ── OVER_SCORE composite ────────────────────────────────────────────────
    over_score, ai_reasons, score_breakdown = _compute_over_score(
        lambda_home=lambda_home, lambda_away=lambda_away,
        h2h_over_rate=h2h_over_rate, btts_rate=btts_rate_val,
        home_atk=home_atk, away_atk=away_atk,
        home_def=home_def, away_def=away_def,
        shots_total=shots_total, shots_on=shots_on, corners=corners,
        home_xg=home_xg, away_xg=away_xg,
        is_live=is_live, minute=minute, prob=prob,
        goals_per_match_home=home_atk,
        goals_per_match_away=away_atk,
    )

    # Score probable cohérent avec Over 2.5 : si prédiction Over 2.5, total >= 3
    if prob >= 0.55 and (prob_score_h + prob_score_a) < 3:
        # Chercher le score Over 2.5 le plus probable
        best_p = -1.0
        best_h2, best_a2 = prob_score_h, prob_score_a
        for h in range(8):
            for a in range(8):
                if h + a < 3:
                    continue
                p = (math.exp(-lambda_home) * lambda_home**h / math.factorial(h) *
                     math.exp(-lambda_away) * lambda_away**a / math.factorial(a))
                if p > best_p:
                    best_p = p
                    best_h2, best_a2 = h, a
        prob_score_h, prob_score_a = best_h2, best_a2

    return _build_result(
        fixture_id, home_name, away_name, home_logo, away_logo,
        home_score, away_score, minute, status_short, status_long,
        league_name, league_country, league_flag, league_id, season,
        start_time, start_date_display, is_live, is_finished,
        prob=prob, lambda_val=lambda_base,
        lambda_home=lambda_home, lambda_away=lambda_away,
        home_xg=home_xg, away_xg=away_xg,
        locked=False, locked_reason="",
        continent=get_continent(league_country),
        has_real_data=_has_real_data,
        over_score=over_score,
        ai_reasons=ai_reasons,
        score_breakdown=score_breakdown,
        btts_prob=btts_rate_val,
        h2h_over_rate=h2h_over_rate,
        probable_score=(prob_score_h, prob_score_a),
        shots_total=shots_total, shots_on=shots_on, corners=corners,
        home_atk=home_atk, away_atk=away_atk,
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
    lambda_home: float = 0.0,
    lambda_away: float = 0.0,
    over_score: float = 0.0,
    ai_reasons: Optional[List[str]] = None,
    score_breakdown: Optional[Dict[str, float]] = None,
    btts_prob: float = 0.5,
    h2h_over_rate: float = 0.5,
    probable_score: Tuple[int, int] = (1, 1),
    shots_total: float = 0.0,
    shots_on: float = 0.0,
    corners: float = 0.0,
    home_atk: float = 1.35,
    away_atk: float = 1.15,
) -> Dict[str, Any]:

    # Confiance basée sur over_score (Partie 4)
    if over_score >= 85:
        conf_label, conf_color = "Exceptionnelle", "#a78bfa"
    elif over_score >= 75:
        conf_label, conf_color = "Très élevée", "#22c55e"
    elif over_score >= 65:
        conf_label, conf_color = "Élevée", "#84cc16"
    elif over_score >= 55:
        conf_label, conf_color = "Modérée", "#f59e0b"
    else:
        conf_label, conf_color = "Faible", "#ef4444"

    # BTTS label
    btts_label = "Oui" if btts_prob >= 0.55 else "Non" if btts_prob < 0.40 else "Incertain"

    # Urgency score (live uniquement)
    urg = _urgency_score(
        home_atk=home_atk, away_atk=away_atk,
        shots_total=shots_total, corners=corners,
        btts_rate=btts_prob, prob=prob,
        is_live=is_live, minute=float(minute),
    )
    final_live_score = round(over_score * 0.70 + urg * 0.30, 1) if is_live else over_score

    # Statistiques d’intensité pour l’UI
    remaining_min = max(0, 90 - int(minute)) if is_live else 0
    expected_goals = round(lambda_home + lambda_away, 2)
    avg_goals_last5 = round(home_atk + away_atk, 2)

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
        "over25_prob":        round(prob, 4),
        "over25_pct":         round(prob * 100, 1),
        "initial_prob":       round(prob, 4),
        "initial_pct":        round(prob * 100, 1),
        "lambda_val":         round(lambda_val, 2),
        "lambda_home":        round(lambda_home, 2),
        "lambda_away":        round(lambda_away, 2),
        "home_xg":            round(home_xg, 2),
        "away_xg":            round(away_xg, 2),
        "locked":             locked,
        "locked_reason":      locked_reason,
        "conf_label":         conf_label,
        "conf_color":         conf_color,
        "continent":          continent,
        "validation":         None,
        "data_source":        "real" if has_real_data else "estimated",
        "over_score":         over_score,
        "ai_reasons":         ai_reasons or [],
        "score_breakdown":    score_breakdown or {},
        "btts_prob":          round(btts_prob, 3),
        "btts_label":         btts_label,
        "h2h_over_rate":      round(h2h_over_rate, 3),
        "probable_score":     probable_score,
        "shots_total":        shots_total,
        "shots_on":           shots_on,
        "corners":            corners,
        "match_type":         "live" if is_live else ("finished" if is_finished else "future"),
        # Champs supplémentaires Partie 7
        "urgency_score":      urg,
        "final_live_score":   final_live_score,
        "remaining_min":      remaining_min,
        "expected_goals":     expected_goals,
        "avg_goals_last5":    avg_goals_last5,
        "home_atk":           round(home_atk, 3),
        "away_atk":           round(away_atk, 3),
    }
