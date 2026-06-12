"""
red_cards_ui.py
===================
Page dédiée : CARTONS ROUGES — AU MOINS 1
Affiche le top 20 IA pour probabilité d'au moins 1 carton rouge, statistiques réelles (1j / 7j / 30j)
et validation automatique via le moniteur dédié.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List

import streamlit as st

from modules.daily_predictions.daily_predictions_engine import fetch_daily_predictions
from modules.daily_predictions.daily_predictions_ui import _render_grid, _render_card


def render_red_cards_page(api) -> None:
    today_str = datetime.date.today().strftime("%d/%m/%Y")
    st.markdown(
        f"<h2 style='font-size:1.4rem;margin-bottom:6px;'>🔴 CARTONS ROUGES — AU MOINS 1</h2>"
        f"<div style='color:#888;font-size:0.85rem;margin-bottom:10px;'>Top 20 IA pour Au moins 1 carton rouge · {today_str}</div>",
        unsafe_allow_html=True,
    )

    # Tentative silencieuse : valider les prédictions PENDING pour ce marché
    try:
        from modules.daily_predictions.daily_predictions_monitor_red import validate_pending as _validate_pending
        updated = _validate_pending(api)
        if updated:
            st.success(f"Mises à jour (cartons rouges) : {len(updated)} prédiction(s) résolue(s)")
            st.rerun()
    except Exception:
        pass

    # Fetch predictions via engine
    with st.spinner("Analyse en cours…"):
        try:
            results = fetch_daily_predictions(api)
        except Exception as e:
            st.error(f"Erreur : {e}")
            results = {"red_cards": []}

    red_list = results.get("red_cards", [])[:20]

    # Enregistrer les prédictions affichées dans le registre dédié
    try:
        from modules.daily_predictions.prediction_registry_red import register_prediction, prediction_exists, compute_real_stats
        for m in red_list:
            try:
                fid = m.get('fixture_id')
                if fid and not prediction_exists(fid):
                    register_prediction(m)
            except Exception:
                continue
    except Exception:
        # registre non disponible → continuer
        pass

    # Afficher statistiques réelles (30j / 7j / Aujourd'hui) via composant partagé
    try:
        from modules.daily_predictions.prediction_registry_red import compute_real_stats
        from modules.shared.stats_ui import render_stats_block

        stats_30 = compute_real_stats(days=30)
        stats_7 = compute_real_stats(days=7)
        stats_1 = compute_real_stats(days=1)

        render_stats_block("📊 Cartons rouges — statistiques réelles", stats_1, stats_7, stats_30)
    except Exception:
        # Ne pas bloquer la page si le registre/statistiques sont indisponibles
        pass

    # Historique des prédictions (validées / échouées)
    try:
        from modules.daily_predictions.prediction_registry_red import get_all_predictions
        from modules.shared.stats_ui import render_prediction_history

        preds = get_all_predictions()
        if preds:
            with st.expander("📜 Historique des prédictions — Cartons rouges (validés / échoués)", expanded=False):
                render_prediction_history("Cartons rouges — Historique", preds)
    except Exception:
        # Ne pas bloquer la page si le registre est indisponible
        pass

    st.markdown("<div style='margin-top:10px;font-size:0.9rem;color:#888;'>Top 20 IA · Probabilités estimées par modèle Poisson · Données API-Football</div>", unsafe_allow_html=True)

    if not red_list:
        st.info("Aucun match avec forte probabilité d'au moins 1 carton rouge aujourd'hui.")
        return

    try:
        _render_grid(red_list, "#ef4444", "Aucun match correspondant aujourd'hui.")
    except Exception:
        for m in red_list:
            _render_card(m, "#ef4444")

