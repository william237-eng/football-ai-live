"""
Predictions Engine - Prédictions avancées pour matchs football
Orchestrateur des moteurs contextuels: Market Validator, Score Filter,
BTTS Engine, Over/Under Engine, Confidence Engine, Momentum Engine,
Pressure Engine, Conclusion Engine.
"""
from typing import Dict, Any, List, Optional, Tuple
import math

from ai_engine.market_validator import get_locked_markets
from ai_engine.score_filter_engine import top_possible_scores, filter_impossible_scores
from ai_engine.btts_engine import compute_btts
from ai_engine.over_under_engine import compute_over_under
from ai_engine.confidence_engine import compute_global_confidence, uniform_confidence_for_market, get_level
from ai_engine.momentum_engine import compute_momentum
from ai_engine.pressure_engine import compute_pressure
from ai_engine.conclusion_engine import generate_conclusion


CONFIDENCE_LEVELS = {
    (0, 0.45): ("faible", "🔴", "#ff4444"),
    (0.45, 0.60): ("moyen", "🟡", "#ffaa00"),
    (0.60, 0.75): ("fort", "🟢", "#00cc44"),
    (0.75, 1.01): ("très fort", "💎", "#00d4ff"),
}


def get_confidence(prob: float) -> Tuple[str, str, str]:
    """Retourne (label, icon, color) selon la probabilité."""
    for (low, high), info in CONFIDENCE_LEVELS.items():
        if low <= prob < high:
            return info
    return ("faible", "🔴", "#ff4444")


def poisson_prob(lam: float, k: int) -> float:
    """P(X=k) pour distribution de Poisson."""
    if lam <= 0:
        return 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)


def poisson_over(lam_home: float, lam_away: float, threshold: float) -> float:
    """P(buts totaux > threshold) avec distributions de Poisson."""
    total_lam = lam_home + lam_away
    # P(X <= floor(threshold)) = somme P(X=k) pour k=0..floor(threshold)
    n = int(threshold)
    prob_under_or_eq = sum(poisson_prob(total_lam, k) for k in range(n + 1))
    return max(0.0, min(1.0, 1.0 - prob_under_or_eq))


def poisson_btts(lam_home: float, lam_away: float) -> float:
    """P(les deux équipes marquent) = P(home>=1) * P(away>=1)."""
    p_home_scores = 1.0 - math.exp(-lam_home)
    p_away_scores = 1.0 - math.exp(-lam_away)
    return max(0.0, min(1.0, p_home_scores * p_away_scores))


def poisson_team_over(lam: float, threshold: float) -> float:
    """P(une équipe marque > threshold buts)."""
    n = int(threshold)
    prob_under_or_eq = sum(poisson_prob(lam, k) for k in range(n + 1))
    return max(0.0, min(1.0, 1.0 - prob_under_or_eq))


def _parse_pct(val) -> float:
    """Convertit '65%' ou 65 en float 0.65."""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace("%", "").strip()) / 100.0
    except Exception:
        return 0.0


def _h2h_goal_avg(h2h_items: List[Dict[str, Any]], home_team: str, away_team: str) -> Tuple[float, float]:
    """Calcule la moyenne de buts H2H pour chaque équipe sur les 5 dernières confrontations."""
    if not h2h_items:
        return 0.0, 0.0
    total_home = total_away = count = 0
    for item in h2h_items[:5]:
        teams = item.get("teams") or {}
        goals = item.get("goals") or {}
        ht = (teams.get("home") or {}).get("name", "")
        gh = goals.get("home") or 0
        ga = goals.get("away") or 0
        if ht == home_team:
            total_home += gh
            total_away += ga
        else:
            total_home += ga
            total_away += gh
        count += 1
    if count == 0:
        return 0.0, 0.0
    return total_home / count, total_away / count


def _standing_rank_factor(standings: Any, team_id: int) -> float:
    """Retourne un facteur [0.7..1.3] basé sur la position au classement."""
    try:
        for group in standings.get("response") or []:
            for league_group in (group if isinstance(group, list) else [group]):
                for entry in (league_group if isinstance(league_group, list) else [league_group]):
                    if (entry.get("team") or {}).get("id") == team_id:
                        rank = entry.get("rank", 10)
                        total = 20
                        return max(0.7, min(1.3, 1.0 + (total - rank) / (total * 2.5)))
    except Exception:
        pass
    return 1.0


