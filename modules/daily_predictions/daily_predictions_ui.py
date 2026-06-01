"""
daily_predictions_ui.py
========================
Interface complète — TOP PRÉDICTIONS DU JOUR
4 rubriques : Victoires · Double Chance · GG · Corners+Cartons
"""
from __future__ import annotations

import time
import datetime
from typing import Any, Dict, List

import streamlit as st

from modules.daily_predictions.daily_predictions_engine import fetch_daily_predictions


# ─────────────────────────────────────────────────────────────────────────────
# Helpers visuels
# ─────────────────────────────────────────────────────────────────────────────

def _prob_bar(pct: float, color: str) -> str:
    safe_pct = min(100.0, max(0.0, pct))
    return (
        f"<div style='background:rgba(255,255,255,0.08);border-radius:4px;"
        f"height:7px;overflow:hidden;margin-top:5px;'>"
        f"<div style='width:{safe_pct}%;height:7px;background:{color};"
        f"border-radius:4px;transition:width 0.4s;'></div></div>"
    )


def _section_divider(title: str, count: int, color: str, bg: str) -> None:
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;margin:20px 0 10px;'>"
        f"<div style='height:3px;flex:1;background:rgba(255,255,255,0.07);border-radius:2px;'></div>"
        f"<span style='background:{bg};color:{color};border-radius:20px;"
        f"padding:5px 18px;font-size:0.9rem;font-weight:800;white-space:nowrap;'>"
        f"{title} "
        f"<span style='opacity:0.7;font-size:0.78rem;'>({count} matchs)</span>"
        f"</span>"
        f"<div style='height:3px;flex:1;background:rgba(255,255,255,0.07);border-radius:2px;'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Carte match générique
# ─────────────────────────────────────────────────────────────────────────────

def _render_card(m: Dict[str, Any], accent: str) -> None:
    flag     = m.get("league_flag", "")
    flag_html = f"<img src='{flag}' style='height:13px;margin-right:4px;vertical-align:middle;'>" if flag else ""
    pct      = m.get("pct", 0.0)
    conf_col = m.get("conf_color", "#888")
    conf_lbl = m.get("conf_label", "—")
    detail   = m.get("detail", "")
    justification = m.get("justification", "")
    pred     = m.get("prediction", "—")
    market   = m.get("market", "—")

    # Infos supplémentaires selon rubrique
    extra_html = ""
    if market == "CORNERS + CARTONS":
        pc = round(m.get("p_corners", 0) * 100, 1)
        pk = round(m.get("p_cards", 0) * 100, 1)
        extra_html = (
            f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px;'>"
            f"<div style='background:rgba(255,255,255,0.05);border-radius:8px;padding:7px;text-align:center;'>"
            f"<div style='font-size:0.75rem;color:#aaa;'>Over 7.5 corners</div>"
            f"<div style='font-weight:800;color:{accent};'>{pc}%</div></div>"
            f"<div style='background:rgba(255,255,255,0.05);border-radius:8px;padding:7px;text-align:center;'>"
            f"<div style='font-size:0.75rem;color:#aaa;'>&ge;3 cartons jaunes</div>"
            f"<div style='font-weight:800;color:{accent};'>{pk}%</div></div>"
            f"</div>"
        )
    elif market == "VICTOIRE":
        ph = round(m.get("win_probs", {}).get("p_home", 0) * 100, 1)
        pa = round(m.get("win_probs", {}).get("p_away", 0) * 100, 1)
        pd = round(m.get("win_probs", {}).get("p_draw", 0) * 100, 1)
        extra_html = (
            f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-top:8px;'>"
            f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:6px;text-align:center;'>"
            f"<div style='font-size:0.68rem;color:#aaa;'>Domicile</div>"
            f"<div style='font-weight:700;font-size:0.9rem;'>{ph}%</div></div>"
            f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:6px;text-align:center;'>"
            f"<div style='font-size:0.68rem;color:#aaa;'>Nul</div>"
            f"<div style='font-weight:700;font-size:0.9rem;'>{pd}%</div></div>"
            f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:6px;text-align:center;'>"
            f"<div style='font-size:0.68rem;color:#aaa;'>Extérieur</div>"
            f"<div style='font-weight:700;font-size:0.9rem;'>{pa}%</div></div>"
            f"</div>"
        )

    card = "".join([
        f"<div style='background:rgba(255,255,255,0.03);border:1px solid {accent}44;"
        f"border-left:4px solid {accent};border-radius:12px;padding:14px;margin-bottom:12px;'>",

        # Heure + ligue
        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;'>",
        f"<span style='font-size:0.72rem;color:#aaa;'>{flag_html}"
        f"{m.get('league_name','—')} · {m.get('league_country','—')}</span>",
        f"<span style='font-size:0.72rem;color:{accent};font-weight:700;'>⏰ {m.get('start_time','—')}</span>",
        f"</div>",

        # Équipes
        f"<div style='font-size:1rem;font-weight:800;text-align:center;margin:6px 0;'>",
        m["home_name"],
        f"<span style='color:#666;margin:0 8px;font-size:0.85rem;'>VS</span>",
        m["away_name"],
        f"</div>",

        # Prédiction
        f"<div style='background:rgba(255,255,255,0.05);border-radius:8px;padding:10px;margin-top:8px;'>",
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>",
        f"<span style='font-size:0.75rem;color:#aaa;'>{market}</span>",
        f"<span style='font-size:0.78rem;font-weight:700;color:{accent};'>{pred}</span>",
        f"</div>",
        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:6px;'>",
        f"<span style='font-size:0.75rem;color:#aaa;'>Probabilité estimée</span>",
        f"<span style='font-weight:900;font-size:1.05rem;'>{pct}%</span>",
        f"</div>",
        _prob_bar(pct, conf_col),
        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:5px;'>",
        f"<span style='font-size:0.72rem;color:#888;'>Confiance</span>",
        f"<span style='font-size:0.75rem;font-weight:700;color:{conf_col};'>{conf_lbl}</span>",
        f"</div>",
        f"</div>",

        # Extra
        extra_html,

        # Détail
        (f"<div style='font-size:0.68rem;color:#666;margin-top:6px;'>{detail}</div>" if detail else ""),
        (f"<div style='font-size:0.70rem;color:#94a3b8;margin-top:8px;line-height:1.35;'>🧠 {justification}</div>" if justification else ""),

        "</div>",
    ])
    st.markdown(card, unsafe_allow_html=True)


