"""
Predictions Engine - Prédictions avancées pour matchs football
Génère des prédictions enrichies: Over/Under, BTTS, Corners, Cartons, etc.
"""
from typing import Dict, Any, List, Optional, Tuple
import math


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
) -> Dict[str, Any]:
    """
    Génère l'ensemble des prédictions enrichies pour un match.
    
    Returns dict avec sections:
    - result: 1X2
    - goals: Over/Under 0.5..3.5
    - btts: Both Teams To Score
    - team_goals: buts par équipe
    - halftime: mi-temps
    - corners: over/under corners (estimé)
    - cards: over/under cartons (estimé)
    - next_goal: prochain buteur
    - confidence_overall: score confiance global
    """
    lam_h = max(0.1, expected_home_goals)
    lam_a = max(0.1, expected_away_goals)

    # Ajustement live si contexte disponible
    if is_live and live_context:
        minute = live_context.get("minute", 0) or 0
        home_score = live_context.get("home_score", 0) or 0
        away_score = live_context.get("away_score", 0) or 0

        if minute > 0:
            remaining = max(5, 90 - minute) / 90.0
            lam_h = lam_h * remaining
            lam_a = lam_a * remaining

            # Recalculer home_win/draw/away_win basé sur score actuel + proba restante
            if home_score > away_score:
                home_win_prob = min(0.92, home_win_prob * 1.3)
                draw_prob = draw_prob * 0.6
                away_win_prob = max(0.02, 1.0 - home_win_prob - draw_prob)
            elif away_score > home_score:
                away_win_prob = min(0.92, away_win_prob * 1.3)
                draw_prob = draw_prob * 0.6
                home_win_prob = max(0.02, 1.0 - away_win_prob - draw_prob)
            else:
                draw_prob = min(0.55, draw_prob * 1.2)
                home_win_prob = (1.0 - draw_prob) * home_win_prob / (home_win_prob + away_win_prob + 1e-9)
                away_win_prob = 1.0 - home_win_prob - draw_prob

    # Normaliser 1X2
    total_1x2 = home_win_prob + draw_prob + away_win_prob
    if total_1x2 > 0:
        home_win_prob /= total_1x2
        draw_prob /= total_1x2
        away_win_prob /= total_1x2

    # ====== SECTION 1X2 ======
    result_preds = [
        {"label": f"Victoire {home_team}", "key": "1", "prob": home_win_prob, "confidence": get_confidence(home_win_prob)},
        {"label": "Match nul", "key": "X", "prob": draw_prob, "confidence": get_confidence(draw_prob)},
        {"label": f"Victoire {away_team}", "key": "2", "prob": away_win_prob, "confidence": get_confidence(away_win_prob)},
    ]

    # ====== SECTION OVER/UNDER BUTS ======
    goals_preds = []
    for threshold in [0.5, 1.5, 2.5, 3.5]:
        over_p = poisson_over(lam_h, lam_a, threshold)
        under_p = 1.0 - over_p
        goals_preds.append({
            "threshold": threshold,
            "over_prob": over_p,
            "under_prob": under_p,
            "over_confidence": get_confidence(over_p),
            "under_confidence": get_confidence(under_p),
        })

    # ====== BTTS ======
    btts_yes = poisson_btts(lam_h, lam_a)
    btts_no = 1.0 - btts_yes
    btts_preds = {
        "yes_prob": btts_yes,
        "no_prob": btts_no,
        "yes_confidence": get_confidence(btts_yes),
        "no_confidence": get_confidence(btts_no),
    }

    # ====== BUTS PAR EQUIPE ======
    team_goals = {
        "home": {
            "name": home_team,
            "expected": round(lam_h, 2),
            "over_05": poisson_team_over(lam_h, 0.5),
            "over_15": poisson_team_over(lam_h, 1.5),
            "under_25": 1.0 - poisson_team_over(lam_h, 2.5),
        },
        "away": {
            "name": away_team,
            "expected": round(lam_a, 2),
            "over_05": poisson_team_over(lam_a, 0.5),
            "over_15": poisson_team_over(lam_a, 1.5),
            "under_25": 1.0 - poisson_team_over(lam_a, 2.5),
        },
    }

    # ====== MI-TEMPS ======
    # Estimation: ~45% des buts en 1ère MT
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

    # ====== CORNERS (estimation statistique) ======
    # Moyenne UEFA: ~10.4 corners/match
    # Home advantage: légèrement plus de corners
    base_corners = 10.5
    expected_corners_home = base_corners * (lam_h / (lam_h + lam_a + 1e-9)) * 1.05
    expected_corners_away = base_corners * (lam_a / (lam_h + lam_a + 1e-9)) * 0.95
    total_expected_corners = expected_corners_home + expected_corners_away

    corners = {
        "expected_total": round(total_expected_corners, 1),
        "over_85": _corners_over_prob(total_expected_corners, 8.5),
        "over_95": _corners_over_prob(total_expected_corners, 9.5),
        "over_105": _corners_over_prob(total_expected_corners, 10.5),
        "under_95": 1.0 - _corners_over_prob(total_expected_corners, 9.5),
        "under_105": 1.0 - _corners_over_prob(total_expected_corners, 10.5),
    }

    # ====== CARTONS (estimation statistique) ======
    # Moyenne: ~3.5 cartons jaunes/match
    base_cards = 3.8
    match_intensity = abs(home_win_prob - away_win_prob)
    expected_cards = base_cards + (match_intensity * 1.5)

    cards = {
        "expected_total": round(expected_cards, 1),
        "over_25": _corners_over_prob(expected_cards, 2.5),
        "over_35": _corners_over_prob(expected_cards, 3.5),
        "over_45": _corners_over_prob(expected_cards, 4.5),
        "under_35": 1.0 - _corners_over_prob(expected_cards, 3.5),
        "under_45": 1.0 - _corners_over_prob(expected_cards, 4.5),
    }

    # ====== PROCHAIN BUT ======
    # Basé sur les lambdas restantes
    total_lambda = lam_h + lam_a
    if total_lambda > 0:
        p_home_next = lam_h / total_lambda
        p_away_next = lam_a / total_lambda
    else:
        p_home_next = 0.5
        p_away_next = 0.5

    # P(aucun but) = e^(-total_lambda) mais simplifié
    p_no_goal = math.exp(-total_lambda * 0.5)  # probabilité relative
    total_ng = p_home_next + p_away_next + p_no_goal
    p_home_next /= total_ng
    p_away_next /= total_ng
    p_no_goal /= total_ng

    next_goal = {
        "home_prob": p_home_next,
        "away_prob": p_away_next,
        "no_goal_prob": p_no_goal,
        "home_name": home_team,
        "away_name": away_team,
        "home_confidence": get_confidence(p_home_next),
        "away_confidence": get_confidence(p_away_next),
    }

    # ====== CONFIDENCE GLOBAL ======
    max_prob = max(home_win_prob, draw_prob, away_win_prob)
    confidence_label, confidence_icon, confidence_color = get_confidence(max_prob)

    return {
        "result": result_preds,
        "goals": goals_preds,
        "btts": btts_preds,
        "team_goals": team_goals,
        "halftime": halftime,
        "corners": corners,
        "cards": cards,
        "next_goal": next_goal,
        "confidence_overall": {
            "label": confidence_label,
            "icon": confidence_icon,
            "color": confidence_color,
            "score": round(max_prob * 100),
        },
        "expected_home_goals": round(lam_h, 2),
        "expected_away_goals": round(lam_a, 2),
        "is_live": is_live,
    }