def generate_full_predictions(
    home_team: str,
    away_team: str,
    expected_home_goals: float,
    expected_away_goals: float,
    home_win_prob: float,
    draw_prob: float,
    away_win_prob: float,
    is_live: bool = False,
    live_context: Optional[Dict[str, Any]] = None,
    h2h_data: Optional[List[Dict[str, Any]]] = None,
    standings: Optional[Any] = None,
    home_team_id: Optional[int] = None,
    away_team_id: Optional[int] = None,
    home_stats: Optional[Dict[str, Any]] = None,
    away_stats: Optional[Dict[str, Any]] = None,
    events: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Orchestrateur principal: génère des prédictions mathématiquement cohérentes.
    Utilise: market_validator, score_filter, btts_engine, over_under_engine,
             confidence_engine, momentum_engine, pressure_engine, conclusion_engine.
    Toutes les prédictions sont conditionnelles au score et à la minute actuels.
    """
    # ── Score et minute live ─────────────────────────────────────────────────
    home_goals = int((live_context or {}).get("home_goals", 0) or 0) if is_live else 0
    away_goals = int((live_context or {}).get("away_goals", 0) or 0) if is_live else 0
    minute = int((live_context or {}).get("minute", 0) or 0) if is_live else 0
    remaining_min = max(0, 90 - minute)
    remaining_frac = remaining_min / 90.0

    # ── xG de base ──────────────────────────────────────────────────────────
    lam_h = max(0.05, expected_home_goals)
    lam_a = max(0.05, expected_away_goals)

    # ── Correction H2H ──────────────────────────────────────────────────────
    if h2h_data:
        h2h_h, h2h_a = _h2h_goal_avg(h2h_data, home_team, away_team)
        if h2h_h > 0 or h2h_a > 0:
            # Blending 60% modèle forme / 40% moyenne H2H
            lam_h = lam_h * 0.6 + h2h_h * 0.4
            lam_a = lam_a * 0.6 + h2h_a * 0.4

    # ── Correction classement ────────────────────────────────────────────────
    if standings and home_team_id and away_team_id:
        rank_h = _standing_rank_factor(standings, home_team_id)
        rank_a = _standing_rank_factor(standings, away_team_id)
        lam_h = max(0.05, lam_h * rank_h)
        lam_a = max(0.05, lam_a * rank_a)
        elo_shift = (rank_h - rank_a) * 0.06
        home_win_prob = max(0.02, home_win_prob + elo_shift)
        away_win_prob = max(0.02, away_win_prob - elo_shift)

    # ── Moteurs contextuels ──────────────────────────────────────────────────
    _ev = events or []
    momentum_result = compute_momentum(
        home_stats or {}, away_stats or {}, _ev,
        home_goals, away_goals, minute
    )
    pressure_result = compute_pressure(home_stats or {}, away_stats or {})

    # ── xG RESTANTS (Poisson conditionnel) ───────────────────────────────────
    # Partir du score actuel, calculer seulement les buts restants
    mom_val = momentum_result.get("value", 0.0)
    pressure_unknown = pressure_result.get("unknown", True)

    if is_live and minute > 0:
        red_shift = (live_context or {}).get("red_card_shift", 0.0) or 0.0
        mom_h = 1.0 + max(-0.35, min(0.35, mom_val * 0.5))
        mom_a = 1.0 - max(-0.35, min(0.35, mom_val * 0.5))

        if not pressure_unknown:
            ph = pressure_result.get("home_index", 50) or 50
            pa = pressure_result.get("away_index", 50) or 50
            press_ratio = ph / (ph + pa + 1e-9)
        else:
            press_ratio = 0.5

        rem_lam_h = max(0.01, lam_h * remaining_frac * mom_h * (0.8 + press_ratio * 0.4))
        rem_lam_a = max(0.01, lam_a * remaining_frac * mom_a * (1.2 - press_ratio * 0.4))

        if red_shift < 0:
            rem_lam_a = max(0.01, rem_lam_a * 0.60)
        elif red_shift > 0:
            rem_lam_h = max(0.01, rem_lam_h * 0.60)

        # 1X2 conditionnel au score actuel
        score_diff = home_goals - away_goals
        time_cert = min(0.92, minute / 90.0)
        if score_diff > 0:
            boost = min(0.50, score_diff * 0.14 * (1 + time_cert))
            home_win_prob = min(0.97, home_win_prob + boost)
            draw_prob = max(0.01, draw_prob * (1 - time_cert * 0.75))
            away_win_prob = max(0.01, 1.0 - home_win_prob - draw_prob)
        elif score_diff < 0:
            boost = min(0.50, abs(score_diff) * 0.14 * (1 + time_cert))
            away_win_prob = min(0.97, away_win_prob + boost)
            draw_prob = max(0.01, draw_prob * (1 - time_cert * 0.75))
            home_win_prob = max(0.01, 1.0 - away_win_prob - draw_prob)
        else:
            draw_boost = min(0.38, time_cert * 0.42)
            draw_prob = min(0.62, draw_prob + draw_boost)
            sides = home_win_prob + away_win_prob + 1e-9
            home_win_prob = (1.0 - draw_prob) * home_win_prob / sides
            away_win_prob = (1.0 - draw_prob) * away_win_prob / sides
    else:
        rem_lam_h = lam_h
        rem_lam_a = lam_a

    # ── Normaliser 1X2 ──────────────────────────────────────────────────────
    _t = home_win_prob + draw_prob + away_win_prob
    if _t > 0:
        home_win_prob /= _t
        draw_prob /= _t
        away_win_prob /= _t

    # ── CONFIANCE GLOBALE (calculée avant tous les marchés) ──────────────────
    has_live_stats = bool(home_stats or away_stats)
    confidence_global = compute_global_confidence(
        home_win_prob, draw_prob, away_win_prob,
        is_live=is_live,
        minute=minute,
        has_live_stats=has_live_stats,
        has_form_data=True,
        has_h2h=bool(h2h_data),
        data_quality_score=1.0 if has_live_stats else 0.7,
    )

    def _conf(prob: float):
        return uniform_confidence_for_market(prob, confidence_global)

    # ── 1X2 ─────────────────────────────────────────────────────────────────
    result_preds = [
        {"label": f"Victoire {home_team}", "key": "1", "prob": home_win_prob, "confidence": _conf(home_win_prob)},
        {"label": "Match nul",             "key": "X", "prob": draw_prob,     "confidence": _conf(draw_prob)},
        {"label": f"Victoire {away_team}", "key": "2", "prob": away_win_prob, "confidence": _conf(away_win_prob)},
    ]

    # ── OVER/UNDER (moteur conditionnel) ─────────────────────────────────────
    ou_markets = compute_over_under(
        home_goals, away_goals, rem_lam_h, rem_lam_a,
        thresholds=[0.5, 1.5, 2.5, 3.5, 4.5],
        is_live=is_live,
    )
    goals_preds = []
    for th in [0.5, 1.5, 2.5, 3.5]:
        key = str(th).replace(".", "")
        ov = ou_markets.get(f"over_{key}", {})
        un = ou_markets.get(f"under_{key}", {})
        ov_p = ov.get("prob", 0.0)
        un_p = un.get("prob", 0.0)
        locked = ov.get("locked", False)
        goals_preds.append({
            "threshold": th,
            "over_prob": ov_p,
            "under_prob": un_p,
            "over_confidence": (("verrouillé", "🔒", "#aaaaaa") if locked and ov_p == 1.0
                                else ("verrouillé", "🔒", "#555555") if locked and ov_p == 0.0
                                else _conf(ov_p)),
            "under_confidence": (("verrouillé", "🔒", "#aaaaaa") if locked and un_p == 1.0
                                 else ("verrouillé", "🔒", "#555555") if locked and un_p == 0.0
                                 else _conf(un_p)),
            "locked": locked,
            "reason": ov.get("reason", ""),
        })

    # ── BTTS (moteur conditionnel) ────────────────────────────────────────────
    btts_result = compute_btts(home_goals, away_goals, rem_lam_h, rem_lam_a, is_live)
    btts_yes = btts_result["yes_prob"]
    btts_no  = btts_result["no_prob"]
    btts_locked = btts_result.get("locked", False)
    btts_preds = {
        "yes_prob": btts_yes,
        "no_prob":  btts_no,
        "yes_confidence": (("verrouillé", "🔒", "#aaaaaa") if btts_locked else _conf(btts_yes)),
        "no_confidence":  (("verrouillé", "🔒", "#555555") if btts_locked else _conf(btts_no)),
        "locked": btts_locked,
        "reason": btts_result.get("reason", ""),
    }

    # ── BUTS PAR EQUIPE ───────────────────────────────────────────────────────
    # Buts restants à marquer conditionnels
    home_remaining_need_05 = max(0, 1 - home_goals) if is_live else 1
    away_remaining_need_05 = max(0, 1 - away_goals) if is_live else 1
    team_goals = {
        "home": {
            "name": home_team,
            "expected": round(rem_lam_h, 2),
            "already_scored": home_goals,
            "over_05": 1.0 if home_goals >= 1 else (1.0 - math.exp(-rem_lam_h)),
            "over_15": 1.0 if home_goals >= 2 else poisson_team_over(rem_lam_h, max(0, 2 - home_goals - 0.5)),
            "under_25": 0.0 if home_goals >= 3 else (1.0 - poisson_team_over(rem_lam_h, max(0, 3 - home_goals - 0.5))),
        },
        "away": {
            "name": away_team,
            "expected": round(rem_lam_a, 2),
            "already_scored": away_goals,
            "over_05": 1.0 if away_goals >= 1 else (1.0 - math.exp(-rem_lam_a)),
            "over_15": 1.0 if away_goals >= 2 else poisson_team_over(rem_lam_a, max(0, 2 - away_goals - 0.5)),
            "under_25": 0.0 if away_goals >= 3 else (1.0 - poisson_team_over(rem_lam_a, max(0, 3 - away_goals - 0.5))),
        },
    }

    # ── MI-TEMPS ──────────────────────────────────────────────────────────────
    if is_live and minute >= 45:
        lam_h_ht = rem_lam_h * 0.5
        lam_a_ht = rem_lam_a * 0.5
    else:
        lam_h_ht = lam_h * 0.45
        lam_a_ht = lam_a * 0.45
    halftime = {
        "home_scores_first": poisson_team_over(lam_h_ht, 0.5),
        "away_scores_first": poisson_team_over(lam_a_ht, 0.5),
        "home_scores_second": poisson_team_over(lam_h * 0.55, 0.5),
        "away_scores_second": poisson_team_over(lam_a * 0.55, 0.5),
        "over_05_ht": poisson_over(lam_h_ht, lam_a_ht, 0.5),
        "btts_ht": poisson_btts(lam_h_ht, lam_a_ht),
    }

    # ── CORNERS ───────────────────────────────────────────────────────────────
    def _istat(stats, *keys):
        for k in keys:
            v = (stats or {}).get(k)
            if v is not None:
                try: return int(str(v).replace("%","").strip())
                except: pass
        return None

    h_corn = _istat(home_stats, "Corner Kicks", "Corners") or 0
    a_corn = _istat(away_stats, "Corner Kicks", "Corners") or 0
    corners_done = h_corn + a_corn
    if is_live and minute > 0 and corners_done > 0:
        rate = corners_done / minute
        total_exp_corners = round(rate * 90, 1)
        proj_source = "live"
    else:
        total_exp_corners = round(max(6.0, min(16.0, 10.5 * (rem_lam_h + rem_lam_a) / 2.2)), 1)
        proj_source = "future"
    rem_corn = max(0.0, total_exp_corners - corners_done)
    corners = {
        "expected_total": total_exp_corners,
        "corners_done": corners_done,
        "proj_source": proj_source,
        "over_75":  _corners_over_prob(rem_corn, max(0, 7.5 - corners_done)),
        "over_85":  _corners_over_prob(rem_corn, max(0, 8.5 - corners_done)),
        "over_95":  _corners_over_prob(rem_corn, max(0, 9.5 - corners_done)),
        "over_105": _corners_over_prob(rem_corn, max(0, 10.5 - corners_done)),
        "under_85":  1.0 - _corners_over_prob(rem_corn, max(0, 8.5 - corners_done)),
        "under_95":  1.0 - _corners_over_prob(rem_corn, max(0, 9.5 - corners_done)),
        "under_105": 1.0 - _corners_over_prob(rem_corn, max(0, 10.5 - corners_done)),
    }

    # ── CARTONS ───────────────────────────────────────────────────────────────
    h_yel = _istat(home_stats, "Yellow Cards") or 0
    a_yel = _istat(away_stats, "Yellow Cards") or 0
    h_red = _istat(home_stats, "Red Cards") or 0
    a_red = _istat(away_stats, "Red Cards") or 0
    cards_done = h_yel + a_yel + h_red + a_red
    match_intensity = abs(home_win_prob - away_win_prob)
    if is_live and minute > 0 and cards_done > 0:
        exp_cards = round(cards_done / minute * 90, 1)
    else:
        exp_cards = round(max(2.0, min(7.0, 3.8 + match_intensity * 1.5)), 1)
    rem_cards = max(0.0, exp_cards - cards_done)
    cards = {
        "expected_total": exp_cards,
        "cards_done": cards_done,
        "over_15": _corners_over_prob(rem_cards, max(0, 1.5 - cards_done)),
        "over_25": _corners_over_prob(rem_cards, max(0, 2.5 - cards_done)),
        "over_35": _corners_over_prob(rem_cards, max(0, 3.5 - cards_done)),
        "over_45": _corners_over_prob(rem_cards, max(0, 4.5 - cards_done)),
        "under_25": 1.0 - _corners_over_prob(rem_cards, max(0, 2.5 - cards_done)),
        "under_35": 1.0 - _corners_over_prob(rem_cards, max(0, 3.5 - cards_done)),
        "under_45": 1.0 - _corners_over_prob(rem_cards, max(0, 4.5 - cards_done)),
    }

    # ── PROCHAIN BUT ──────────────────────────────────────────────────────────
    total_rem = rem_lam_h + rem_lam_a
    p_h_next = rem_lam_h / total_rem if total_rem > 0 else 0.5
    p_a_next = rem_lam_a / total_rem if total_rem > 0 else 0.5
    p_no = math.exp(-min(total_rem, 3.5))
    _sum = p_h_next + p_a_next + p_no
    p_h_next /= _sum; p_a_next /= _sum; p_no /= _sum
    next_goal = {
        "home_prob": p_h_next,
        "away_prob": p_a_next,
        "no_goal_prob": p_no,
        "home_name": home_team,
        "away_name": away_team,
        "home_confidence": _conf(p_h_next),
        "away_confidence": _conf(p_a_next),
    }

    # ── SCORES PROBABLES (filtrés) ────────────────────────────────────────────
    from ai_engine.poisson_engine import score_matrix_live
    sm = score_matrix_live(rem_lam_h, rem_lam_a, home_goals, away_goals, max_goals=7)
    top_scores = top_possible_scores(sm, home_goals, away_goals, count=5)

    # ── CONCLUSION ────────────────────────────────────────────────────────────
    conclusion_text = generate_conclusion(
        home_name=home_team, away_name=away_team,
        home_goals=home_goals, away_goals=away_goals,
        minute=minute,
        home_win_prob=home_win_prob, draw_prob=draw_prob, away_win_prob=away_win_prob,
        btts_result=btts_result,
        over_under=ou_markets,
        momentum=momentum_result,
        is_live=is_live,
        home_xg=rem_lam_h, away_xg=rem_lam_a,
        confidence=confidence_global,
    )

    return {
        "result": result_preds,
        "goals": goals_preds,
        "btts": btts_preds,
        "team_goals": team_goals,
        "halftime": halftime,
        "corners": corners,
        "cards": cards,
        "next_goal": next_goal,
        "top_scores": top_scores,
        "confidence_overall": confidence_global,
        "momentum": momentum_result,
        "pressure": pressure_result,
        "conclusion": conclusion_text,
        "expected_home_goals": round(rem_lam_h, 2),
        "expected_away_goals": round(rem_lam_a, 2),
        "home_goals": home_goals,
        "away_goals": away_goals,
        "minute": minute,
        "is_live": is_live,
    }


def _corners_over_prob(expected: float, threshold: float) -> float:
    """Approximation Poisson pour corners/cartons."""
    return max(0.0, min(1.0, poisson_over(expected * 0.6, expected * 0.4, threshold)))


def render_predictions_section(predictions: Dict[str, Any], home: str, away: str):
    """Affiche les prédictions dans Streamlit — version contextuelle live."""
    import streamlit as st

    if not predictions:
        st.info("Prédictions non disponibles.")
        return

    is_live = predictions.get("is_live", False)
    home_goals = predictions.get("home_goals", 0)
    away_goals = predictions.get("away_goals", 0)
    minute = predictions.get("minute", 0)

    st.markdown("## 🎯 Prédictions Avancées")

    # ── Header contextuel ────────────────────────────────────────────────────
    conf = predictions.get("confidence_overall", {})
    col_conf, col_ctx = st.columns([2, 1])
    with col_conf:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:8px;'>"
            f"<span style='font-size:1.4rem'>{conf.get('icon','🎯')}</span>"
            f"<div><b>Confiance globale:</b> "
            f"<span style='color:{conf.get('color','#ccc')};font-weight:700'>"
            f"{conf.get('label','').upper()} ({conf.get('score',0)}%)</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_ctx:
        if is_live:
            st.markdown(
                f"<div style='text-align:right;'>"
                f"<span style='background:#e74c3c;color:#fff;border-radius:6px;"
                f"padding:3px 10px;font-weight:700;font-size:0.85rem;'>🔴 LIVE {minute}'</span><br>"
                f"<span style='font-size:1.1rem;font-weight:700;'>{home_goals} – {away_goals}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Conclusion ────────────────────────────────────────────────────────────
    conclusion = predictions.get("conclusion", "")
    if conclusion:
        with st.expander("📋 Analyse & Conclusion", expanded=is_live):
            st.markdown(conclusion)

    # ── Scores probables (filtrés) ────────────────────────────────────────────
    top_scores_list = predictions.get("top_scores", [])
    if top_scores_list:
        st.markdown("#### 🔢 Scores finaux probables")
        score_cols = st.columns(len(top_scores_list))
        for i, sc in enumerate(top_scores_list):
            with score_cols[i]:
                is_current = sc.get("is_current", False)
                border = "#f39c12" if is_current else "#444"
                badge = " 🔴" if is_current else ""
                st.markdown(
                    f"<div style='text-align:center;border:2px solid {border};"
                    f"border-radius:8px;padding:8px 4px;'>"
                    f"<div style='font-size:1.3rem;font-weight:800;'>{sc['score']}{badge}</div>"
                    f"<div style='font-size:0.75rem;color:#aaa;'>{sc['probability']}%</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    tabs = st.tabs(["1X2", "Buts", "BTTS", "Équipes", "Mi-temps", "Corners", "Cartons", "Prochain but"])

    # === TAB 1X2 ===
    with tabs[0]:
        st.markdown("### ⚽ Résultat du match")
        if is_live:
            st.caption(f"Score actuel: {home} **{home_goals}** – **{away_goals}** {away} · {minute}'")
        result = predictions.get("result", [])
        cols = st.columns(3)
        for i, pred in enumerate(result):
            with cols[i % 3]:
                prob = pred["prob"]
                conf_label, conf_icon, conf_color = pred["confidence"]
                _render_pred_card(pred["label"], prob, conf_label, conf_icon, conf_color, pred["key"])

    # === TAB BUTS ===
    with tabs[1]:
        st.markdown("### 📊 Over / Under Buts")
        lam_h = predictions.get("expected_home_goals", 0)
        lam_a = predictions.get("expected_away_goals", 0)
        total_done = home_goals + away_goals
        if is_live:
            st.caption(f"Score: **{total_done}** buts marqués · xG restants: {home} **{lam_h}** – **{lam_a}** {away}")
        else:
            st.caption(f"xG attendus: {home} **{lam_h}** – **{lam_a}** {away}")
        goals = predictions.get("goals", [])
        for g in goals:
            th = g["threshold"]
            locked = g.get("locked", False)
            reason = g.get("reason", "")
            c1, c2 = st.columns(2)
            with c1:
                if locked and g["over_prob"] == 1.0:
                    _render_realized_card(f"Over {th}", size="normal")
                else:
                    cl, ci, cc = g["over_confidence"]
                    _render_pred_card(f"Over {th}", g["over_prob"], cl, ci, cc)
            with c2:
                if locked and g["under_prob"] == 1.0:
                    _render_realized_card(f"Under {th}", size="normal")
                elif locked and g["under_prob"] == 0.0:
                    _render_pred_card(f"Under {th}", 0.0, "Impossible", "🚫", "#666666")
                else:
                    cl, ci, cc = g["under_confidence"]
                    _render_pred_card(f"Under {th}", g["under_prob"], cl, ci, cc)
            if locked and reason:
                st.caption(f"✓ {reason}")

    # === TAB BTTS ===
    with tabs[2]:
        st.markdown("### 🥅 Les deux équipes marquent (BTTS)")
        btts = predictions.get("btts", {})
        btts_locked = btts.get("locked", False)
        btts_reason = btts.get("reason", "")
        c1, c2 = st.columns(2)
        with c1:
            if btts_locked and btts.get("yes_prob", 0) == 1.0:
                _render_realized_card("GG Oui", size="normal")
            else:
                cl, ci, cc = btts.get("yes_confidence", ("faible", "🔴", "#ff4444"))
                _render_pred_card("GG Oui", btts.get("yes_prob", 0), cl, ci, cc)
        with c2:
            if btts_locked and btts.get("no_prob", 0) == 0.0:
                _render_pred_card("GG Non", 0.0, "Impossible", "🚫", "#666666")
            else:
                cl, ci, cc = btts.get("no_confidence", ("faible", "🔴", "#ff4444"))
                _render_pred_card("GG Non", btts.get("no_prob", 0), cl, ci, cc)
        if btts_locked and btts_reason:
            st.caption(f"✓ {btts_reason}")

    # === TAB EQUIPES ===
    with tabs[3]:
        st.markdown("### ⚽ Buts par équipe")
        tg = predictions.get("team_goals", {})
        for side_key, side_label in [("home", home), ("away", away)]:
            side = tg.get(side_key, {})
            if side:
                already = side.get("already_scored", 0)
                suffix = f" · {already} but(s) marqué(s)" if is_live and already > 0 else ""
                st.markdown(f"**{side_label}** (xG restants: {side.get('expected', 0)}){suffix}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    v = side.get("over_05", 0)
                    cl, ci, cc = get_confidence(v)
                    lbl = "Plus de 0.5 🔒" if v == 1.0 else "Plus de 0.5"
                    _render_pred_card(lbl, v, cl, ci, cc, size="sm")
                with c2:
                    v = side.get("over_15", 0)
                    cl, ci, cc = get_confidence(v)
                    lbl = "Plus de 1.5 🔒" if v == 1.0 else "Plus de 1.5"
                    _render_pred_card(lbl, v, cl, ci, cc, size="sm")
                with c3:
                    v = side.get("under_25", 0)
                    cl, ci, cc = get_confidence(v)
                    _render_pred_card("Moins de 2.5", v, cl, ci, cc, size="sm")
                st.markdown("---")

    # === TAB MI-TEMPS ===
    with tabs[4]:
        st.markdown("### ⏱️ Mi-temps")
        ht = predictions.get("halftime", {})
        c1, c2 = st.columns(2)
        with c1:
            if ht.get("home_ht1_realized"):
                _render_realized_card(f"{home} marque 1ère MT")
            else:
                v = ht.get("home_scores_first", 0)
                cl, ci, cc = get_confidence(v)
                _render_pred_card(f"{home} marque 1ère MT", v, cl, ci, cc, size="sm")
            if ht.get("home_ht2_realized"):
                _render_realized_card(f"{home} marque 2ème MT")
            else:
                v2 = ht.get("home_scores_second", 0)
                cl2, ci2, cc2 = get_confidence(v2)
                _render_pred_card(f"{home} marque 2ème MT", v2, cl2, ci2, cc2, size="sm")
        with c2:
            if ht.get("away_ht1_realized"):
                _render_realized_card(f"{away} marque 1ère MT")
            else:
                v = ht.get("away_scores_first", 0)
                cl, ci, cc = get_confidence(v)
                _render_pred_card(f"{away} marque 1ère MT", v, cl, ci, cc, size="sm")
            if ht.get("away_ht2_realized"):
                _render_realized_card(f"{away} marque 2ème MT")
            else:
                v2 = ht.get("away_scores_second", 0)
                cl2, ci2, cc2 = get_confidence(v2)
                _render_pred_card(f"{away} marque 2ème MT", v2, cl2, ci2, cc2, size="sm")
        st.markdown("---")
        v = ht.get("btts_ht", 0)
        cl, ci, cc = get_confidence(v)
        _render_pred_card("BTTS 1ère MT", v, cl, ci, cc)

    # === TAB CORNERS ===
    with tabs[5]:
        corners = predictions.get("corners", {})
        st.markdown("### 🔄 Corners")
        done_c = corners.get("corners_done", 0)
        src = corners.get("proj_source", "future")
        info = f" · Déjà joués: **{done_c}** (rythme live)" if src == "live" and done_c > 0 else ""
        st.caption(f"Corners projetés sur 90 min: **{corners.get('expected_total', 0)}**{info}")
        pairs = [
            ("Over 7.5", corners.get("over_75", 0)),
            ("Over 8.5", corners.get("over_85", 0)),
            ("Over 9.5", corners.get("over_95", 0)),
            ("Over 10.5", corners.get("over_105", 0)),
            ("Under 8.5", corners.get("under_85", 0)),
            ("Under 9.5", corners.get("under_95", 0)),
            ("Under 10.5", corners.get("under_105", 0)),
        ]
        cols = st.columns(3)
        for i, (label, prob) in enumerate(pairs):
            with cols[i % 3]:
                cl, ci, cc = get_confidence(prob)
                _render_pred_card(label, prob, cl, ci, cc, size="sm")

    # === TAB CARTONS ===
    with tabs[6]:
        cards = predictions.get("cards", {})
        st.markdown("### 🟨 Cartons")
        done_k = cards.get("cards_done", 0)
        info_k = f" · Déjà distribués: **{done_k}**" if done_k > 0 else ""
        st.caption(f"Cartons projetés sur 90 min: **{cards.get('expected_total', 0)}**{info_k}")
        pairs = [
            ("Over 1.5", cards.get("over_15", 0)),
            ("Over 2.5", cards.get("over_25", 0)),
            ("Over 3.5", cards.get("over_35", 0)),
            ("Over 4.5", cards.get("over_45", 0)),
            ("Under 2.5", cards.get("under_25", 0)),
            ("Under 3.5", cards.get("under_35", 0)),
            ("Under 4.5", cards.get("under_45", 0)),
        ]
        cols = st.columns(3)
        for i, (label, prob) in enumerate(pairs):
            with cols[i % 3]:
                cl, ci, cc = get_confidence(prob)
                _render_pred_card(label, prob, cl, ci, cc, size="sm")

    # === TAB PROCHAIN BUT ===
    with tabs[7]:
        ng = predictions.get("next_goal", {})
        st.markdown("### 🎯 Prochain but")
        mom = predictions.get("momentum", {})
        if mom:
            if mom.get("data_available"):
                hp = mom.get("home_pct", 50)
                ap = mom.get("away_pct", 50)
                st.caption(
                    f"Momentum: {mom.get('label','—')} · "
                    f"{home}: {hp}% / {away}: {ap}%"
                )
            else:
                st.caption(f"⚠️ {mom.get('label', 'Données live insuffisantes')}")
        c1, c2, c3 = st.columns(3)
        with c1:
            cl, ci, cc = ng.get("home_confidence", ("faible", "🔴", "#ff4444"))
            _render_pred_card(ng.get("home_name", home), ng.get("home_prob", 0), cl, ci, cc)
        with c2:
            v = ng.get("no_goal_prob", 0)
            cl, ci, cc = get_confidence(v)
            _render_pred_card("Aucun but", v, cl, ci, cc)
        with c3:
            cl, ci, cc = ng.get("away_confidence", ("faible", "🔴", "#ff4444"))
            _render_pred_card(ng.get("away_name", away), ng.get("away_prob", 0), cl, ci, cc)


def _render_realized_card(label: str, size: str = "sm"):
    """Affiche une carte de marché déjà réalisé (événement confirmé)."""
    import streamlit as st
    font_size = "0.75rem" if size == "sm" else "0.85rem"
    st.markdown(
        f"<div style='background:rgba(0,200,100,0.10);border:2px solid #00c864;"
        f"border-radius:10px;padding:10px 12px;margin-bottom:8px;'>"
        f"<div style='font-size:{font_size};color:#aaa;line-height:1.2;margin-bottom:4px;'>{label}</div>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#00c864;'>✓ Réalisé</div>"
        f"<div style='width:100%;height:4px;background:#00c86444;border-radius:2px;margin-top:6px;'>"
        f"<div style='width:100%;height:4px;background:#00c864;border-radius:2px;'></div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def _render_pred_card(label: str, prob: float, conf_label: str, conf_icon: str, conf_color: str, key_badge: str = "", size: str = "normal"):
    """Affiche une carte de prédiction."""
    import streamlit as st

    pct = round(prob * 100)
    font_size = "0.75rem" if size == "sm" else "0.85rem"
    pct_size = "1.4rem" if size == "sm" else "1.8rem"
    bar_width = max(5, pct)

    badge_html = (
        f"<span style='background:{conf_color};color:#000;border-radius:4px;"
        f"padding:1px 6px;font-size:0.7rem;font-weight:700;'>{key_badge}</span>"
        if key_badge else ""
    )

    html = (
        f"<div style='background:var(--bg-card,#1a1a2e);"
        f"border:1px solid {conf_color}55;border-radius:10px;padding:10px 12px;"
        f"margin-bottom:8px;backdrop-filter:blur(4px);'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;'>"
        f"<span style='font-size:{font_size};color:var(--text-secondary,#ccc);line-height:1.2;'>{label}</span>"
        f"{badge_html}"
        f"</div>"
        f"<div style='font-size:{pct_size};font-weight:800;color:{conf_color};line-height:1;'>{pct}%</div>"
        f"<div style='width:100%;height:4px;background:rgba(128,128,128,0.2);"
        f"border-radius:2px;margin-top:6px;overflow:hidden;'>"
        f"<div style='width:{bar_width}%;height:100%;background:{conf_color};"
        f"border-radius:2px;transition:width 0.5s;'></div>"
        f"</div>"
        f"<div style='font-size:0.68rem;color:{conf_color};margin-top:4px;'>{conf_icon} {conf_label.upper()}</div>"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