def _render_grid(matches: List[Dict], accent: str, empty_msg: str) -> None:
    if not matches:
        st.markdown(
            f"<div style='text-align:center;padding:16px;color:#888;"
            f"border:2px dashed {accent}33;border-radius:10px;font-size:0.82rem;'>"
            f"{empty_msg}</div>",
            unsafe_allow_html=True,
        )
        return

    n = len(matches)
    cols_count = 1 if n == 1 else 2 if n == 2 else 3
    cols = st.columns(cols_count)
    for i, m in enumerate(matches):
        with cols[i % cols_count]:
            _render_card(m, accent)


# ─────────────────────────────────────────────────────────────────────────────
# Barre résumé
# ─────────────────────────────────────────────────────────────────────────────

def _render_summary(results: Dict[str, List]) -> None:
    cats = [
        ("⚽ Victoires",      len(results["wins"]),          "#3b82f6"),
        ("🔄 Double Chance",  len(results["double_chance"]), "#8b5cf6"),
        ("🎯 GG",             len(results["btts"]),          "#22c55e"),
        ("🟨 Corners+Cartons",len(results["corners_cards"]), "#f59e0b"),
    ]
    total = sum(c[1] for c in cats)
    html_parts = [
        f"<div style='display:grid;grid-template-columns:repeat({len(cats)+1},1fr);"
        f"gap:8px;margin-bottom:16px;'>",
        f"<div style='background:rgba(255,255,255,0.04);border-radius:10px;"
        f"padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;'>{total}</div>"
        f"<div style='font-size:0.7rem;color:#888;'>Total prédictions</div></div>",
    ]
    for label, count, color in cats:
        html_parts.append(
            f"<div style='background:{color}18;border-radius:10px;"
            f"padding:10px;text-align:center;border:1px solid {color}33;'>"
            f"<div style='font-size:1.3rem;font-weight:900;color:{color};'>{count}</div>"
            f"<div style='font-size:0.7rem;color:#888;'>{label}</div></div>"
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def render_daily_predictions_page(api) -> None:
    """Page principale TOP PRÉDICTIONS DU JOUR."""

    today_str = datetime.date.today().strftime("%d/%m/%Y")

    st.markdown(
        f"<h2 style='font-size:1.6rem;margin-bottom:2px;'>🔮 TOP PRÉDICTIONS DU JOUR</h2>"
        f"<p style='color:#888;font-size:0.85rem;margin-bottom:14px;'>"
        f"Analyse automatique des matchs du {today_str} · TOP 10 global du jour · "
        f"<span style='color:#f59e0b;'>Probabilités estimées — pas de garantie</span></p>",
        unsafe_allow_html=True,
    )

    col_ref, col_info = st.columns([1, 3])
    with col_ref:
        force_refresh = st.button("🔄 Actualiser", use_container_width=True, key="daily_refresh")
    with col_info:
        st.markdown(
            "<div style='font-size:0.78rem;color:#888;padding-top:6px;'>"
            "⚽ Victoires · 🔄 Double Chance · 🎯 GG · 🟨 Over 7.5 corners + 3 cartons jaunes</div>",
            unsafe_allow_html=True,
        )

    # ── Cache session ─────────────────────────────────────────────────────
    now_ts    = time.time()
    FULL_TTL  = 300  # 5 min
    cache_key = "daily_pred_results"
    ts_key    = "daily_pred_ts"

    cached   = st.session_state.get(cache_key)
    last_ts  = st.session_state.get(ts_key, 0)
    need_fetch = (cached is None or force_refresh or (now_ts - last_ts) > FULL_TTL)

    if need_fetch:
        with st.spinner("Analyse des matchs du jour en cours…"):
            try:
                results = fetch_daily_predictions(api)
            except Exception as e:
                st.error(f"Erreur : {e}")
                results = {"wins": [], "double_chance": [], "btts": [], "corners_cards": []}
        st.session_state[cache_key] = results
        st.session_state[ts_key]    = now_ts
    else:
        results = cached

    dt_str = datetime.datetime.fromtimestamp(st.session_state.get(ts_key, now_ts)).strftime("%H:%M:%S")
    st.caption(f"⏱️ Dernière analyse : {dt_str} · Maximum 10 matchs du jour · Rafraîchissement toutes les 5 min")

    total = sum(len(v) for v in results.values())
    if total == 0:
        st.info(
            "Aucune prédiction disponible pour le moment. "
            "Les matchs du jour seront analysés dès leur publication par l'API."
        )
        return

    # ── Résumé ────────────────────────────────────────────────────────────
    _render_summary(results)

    # ════════════════════════════════════════════════════════════════════
    # RUBRIQUE 1 — VICTOIRES
    # ════════════════════════════════════════════════════════════════════
    _section_divider("⚽ VICTOIRES", len(results["wins"]), "#3b82f6", "rgba(59,130,246,0.15)")
    st.caption("Équipe favorite avec la plus forte probabilité de victoire · Seuil ≥ 55%")
    _render_grid(
        results["wins"], "#3b82f6",
        "Aucune victoire assez probable aujourd'hui (seuil 55%)."
    )

    # ════════════════════════════════════════════════════════════════════
    # RUBRIQUE 2 — DOUBLE CHANCE
    # ════════════════════════════════════════════════════════════════════
    _section_divider("🔄 DOUBLE CHANCE", len(results["double_chance"]), "#8b5cf6", "rgba(139,92,246,0.15)")
    st.caption("Meilleure double chance (1X / X2 / 12) par match · Seuil ≥ 70%")
    _render_grid(
        results["double_chance"], "#8b5cf6",
        "Aucune double chance assez sûre aujourd'hui (seuil 70%)."
    )

    # ════════════════════════════════════════════════════════════════════
    # RUBRIQUE 3 — GG (BTTS)
    # ════════════════════════════════════════════════════════════════════
    _section_divider("🎯 GG — LES DEUX MARQUENT", len(results["btts"]), "#22c55e", "rgba(34,197,94,0.15)")
    st.caption("Les deux équipes marquent au moins 1 but · Seuil ≥ 55%")
    _render_grid(
        results["btts"], "#22c55e",
        "Aucun match GG suffisamment probable aujourd'hui (seuil 55%)."
    )

    # ════════════════════════════════════════════════════════════════════
    # RUBRIQUE 4 — CORNERS + CARTONS
    # ════════════════════════════════════════════════════════════════════
    _section_divider("🟨 OVER 7.5 CORNERS + 3 CARTONS JAUNES", len(results["corners_cards"]), "#f59e0b", "rgba(245,158,11,0.15)")
    st.caption("Over 7.5 corners ET au moins 3 cartons jaunes · Seuil combiné ≥ 45%")
    _render_grid(
        results["corners_cards"], "#f59e0b",
        "Aucun match répondant aux critères corners+cartons aujourd'hui (seuil 45%)."
    )

    st.markdown(
        "<div style='text-align:center;font-size:0.7rem;color:#555;margin-top:16px;'>"
        "Probabilités estimées par modèle Poisson · Forme récente · Données API-Football · "
        "Aucune garantie de résultat</div>",
        unsafe_allow_html=True,
    )
