import html as html_lib
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from ai_engine.bet_suggestion_engine import analyze_bet_opportunities
from ai_engine.form_analyzer import analyze_form
from ai_engine.live_context_engine import build_live_context
from ai_engine.smart_stats_fallback import estimate_missing_stats, mark_estimated
from ai_engine.prediction_fusion_engine import build_final_prediction
from ai_engine.consistency_validator import validate_and_fix, get_favorite
from ai_engine.predictions_engine import render_predictions_section
from services.football_api import FootballAPI


def _response(data: Dict[str, Any]) -> Any:
    if isinstance(data, dict):
        return data.get("response") or []
    return data or []


# ─────────────────────────────────────────────────────────────────────────────
# ENJEU DU MATCH
# ─────────────────────────────────────────────────────────────────────────────

def _detect_match_type(league_name: str, round_str: str) -> str:
    """Détecte le type de match : Championnat, Coupe, Ligue des Champions, Derby…"""
    ln = (league_name or "").lower()
    rn = (round_str or "").lower()
    if any(k in ln for k in ("champions league", "ligue des champions", "ucl")):
        return "⭐ Ligue des Champions UEFA"
    if any(k in ln for k in ("europa league", "conference league")):
        return "🌍 Coupe d'Europe"
    if any(k in ln for k in ("world cup", "coupe du monde")):
        return "🌍 Coupe du Monde"
    if any(k in ln for k in ("cup", "coupe", "fa cup", "dfb", "copa del")):
        return "🏆 Coupe nationale"
    if any(k in rn for k in ("final", "semi-final", "quarter")):
        return "🏆 Phase éliminatoire"
    return "📋 Championnat"


def _standing_label(row: Dict) -> str:
    if not row:
        return "—"
    rank  = row.get("rank", "—")
    pts   = row.get("points", "—")
    gd    = row.get("goalsDiff", "—")
    gd_str = f"+{gd}" if isinstance(gd, int) and gd > 0 else str(gd)
    return f"#{rank} · {pts} pts · diff {gd_str}"


def _analyse_stake(row: Dict, team_name: str) -> tuple:
    """
    Analyse l'enjeu d'une équipe selon son classement.
    Retourne (icone, label_enjeu, couleur, description).
    Logique : rang 1-4 = titre/Europe, 5-6 = Europa, zone relégation = danger.
    """
    if not row:
        return ("❓", "Enjeu inconnu", "#888888",
                "Données de classement non disponibles.",
                "—", 0, "—", 0, 0, 0, 0, 0)

    rank  = row.get("rank") or 99
    pts   = row.get("points") or 0
    played = (row.get("all") or {}).get("played") or 0
    wins  = (row.get("all") or {}).get("win") or 0
    draws = (row.get("all") or {}).get("draw") or 0
    losses= (row.get("all") or {}).get("lose") or 0
    gd    = row.get("goalsDiff") or 0

    # Forme récente (chaîne ex: "WWDLW")
    form_str = row.get("form") or ""
    recent = list(form_str[-5:]) if form_str else []
    recent_wins   = recent.count("W")
    recent_losses = recent.count("L")
    recent_draws  = recent.count("D")

    form_label = ""
    if len(recent) >= 3:
        if recent_wins >= 4:
            form_label = "🔥 En feu (série W)"
        elif recent_losses >= 3:
            form_label = "❄️ Série noire"
        elif recent_wins >= 2 and recent_losses == 0:
            form_label = "📈 Bonne dynamique"
        elif recent_draws >= 3:
            form_label = "🤝 Beaucoup de nuls"
        else:
            form_label = "↔️ Forme irrégulière"

    # Description des 5 derniers matchs
    form_detail = " ".join(
        f"<span style='color:{'#22c55e' if r=='W' else '#ef4444' if r=='L' else '#f59e0b'}'>"
        f"{'V' if r=='W' else 'D' if r=='L' else 'N'}</span>"
        for r in recent
    ) if recent else "—"

    # Points par match
    ppm = round(pts / max(played, 1), 2)

    # Détermination de l'enjeu selon le rang
    if rank == 1:
        icon, label, color = "👑", "LEADER — Course au titre", "#f59e0b"
        desc = f"1er au classement avec {pts} pts. Doit maintenir la pression pour décrocher le titre."
    elif rank <= 3:
        icon, label, color = "🏆", "Podium — Zone titre / C1", "#f59e0b"
        desc = f"#{rank} au classement ({pts} pts). Objectif : rester dans le top 3 pour le titre ou la C1."
    elif rank <= 6:
        icon, label, color = "🌍", "Course à l'Europe", "#3b82f6"
        desc = f"#{rank} au classement ({pts} pts). Lutte pour une place européenne (C3/Conference League)."
    elif rank <= 10:
        icon, label, color = "📊", "Milieu de tableau", "#888888"
        desc = f"#{rank} au classement ({pts} pts, {ppm} pts/match). Enjeu de positionnement."
    elif rank <= 15:
        icon, label, color = "⚠️", "Vigilance — Milieu bas", "#f59e0b"
        desc = f"#{rank} au classement ({pts} pts). Doit s'éloigner de la zone dangereuse."
    elif rank <= 18:
        icon, label, color = "🚨", "DANGER — Zone relégation", "#ef4444"
        desc = f"#{rank} au classement ({pts} pts). En zone de relégation — match CRUCIAL pour s'en sortir."
    else:
        icon, label, color = "🔴", "URGENCE — Dernier recours", "#ef4444"
        desc = f"#{rank} au classement ({pts} pts). Situation critique — victoire impérative."

    if form_label:
        desc += f" {form_label}."

    return (icon, label, color, desc, form_detail, pts, rank, played, wins, draws, losses, gd)


