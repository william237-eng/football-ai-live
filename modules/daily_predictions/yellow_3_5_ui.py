"""
yellow_3_5_ui.py
==================
Page dédiée : CARTONS JAUNES — OVER 3.5
Affiche le top 20 IA pour Over 3.5 cartons jaunes, statistiques réelles (1j / 7j / 30j)
et validation automatique via le moniteur dédié.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List

import streamlit as st

from modules.daily_predictions.daily_predictions_engine import fetch_daily_predictions
from modules.daily_predictions.daily_predictions_ui import _render_grid, _render_card


def render_yellow_3_5_page(api) -> None:
    today_str = datetime.date.today().strftime("%d/%m/%Y")
    st.markdown(
        f"<h2 style='font-size:1.4rem;margin-bottom:6px;'>🟨 CARTONS JAUNES — OVER 3.5</h2>"
        f"<div style='color:#888;font-size:0.85rem;margin-bottom:10px;'>Top 20 IA pour Over 3.5 cartons jaunes · {today_str}</div>",
        unsafe_allow_html=True,
    )

    # Tentative silencieuse : valider les prédictions PENDING pour ce marché
    try:
        from modules.daily_predictions.daily_predictions_monitor_o3_5 import validate_pending as _validate_pending
        updated = _validate_pending(api)
        if updated:
            st.success(f"Mises à jour (cartons +3.5) : {len(updated)} prédiction(s) résolue(s)")
            st.rerun()
    except Exception:
        pass

    # Fetch predictions via engine
    with st.spinner("Analyse en cours…"):
        try:
            results = fetch_daily_predictions(api)
        except Exception as e:
            st.error(f"Erreur : {e}")
            results = {"yellow_cards_o3_5": []}

    yellow_list = results.get("yellow_cards_o3_5", [])[:20]

    # Enregistrer les prédictions affichées dans le registre dédié
    try:
        from modules.daily_predictions.prediction_registry_yellow_3_5 import register_prediction, prediction_exists, compute_real_stats
        for m in yellow_list:
            try:
                fid = m.get('fixture_id')
                if fid and not prediction_exists(fid):
                    register_prediction(m)
            except Exception:
                continue
    except Exception:
        # registre non disponible → continuer
        pass

    # Afficher statistiques réelles (30j + 7j + today)
    try:
        stats_30 = compute_real_stats(days=30)
        stats_7 = compute_real_stats(days=7)
        stats_1 = compute_real_stats(days=1)

        st.markdown(
            f"<div style='margin-top:8px;background:rgba(255,255,255,0.03);border-radius:8px;padding:8px;'>"
            f"<div style='font-weight:800;color:#fb923c;'>📊 Cartons jaunes +3.5 — statistiques réelles (30j)</div>"
            f"<div style='font-size:0.9rem;margin-top:6px;'>Validés: {stats_30['won']} · Échoués: {stats_30['lost']} · En attente: {stats_30['pending']} · Winrate: {stats_30['winrate']}% · ROI: {stats_30['roi']}%</div>"
            f"</div>", unsafe_allow_html=True
        )

        col_a, col_b = st.columns([1,1])
        with col_a:
            today_label = datetime.date.today().strftime("%d/%m/%Y")
            st.markdown(
                f"<div style='margin-top:8px;background:rgba(255,255,255,0.02);border-radius:8px;padding:8px;'>"
                f"<div style='font-weight:800;color:#fb923c;'>📅 Aujourd'hui — {today_label}</div>"
                f"<div style='font-size:0.9rem;margin-top:6px;'>Emis: {stats_1['total_emitted']} · Validés: {stats_1['won']} · Échoués: {stats_1['lost']} · En attente: {stats_1['pending']} · Winrate: {stats_1['winrate']}% · ROI: {stats_1['roi']}%</div>"
                f"</div>", unsafe_allow_html=True
            )
        with col_b:
            st.markdown(
                f"<div style='margin-top:8px;background:rgba(255,255,255,0.02);border-radius:8px;padding:8px;'>"
                f"<div style='font-weight:800;color:#f97316;'>🗓️ Dernière semaine (7j)</div>"
                f"<div style='font-size:0.9rem;margin-top:6px;'>Emis: {stats_7['total_emitted']} · Validés: {stats_7['won']} · Échoués: {stats_7['lost']} · En attente: {stats_7['pending']} · Winrate: {stats_7['winrate']}% · ROI: {stats_7['roi']}%</div>"
                f"</div>", unsafe_allow_html=True
            )
    except Exception:
        pass

    st.markdown("<div style='margin-top:10px;font-size:0.9rem;color:#888;'>Top 20 IA · Probabilités estimées par modèle Poisson · Données API-Football</div>", unsafe_allow_html=True)

    if not yellow_list:
        st.info("Aucun match carton jaune +3.5 correspondant aujourd'hui.")
        return

    try:
        _render_grid(yellow_list, "#fb923c", "Aucun match carton jaune +3.5 correspondant aujourd'hui.")
    except Exception:
        for m in yellow_list:
            _render_card(m, "#fb923c")


