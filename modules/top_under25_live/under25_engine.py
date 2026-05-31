"""
under25_engine.py
=================
Moteur IA UNDER 2.5 STRICT.
UNDER_SCORE = attack*0.30 + defense*0.25 + form*0.20 + h2h*0.15 + btts*0.10
Confiance basée sur UNDER_SCORE (90/80/70/60).
"""
from __future__ import annotations

import math
import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

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
    """P(goals <= threshold-1) via Poisson(lambda)."""
    if lam <= 0:
        return 1.0
    return max(0.0, min(1.0, sum(
        math.exp(-lam) * (lam ** k) / math.factorial(k)
        for k in range(threshold)
    )))


def _team_attack_defense(fixtures: List[Dict], team_id: int, last: int = 6) -> Tuple[float, float]:
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
        return 1.0, 1.0
    return round(scored / count, 3), round(conceded / count, 3)


def _h2h_stats(h2h_fixtures: List[Dict]) -> Tuple[float, float]:
    """Retourne (avg_goals, under25_rate) sur les 5 derniers H2H."""
    if not h2h_fixtures:
        return 2.5, 0.50
    total = count = under_count = 0.0
    for fx in h2h_fixtures[-5:]:
        try:
            goals  = fx.get("goals", {})
            g      = _safe(goals.get("home")) + _safe(goals.get("away"))
            total += g
            count += 1
            if g <= 2:
                under_count += 1
        except Exception:
            continue
    if count == 0:
        return 2.5, 0.50
    return round(total / count, 2), round(under_count / count, 3)


def _btts_rate(home_recent: List[Dict], away_recent: List[Dict],
               home_id: int, away_id: int) -> float:
    """Taux de matchs où les deux équipes ont marqué."""
    total = btts = 0
    for fx_list, tid in [(home_recent, home_id), (away_recent, away_id)]:
        for fx in (fx_list or [])[-5:]:
            try:
                goals = fx.get("goals", {})
                hg = _safe(goals.get("home"))
                ag = _safe(goals.get("away"))
                total += 1
                if hg > 0 and ag > 0:
                    btts += 1
            except Exception:
                continue
    return round(btts / total, 3) if total > 0 else 0.5


def _extract_live_shots(live_stats: List[Dict], home_id: int, away_id: int) -> Tuple[float, float, float, float]:
    sh = shon = sa = saon = 0.0
    for ts in (live_stats or []):
        sid = (ts.get("team") or {}).get("id")
        for s in (ts.get("statistics") or []):
            t = (s.get("type") or "").lower()
            v = _safe(s.get("value"), 0)
            if sid == home_id:
                if "shots on" in t: shon = v
                elif "shots" in t:  sh   = v
            elif sid == away_id:
                if "shots on" in t: saon = v
                elif "shots" in t:  sa   = v
    return sh, shon, sa, saon


def _extract_live_corners(live_stats: List[Dict], home_id: int, away_id: int) -> float:
    total = 0.0
    for ts in (live_stats or []):
        for s in (ts.get("statistics") or []):
            if "corner" in (s.get("type") or "").lower():
                total += _safe(s.get("value"), 0)
    return total


def _count_red_cards(live_stats: List[Dict]) -> int:
    total = 0
    for ts in (live_stats or []):
        for s in (ts.get("statistics") or []):
            if "red card" in (s.get("type") or "").lower():
                try:
                    total += int(s.get("value") or 0)
                except (TypeError, ValueError):
                    pass
    return total


def _probable_score_under(lambda_home: float, lambda_away: float) -> Tuple[int, int]:
    """Score le plus probable avec total <= 2."""
    best_p, best_h, best_a = -1.0, 0, 0
    for h in range(6):
        for a in range(6):
            if h + a > 2:
                continue
            p = (math.exp(-lambda_home) * lambda_home ** h / math.factorial(h) *
                 math.exp(-lambda_away) * lambda_away ** a / math.factorial(a))
            if p > best_p:
                best_p, best_h, best_a = p, h, a
    return best_h, best_a


