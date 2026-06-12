"""
world_cup_ui.py
===============
Page dédiée : Coupe du Monde — sélection automatique IA
Affiche pour les matchs de la Coupe du Monde les rubriques demandées :
- 7 victoires prédictes
- 7 double chance
- 7 over 2.5 buts
- 7 under 2.5 buts
- 7 over 2.5 cartons jaunes
- 7 over 7.5 corners
- 7 GG (BTTS)
- 7 probable cartons rouges
Chaque rubrique est sans doublon (un match n'apparait qu'une fois) et les prédictions affichées
sont enregistrées dans `database/prediction_registry_worldcup.json` pour calcul des stats.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List

import streamlit as st

from services.football_api import FootballAPI
from modules.daily_predictions.daily_predictions_engine import analyze_fixtures_for_daily, _poisson_over, _poisson_prob
from modules.daily_predictions.daily_predictions_engine import _safe
from modules.world_cup.prediction_registry_worldcup import (
    register_prediction, prediction_exists, compute_real_stats,
)


# Helper: match filter for World Cup competitions
WC_KEYWORDS = ("world cup", "worldcup", "fifa world", "fifa world cup")

# Mapping affichage -> clé marché canonique utilisée pour l'enregistrement et les stats
MARKET_DISPLAY_TO_KEY = {
    "⚽ VICTOIRES": "VICTOIRE",
    "🔄 DOUBLE CHANCE": "DOUBLE CHANCE",
    "➕ OVER 2.5 BUTS": "OVER 2.5 BUTS",
    "➖ UNDER 2.5 BUTS": "UNDER 2.5 BUTS",
    "🟨 OVER 2.5 CARTONS JAUNES": "YELLOW_CARDS",
    "⚪ OVER 7.5 CORNERS": "CORNERS + CARTONS",
    "🎯 GG — LES DEUX MARQUENT": "GG (BTTS)",
    "🔴 AU MOINS 1 ROUGE": "RED_CARDS",
}

def _is_world_cup_league(league_name: str) -> bool:
    if not league_name:
        return False
    ln = league_name.lower()
    return any(k in ln for k in WC_KEYWORDS)


def _discover_world_cup_league_ids(api: FootballAPI) -> List[int]:
    ids = []
    try:
        current_year = datetime.date.today().year
        data = api.get_leagues(current=True, season=current_year)
        items = []
        if isinstance(data, dict) and "response" in data:
            items = data["response"] or []
        elif isinstance(data, list):
            items = data

        for item in items:
            league = item.get("league") if isinstance(item, dict) else item
            if not isinstance(league, dict):
                continue
            name = str(league.get("name", "")).lower()
            lid = league.get("id")
            if lid and any(k in name for k in WC_KEYWORDS):
                ids.append(int(lid))
    except Exception:
        pass
    return sorted(set(ids))


def _select_top_unique(results_map: Dict[str, List[Dict[str, Any]]], market_key: str, used_fids: set, limit: int = 7) -> List[Dict[str, Any]]:
    candidates = results_map.get(market_key, [])
    out = []
    for c in candidates:
        fid = c.get("fixture_id")
        if not fid or fid in used_fids:
            continue
        out.append(c)
        used_fids.add(fid)
        if len(out) >= limit:
            break
    return out


def render_world_cup_page(api: FootballAPI) -> None:
    st.markdown("<h2 style='font-size:1.4rem;margin-bottom:6px;'>🏆 COUPE DU MONDE — Sélections IA</h2>", unsafe_allow_html=True)
    st.markdown("<div style='color:#888;margin-bottom:10px;'>Sélection automatique des meilleurs matchs Coupe du Monde par marché · Top 7 par rubrique</div>", unsafe_allow_html=True)

    # Fetch upcoming fixtures (next 200) and filter World Cup leagues
    with st.spinner("Récupération des matchs Coupe du Monde…"):
        try:
            raw, meta = api.get_fixtures_next_n(n=50)
            fixtures = raw or []
        except Exception as e:
            st.error(f"Impossible de récupérer les fixtures: {e}")
            return

    wc_fixtures = [f for f in fixtures if _is_world_cup_league(((f.get('league') or {}).get('name') or ''))]

    if not wc_fixtures:
        # Fallback: récupérer d'abord la compétition principale World Cup (league_id=1)
        recovered = []
        seen_fixtures = set()
        try:
            direct_raw, _ = api.get_fixtures_next_n(n=50, league_id=1)
            for fx in direct_raw or []:
                fid = (fx.get('fixture') or {}).get('id')
                if fid and fid not in seen_fixtures:
                    seen_fixtures.add(fid)
                    recovered.append(fx)
        except Exception:
            direct_raw = []

        # Si rien, découvrir les ligues World Cup et récupérer leurs fixtures
        if not recovered:
            league_ids = _discover_world_cup_league_ids(api)
            for lid in league_ids:
                if lid == 1:
                    continue
                try:
                    raw_league, _ = api.get_fixtures_next_n(n=50, league_id=lid)
                    for fx in raw_league or []:
                        fid = (fx.get('fixture') or {}).get('id')
                        if fid and fid not in seen_fixtures:
                            seen_fixtures.add(fid)
                            recovered.append(fx)
                except Exception:
                    continue

        wc_fixtures = [f for f in recovered if _is_world_cup_league(((f.get('league') or {}).get('name') or ''))]

    if not wc_fixtures:
        st.info("Aucun match Coupe du Monde trouvé dans les prochaines fixtures (vérifie ta configuration API ou augmente la fenêtre).")
        return

    # Analyse via moteur pour obtenir prédictions par match
    with st.spinner("Analyse IA des matchs Coupe du Monde…"):
        try:
            results = analyze_fixtures_for_daily(wc_fixtures)
        except Exception as e:
            st.error(f"Erreur d'analyse: {e}")
            return

    used = set()
    sections = []

    # 1. Victoires (wins)
    wins_sel = _select_top_unique(results, "wins", used, limit=7)
    sections.append(("⚽ VICTOIRES (Top 7)", wins_sel, "#3b82f6"))

    # 2. Double Chance
    dc_sel = _select_top_unique(results, "double_chance", used, limit=7)
    sections.append(("🔄 DOUBLE CHANCE (Top 7)", dc_sel, "#8b5cf6"))

    # 3. Over 2.5 buts — compute from lam_h + lam_a
    over25_cands = []
    for win in results.get("wins", []) + results.get("double_chance", []) + results.get("btts", []) + results.get("corners_cards", []) + results.get("yellow_cards", []) + results.get("yellow_cards_o3_5", []) + results.get("red_cards", []):
        fid = win.get("fixture_id")
        if not fid:
            continue
        if fid in used:
            continue
        # lam_h / lam_a in win_probs
        wp = win.get("win_probs") or {}
        lam_h = _safe(wp.get("lam_h", 0.0))
        lam_a = _safe(wp.get("lam_a", 0.0))
        lam_total = max(0.3, lam_h + lam_a)
        # prob over 2.5 -> 1 - sum_{k=0..2} Poisson(lam_total,k)
        prob_under = sum(_poisson_prob(lam_total, k) for k in range(3))
        p_over25 = max(0.0, min(0.99, 1.0 - prob_under))
        entry = dict(win)
        entry["prob_over_25"] = round(p_over25, 4)
        entry["pct"] = round(p_over25 * 100, 1)
        over25_cands.append(entry)
    over25_cands.sort(key=lambda x: x.get("prob_over_25", 0), reverse=True)
    over25_sel = []
    for c in over25_cands:
        fid = c.get("fixture_id")
        if fid in used:
            continue
        over25_sel.append(c)
        used.add(fid)
        if len(over25_sel) >= 7:
            break
    sections.append(("➕ OVER 2.5 BUTS (Top 7)", over25_sel, "#10b981"))

    # 4. Under 2.5 — choose matches with high prob under
    under25_cands = []
    for win in results.get("wins", []) + results.get("double_chance", []) + results.get("btts", []) + results.get("corners_cards", []) + results.get("yellow_cards", []) + results.get("yellow_cards_o3_5", []) + results.get("red_cards", []):
        fid = win.get("fixture_id")
        if not fid or fid in used:
            continue
        wp = win.get("win_probs") or {}
        lam_h = _safe(wp.get("lam_h", 0.0))
        lam_a = _safe(wp.get("lam_a", 0.0))
        lam_total = max(0.3, lam_h + lam_a)
        prob_under = sum(_poisson_prob(lam_total, k) for k in range(3))
        p_under25 = max(0.0, min(0.99, prob_under))
        entry = dict(win)
        entry["prob_under_25"] = round(p_under25, 4)
        entry["pct"] = round(p_under25 * 100, 1)
        under25_cands.append(entry)
    under25_cands.sort(key=lambda x: x.get("prob_under_25", 0), reverse=True)
    under25_sel = []
    for c in under25_cands:
        fid = c.get("fixture_id")
        if fid in used:
            continue
        under25_sel.append(c)
        used.add(fid)
        if len(under25_sel) >= 7:
            break
    sections.append(("➖ UNDER 2.5 BUTS (Top 7)", under25_sel, "#ef4444"))

    # 5. Over 2.5 cartons jaunes — compute lam_cards
    yellow_cands = []
    for win in results.get("wins", []) + results.get("double_chance", []) + results.get("btts", []) + results.get("corners_cards", []) + results.get("yellow_cards", []) + results.get("yellow_cards_o3_5", []) + results.get("red_cards", []):
        fid = win.get("fixture_id")
        if not fid or fid in used:
            continue
        hs = win.get("home_stats") or {}
        as_ = win.get("away_stats") or {}
        win_rate_gap = abs(hs.get("win_rate", 0.0) - as_.get("win_rate", 0.0))
        lam_cards = max(2.0, min(6.0, 3.8 - win_rate_gap * 1.2))
        p_over2_5 = _poisson_over(lam_cards, 3)  # threshold 3 => >2.5
        entry = dict(win)
        entry["prob_over_2_5_yellow"] = round(p_over2_5, 4)
        entry["pct"] = round(p_over2_5 * 100, 1)
        yellow_cands.append(entry)
    yellow_cands.sort(key=lambda x: x.get("prob_over_2_5_yellow", 0), reverse=True)
    yellow_sel = []
    for c in yellow_cands:
        fid = c.get("fixture_id")
        if fid in used:
            continue
        yellow_sel.append(c)
        used.add(fid)
        if len(yellow_sel) >= 7:
            break
    sections.append(("🟨 OVER 2.5 CARTONS JAUNES (Top 7)", yellow_sel, "#f59e0b"))

    # 6. Over 7.5 corners — use results["corners_cards"] entries
    corners_sel = _select_top_unique(results, "corners_cards", used, limit=7)
    sections.append(("⚪ OVER 7.5 CORNERS (Top 7)", corners_sel, "#f59e0b"))

    # 7. GG (BTTS)
    btts_sel = _select_top_unique(results, "btts", used, limit=7)
    sections.append(("🎯 GG — LES DEUX MARQUENT (Top 7)", btts_sel, "#22c55e"))

    # 8. Red cards probable
    red_sel = _select_top_unique(results, "red_cards", used, limit=7)
    sections.append(("🔴 AU MOINS 1 ROUGE (Top 7)", red_sel, "#ef4444"))

    # Register displayed predictions in registry (use key marché canonique)
    for title, lst, _ in sections:
        for m in lst:
            try:
                fid = m.get("fixture_id")
                market_display = title.split("(")[0].strip()
                market_key = MARKET_DISPLAY_TO_KEY.get(market_display, market_display)
                # éviter doublons : vérifier aussi la clé affichée précédente
                if fid and not (prediction_exists(fid, market_key) or prediction_exists(fid, market_display)):
                    register_prediction(m, market_key)
            except Exception:
                continue

    # Display overall stats header
    st.markdown("<div style='margin-top:8px;font-size:0.9rem;color:#888;'>Statistiques réelles par rubrique (Aujourd'hui / 7j)</div>", unsafe_allow_html=True)

    # For each section, show stats and matches
    for title, lst, color in sections:
        market_display = title.split("(")[0].strip()
        market_key = MARKET_DISPLAY_TO_KEY.get(market_display, market_display)
        st.markdown(f"<h3 style='margin-top:12px;color:{color};'>{title}</h3>", unsafe_allow_html=True)
        try:
            from modules.shared.stats_ui import render_stats_block

            stats_1 = compute_real_stats(market=market_key, days=1)
            stats_7 = compute_real_stats(market=market_key, days=7)
            stats_30 = compute_real_stats(market=market_key, days=30)

            render_stats_block(f"📊 {market_display} — statistiques réelles", stats_1, stats_7, stats_30)
        except Exception:
            # Silencieux si registre/statistiques indisponibles
            pass

        # Historique des prédictions pour ce marché (résolus)
        try:
            from modules.world_cup.prediction_registry_worldcup import get_predictions_by_market
            from modules.shared.stats_ui import render_prediction_history

            preds = get_predictions_by_market(market_key)
            if preds:
                with st.expander(f"📜 Historique — {market_display} (validés / échoués)", expanded=False):
                    render_prediction_history(f"{market_display} — Historique", preds)
        except Exception:
            # continuer silencieusement si registre indisponible
            pass

        if not lst:
            st.info(f"Aucun match pour {market_display}.")
            continue

        # Render grid
        try:
            # reuse _render_grid from daily ui
            from modules.daily_predictions.daily_predictions_ui import _render_grid
            _render_grid(lst, color, f"Aucun match {market_display}.")
        except Exception:
            for m in lst:
                try:
                    from modules.daily_predictions.daily_predictions_ui import _render_card
                    _render_card(m, color)
                except Exception:
                    st.write(m)

    st.markdown("<div style='margin-top:12px;font-size:0.8rem;color:#666;'>Données estimées par modèle IA · Enregistrer les prédictions permet le suivi et la validation automatique.</div>", unsafe_allow_html=True)

