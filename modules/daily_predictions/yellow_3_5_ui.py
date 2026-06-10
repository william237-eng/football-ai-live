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

    # Afficher statistiques réelles (30j + 7j + today) — usage du composant partagé
    try:
        from modules.daily_predictions.prediction_registry_yellow_3_5 import compute_real_stats
        from modules.shared.stats_ui import render_stats_block

        stats_30 = compute_real_stats(days=30)
        stats_7 = compute_real_stats(days=7)
        stats_1 = compute_real_stats(days=1)

        render_stats_block("📊 Cartons jaunes +3.5 — statistiques réelles", stats_1, stats_7, stats_30)
    except Exception:
        # si le registre n'est pas dispo, on continue silencieusement
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