# ─────────────────────────────────────────────────────────────────────────────
# UNDER_SCORE composite (Règle 4)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_under_score(
    home_atk: float, away_atk: float,
    home_def: float, away_def: float,
    prob: float,
    h2h_under_rate: float,
    btts_rate: float,
    home_xg: float, away_xg: float,
    is_live: bool, minute: float,
    shots_total: float, corners: float,
) -> Tuple[float, List[str], Dict[str, float]]:
    """
    UNDER_SCORE = attack_component*0.30 + defense_component*0.25
                + form_component*0.20 + h2h_component*0.15
                + btts_component*0.10
    Normalisé [0, 100].
    """
    reasons: List[str] = []
    breakdown: Dict[str, float] = {}

    # 1. Attack component (max 30) — faible attaque = bon signe Under
    avg_atk = (home_atk + away_atk) / 2
    # Inverser : moins offensive = plus de points Under
    atk_raw  = max(0.0, min(1.0, 1.0 - (avg_atk - 0.5) / 2.0))
    atk_pts  = round(atk_raw * 30, 1)
    breakdown["Attack"] = atk_pts
    if avg_atk <= 1.1:
        reasons.append(f"✓ Attaques très discrètes ({home_atk:.1f} + {away_atk:.1f} buts/match)")
    elif avg_atk <= 1.5:
        reasons.append(f"✓ Faible offensive ({home_atk:.1f} + {away_atk:.1f} buts/match)")
    else:
        reasons.append(f"■ Moyenne buts : {home_atk:.1f} + {away_atk:.1f} (modérée)")

    # 2. Defense component (max 25) — bonne défense = moins de buts encaissés
    avg_def  = (home_def + away_def) / 2
    def_raw  = max(0.0, min(1.0, 1.0 - (avg_def - 0.4) / 2.0))
    def_pts  = round(def_raw * 25, 1)
    breakdown["Defense"] = def_pts
    if home_def <= 1.0 and away_def <= 1.0:
        reasons.append(f"✓ Défenses solides ({home_def:.1f} + {away_def:.1f} concédés/match)")
    elif avg_def <= 1.3:
        reasons.append(f"✓ Défenses correctes ({avg_def:.1f} moy. concédés)")
    else:
        reasons.append(f"■ Défenses perméables ({avg_def:.1f} moy. concédés)")

    # 3. Form component (max 20) — probabilité Poisson Under
    form_pts = round(min(1.0, prob / 0.95) * 20, 1)
    breakdown["Form"] = form_pts
    if prob >= 0.80:
        reasons.append(f"✓ Probabilité Poisson élevée ({round(prob*100,1)}%)")
    elif prob >= 0.65:
        reasons.append(f"✓ Probabilité Poisson modérée ({round(prob*100,1)}%)")
    else:
        reasons.append(f"■ Probabilité Poisson faible ({round(prob*100,1)}%)")

    # 4. H2H Under 2.5 component (max 15)
    h2h_pts  = round(h2h_under_rate * 15, 1)
    breakdown["H2H"] = h2h_pts
    h2h_pct = round(h2h_under_rate * 100)
    if h2h_under_rate >= 0.60:
        reasons.append(f"✓ Historique favorable : {h2h_pct}% Under 2.5 en H2H")
    elif h2h_under_rate >= 0.45:
        reasons.append(f"■ H2H Under 2.5 : {h2h_pct}% (neutre)")
    else:
        reasons.append(f"■ H2H Under 2.5 : {h2h_pct}% (défavorable)")

    # 5. BTTS component (max 10) — faible BTTS = bien pour Under
    btts_pts = round((1.0 - btts_rate) * 10, 1)
    breakdown["BTTS"] = btts_pts
    btts_pct = round(btts_rate * 100)
    if btts_rate <= 0.35:
        reasons.append(f"✓ Faible BTTS ({btts_pct}%) — score verrouillé probable")
    elif btts_rate <= 0.50:
        reasons.append(f"✓ BTTS modéré ({btts_pct}%)")
    else:
        reasons.append(f"■ BTTS élevé ({btts_pct}%) — risque les deux équipes marquent")

    base_score = atk_pts + def_pts + form_pts + h2h_pts + btts_pts

    # Bonus xG faible (live ou pré-match)
    xg_total = home_xg + away_xg
    xg_bonus = 0.0
    if xg_total > 0:
        xg_bonus = round(max(0.0, min(1.0, 1.0 - xg_total / 3.0)) * 8, 1)
        breakdown["xG"] = xg_bonus
        reasons.append(f"✓ xG cumulé faible : {home_xg:.2f} + {away_xg:.2f} = {xg_total:.2f}")
    else:
        breakdown["xG"] = 0.0

    # Bonus live : peu de tirs = bien pour Under
    live_bonus = 0.0
    if is_live and shots_total > 0:
        live_bonus = round(max(0.0, min(1.0, 1.0 - shots_total / 20.0)) * 7, 1)
        breakdown["Live pressure"] = live_bonus
        if shots_total <= 6:
            reasons.append(f"✓ Seulement {int(shots_total)} tirs à la {int(minute)}' (faible intensité)")
        else:
            reasons.append(f"■ {int(shots_total)} tirs à la {int(minute)}' (pression modérée)")
    else:
        breakdown["Live pressure"] = 0.0

    total = round(min(100.0, max(0.0, base_score + xg_bonus + live_bonus)), 1)
    breakdown["Total"] = total
    return total, reasons, breakdown


# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

MIN_UNDER_SCORE = 65.0   # NE JAMAIS afficher un match avec under_score < 65


