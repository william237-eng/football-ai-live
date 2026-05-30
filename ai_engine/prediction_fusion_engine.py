"""
Prediction Fusion Engine
========================
SOURCE UNIQUE DE VÉRITÉ pour toutes les prédictions du match.

Architecture:
  Inputs (forme, ELO, H2H, classement, live stats, événements)
       ↓
  Fusion Engine  (ce fichier)
       ↓
  Consistency Validator
       ↓
  final_probabilities  ←  utilisé par TOUS les modules
  final_score_predictions
  final_confidence
  final_conclusion

AUCUN autre module ne doit calculer ses propres 1X2 ou confiance.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ai_engine.poisson_engine import (
    expected_goals,
    score_matrix_live,
)
from ai_engine.live_context_engine import dynamic_lambdas, build_live_context
from ai_engine.elo_rating import calculate_elo
from ai_engine.btts_engine import compute_btts
from ai_engine.over_under_engine import compute_over_under
from ai_engine.confidence_engine import compute_global_confidence, get_level
from ai_engine.momentum_engine import compute_momentum
from ai_engine.pressure_engine import compute_pressure
from ai_engine.score_filter_engine import top_possible_scores
from ai_engine.conclusion_engine import generate_conclusion


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(v, default=0.0) -> float:
    try:
        return float(str(v).replace("%", "").strip())
    except Exception:
        return default


def _h2h_goal_avg(
    h2h_items: List[Dict], home_team: str
) -> Tuple[float, float]:
    if not h2h_items:
        return 0.0, 0.0
    th = ta = count = 0
    for item in h2h_items[:5]:
        teams = item.get("teams") or {}
        goals = item.get("goals") or {}
        ht_name = (teams.get("home") or {}).get("name", "")
        gh = goals.get("home") or 0
        ga = goals.get("away") or 0
        if ht_name == home_team:
            th += gh; ta += ga
        else:
            th += ga; ta += gh
        count += 1
    return (th / count, ta / count) if count else (0.0, 0.0)


def _rank_factor(standings: Any, team_id: int) -> float:
    try:
        for group in (standings or {}).get("response") or []:
            for lg in (group if isinstance(group, list) else [group]):
                for entry in (lg if isinstance(lg, list) else [lg]):
                    if (entry.get("team") or {}).get("id") == team_id:
                        rank = entry.get("rank", 10)
                        return max(0.7, min(1.3, 1.0 + (20 - rank) / 50.0))
    except Exception:
        pass
    return 1.0


# ─────────────────────────────────────────────────────────────────────────────
# FUSION ENGINE — Point d'entrée unique
# ─────────────────────────────────────────────────────────────────────────────

def build_final_prediction(
    *,
    home_team: str,
    away_team: str,
    home_form: Dict[str, Any],
    away_form: Dict[str, Any],
    home_team_id: int = 0,
    away_team_id: int = 0,
    home_stats: Optional[Dict[str, Any]] = None,
    away_stats: Optional[Dict[str, Any]] = None,
    events: Optional[List[Dict[str, Any]]] = None,
    h2h_data: Optional[List[Dict[str, Any]]] = None,
    standings: Optional[Any] = None,
    live_context: Optional[Dict[str, Any]] = None,
    is_live: bool = False,
) -> Dict[str, Any]:
    """
    Calcule UNE SEULE fois toutes les prédictions.
    Retourne final_prediction utilisé par l'UI et tous les sous-modules.
    """
    home_stats = home_stats or {}
    away_stats = away_stats or {}
    events = events or []

    # ── Score & minute live ─────────────────────────────────────────────────
    ctx = live_context or {}
    home_goals = int(ctx.get("home_goals", 0) or 0)
    away_goals = int(ctx.get("away_goals", 0) or 0)
    minute = int(ctx.get("minute", 0) or 0)
    remaining_min = max(0, 90 - minute)
    remaining_frac = remaining_min / 90.0

    # ── ELO ─────────────────────────────────────────────────────────────────
    home_elo = calculate_elo(home_form, home_advantage=True)
    away_elo = calculate_elo(away_form, home_advantage=False)
    elo_delta = max(-350, min(350, home_elo - away_elo))
    elo_shift = elo_delta / 3500.0

    # ── xG de base (forme) ──────────────────────────────────────────────────
    base_h_xg, base_a_xg = expected_goals(home_form, away_form)

    # ── Correction H2H ──────────────────────────────────────────────────────
    if h2h_data:
        h2h_h, h2h_a = _h2h_goal_avg(h2h_data, home_team)
        if h2h_h > 0 or h2h_a > 0:
            base_h_xg = base_h_xg * 0.6 + h2h_h * 0.4
            base_a_xg = base_a_xg * 0.6 + h2h_a * 0.4

    # ── Correction classement ────────────────────────────────────────────────
    if standings and home_team_id and away_team_id:
        base_h_xg = max(0.05, base_h_xg * _rank_factor(standings, home_team_id))
        base_a_xg = max(0.05, base_a_xg * _rank_factor(standings, away_team_id))

    # ── Moteurs contextuels ──────────────────────────────────────────────────
    momentum_result = compute_momentum(home_stats, away_stats, events, home_goals, away_goals, minute)
    pressure_result = compute_pressure(home_stats, away_stats)

    # ── xG restants ajustés (Poisson conditionnel) ───────────────────────────
    mom_val = momentum_result.get("value", 0.0)
    pressure_unknown = pressure_result.get("unknown", True)

    if is_live and minute > 0:
        red_shift = ctx.get("red_card_shift", 0.0) or 0.0
        mom_h = 1.0 + max(-0.35, min(0.35, mom_val * 0.5))
        mom_a = 1.0 - max(-0.35, min(0.35, mom_val * 0.5))

        if not pressure_unknown:
            ph = pressure_result.get("home_index", 50) or 50
            pa = pressure_result.get("away_index", 50) or 50
            pr = ph / (ph + pa + 1e-9)
        else:
            pr = 0.5

        rem_h = max(0.01, base_h_xg * remaining_frac * mom_h * (0.8 + pr * 0.4))
        rem_a = max(0.01, base_a_xg * remaining_frac * mom_a * (1.2 - pr * 0.4))

        if red_shift < 0:
            rem_a = max(0.01, rem_a * 0.60)
        elif red_shift > 0:
            rem_h = max(0.01, rem_h * 0.60)
    else:
        rem_h = base_h_xg
        rem_a = base_a_xg

    # ── Matrice de scores (buts restants) ────────────────────────────────────
    matrix = score_matrix_live(rem_h, rem_a, home_goals, away_goals, max_goals=8)

    # ── 1X2 brut depuis la matrice ──────────────────────────────────────────
    hw_raw = sum(p for (h, a), p in matrix.items() if h > a)
    d_raw  = sum(p for (h, a), p in matrix.items() if h == a)
    aw_raw = sum(p for (h, a), p in matrix.items() if h < a)

    # ── Correction ELO (plafonnée à ±8 pp) ──────────────────────────────────
    elo_shift_capped = max(-0.08, min(0.08, elo_shift))
    hw = max(0.01, hw_raw + elo_shift_capped)
    aw = max(0.01, aw_raw - elo_shift_capped)
    d  = max(0.01, d_raw)

    # ── Ajustement 1X2 conditionnel — calibré pour éviter les extrêmes ───────
    # Plafonds par écart de buts : 1 but→82%, 2→88%, 3+→93%
    # Régression vers Poisson en début de match pour éviter sur-réaction
    _MAX_BY_DIFF = {0: 0.70, 1: 0.82, 2: 0.88, 3: 0.93}
    if is_live and minute > 0:
        score_diff = home_goals - away_goals
        abs_diff = min(3, abs(score_diff))
        # time_cert croît lentement (max 0.70 à 90')
        time_cert = min(0.70, minute / 90.0 * 0.72)
        # Régression vers Poisson si tôt dans le match
        regression = max(0.0, 1.0 - minute / 90.0) * 0.28
        if score_diff > 0:
            cap = _MAX_BY_DIFF[abs_diff]
            boost = min(cap - hw, abs_diff * 0.085 * (1.0 + time_cert))
            hw = min(cap, hw + boost)
            d  = max(0.02, d * (1.0 - time_cert * 0.55))
            aw = max(0.01, 1.0 - hw - d)
            hw = hw * (1 - regression) + hw_raw * regression
        elif score_diff < 0:
            cap = _MAX_BY_DIFF[abs_diff]
            boost = min(cap - aw, abs_diff * 0.085 * (1.0 + time_cert))
            aw = min(cap, aw + boost)
            d  = max(0.02, d * (1.0 - time_cert * 0.55))
            hw = max(0.01, 1.0 - aw - d)
            aw = aw * (1 - regression) + aw_raw * regression
        else:
            draw_boost = min(0.26, time_cert * 0.30)
            d = min(0.52, d + draw_boost)
            sides = hw + aw + 1e-9
            hw = (1.0 - d) * hw / sides
            aw = (1.0 - d) * aw / sides

    # ── Normaliser ──────────────────────────────────────────────────────────
    _t = hw + d + aw
    hw /= _t; d /= _t; aw /= _t

    # ── final_probabilities : SOURCE UNIQUE ─────────────────────────────────
    final_probabilities = {
        "home_win": round(hw * 100, 1),
        "draw":     round(d  * 100, 1),
        "away_win": round(aw * 100, 1),
    }

    # ── final_score_predictions (filtrés par score actuel) ───────────────────
    top_scores = top_possible_scores(matrix, home_goals, away_goals, count=5)

    # ── BTTS conditionnel ────────────────────────────────────────────────────
    btts_result = compute_btts(home_goals, away_goals, rem_h, rem_a, is_live)

    # ── Over/Under conditionnel ──────────────────────────────────────────────
    ou_markets = compute_over_under(
        home_goals, away_goals, rem_h, rem_a,
        thresholds=[0.5, 1.5, 2.5, 3.5, 4.5],
        is_live=is_live,
    )

    # ── Confiance UNIQUE — calibrée sur l'incertitude réelle ────────────────
    # L'incertitude est l'entropie de Shannon normalisée (max à 1/3-1/3-1/3)
    import math as _math
    def _entropy(p1, p2, p3):
        probs = [x for x in [p1, p2, p3] if x > 0]
        return -sum(p * _math.log(p) for p in probs)
    raw_entropy = _entropy(hw, d, aw)          # 0 (certitude) → 1.099 (max)
    max_entropy = _math.log(3)                 # 1.099
    uncertainty = raw_entropy / max_entropy    # 0→1 (1 = totalement incertain)
    certainty   = 1.0 - uncertainty            # 0→1 (1 = certitude totale)
    has_live_stats = bool(home_stats or away_stats)
    final_confidence = compute_global_confidence(
        hw, d, aw,
        is_live=is_live,
        minute=minute,
        has_live_stats=has_live_stats,
        has_form_data=bool(home_form.get("played", 0)),
        has_h2h=bool(h2h_data),
        data_quality_score=1.0 if has_live_stats else 0.7,
        certainty_override=certainty,
    )

    # ── Corners ─────────────────────────────────────────────────────────────
    def _istat(stats, *keys):
        for k in keys:
            v = (stats or {}).get(k)
            if v is not None:
                try: return int(str(v).replace("%", "").strip())
                except: pass
        return None

    h_corn = _istat(home_stats, "Corner Kicks", "Corners") or 0
    a_corn = _istat(away_stats, "Corner Kicks", "Corners") or 0
    corners_done = h_corn + a_corn
    if is_live and minute > 0 and corners_done > 0:
        total_exp_corn = round(corners_done / minute * 90, 1)
        proj_src = "live"
    else:
        total_exp_corn = round(max(6.0, min(16.0, 10.5 * (rem_h + rem_a) / 2.2)), 1)
        proj_src = "future"
    rem_corn = max(0.0, total_exp_corn - corners_done)
    corners = _corners_markets(rem_corn, corners_done, total_exp_corn, proj_src)

    # ── Cartons ─────────────────────────────────────────────────────────────
    h_yel = _istat(home_stats, "Yellow Cards") or 0
    a_yel = _istat(away_stats, "Yellow Cards") or 0
    h_red = _istat(home_stats, "Red Cards") or 0
    a_red = _istat(away_stats, "Red Cards") or 0
    cards_done = h_yel + a_yel + h_red + a_red
    intensity = abs(hw - aw)
    if is_live and minute > 0 and cards_done > 0:
        exp_cards = round(cards_done / minute * 90, 1)
    else:
        exp_cards = round(max(2.0, min(7.0, 3.8 + intensity * 1.5)), 1)
    rem_cards = max(0.0, exp_cards - cards_done)
    cards = _cards_markets(rem_cards, cards_done, exp_cards)

    # ── Buts par équipe ──────────────────────────────────────────────────────
    team_goals = _team_goals(home_team, away_team, home_goals, away_goals, rem_h, rem_a, is_live)

    # ── Mi-temps avec détection marchés réalisés ─────────────────────────────
    # Un marché est "réalisé" quand l'événement s'est déjà produit
    ht_passed = is_live and minute >= 45
    if ht_passed:
        lh_ht = rem_h * 0.5
        la_ht = rem_a * 0.5
    else:
        lh_ht = base_h_xg * 0.45
        la_ht = base_a_xg * 0.45

    # Déterminer si les équipes ont marqué en 1ère MT depuis les événements
    home_scored_ht1 = False
    away_scored_ht1 = False
    home_scored_ht2 = False
    away_scored_ht2 = False
    for ev in events:
        ev_type = (ev.get("type") or "").lower()
        ev_detail = (ev.get("detail") or "").lower()
        if ev_type not in ("goal",) and "goal" not in ev_type:
            continue
        if "penalty missed" in ev_detail or "own" in ev_detail:
            continue
        ev_minute = ev.get("time", {}).get("elapsed") or 0
        ev_team = (ev.get("team") or {}).get("name", "")
        is_home_ev = ev_team == home_team
        if ev_minute <= 45:
            if is_home_ev: home_scored_ht1 = True
            else: away_scored_ht1 = True
        elif ev_minute <= 90:
            if is_home_ev: home_scored_ht2 = True
            else: away_scored_ht2 = True

    halftime = {
        "home_scores_first":  1.0 if home_scored_ht1 else (_team_over(lh_ht, 0.5) if not ht_passed else 0.0),
        "away_scores_first":  1.0 if away_scored_ht1 else (_team_over(la_ht, 0.5) if not ht_passed else 0.0),
        "home_scores_second": 1.0 if home_scored_ht2 else (_team_over(base_h_xg * 0.55, 0.5) if ht_passed else _team_over(base_h_xg * 0.55, 0.5)),
        "away_scores_second": 1.0 if away_scored_ht2 else (_team_over(base_a_xg * 0.55, 0.5) if ht_passed else _team_over(base_a_xg * 0.55, 0.5)),
        "over_05_ht": _over(lh_ht, la_ht, 0.5),
        "btts_ht":    _btts(lh_ht, la_ht),
        # Tags réalisé
        "home_ht1_realized": home_scored_ht1,
        "away_ht1_realized": away_scored_ht1,
        "home_ht2_realized": home_scored_ht2,
        "away_ht2_realized": away_scored_ht2,
    }

    # ── Prochain but ────────────────────────────────────────────────────────
    total_rem = rem_h + rem_a
    p_h = rem_h / total_rem if total_rem > 0 else 0.5
    p_a = rem_a / total_rem if total_rem > 0 else 0.5
    p_no = math.exp(-min(total_rem, 3.5))
    _s = p_h + p_a + p_no
    next_goal = {
        "home_prob":    p_h / _s,
        "away_prob":    p_a / _s,
        "no_goal_prob": p_no / _s,
        "home_name": home_team,
        "away_name": away_team,
    }

    # ── Conclusion UNIQUE ────────────────────────────────────────────────────
    final_conclusion = generate_conclusion(
        home_name=home_team, away_name=away_team,
        home_goals=home_goals, away_goals=away_goals,
        minute=minute,
        home_win_prob=hw, draw_prob=d, away_win_prob=aw,
        btts_result=btts_result,
        over_under=ou_markets,
        momentum=momentum_result,
        is_live=is_live,
        home_xg=rem_h, away_xg=rem_a,
        confidence=final_confidence,
    )

    # ── Package final ────────────────────────────────────────────────────────
    return {
        # SOURCE DE VÉRITÉ
        "final_probabilities":     final_probabilities,
        "final_score_predictions": top_scores,
        "final_confidence":        final_confidence,
        "final_conclusion":        final_conclusion,

        # Marchés dérivés (tous basés sur final_probabilities)
        "btts":       btts_result,
        "ou_markets": ou_markets,
        "corners":    corners,
        "cards":      cards,
        "team_goals": team_goals,
        "halftime":   halftime,
        "next_goal":  next_goal,
        "momentum":   momentum_result,
        "pressure":   pressure_result,

        # Meta
        "home_goals":  home_goals,
        "away_goals":  away_goals,
        "minute":      minute,
        "is_live":     is_live,
        "home_xg":     round(rem_h, 2),
        "away_xg":     round(rem_a, 2),
        "home_elo":    home_elo,
        "away_elo":    away_elo,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes Poisson
# ─────────────────────────────────────────────────────────────────────────────

def _pois(lam: float, k: int) -> float:
    lam = max(0.001, min(10.0, lam))
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def _over(lh: float, la: float, threshold: float) -> float:
    n = int(threshold)
    total = max(0.001, lh + la)
    return max(0.0, min(1.0, 1.0 - sum(_pois(total, k) for k in range(n + 1))))

def _team_over(lam: float, threshold: float) -> float:
    n = int(threshold)
    return max(0.0, min(1.0, 1.0 - sum(_pois(lam, k) for k in range(n + 1))))

def _btts(lh: float, la: float) -> float:
    return max(0.0, min(1.0, (1.0 - math.exp(-lh)) * (1.0 - math.exp(-la))))

def _cor_over(rem: float, need: float) -> float:
    if need <= 0: return 1.0
    if rem <= 0: return 0.0
    n = int(need)
    return max(0.0, min(1.0, 1.0 - sum(_pois(rem, k) for k in range(n + 1))))

def _corners_markets(rem: float, done: int, total: float, src: str) -> Dict:
    return {
        "expected_total": total, "corners_done": done, "proj_source": src,
        "over_75":  _cor_over(rem, max(0, 7.5 - done)),
        "over_85":  _cor_over(rem, max(0, 8.5 - done)),
        "over_95":  _cor_over(rem, max(0, 9.5 - done)),
        "over_105": _cor_over(rem, max(0, 10.5 - done)),
        "under_85":  1.0 - _cor_over(rem, max(0, 8.5 - done)),
        "under_95":  1.0 - _cor_over(rem, max(0, 9.5 - done)),
        "under_105": 1.0 - _cor_over(rem, max(0, 10.5 - done)),
    }

def _cards_markets(rem: float, done: int, total: float) -> Dict:
    return {
        "expected_total": total, "cards_done": done,
        "over_15":  _cor_over(rem, max(0, 1.5 - done)),
        "over_25":  _cor_over(rem, max(0, 2.5 - done)),
        "over_35":  _cor_over(rem, max(0, 3.5 - done)),
        "over_45":  _cor_over(rem, max(0, 4.5 - done)),
        "under_25": 1.0 - _cor_over(rem, max(0, 2.5 - done)),
        "under_35": 1.0 - _cor_over(rem, max(0, 3.5 - done)),
        "under_45": 1.0 - _cor_over(rem, max(0, 4.5 - done)),
    }

def _team_goals(hn, an, hg, ag, rh, ra, live) -> Dict:
    return {
        "home": {
            "name": hn, "expected": round(rh, 2), "already_scored": hg,
            "over_05": 1.0 if hg >= 1 else (1.0 - math.exp(-rh)),
            "over_15": 1.0 if hg >= 2 else _team_over(rh, max(0, 2 - hg - 0.5)),
            "under_25": 0.0 if hg >= 3 else (1.0 - _team_over(rh, max(0, 3 - hg - 0.5))),
        },
        "away": {
            "name": an, "expected": round(ra, 2), "already_scored": ag,
            "over_05": 1.0 if ag >= 1 else (1.0 - math.exp(-ra)),
            "over_15": 1.0 if ag >= 2 else _team_over(ra, max(0, 2 - ag - 0.5)),
            "under_25": 0.0 if ag >= 3 else (1.0 - _team_over(ra, max(0, 3 - ag - 0.5))),
        },
    }