def render_match_stakes(
    home_name: str,
    away_name: str,
    home_logo: str,
    away_logo: str,
    league_name: str,
    league_country: str,
    venue_name: str,
    match_date: str,
    round_str: str,
    home_standing: Dict,
    away_standing: Dict,
    is_live: bool,
    score: str,
    minute: int,
    status_short: str,
) -> None:
    """Affiche le bloc ENJEU DU MATCH en tête de page avec analyse des objectifs de chaque équipe."""

    match_type = _detect_match_type(league_name, round_str)

    # ── Badge état ─────────────────────────────────────────────────────────
    if is_live:
        state_badge = (
            f"<span style='background:#e74c3c;color:#fff;border-radius:20px;"
            f"padding:4px 14px;font-weight:800;font-size:0.85rem;'>🔴 LIVE {minute}'</span>"
        )
    elif status_short in ("FT", "AET", "PEN"):
        state_badge = (
            f"<span style='background:#444;color:#ccc;border-radius:20px;"
            f"padding:4px 14px;font-weight:700;font-size:0.85rem;'>⚫ Terminé</span>"
        )
    else:
        state_badge = (
            f"<span style='background:#3b82f6;color:#fff;border-radius:20px;"
            f"padding:4px 14px;font-weight:700;font-size:0.85rem;'>📅 {match_date}</span>"
        )

    # ── Logos ──────────────────────────────────────────────────────────────
    def logo_html(url):
        if url:
            return (
                f"<img src='{html_lib.escape(url)}' "
                f"style='height:52px;width:52px;object-fit:contain;'>"
            )
        return "<span style='font-size:2rem;'>⚽</span>"

    # ── Score ou VS ─────────────────────────────────────────────────────────
    score_block = (
        f"<div style='font-size:2.2rem;font-weight:900;letter-spacing:6px;color:#fff;'>{score}</div>"
        if (is_live or status_short in ("FT", "AET", "PEN")) else
        "<div style='font-size:1.2rem;color:#888;font-weight:700;'>VS</div>"
    )

    # ── Analyse enjeux chaque équipe ────────────────────────────────────────
    h = _analyse_stake(home_standing, home_name)
    a = _analyse_stake(away_standing, away_name)
    h_icon, h_label, h_color, h_desc, h_form, h_pts, h_rank, h_played, h_wins, h_draws, h_losses, h_gd = h
    a_icon, a_label, a_color, a_desc, a_form, a_pts, a_rank, a_played, a_wins, a_draws, a_losses, a_gd = a

    gd_h = f"+{h_gd}" if isinstance(h_gd, int) and h_gd > 0 else str(h_gd)
    gd_a = f"+{a_gd}" if isinstance(a_gd, int) and a_gd > 0 else str(a_gd)

    # ── Intensité du duel (écart de rang) ───────────────────────────────────
    if isinstance(h_rank, int) and isinstance(a_rank, int):
        rank_gap = abs(h_rank - a_rank)
        if rank_gap <= 2:
            duel_label = "⚔️ Duel entre équipes proches — match tendu attendu"
            duel_color = "#f59e0b"
        elif rank_gap <= 5:
            duel_label = "📊 Légère différence de niveau entre les deux équipes"
            duel_color = "#888"
        else:
            top = home_name if h_rank < a_rank else away_name
            duel_label = f"🔝 {top} nettement favoris au classement"
            duel_color = "#3b82f6"
    else:
        duel_label = ""
        duel_color = "#888"

    duel_html = (
        f"<div style='text-align:center;font-size:0.75rem;color:{duel_color};"
        f"font-weight:700;margin:10px 0 6px;'>{duel_label}</div>"
        if duel_label else ""
    )

    # ── HTML enjeu équipe ───────────────────────────────────────────────────
    def team_stake_html(name, logo, icon, label, color, desc, form_detail,
                        pts, rank, played, wins, draws, losses, gd_str, align):
        flex_dir = "row" if align == "left" else "row-reverse"
        text_align = "left" if align == "left" else "right"
        return (
            "<div style='background:" + color + "12;border:1px solid " + color + "33;"
            "border-radius:12px;padding:14px 16px;height:100%;'>"

            # Logo + nom + badge enjeu
            "<div style='display:flex;align-items:center;gap:10px;"
            "flex-direction:" + flex_dir + ";margin-bottom:10px;'>"
            + logo_html(logo) +
            "<div style='text-align:" + text_align + ";'>"
            "<div style='font-size:1rem;font-weight:800;color:#fff;'>" + html_lib.escape(name) + "</div>"
            "<div style='font-size:0.7rem;font-weight:700;color:" + color + ";"
            "background:" + color + "22;border-radius:8px;padding:2px 8px;"
            "display:inline-block;margin-top:3px;'>"
            + icon + " " + label +
            "</div>"
            "</div>"
            "</div>"

            # Stats classement
            "<div style='display:grid;grid-template-columns:repeat(4,1fr);"
            "gap:4px;margin-bottom:10px;text-align:center;'>"
            "<div style='background:rgba(255,255,255,0.05);border-radius:6px;padding:5px 2px;'>"
            "<div style='font-size:1rem;font-weight:900;color:" + color + ";'>#" + str(rank) + "</div>"
            "<div style='font-size:0.6rem;color:#888;'>Rang</div></div>"
            "<div style='background:rgba(255,255,255,0.05);border-radius:6px;padding:5px 2px;'>"
            "<div style='font-size:1rem;font-weight:900;color:#fff;'>" + str(pts) + "</div>"
            "<div style='font-size:0.6rem;color:#888;'>Points</div></div>"
            "<div style='background:rgba(255,255,255,0.05);border-radius:6px;padding:5px 2px;'>"
            "<div style='font-size:0.82rem;font-weight:700;color:#fff;'>"
            + str(wins) + "V " + str(draws) + "N " + str(losses) + "D</div>"
            "<div style='font-size:0.6rem;color:#888;'>Bilan</div></div>"
            "<div style='background:rgba(255,255,255,0.05);border-radius:6px;padding:5px 2px;'>"
            "<div style='font-size:0.9rem;font-weight:700;color:#fff;'>" + gd_str + "</div>"
            "<div style='font-size:0.6rem;color:#888;'>Diff. buts</div></div>"
            "</div>"

            # Forme récente
            "<div style='font-size:0.68rem;color:#aaa;margin-bottom:4px;'>Forme (5 der.) : "
            + form_detail +
            "</div>"

            # Description enjeu
            "<div style='font-size:0.72rem;color:#ccc;line-height:1.5;"
            "border-top:1px solid rgba(255,255,255,0.08);"
            "padding-top:8px;margin-top:4px;'>" + html_lib.escape(desc) + "</div>"

            "</div>"
        )

    h_html = team_stake_html(
        home_name, home_logo, h_icon, h_label, h_color, h_desc,
        h_form, h_pts, h_rank, h_played, h_wins, h_draws, h_losses, gd_h, "left"
    )
    a_html = team_stake_html(
        away_name, away_logo, a_icon, a_label, a_color, a_desc,
        a_form, a_pts, a_rank, a_played, a_wins, a_draws, a_losses, gd_a, "right"
    )

    # ── Rendu complet ───────────────────────────────────────────────────────
    st.markdown(
        # Bandeau compétition
        f"<div style='background:linear-gradient(90deg,rgba(245,158,11,0.15),rgba(0,0,0,0.3),rgba(59,130,246,0.15));"
        f"border:1px solid rgba(255,255,255,0.08);border-radius:16px;"
        f"padding:16px 20px;margin-bottom:6px;'>"

        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<div>"
        f"<span style='font-size:0.78rem;color:#f59e0b;font-weight:700;letter-spacing:1px;'>{match_type}</span>"
        f"<span style='font-size:0.72rem;color:#888;margin-left:10px;'>{html_lib.escape(league_name)}"
        f"{(' · ' + html_lib.escape(round_str)) if round_str else ''}"
        f" · {html_lib.escape(league_country)}</span>"
        f"</div>"
        f"{state_badge}"
        f"</div>"

        # Score central
        f"<div style='text-align:center;margin:10px 0 4px;'>"
        f"{score_block}"
        f"<div style='font-size:0.68rem;color:#666;margin-top:2px;'>"
        f"🏟️ {html_lib.escape(venue_name or 'Stade non communiqué')}"
        f"</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Cartes enjeu côte à côte
    col_h, col_a = st.columns(2)
    with col_h:
        st.markdown(h_html, unsafe_allow_html=True)
    with col_a:
        st.markdown(a_html, unsafe_allow_html=True)

    # Ligne intensité du duel
    if duel_label:
        st.markdown(
            f"<div style='text-align:center;font-size:0.78rem;color:{duel_color};"
            f"font-weight:700;margin:8px 0 16px;'>{duel_label}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# VERDICT IA FINAL
# ─────────────────────────────────────────────────────────────────────────────

def render_verdict_ia(
    home_name: str,
    away_name: str,
    fp: Dict[str, Any],
    is_live: bool,
) -> None:
    """
    Affiche le verdict IA en haut de page :
    favori + probabilités 1X2 + marché recommandé + niveau de confiance.
    """
    from ai_engine.conclusion_engine import _pick_market

    final_probs = fp.get("final_probabilities", {})
    final_conf  = fp.get("final_confidence", {})
    btts        = fp.get("btts", {})
    ou_markets  = fp.get("ou_markets", {})

    hw  = final_probs.get("home_win", 33.3) / 100.0
    d   = final_probs.get("draw", 33.3)     / 100.0
    aw  = final_probs.get("away_win", 33.3) / 100.0

    hg  = fp.get("home_goals", 0)
    ag  = fp.get("away_goals", 0)
    min_= fp.get("minute", 0)

    btts_yes = btts.get("yes_prob", 0.5)
    ou25      = ou_markets.get("over_25", {})
    over25_p  = ou25.get("prob", 0.0) if isinstance(ou25, dict) else 0.0

    market_label, market_conseil, market_prob = _pick_market(
        home_name, away_name, hw, d, aw,
        btts_yes, over25_p,
        is_live, hg, ag, min_,
        home_xg=float(fp.get("home_xg", 0.0)),
        away_xg=float(fp.get("away_xg", 0.0)),
    )

    conf_color = final_conf.get("color", "#f59e0b")
    conf_label = final_conf.get("label", "Moyen")
    conf_score = final_conf.get("score", 50)
    conf_icon  = final_conf.get("icon", "🟡")

    # Cas : verdict déjà réalisé ou impossible en live
    verdict_done = (market_label == "—")

    if verdict_done:
        signal_txt   = "🔒 Verdict en cours de réalisation"
        signal_color = "#6b7280"
    elif market_prob >= 0.80:
        signal_txt   = "💎 Signal très fort"
        signal_color = "#22c55e"
    elif market_prob >= 0.70:
        signal_txt   = "✅ Signal fort"
        signal_color = "#84cc16"
    elif market_prob >= 0.60:
        signal_txt   = "🟡 Signal modéré"
        signal_color = "#f59e0b"
    else:
        signal_txt   = "⚠️ Signal faible"
        signal_color = "#ef4444"

    # 1X2 pill
    def pill(label, prob, is_fav):
        bg = "#22c55e22" if is_fav else "rgba(255,255,255,0.04)"
        border = "#22c55e" if is_fav else "rgba(255,255,255,0.1)"
        fw = "900" if is_fav else "600"
        return (
            f"<div style='background:{bg};border:2px solid {border};"
            f"border-radius:12px;padding:10px 6px;text-align:center;'>"
            f"<div style='font-size:0.75rem;color:#aaa;margin-bottom:4px;'>{label}</div>"
            f"<div style='font-size:1.4rem;font-weight:{fw};color:#fff;'>{round(prob*100)}%</div>"
            f"</div>"
        )

    home_fav = hw >= d and hw >= aw
    away_fav = aw >= d and aw >= hw

    st.markdown(
        f"<div style='background:linear-gradient(135deg,rgba(0,212,255,0.06),rgba(139,92,246,0.08));"
        f"border:1px solid {conf_color}44;border-radius:16px;"
        f"padding:20px 24px;margin-bottom:18px;'>"

        # Titre
        f"<div style='font-size:0.8rem;font-weight:700;color:{conf_color};"
        f"letter-spacing:2px;margin-bottom:12px;'>🤖 VERDICT IA — ANALYSE COMPLÈTE</div>"

        # 1X2 grid
        f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px;'>"
        + pill(f"Victoire {home_name}", hw, home_fav)
        + pill("Match Nul", d, not home_fav and not away_fav)
        + pill(f"Victoire {away_name}", aw, away_fav)
        + f"</div>"

        # Marché recommandé
        f"<div style='background:{signal_color}18;border:1px solid {signal_color}44;"
        f"border-radius:12px;padding:14px 18px;margin-bottom:12px;'>"
        f"<div style='font-size:0.72rem;color:#aaa;margin-bottom:4px;'>MARCHÉ RECOMMANDÉ</div>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='font-size:1.1rem;font-weight:800;color:#fff;'>{market_conseil}</span>"
        f"<span style='font-size:1.5rem;font-weight:900;color:{signal_color};'>{round(market_prob*100)}%</span>"
        f"</div>"
        f"<div style='margin-top:6px;font-size:0.78rem;font-weight:700;color:{signal_color};'>{signal_txt}</div>"
        f"</div>"

        # Confiance globale
        f"<div style='display:flex;align-items:center;gap:10px;'>"
        f"<span style='font-size:1.3rem;'>{conf_icon}</span>"
        f"<div style='font-size:0.82rem;color:#aaa;'>Confiance globale : "
        f"<b style='color:{conf_color};'>{conf_label} ({conf_score}%)</b></div>"
        f"</div>"

        f"</div>",
        unsafe_allow_html=True,
    )


def _fusion_to_render_format(fp: Dict[str, Any], home_name: str = "", away_name: str = "") -> Dict[str, Any]:
    """
    Convertit le final_prediction du fusion engine vers le format
    attendu par render_predictions_section.
    Toutes les valeurs viennent de fp — aucun recalcul.
    """
    from ai_engine.confidence_engine import uniform_confidence_for_market

    final_probs = fp["final_probabilities"]
    conf = fp["final_confidence"]
    is_live = fp.get("is_live", False)

    hw = final_probs["home_win"] / 100.0
    d  = final_probs["draw"]     / 100.0
    aw = final_probs["away_win"] / 100.0

    def _conf(prob: float):
        return uniform_confidence_for_market(prob, conf)

    result_preds = [
        {"label": f"Victoire {home_name or 'Domicile'}", "key": "1",
         "prob": hw, "confidence": _conf(hw)},
        {"label": "Match nul", "key": "X",
         "prob": d,  "confidence": _conf(d)},
        {"label": f"Victoire {away_name or 'Extérieur'}", "key": "2",
         "prob": aw, "confidence": _conf(aw)},
    ]

    ou = fp.get("ou_markets", {})
    goals_preds = []
    for th in [0.5, 1.5, 2.5, 3.5]:
        key = str(th).replace(".", "")
        ov = ou.get(f"over_{key}", {})
        un = ou.get(f"under_{key}", {})
        ov_p = ov.get("prob", 0.0)
        un_p = un.get("prob", 0.0)
        locked = ov.get("locked", False)
        goals_preds.append({
            "threshold": th,
            "over_prob": ov_p, "under_prob": un_p,
            "over_confidence":  (("verrouillé", "🔒", "#aaaaaa") if locked and ov_p == 1.0
                                 else ("verrouillé", "🔒", "#555555") if locked and ov_p == 0.0
                                 else _conf(ov_p)),
            "under_confidence": (("verrouillé", "🔒", "#aaaaaa") if locked and un_p == 1.0
                                 else ("verrouillé", "🔒", "#555555") if locked and un_p == 0.0
                                 else _conf(un_p)),
            "locked": locked,
            "reason": ov.get("reason", ""),
        })

    btts = fp.get("btts", {})
    btts_locked = btts.get("locked", False)
    btts_preds = {
        "yes_prob": btts.get("yes_prob", 0.0),
        "no_prob":  btts.get("no_prob",  0.0),
        "yes_confidence": (("verrouillé", "🔒", "#aaaaaa") if btts_locked else _conf(btts.get("yes_prob", 0.0))),
        "no_confidence":  (("verrouillé", "🔒", "#555555") if btts_locked else _conf(btts.get("no_prob",  0.0))),
        "locked": btts_locked,
        "reason": btts.get("reason", ""),
    }

    ng = fp.get("next_goal", {})
    next_goal = {
        "home_prob":    ng.get("home_prob", 0.5),
        "away_prob":    ng.get("away_prob", 0.5),
        "no_goal_prob": ng.get("no_goal_prob", 0.1),
        "home_name": ng.get("home_name", ""),
        "away_name": ng.get("away_name", ""),
        "home_confidence": _conf(ng.get("home_prob", 0.5)),
        "away_confidence": _conf(ng.get("away_prob", 0.5)),
    }

    return {
        "result":           result_preds,
        "goals":            goals_preds,
        "btts":             btts_preds,
        "team_goals":       fp.get("team_goals", {}),
        "halftime":         fp.get("halftime", {}),
        "corners":          fp.get("corners", {}),
        "cards":            fp.get("cards", {}),
        "next_goal":        next_goal,
        "top_scores":       fp.get("final_score_predictions", []),
        "confidence_overall": conf,
        "momentum":         fp.get("momentum", {}),
        "pressure":         fp.get("pressure", {}),
        "conclusion":       fp.get("final_conclusion", ""),
        "expected_home_goals": fp.get("home_xg", 0),
        "expected_away_goals": fp.get("away_xg", 0),
        "home_goals":  fp.get("home_goals", 0),
        "away_goals":  fp.get("away_goals", 0),
        "minute":      fp.get("minute", 0),
        "is_live":     is_live,
    }


def _first_response(data: Dict[str, Any]) -> Dict[str, Any]:
    items = _response(data)
    if isinstance(items, list) and items:
        return items[0] or {}
    if isinstance(items, dict):
        return items
    return {}


def _stat_map(stat_item: Dict[str, Any]) -> Dict[str, Any]:
    stats = {}
    for row in stat_item.get("statistics") or []:
        stat_type = row.get("type")
        if stat_type:
            stats[stat_type] = row.get("value")
    return stats


def _num(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace("%", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return 0


def _display_value(value: Any) -> Any:
    if value is None or value == "—":
        return "Non disponible"
    return value


def _stat_value(stats: Dict[str, Any], aliases: List[str], fallback: Any = 0) -> Any:
    normalized = {str(key).lower().strip(): value for key, value in stats.items()}
    for alias in aliases:
        key = alias.lower().strip()
        if key in normalized and normalized[key] is not None:
            return normalized[key]
    return fallback


def _team_stat_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    response = _response(data)
    if isinstance(response, dict):
        return response
    if isinstance(response, list) and response:
        return response[0] or {}
    return {}


def _team_average_goals(team_stats_data: Dict[str, Any], side: str) -> float:
    payload = _team_stat_payload(team_stats_data)
    goals = payload.get("goals") or {}
    section = goals.get("for" if side == "for" else "against") or {}
    average = section.get("average") or {}
    total = average.get("total")
    try:
        return float(total or 0)
    except (TypeError, ValueError):
        return 0.0


def _fixture_score(item: Dict[str, Any]) -> str:
    goals = item.get("goals") or {}
    home = goals.get("home")
    away = goals.get("away")
    return f"{home if home is not None else '-'} - {away if away is not None else '-'}"


def _team_form(fixtures: List[Dict[str, Any]], team_id: int) -> Dict[str, Any]:
    wins = draws = losses = goals_for = goals_against = 0
    rows = []
    for item in fixtures[:5]:
        teams = item.get("teams") or {}
        goals = item.get("goals") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        is_home = home.get("id") == team_id
        gf = goals.get("home") if is_home else goals.get("away")
        ga = goals.get("away") if is_home else goals.get("home")
        gf = gf if gf is not None else 0
        ga = ga if ga is not None else 0
        goals_for += gf
        goals_against += ga
        if gf > ga:
            wins += 1
            result = "V"
        elif gf < ga:
            losses += 1
            result = "D"
        else:
            draws += 1
            result = "N"
        rows.append({"opponent": (away if is_home else home).get("name") or "—", "score": _fixture_score(item), "result": result})
    return {"wins": wins, "draws": draws, "losses": losses, "goals_for": goals_for, "goals_against": goals_against, "rows": rows}


def _standing_for_team(standings_data: Dict[str, Any], team_id: int) -> Dict[str, Any]:
    for league in _response(standings_data):
        for group in (league.get("league") or {}).get("standings") or []:
            for row in group:
                team = row.get("team") or {}
                if team.get("id") == team_id:
                    return row
    return {}


@st.cache_data(ttl=30)
def fetch_analysis_data_live(fixture_id: int, home_team_id: int, away_team_id: int, league_id: int, season: int) -> Dict[str, Any]:
    """Cache court (30s) pour matchs en cours."""
    api = FootballAPI(timeout=15, max_retries=3)
    return {
        "fixture": api.get_fixture_detail(fixture_id),
        "statistics": api.get_fixture_statistics(fixture_id),
        "events": api.get_fixture_events(fixture_id),
        "lineups": api.get_fixture_lineups(fixture_id),
        "home_recent": api.get_team_recent_fixtures(home_team_id, 5),
        "away_recent": api.get_team_recent_fixtures(away_team_id, 5),
        "home_team_stats": api.get_team_statistics(league_id, season, home_team_id),
        "away_team_stats": api.get_team_statistics(league_id, season, away_team_id),
        "h2h": api.get_head_to_head(home_team_id, away_team_id, 5),
        "standings": api.get_standings(league_id, season),
    }


@st.cache_data(ttl=300)
def fetch_analysis_data(fixture_id: int, home_team_id: int, away_team_id: int, league_id: int, season: int) -> Dict[str, Any]:
    """Cache long (5min) pour matchs futurs/termines."""
    api = FootballAPI(timeout=15, max_retries=3)
    return {
        "fixture": api.get_fixture_detail(fixture_id),
        "statistics": api.get_fixture_statistics(fixture_id),
        "events": api.get_fixture_events(fixture_id),
        "lineups": api.get_fixture_lineups(fixture_id),
        "home_recent": api.get_team_recent_fixtures(home_team_id, 5),
        "away_recent": api.get_team_recent_fixtures(away_team_id, 5),
        "home_team_stats": api.get_team_statistics(league_id, season, home_team_id),
        "away_team_stats": api.get_team_statistics(league_id, season, away_team_id),
        "h2h": api.get_head_to_head(home_team_id, away_team_id, 5),
        "standings": api.get_standings(league_id, season),
    }


def render_analysis_dashboard(fixture_id: int, home_team_id: int, away_team_id: int, league_id: int, season: int):
    nav_c1, nav_c2, nav_c3 = st.columns([2, 1, 1])
    with nav_c1:
        if st.button("\u2190 Retour aux matchés", use_container_width=True):
            st.query_params.clear()
            st.session_state["active_page"] = st.session_state.get("active_page", "live")
            st.rerun()
    with nav_c2:
        if st.button("\U0001f534 Matchs Live", use_container_width=True):
            st.query_params.clear()
            st.session_state["active_page"] = "live"
            st.rerun()
    with nav_c3:
        if st.button("\U0001f4c5 Matchs Futurs", use_container_width=True):
            st.query_params.clear()
            st.session_state["active_page"] = "future"
            st.rerun()

    with st.spinner("Chargement de l'analyse réelle API-Football..."):
        # Première récupération rapide pour détecter si le match est live
        _quick = fetch_analysis_data_live(fixture_id, home_team_id, away_team_id, league_id, season)
        _quick_fixture = (_quick.get("fixture") or {})
        _quick_resp = _quick_fixture.get("response") or []
        _quick_status = {}
        if isinstance(_quick_resp, list) and _quick_resp:
            _quick_status = (_quick_resp[0] or {}).get("fixture", {}).get("status", {})
        elif isinstance(_quick_resp, dict):
            _quick_status = _quick_resp.get("fixture", {}).get("status", {})
        _match_is_live = _quick_status.get("short", "") in ("1H", "2H", "HT", "ET", "BT", "P", "SUSP", "INT", "LIVE")
        data = _quick  # réutiliser les données déjà récupérées

    fixture = _first_response(data["fixture"])
    fixture_info = fixture.get("fixture") or {}
    teams = fixture.get("teams") or {}
    goals = fixture.get("goals") or {}
    league = fixture.get("league") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    venue = fixture_info.get("venue") or {}
    status = fixture_info.get("status") or {}

    home_name = home.get("name") or "Equipe domicile"
    away_name = away.get("name") or "Equipe extérieur"
    score = f"{goals.get('home') if goals.get('home') is not None else '-'} - {goals.get('away') if goals.get('away') is not None else '-'}"
    time_label = f"{status.get('elapsed')}’ {status.get('short') or ''}" if status.get("elapsed") else fixture_info.get("date", "")

    st.markdown("<div class='analysis-shell'>", unsafe_allow_html=True)

    # ── Classements (récupérés tôt pour render_match_stakes) ─────────────────
    _home_standing_early = _standing_for_team(data["standings"], home_team_id)
    _away_standing_early = _standing_for_team(data["standings"], away_team_id)
    _round_str = league.get("round", "")
    _match_date_str = (fixture_info.get("date") or "")[:10]

    # ══════════════════════════════════════════════════════════════════════════
    # ENJEU DU MATCH — Affiché EN PREMIER
    # ══════════════════════════════════════════════════════════════════════════
    render_match_stakes(
        home_name=home_name,
        away_name=away_name,
        home_logo=home.get("logo") or "",
        away_logo=away.get("logo") or "",
        league_name=league.get("name") or "",
        league_country=league.get("country") or "",
        venue_name=venue.get("name") or "",
        match_date=_match_date_str,
        round_str=_round_str,
        home_standing=_home_standing_early,
        away_standing=_away_standing_early,
        is_live=_match_is_live,
        score=score,
        minute=int(status.get("elapsed") or 0),
        status_short=status.get("short") or "NS",
    )

    stats_items = _response(data["statistics"])
    home_stats = _stat_map(stats_items[0]) if isinstance(stats_items, list) and len(stats_items) > 0 else {}
    away_stats = _stat_map(stats_items[1]) if isinstance(stats_items, list) and len(stats_items) > 1 else {}

    stat_names = [
        ("Possession", ["Ball Possession", "Possession"], "Non disponible"),
        ("Tirs", ["Total Shots", "Shots Total", "Total shots"], 0),
        ("Tirs cadrés", ["Shots on Goal", "Shots on goal", "On Target"], 0),
        ("Corners", ["Corner Kicks", "Corners"], 0),
        ("Fautes", ["Fouls"], 0),
        ("Cartons jaunes", ["Yellow Cards"], 0),
        ("Cartons rouges", ["Red Cards"], 0),
        ("Expected goals", ["expected_goals", "Expected Goals", "xG"], "Non disponible"),
    ]

    st.markdown("### 📊 Statistiques match")

    if home_stats or away_stats:
        # Stats live/terminées disponibles
        for name, aliases, fallback in stat_names:
            left = _stat_value(home_stats, aliases, fallback)
            right = _stat_value(away_stats, aliases, fallback)
            left_num = _num(left)
            right_num = _num(right)
            total = max(left_num + right_num, 1)
            st.markdown(f"**{name}**")
            cols = st.columns([1, 3, 1])
            cols[0].metric(home_name, _display_value(left))
            cols[1].progress(min(left_num / total, 1.0))
            cols[2].metric(away_name, _display_value(right))
    else:
        # Stats de match non disponibles → afficher les stats de saison des équipes
        home_payload = _team_stat_payload(data.get("home_team_stats", {}))
        away_payload = _team_stat_payload(data.get("away_team_stats", {}))

        def _season_val(payload: dict, *path):
            """Navigue dans un dict imbriqué par chemin de clés."""
            cur = payload
            for k in path:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(k)
            return cur

        if home_payload or away_payload:
            st.caption("📈 *Statistiques de saison (stats du match non encore disponibles)*")

            season_stats = [
                ("Matchs joués",
                 _season_val(home_payload, "fixtures", "played", "total"),
                 _season_val(away_payload, "fixtures", "played", "total")),
                ("Victoires",
                 _season_val(home_payload, "fixtures", "wins", "total"),
                 _season_val(away_payload, "fixtures", "wins", "total")),
                ("Défaites",
                 _season_val(home_payload, "fixtures", "loses", "total"),
                 _season_val(away_payload, "fixtures", "loses", "total")),
                ("Buts marqués (saison)",
                 _season_val(home_payload, "goals", "for", "total", "total"),
                 _season_val(away_payload, "goals", "for", "total", "total")),
                ("Buts encaissés (saison)",
                 _season_val(home_payload, "goals", "against", "total", "total"),
                 _season_val(away_payload, "goals", "against", "total", "total")),
                ("Moy. buts marqués/match",
                 _season_val(home_payload, "goals", "for", "average", "total"),
                 _season_val(away_payload, "goals", "for", "average", "total")),
                ("Moy. buts encaissés/match",
                 _season_val(home_payload, "goals", "against", "average", "total"),
                 _season_val(away_payload, "goals", "against", "average", "total")),
                ("Clean sheets",
                 _season_val(home_payload, "clean_sheet", "total"),
                 _season_val(away_payload, "clean_sheet", "total")),
                ("Buts en 1ère MT",
                 _season_val(home_payload, "goals", "for", "minute", "0-15", "total"),
                 _season_val(away_payload, "goals", "for", "minute", "0-15", "total")),
            ]

            for name, lv, rv in season_stats:
                lv_str = str(lv) if lv is not None else "—"
                rv_str = str(rv) if rv is not None else "—"
                try:
                    lv_num = float(str(lv).replace("%", "")) if lv is not None else 0
                    rv_num = float(str(rv).replace("%", "")) if rv is not None else 0
                except (ValueError, TypeError):
                    lv_num = rv_num = 0
                total_s = max(lv_num + rv_num, 0.01)
                st.markdown(f"**{name}**")
                cols = st.columns([1, 3, 1])
                cols[0].metric(home_name, lv_str)
                if lv_num + rv_num > 0:
                    cols[1].progress(min(lv_num / total_s, 1.0))
                else:
                    cols[1].progress(0.0)
                cols[2].metric(away_name, rv_str)
        else:
            st.info("⚠️ Aucune statistique disponible pour ce match ou ces équipes via l'API.")

    home_recent = _response(data["home_recent"])
    away_recent = _response(data["away_recent"])
    home_form = analyze_form(home_recent, home_team_id)
    away_form = analyze_form(away_recent, away_team_id)
    home_team_avg_for = _team_average_goals(data["home_team_stats"], "for")
    home_team_avg_against = _team_average_goals(data["home_team_stats"], "against")
    away_team_avg_for = _team_average_goals(data["away_team_stats"], "for")
    away_team_avg_against = _team_average_goals(data["away_team_stats"], "against")
    if home_team_avg_for:
        home_form["avg_goals_for"] = home_team_avg_for
    if home_team_avg_against:
        home_form["avg_goals_against"] = home_team_avg_against
    if away_team_avg_for:
        away_form["avg_goals_for"] = away_team_avg_for
    if away_team_avg_against:
        away_form["avg_goals_against"] = away_team_avg_against

    # Smart Stats Fallback: enrichir les statistiques manquantes
    events = _response(data["events"])
    estimated_stats = estimate_missing_stats(
        home_stats=home_stats,
        away_stats=away_stats,
        home_form=home_form,
        away_form=away_form,
        home_team_stats=data["home_team_stats"],
        away_team_stats=data["away_team_stats"],
        events=events,
        minute=status.get("elapsed") or 0,
    )
    # Marquer les stats estimées avec astérisque
    original_home_stats = dict(home_stats)
    original_away_stats = dict(away_stats)
    home_stats = mark_estimated(estimated_stats["home"], original_home_stats)
    away_stats = mark_estimated(estimated_stats["away"], original_away_stats)

    # ── Build live context ────────────────────────────────────────────────────
    current_home_goals = goals.get("home") or 0
    current_away_goals = goals.get("away") or 0
    minute = status.get("elapsed") or 0
    status_short = status.get("short") or "NS"
    events = _response(data["events"])

    live_context = build_live_context(
        home_goals=current_home_goals,
        away_goals=current_away_goals,
        minute=minute,
        status=status_short,
        home_stats=home_stats,
        away_stats=away_stats,
        events=events,
    )
    is_live = _match_is_live or bool(live_context and live_context.get("is_live"))

    # ══════════════════════════════════════════════════════════════════════════
    # FUSION ENGINE — UN SEUL CALCUL, UNE SEULE VÉRITÉ
    # ══════════════════════════════════════════════════════════════════════════
    raw_prediction = build_final_prediction(
        home_team=home_name,
        away_team=away_name,
        home_form=home_form,
        away_form=away_form,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_stats=home_stats,
        away_stats=away_stats,
        events=events,
        h2h_data=_response(data.get("h2h", {})),
        standings=data.get("standings"),
        live_context=live_context if is_live else None,
        is_live=is_live,
    )
    fp = validate_and_fix(raw_prediction)

    # Source unique utilisée partout ci-dessous
    final_probs  = fp["final_probabilities"]
    final_scores = fp["final_score_predictions"]
    final_conf   = fp["final_confidence"]
    final_conc   = fp["final_conclusion"]
    consistency_warns = fp.get("consistency_warnings", [])

    # ══════════════════════════════════════════════════════════════════════════
    # VERDICT IA — Affiché juste après l'enjeu, avant toute analyse
    # ══════════════════════════════════════════════════════════════════════════
    render_verdict_ia(home_name, away_name, fp, is_live)

    # ── Forme récente ─────────────────────────────────────────────────────────
    st.markdown("### 🔥 Forme récente")
    col_home, col_away = st.columns(2)
    for col, title, form in [(col_home, home_name, home_form), (col_away, away_name, away_form)]:
        with col:
            st.markdown(f"<div class='analysis-card'><h4>{html_lib.escape(title)}</h4></div>", unsafe_allow_html=True)
            st.metric("Victoires", form["wins"])
            st.metric("Nuls", form["draws"])
            st.metric("Défaites", form["losses"])
            st.metric("Buts marqués", form["goals_for"])
            st.metric("Buts encaissés", form["goals_against"])
            st.metric("Moy. buts marqués", round(form["avg_goals_for"], 2))
            st.metric("Moy. buts encaissés", round(form["avg_goals_against"], 2))
            for row in form["rows"]:
                st.write(f"{row['result']} · {row['opponent']} · {row['score']}")

    # ── H2H ──────────────────────────────────────────────────────────────────
    st.markdown("### ⚔️ Head to Head")
    h2h_items = _response(data["h2h"])
    if h2h_items:
        for item in h2h_items[:5]:
            item_teams = item.get("teams") or {}
            st.write(f"{(item_teams.get('home') or {}).get('name', '—')} {_fixture_score(item)} {(item_teams.get('away') or {}).get('name', '—')}")
    else:
        st.info("Aucune confrontation directe disponible via l'API.")

    # ── Classement ───────────────────────────────────────────────────────────
    st.markdown("### 🏆 Classement")
    home_standing = _standing_for_team(data["standings"], home_team_id)
    away_standing = _standing_for_team(data["standings"], away_team_id)
    standing_cols = st.columns(2)
    for col, title, row in [(standing_cols[0], home_name, home_standing), (standing_cols[1], away_name, away_standing)]:
        with col:
            st.markdown(f"**{title}**")
            st.metric("Position", row.get("rank", "Non disponible"))
            st.metric("Points", row.get("points", "Non disponible"))
            st.metric("Différence buts", row.get("goalsDiff", "Non disponible"))

    # ── Événements & lineups ──────────────────────────────────────────────────
    lineups = _response(data["lineups"])
    st.markdown("### 🧩 Événements & compositions")
    st.write(f"Événements disponibles : {len(events)}  ·  Compositions : {len(lineups)}")

    # ── Contexte live ─────────────────────────────────────────────────────────
    if is_live and live_context and live_context.get("is_live"):
        st.markdown("### 🤖 Contexte live")
        live_cols = st.columns(4)
        live_cols[0].metric("Minute", f"{live_context.get('minute', 0)}'")
        live_cols[1].metric("Phase",  live_context.get("phase", "—"))
        live_cols[2].metric("État",   live_context.get("state", "—"))
        pres = fp.get("pressure", {})
        if not pres.get("unknown"):
            live_cols[3].metric("Pression dom.", f"{pres.get('home_index', 0):.0f}")
        mom = fp.get("momentum", {})
        if mom.get("data_available"):
            st.caption(f"Momentum: {mom.get('label','—')} · {home_name}: {mom.get('home_pct',50)}% / {away_name}: {mom.get('away_pct',50)}%")
        else:
            st.caption(f"⚠️ {mom.get('label', 'Données live insuffisantes')}")

    # ── ELO (informatif) ──────────────────────────────────────────────────────
    elo_cols = st.columns(2)
    elo_cols[0].metric(f"Elo {home_name}", fp.get("home_elo", "—"))
    elo_cols[1].metric(f"Elo {away_name}", fp.get("away_elo", "—"))

    # ══════════════════════════════════════════════════════════════════════════
    # PROBABILITÉS — AFFICHÉES UNE SEULE FOIS (source: final_probabilities)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 📈 Probabilités (source unique)")
    prob_cols = st.columns(3)
    prob_cols[0].metric(f"Victoire {home_name}", f"{final_probs['home_win']}%")
    prob_cols[0].progress(final_probs["home_win"] / 100)
    prob_cols[1].metric("Match nul", f"{final_probs['draw']}%")
    prob_cols[1].progress(final_probs["draw"] / 100)
    prob_cols[2].metric(f"Victoire {away_name}", f"{final_probs['away_win']}%")
    prob_cols[2].progress(final_probs["away_win"] / 100)

    # ── Scores probables (filtrés) ────────────────────────────────────────────
    st.markdown("### 🎯 Scores probables (filtrés par score actuel)")
    if final_scores:
        score_cols = st.columns(min(5, len(final_scores)))
        for col, sc in zip(score_cols, final_scores):
            is_cur = sc.get("is_current", False)
            col.metric(
                f"{sc['score']} {'🔴' if is_cur else ''}",
                f"{sc['probability']}%"
            )

    # ══════════════════════════════════════════════════════════════════════════
    # CONFIANCE — AFFICHÉE UNE SEULE FOIS (source: final_confidence)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🧠 Confiance du modèle (source unique)")
    conf_icon = final_conf.get("icon", "🟡")
    conf_label = final_conf.get("label", "Moyen")
    conf_score = final_conf.get("score", 50)
    conf_color = final_conf.get("color", "#ffaa00")
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;padding:12px;border-radius:10px;"
        f"border:2px solid {conf_color}44;background:{conf_color}11;'>"
        f"<span style='font-size:2rem'>{conf_icon}</span>"
        f"<div><div style='font-size:1.2rem;font-weight:800;color:{conf_color};'>{conf_label}</div>"
        f"<div style='font-size:0.85rem;color:#aaa;'>Score: {conf_score}%</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"xG restants: {fp.get('home_xg', 0)} ({home_name}) · {fp.get('away_xg', 0)} ({away_name}). "
        "Calcul centralisé depuis forme, ELO, H2H, classement et contexte live."
    )

    # ── Avertissements de cohérence ───────────────────────────────────────────
    if consistency_warns:
        with st.expander("⚠️ Corrections de cohérence appliquées", expanded=False):
            for w in consistency_warns:
                st.caption(f"• {w}")

    # ── Paris suggérés (utilisent final_probs) ────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔥 Paris suggérés")

    ai_result_compat = {
        "home_xg": fp.get("home_xg", 1.2),
        "away_xg": fp.get("away_xg", 1.0),
        "probabilities": final_probs,
        "top_scores": [{"score": s["score"], "probability": s["probability"]} for s in final_scores],
        "confidence": conf_score,
        "confidence_label": conf_label,
    }
    bet_analysis = analyze_bet_opportunities(
        live_context=live_context,
        ai_result=ai_result_compat,
        home_form=home_form,
        away_form=away_form,
        home_stats=home_stats,
        away_stats=away_stats,
        events=events,
    )
    suggestions = bet_analysis.get("suggestions", [])
    if suggestions:
        for i, suggestion in enumerate(suggestions[:4], 1):
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 3])
                col1.markdown(f"**{i}. {suggestion['bet']}**")
                col1.caption(f"Type: {suggestion['type']}")
                col2.metric("Confiance", f"{suggestion['confidence']:.0f}%")
                col3.caption(f"🧠 {suggestion['logic']}")
                st.progress(suggestion['confidence'] / 100)
                st.markdown("---")
    else:
        st.info("Pas de suggestion de pari assez fiable pour ce match.")

    # ══════════════════════════════════════════════════════════════════════════
    # CONCLUSION — AFFICHÉE UNE SEULE FOIS (source: final_conclusion)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🧠 Conclusion IA")
    favorite_name, favorite_pct = get_favorite(final_probs, home_name, away_name)
    st.markdown(
        f"<div style='background:linear-gradient(135deg,rgba(0,255,136,0.08),rgba(45,151,245,0.08));"
        f"padding:20px;border-radius:12px;border-left:4px solid {conf_color};'>"
        f"{final_conc.replace(chr(10), '<br>')}"
        f"</div>",
        unsafe_allow_html=True,
    )

    if any("*" in str(v) for v in home_stats.values()) or any("*" in str(v) for v in away_stats.values()):
        st.caption("* Statistiques estimées intelligemment par l'IA.")

    # ══════════════════════════════════════════════════════════════════════════
    # PRÉDICTIONS AVANCÉES — utilisent le final_prediction du fusion engine
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    render_predictions_section(
        _fusion_to_render_format(fp, home_name, away_name),
        home_name,
        away_name,
    )

    st.markdown("</div>", unsafe_allow_html=True)