# ─────────────────────────────────────────────────────────────────────────────
# Moteur principal
# ─────────────────────────────────────────────────────────────────────────────

def compute_under25_probability(
    fixture_raw: Dict[str, Any],
    home_recent: Optional[List[Dict]] = None,
    away_recent: Optional[List[Dict]] = None,
    h2h_fixtures: Optional[List[Dict]] = None,
    live_stats: Optional[List[Dict]] = None,
) -> Dict[str, Any]:

    teams       = fixture_raw.get("teams", {})
    goals_raw   = fixture_raw.get("goals", {})
    fixture     = fixture_raw.get("fixture", {})
    league      = fixture_raw.get("league", {})
    status_info = fixture.get("status", {})

    home_id   = (teams.get("home") or {}).get("id")
    away_id   = (teams.get("away") or {}).get("id")
    home_name = (teams.get("home") or {}).get("name", "—")
    away_name = (teams.get("away") or {}).get("name", "—")
    home_logo = (teams.get("home") or {}).get("logo", "")
    away_logo = (teams.get("away") or {}).get("logo", "")

    home_score   = _safe(goals_raw.get("home"), 0)
    away_score   = _safe(goals_raw.get("away"), 0)
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

    # ── Stats équipes ──────────────────────────────────────────────────────
    home_atk, home_def = _team_attack_defense(home_recent or [], home_id or 0)
    away_atk, away_def = _team_attack_defense(away_recent or [], away_id or 0)

    # ── Rejet équipes ultra-offensives (Règle 2) ──────────────────────────
    is_ultra_offensive = (home_atk > 2.0 or away_atk > 2.0)

    # ── Lambda Poisson ─────────────────────────────────────────────────────
    LEAGUE_AVG  = 1.25
    lambda_home = home_atk * (away_def / LEAGUE_AVG) if away_def > 0 else home_atk
    lambda_away = away_atk * (home_def / LEAGUE_AVG) if home_def > 0 else away_atk
    lambda_base = lambda_home + lambda_away

    # ── H2H ───────────────────────────────────────────────────────────────
    h2h_avg_goals, h2h_under_rate = _h2h_stats(h2h_fixtures or [])
    if h2h_avg_goals != 2.5:
        lambda_base = lambda_base * 0.65 + h2h_avg_goals * 0.35

    # ── BTTS ──────────────────────────────────────────────────────────────
    btts_rate_val = _btts_rate(home_recent or [], away_recent or [], home_id or 0, away_id or 0)

    # ── xG live ───────────────────────────────────────────────────────────
    home_xg = away_xg = 0.0
    shots_total = corners_total = 0.0
    red_cards   = 0
    if live_stats:
        for ts in live_stats:
            sid = (ts.get("team") or {}).get("id")
            for s in (ts.get("statistics") or []):
                t = (s.get("type") or "").lower()
                v = s.get("value")
                if "xg" in t:
                    try:
                        fv = float(v or 0)
                        if sid == home_id:   home_xg = fv
                        elif sid == away_id: away_xg = fv
                    except Exception: pass
                elif "shots" in t and "on" not in t:
                    try: shots_total += float(v or 0)
                    except Exception: pass
                elif "corner" in t:
                    try: corners_total += float(v or 0)
                    except Exception: pass
                elif "red card" in t:
                    try: red_cards += int(v or 0)
                    except Exception: pass
        if home_xg + away_xg > 0:
            lambda_base = lambda_base * 0.55 + (home_xg + away_xg) * 0.45

    # ── Probabilité Under 2.5 ─────────────────────────────────────────────
    if is_live and minute > 0:
        if total_goals >= 3:
            return _build_result(
                fixture_id, home_name, away_name, home_logo, away_logo,
                home_score, away_score, minute, status_short, status_long,
                league_name, league_country, league_flag, league_id, season,
                start_time, start_date_display, is_live, is_finished,
                prob=0.0, lambda_home=lambda_home, lambda_away=lambda_away,
                home_xg=home_xg, away_xg=away_xg,
                locked=True, locked_reason=f"Déjà {total_goals} buts → Under 2.5 impossible",
                continent=get_continent(league_country),
                has_real_data=_has_real_data,
                home_atk=home_atk, away_atk=away_atk,
                home_def=home_def, away_def=away_def,
                h2h_under_rate=h2h_under_rate, btts_rate=btts_rate_val,
                shots_total=shots_total, corners_total=corners_total,
                red_cards=red_cards, is_ultra_offensive=is_ultra_offensive,
            )
        remaining = max(1, 90 - minute)
        goals_allowed = 2 - total_goals
        lambda_residual = lambda_base * (remaining / 90.0)
        prob = _poisson_under(lambda_residual, threshold=goals_allowed + 1)
    else:
        prob = _poisson_under(lambda_base, threshold=3)

    prob = min(0.95, max(0.0, prob))

    # ── UNDER_SCORE ────────────────────────────────────────────────────────
    under_score, ai_reasons, score_breakdown = _compute_under_score(
        home_atk=home_atk, away_atk=away_atk,
        home_def=home_def, away_def=away_def,
        prob=prob,
        h2h_under_rate=h2h_under_rate,
        btts_rate=btts_rate_val,
        home_xg=home_xg, away_xg=away_xg,
        is_live=is_live, minute=minute,
        shots_total=shots_total, corners=corners_total,
    )

    # ── Score probable (total <= 2) ────────────────────────────────────────
    prob_score_h, prob_score_a = _probable_score_under(lambda_home, lambda_away)

    return _build_result(
        fixture_id, home_name, away_name, home_logo, away_logo,
        home_score, away_score, minute, status_short, status_long,
        league_name, league_country, league_flag, league_id, season,
        start_time, start_date_display, is_live, is_finished,
        prob=prob, lambda_home=lambda_home, lambda_away=lambda_away,
        home_xg=home_xg, away_xg=away_xg,
        locked=False, locked_reason="",
        continent=get_continent(league_country),
        has_real_data=_has_real_data,
        home_atk=home_atk, away_atk=away_atk,
        home_def=home_def, away_def=away_def,
        h2h_under_rate=h2h_under_rate, btts_rate=btts_rate_val,
        shots_total=shots_total, corners_total=corners_total,
        red_cards=red_cards, is_ultra_offensive=is_ultra_offensive,
        under_score=under_score, ai_reasons=ai_reasons,
        score_breakdown=score_breakdown,
        probable_score=(prob_score_h, prob_score_a),
    )


