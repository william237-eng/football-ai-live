"""
daily_predictions_engine.py
============================
Moteur multi-marchés pour les prédictions des matchs futurs du jour.
4 rubriques : Victoires · Double Chance · GG (BTTS) · Corners+Cartons
Sélectionne TOP 10 par rubrique, analyse basée sur forme récente + stats.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(v, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _poisson_prob(lam: float, k: int) -> float:
    if lam <= 0:
        return 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _poisson_over(lam: float, threshold: int) -> float:
    if lam <= 0:
        return 0.0
    prob_under = sum(_poisson_prob(lam, k) for k in range(threshold))
    return max(0.0, min(0.95, 1.0 - prob_under))


def _team_stats_from_recent(
    fixtures: List[Dict], team_id: int, last: int = 6
) -> Dict[str, float]:
    """
    Calcule les stats d'une équipe depuis ses derniers matchs :
    avg_scored, avg_conceded, btts_rate, win_rate, clean_sheet_rate,
    avg_corners_for (si dispo), avg_cards_for (si dispo).
    """
    scored    = []
    conceded  = []
    btts      = []
    wins      = []
    recent = fixtures[-last:] if len(fixtures) >= last else fixtures

    for fx in recent:
        try:
            teams  = fx.get("teams", {})
            goals  = fx.get("goals", {})
            hid    = (teams.get("home") or {}).get("id")
            home_g = _safe(goals.get("home"))
            away_g = _safe(goals.get("away"))
            if hid == team_id:
                sc, co = home_g, away_g
                won = home_g > away_g
            else:
                sc, co = away_g, home_g
                won = away_g > home_g
            scored.append(sc)
            conceded.append(co)
            btts.append(1.0 if sc > 0 and co > 0 else 0.0)
            wins.append(1.0 if won else 0.0)
        except Exception:
            continue

    n = len(scored)
    if n == 0:
        return {
            "avg_scored": 1.2, "avg_conceded": 1.2,
            "btts_rate": 0.5, "win_rate": 0.35,
            "clean_sheet_rate": 0.25,
            "avg_goals_total": 2.4,
        }
    return {
        "avg_scored":       round(sum(scored) / n, 3),
        "avg_conceded":     round(sum(conceded) / n, 3),
        "btts_rate":        round(sum(btts) / n, 3),
        "win_rate":         round(sum(wins) / n, 3),
        "clean_sheet_rate": round(sum(1 for c in conceded if c == 0) / n, 3),
        "avg_goals_total":  round((sum(scored) + sum(conceded)) / n, 3),
    }


def _parse_datetime(raw_date: str):
    import datetime as _dt
    try:
        if raw_date.endswith("Z"):
            raw_date = raw_date[:-1] + "+00:00"
        return _dt.datetime.fromisoformat(raw_date).astimezone()
    except Exception:
        return None


def _base_match_info(fx: Dict) -> Dict[str, Any]:
    """Extrait les infos de base d'un fixture API-Football."""
    fixture    = fx.get("fixture") or {}
    teams      = fx.get("teams") or {}
    league     = fx.get("league") or {}
    status_inf = fixture.get("status") or {}

    home = teams.get("home") or {}
    away = teams.get("away") or {}

    raw_date = fixture.get("date", "")
    dtobj    = _parse_datetime(raw_date)
    start_time         = dtobj.strftime("%H:%M") if dtobj else "—"
    start_date_display = dtobj.strftime("%d/%m/%Y") if dtobj else "—"

    return {
        "fixture_id":        fixture.get("id"),
        "home_id":           home.get("id"),
        "away_id":           away.get("id"),
        "home_name":         home.get("name", "—"),
        "away_name":         away.get("name", "—"),
        "home_logo":         home.get("logo", ""),
        "away_logo":         away.get("logo", ""),
        "league_name":       league.get("name", "—"),
        "league_country":    league.get("country", "—"),
        "league_flag":       league.get("flag", ""),
        "league_id":         league.get("id"),
        "season":            league.get("season"),
        "start_time":        start_time,
        "start_date_display": start_date_display,
        "status_short":      status_inf.get("short", "NS"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Calculs par marché
# ─────────────────────────────────────────────────────────────────────────────

def _compute_win_prob(
    home_stats: Dict, away_stats: Dict,
    home_elo: float = 1500, away_elo: float = 1500,
) -> Dict[str, float]:
    """
    Calcule P(home win), P(draw), P(away win) via force relative + ELO.
    """
    LEAGUE_AVG = 1.25
    h_atk = home_stats["avg_scored"]
    h_def = home_stats["avg_conceded"]
    a_atk = away_stats["avg_scored"]
    a_def = away_stats["avg_conceded"]

    lam_h = h_atk * (a_def / LEAGUE_AVG) if a_def > 0 else h_atk
    lam_a = a_atk * (h_def / LEAGUE_AVG) if h_def > 0 else a_atk

    lam_h = max(0.3, lam_h)
    lam_a = max(0.3, lam_a)

    # Matrice de scores jusqu'à 6 buts
    p_home, p_draw, p_away = 0.0, 0.0, 0.0
    for i in range(7):
        for j in range(7):
            p = _poisson_prob(lam_h, i) * _poisson_prob(lam_a, j)
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p

    # Ajustement ELO léger
    elo_diff = (home_elo - away_elo) / 400.0
    elo_factor = 1.0 / (1.0 + 10 ** (-elo_diff))  # 0.5 si égaux
    boost = (elo_factor - 0.5) * 0.15
    p_home = min(0.92, max(0.03, p_home + boost))
    p_away = min(0.92, max(0.03, p_away - boost))
    total  = p_home + p_draw + p_away
    return {
        "p_home": round(p_home / total, 4),
        "p_draw": round(p_draw / total, 4),
        "p_away": round(p_away / total, 4),
        "lam_h":  round(lam_h, 2),
        "lam_a":  round(lam_a, 2),
    }


def _compute_double_chance(win_probs: Dict) -> Dict[str, float]:
    """Calcule les 3 double chances : 1X, X2, 12."""
    ph = win_probs["p_home"]
    pd = win_probs["p_draw"]
    pa = win_probs["p_away"]
    return {
        "dc_1x": round(min(0.95, ph + pd), 4),   # Home ou Nul
        "dc_x2": round(min(0.95, pd + pa), 4),   # Nul ou Away
        "dc_12": round(min(0.95, ph + pa), 4),   # Home ou Away (pas nul)
    }


def _compute_btts(home_stats: Dict, away_stats: Dict) -> float:
    """
    Probabilité GG (les deux équipes marquent).
    P(GG) ≈ P(home scores) × P(away scores)
    P(home scores) = 1 - P(home scores 0) = 1 - Poisson(lam_h, 0)
    """
    lam_h = max(0.3, home_stats["avg_scored"])
    lam_a = max(0.3, away_stats["avg_scored"])
    p_home_scores = 1.0 - math.exp(-lam_h)
    p_away_scores = 1.0 - math.exp(-lam_a)

    # Pondérer avec le taux historique BTTS
    btts_hist = (home_stats["btts_rate"] + away_stats["btts_rate"]) / 2
    btts_model = p_home_scores * p_away_scores

    prob = btts_model * 0.60 + btts_hist * 0.40
    return round(min(0.93, max(0.05, prob)), 4)


def _compute_corners_cards(
    home_stats: Dict, away_stats: Dict,
    corner_threshold: int = 8,   # Over 7.5
    card_threshold: int   = 3,   # Over 2.5 cartons (= au moins 3)
) -> Dict[str, float]:
    """
    Probabilité Over 7.5 corners + probabilité Over 2.5 cartons jaunes.
    Basé sur des lambdas estimés depuis stats/forme (sans stats de corners explicites,
    on utilise des proxies : intensité du match, ligue, rivalité).
    """
    # Lambda corners : proxy basé sur avg_goals total (matchs ouverts → plus de corners)
    total_goals_h = home_stats.get("avg_goals_total", 2.4)
    total_goals_a = away_stats.get("avg_goals_total", 2.4)
    intensity = (total_goals_h + total_goals_a) / 2.0

    # Calibration empirique : ~10 corners/match en moyenne europeenne
    lam_corners = 9.5 + (intensity - 2.5) * 0.8
    lam_corners = max(6.0, min(14.0, lam_corners))

    # Lambda cartons : matchs serrés → plus de cartons
    win_rate_gap = abs(home_stats["win_rate"] - away_stats["win_rate"])
    lam_cards = 3.8 - win_rate_gap * 1.2   # matchs serrés → plus de cartons
    lam_cards = max(2.0, min(6.0, lam_cards))

    p_over_corners = _poisson_over(lam_corners, corner_threshold)
    p_over_cards   = _poisson_over(lam_cards, card_threshold)

    # Probabilité combinée : les deux conditions simultanément
    p_combined = p_over_corners * p_over_cards

    return {
        "p_over_corners":  round(p_over_corners, 4),
        "p_over_cards":    round(p_over_cards, 4),
        "p_combined":      round(min(0.90, p_combined), 4),
        "lam_corners":     round(lam_corners, 1),
        "lam_cards":       round(lam_cards, 1),
    }


def _confidence_label(prob: float) -> Tuple[str, str]:
    if prob >= 0.80:
        return "Très élevée", "#22c55e"
    elif prob >= 0.70:
        return "Élevée", "#84cc16"
    elif prob >= 0.60:
        return "Modérée", "#f59e0b"
    elif prob >= 0.50:
        return "Faible", "#f97316"
    return "Très faible", "#ef4444"


# ─────────────────────────────────────────────────────────────────────────────
# Seuils minimums par rubrique
# ─────────────────────────────────────────────────────────────────────────────
MIN_WIN_PROB    = 0.55   # min pour qu'une victoire soit sélectionnée
MIN_DC_PROB     = 0.70   # double chance
MIN_BTTS_PROB   = 0.55   # GG
MIN_CORNER_PROB = 0.45   # combiné corners+cartons (plus difficile à atteindre)
TOP_N           = 10


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée : analyse d'une liste de fixtures
# ─────────────────────────────────────────────────────────────────────────────

def analyze_fixtures_for_daily(
    fixtures: List[Dict[str, Any]],
    recent_map: Optional[Dict[int, List[Dict]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Analyse les fixtures et retourne 4 listes TOP 10 :
    - wins       : Victoires (home ou away)
    - double_chance : Double Chances
    - btts       : GG (les deux marquent)
    - corners_cards : Over 7.5 corners + 3 cartons jaunes

    recent_map : {team_id: [fixtures récents]} — optionnel, enrichit l'analyse
    """
    recent_map = recent_map or {}

    wins_list    = []
    dc_list      = []
    btts_list    = []
    cc_list      = []

    for fx in fixtures:
        info = _base_match_info(fx)
        if not info["fixture_id"]:
            continue

        # Ne prendre que les matchs non commencés
        if info["status_short"] not in ("NS", "TBD"):
            continue

        home_id = info["home_id"]
        away_id = info["away_id"]

        home_recent = recent_map.get(home_id, [])
        away_recent = recent_map.get(away_id, [])

        home_stats = _team_stats_from_recent(home_recent, home_id)
        away_stats = _team_stats_from_recent(away_recent, away_id)

        # ── Calculs ──────────────────────────────────────────────────────
        win_probs = _compute_win_prob(home_stats, away_stats)
        dc_probs  = _compute_double_chance(win_probs)
        btts_prob = _compute_btts(home_stats, away_stats)
        cc_probs  = _compute_corners_cards(home_stats, away_stats)

        base = {
            **info,
            "home_stats": home_stats,
            "away_stats": away_stats,
            "win_probs":  win_probs,
            "dc_probs":   dc_probs,
            "btts_prob":  btts_prob,
            "cc_probs":   cc_probs,
        }

        # ── Victoire la plus probable ─────────────────────────────────────
        ph, pa = win_probs["p_home"], win_probs["p_away"]
        best_win_prob = max(ph, pa)
        best_win_team = info["home_name"] if ph >= pa else info["away_name"]
        best_win_side = "home" if ph >= pa else "away"
        if best_win_prob >= MIN_WIN_PROB:
            conf_lbl, conf_col = _confidence_label(best_win_prob)
            wins_list.append({
                **base,
                "market":        "VICTOIRE",
                "prediction":    best_win_team,
                "side":          best_win_side,
                "prob":          round(best_win_prob, 4),
                "pct":           round(best_win_prob * 100, 1),
                "conf_label":    conf_lbl,
                "conf_color":    conf_col,
                "detail":        f"P(home)={round(ph*100,1)}% · P(away)={round(pa*100,1)}%",
            })

        # ── Double Chance ──────────────────────────────────────────────────
        best_dc_key  = max(dc_probs, key=lambda k: dc_probs[k])
        best_dc_prob = dc_probs[best_dc_key]
        dc_labels    = {
            "dc_1x": f"{info['home_name']} ou Nul (1X)",
            "dc_x2": f"Nul ou {info['away_name']} (X2)",
            "dc_12": f"{info['home_name']} ou {info['away_name']} (12)",
        }
        if best_dc_prob >= MIN_DC_PROB:
            conf_lbl, conf_col = _confidence_label(best_dc_prob)
            dc_list.append({
                **base,
                "market":        "DOUBLE CHANCE",
                "prediction":    dc_labels[best_dc_key],
                "dc_key":        best_dc_key,
                "prob":          best_dc_prob,
                "pct":           round(best_dc_prob * 100, 1),
                "conf_label":    conf_lbl,
                "conf_color":    conf_col,
                "detail":        f"1X={round(dc_probs['dc_1x']*100,1)}% · X2={round(dc_probs['dc_x2']*100,1)}% · 12={round(dc_probs['dc_12']*100,1)}%",
            })

        # ── GG / BTTS ──────────────────────────────────────────────────────
        if btts_prob >= MIN_BTTS_PROB:
            conf_lbl, conf_col = _confidence_label(btts_prob)
            btts_list.append({
                **base,
                "market":        "GG (BTTS)",
                "prediction":    "Les deux équipes marquent",
                "prob":          btts_prob,
                "pct":           round(btts_prob * 100, 1),
                "conf_label":    conf_lbl,
                "conf_color":    conf_col,
                "detail":        f"Taux hist. GG : home={round(home_stats['btts_rate']*100)}% · away={round(away_stats['btts_rate']*100)}%",
            })

        # ── Corners + Cartons ──────────────────────────────────────────────
        p_comb = cc_probs["p_combined"]
        if p_comb >= MIN_CORNER_PROB:
            conf_lbl, conf_col = _confidence_label(p_comb)
            cc_list.append({
                **base,
                "market":        "CORNERS + CARTONS",
                "prediction":    "Over 7.5 corners + 3 cartons jaunes",
                "prob":          p_comb,
                "pct":           round(p_comb * 100, 1),
                "conf_label":    conf_lbl,
                "conf_color":    conf_col,
                "p_corners":     cc_probs["p_over_corners"],
                "p_cards":       cc_probs["p_over_cards"],
                "detail":        f"Corners Over 7.5 : {round(cc_probs['p_over_corners']*100,1)}% · Cartons ≥3 : {round(cc_probs['p_over_cards']*100,1)}%",
            })

    # ── Tri par probabilité décroissante + TOP 10 ──────────────────────────
    wins_list.sort(key=lambda x: x["prob"], reverse=True)
    dc_list.sort(key=lambda x: x["prob"], reverse=True)
    btts_list.sort(key=lambda x: x["prob"], reverse=True)
    cc_list.sort(key=lambda x: x["prob"], reverse=True)

    return {
        "wins":          wins_list[:TOP_N],
        "double_chance": dc_list[:TOP_N],
        "btts":          btts_list[:TOP_N],
        "corners_cards": cc_list[:TOP_N],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fetch + analyse via API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_daily_predictions(api) -> Dict[str, List[Dict[str, Any]]]:
    """
    Récupère les fixtures du jour (non commencés), les analyse, retourne les 4 rubriques.
    """
    from modules.top_over25_live.league_blacklist import is_blacklisted

    today_str = date.today().isoformat()
    raw_items: List[Dict] = []

    try:
        raw, _ = api.get_fixtures_by_date(today_str)
        if isinstance(raw, dict) and "response" in raw:
            raw_items = raw["response"] or []
        elif isinstance(raw, list):
            raw_items = raw
    except Exception:
        pass

    # Filtrer : seulement NS + pas blacklistés
    fixtures = []
    for fx in raw_items:
        status_short = (fx.get("fixture") or {}).get("status", {}).get("short", "NS")
        if status_short not in ("NS", "TBD"):
            continue
        if is_blacklisted(fx):
            continue
        fixtures.append(fx)

    return analyze_fixtures_for_daily(fixtures)