def _corners_over_prob(expected: float, threshold: float) -> float:
    """Approximation Poisson pour corners/cartons."""
    return max(0.0, min(1.0, poisson_over(expected * 0.6, expected * 0.4, threshold)))


def render_predictions_section(predictions: Dict[str, Any], home: str, away: str):
    """
    Affiche les prédictions dans Streamlit.
    Appeler cette fonction depuis analysis_dashboard.py
    """
    import streamlit as st

    if not predictions:
        st.info("Prédictions non disponibles.")
        return

    st.markdown("## 🎯 Prédictions Avancées")

    conf = predictions.get("confidence_overall", {})
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:16px;'>"
        f"<span style='font-size:1.5rem'>{conf.get('icon','')}</span>"
        f"<div><b>Confiance globale:</b> "
        f"<span style='color:{conf.get('color','#ccc')};font-weight:700'>{conf.get('label','').upper()} ({conf.get('score',0)}%)</span></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["1X2", "Buts", "BTTS", "Équipes", "Mi-temps", "Corners", "Cartons", "Prochain but"])

    # === TAB 1X2 ===
    with tabs[0]:
        st.markdown("### ⚽ Résultat du match")
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
        goals = predictions.get("goals", [])
        lam_h = predictions.get("expected_home_goals", 0)
        lam_a = predictions.get("expected_away_goals", 0)
        st.caption(f"Buts attendus: {home} **{lam_h}** - **{lam_a}** {away}")
        for g in goals:
            th = g["threshold"]
            c1, c2 = st.columns(2)
            with c1:
                cl, ci, cc = g["over_confidence"]
                _render_pred_card(f"Over {th}", g["over_prob"], cl, ci, cc)
            with c2:
                cl, ci, cc = g["under_confidence"]
                _render_pred_card(f"Under {th}", g["under_prob"], cl, ci, cc)

    # === TAB BTTS ===
    with tabs[2]:
        st.markdown("### 🥅 Les deux équipes marquent (BTTS)")
        btts = predictions.get("btts", {})
        c1, c2 = st.columns(2)
        with c1:
            cl, ci, cc = btts.get("yes_confidence", ("faible", "🔴", "#ff4444"))
            _render_pred_card("GG Oui", btts.get("yes_prob", 0), cl, ci, cc)
        with c2:
            cl, ci, cc = btts.get("no_confidence", ("faible", "🔴", "#ff4444"))
            _render_pred_card("GG Non", btts.get("no_prob", 0), cl, ci, cc)

    # === TAB EQUIPES ===
    with tabs[3]:
        st.markdown("### ⚽ Buts par équipe")
        tg = predictions.get("team_goals", {})
        for side_key, side_label in [("home", home), ("away", away)]:
            side = tg.get(side_key, {})
            if side:
                st.markdown(f"**{side_label}** (moy. attendus: {side.get('expected', 0)})")
                c1, c2, c3 = st.columns(3)
                with c1:
                    v = side.get("over_05", 0)
                    cl, ci, cc = get_confidence(v)
                    _render_pred_card("Plus de 0.5", v, cl, ci, cc, size="sm")
                with c2:
                    v = side.get("over_15", 0)
                    cl, ci, cc = get_confidence(v)
                    _render_pred_card("Plus de 1.5", v, cl, ci, cc, size="sm")
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
            v = ht.get("home_scores_first", 0)
            cl, ci, cc = get_confidence(v)
            _render_pred_card(f"{home} marque 1ère MT", v, cl, ci, cc, size="sm")
            v2 = ht.get("home_scores_second", 0)
            cl2, ci2, cc2 = get_confidence(v2)
            _render_pred_card(f"{home} marque 2ème MT", v2, cl2, ci2, cc2, size="sm")
        with c2:
            v = ht.get("away_scores_first", 0)
            cl, ci, cc = get_confidence(v)
            _render_pred_card(f"{away} marque 1ère MT", v, cl, ci, cc, size="sm")
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
        st.caption(f"Corners attendus: **{corners.get('expected_total', 0)}**")
        pairs = [
            ("Over 8.5", corners.get("over_85", 0)),
            ("Over 9.5", corners.get("over_95", 0)),
            ("Over 10.5", corners.get("over_105", 0)),
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
        st.caption(f"Cartons attendus: **{cards.get('expected_total', 0)}**")
        pairs = [
            ("Over 2.5", cards.get("over_25", 0)),
            ("Over 3.5", cards.get("over_35", 0)),
            ("Over 4.5", cards.get("over_45", 0)),
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
        f"<div style='background:linear-gradient(135deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02));"
        f"border:1px solid {conf_color}44;border-radius:10px;padding:10px 12px;"
        f"margin-bottom:8px;backdrop-filter:blur(4px);'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;'>"
        f"<span style='font-size:{font_size};color:#ccc;line-height:1.2;'>{label}</span>"
        f"{badge_html}"
        f"</div>"
        f"<div style='font-size:{pct_size};font-weight:800;color:{conf_color};line-height:1;'>{pct}%</div>"
        f"<div style='width:100%;height:4px;background:rgba(255,255,255,0.1);"
        f"border-radius:2px;margin-top:6px;overflow:hidden;'>"
        f"<div style='width:{bar_width}%;height:100%;background:{conf_color};"
        f"border-radius:2px;transition:width 0.5s;'></div>"
        f"</div>"
        f"<div style='font-size:0.68rem;color:{conf_color};margin-top:4px;'>{conf_icon} {conf_label.upper()}</div>"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