def _build_result(
    fixture_id, home_name, away_name, home_logo, away_logo,
    home_score, away_score, minute, status_short, status_long,
    league_name, league_country, league_flag, league_id, season,
    start_time, start_date_display,
    is_live, is_finished,
    prob, home_xg, away_xg,
    locked, locked_reason, continent,
    has_real_data: bool = False,
    lambda_home: float = 1.0,
    lambda_away: float = 1.0,
    home_atk: float = 1.0,
    away_atk: float = 1.0,
    home_def: float = 1.0,
    away_def: float = 1.0,
    h2h_under_rate: float = 0.5,
    btts_rate: float = 0.5,
    shots_total: float = 0.0,
    corners_total: float = 0.0,
    red_cards: int = 0,
    is_ultra_offensive: bool = False,
    under_score: float = 0.0,
    ai_reasons: Optional[List[str]] = None,
    score_breakdown: Optional[Dict[str, float]] = None,
    probable_score: Tuple[int, int] = (1, 0),
) -> Dict[str, Any]:

    # Confiance basée sur UNDER_SCORE (Règle 4)
    if under_score >= 90:
        conf_label, conf_color = "Exceptionnelle", "#a78bfa"
    elif under_score >= 80:
        conf_label, conf_color = "Très élevée", "#22c55e"
    elif under_score >= 70:
        conf_label, conf_color = "Élevée", "#84cc16"
    elif under_score >= 60:
        conf_label, conf_color = "Modérée", "#f59e0b"
    else:
        conf_label, conf_color = "Faible", "#ef4444"

    btts_label = "Oui" if btts_rate >= 0.55 else "Non" if btts_rate < 0.40 else "Incertain"
    expected_goals = round(lambda_home + lambda_away, 2)
    avg_goals_last5 = round(home_atk + away_atk, 2)
    match_type = "live" if is_live else ("finished" if is_finished else "future")

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
        "lambda_home":        round(lambda_home, 2),
        "lambda_away":        round(lambda_away, 2),
        "lambda_val":         round(lambda_home + lambda_away, 2),
        "home_xg":            round(home_xg, 2),
        "away_xg":            round(away_xg, 2),
        "locked":             locked,
        "locked_reason":      locked_reason,
        "conf_label":         conf_label,
        "conf_color":         conf_color,
        "continent":          continent,
        "validation":         None,
        "data_source":        "real" if has_real_data else "estimated",
        # Champs enrichis
        "under_score":        under_score,
        "ai_reasons":         ai_reasons or [],
        "score_breakdown":    score_breakdown or {},
        "home_atk":           round(home_atk, 3),
        "away_atk":           round(away_atk, 3),
        "home_def":           round(home_def, 3),
        "away_def":           round(away_def, 3),
        "h2h_under_rate":     round(h2h_under_rate, 3),
        "btts_rate":          round(btts_rate, 3),
        "btts_label":         btts_label,
        "shots_total":        shots_total,
        "corners_total":      corners_total,
        "red_cards":          red_cards,
        "is_ultra_offensive": is_ultra_offensive,
        "probable_score":     probable_score,
        "expected_goals":     expected_goals,
        "avg_goals_last5":    avg_goals_last5,
        "match_type":         match_type,
    }
