"""
top_over25_ui.py
================
Interface complète pour la section TOP +2.5 BUTS.
Modulaire — ne modifie rien d'existant.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from modules.top_over25_live.match_monitor import fetch_top_over25, refresh_live_matches, categorize_matches
from modules.top_over25_live.metrics_engine import compute_all_periods


# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

CONTINENT_OPTIONS = ["Tous", "Europe", "Amériques", "Asie", "Afrique", "Autre"]

STATUS_LABELS = {
    "NS":   ("⏳ À venir",    "#f59e0b", "rgba(245,158,11,0.12)"),
    "1H":   ("🟡 1ère MT",    "#f59e0b", "rgba(245,158,11,0.12)"),
    "HT":   ("🟡 Mi-temps",   "#f59e0b", "rgba(245,158,11,0.12)"),
    "2H":   ("🟡 2ème MT",    "#f59e0b", "rgba(245,158,11,0.12)"),
    "ET":   ("🟡 Prolong.",   "#f59e0b", "rgba(245,158,11,0.12)"),
    "BT":   ("🟡 Pause Prol.","#f59e0b", "rgba(245,158,11,0.12)"),
    "P":    ("🟡 Tirs au but","#f59e0b", "rgba(245,158,11,0.12)"),
    "FT":   ("⚫ Terminé",    "#888888", "rgba(128,128,128,0.10)"),
    "AET":  ("⚫ Terminé AET","#888888", "rgba(128,128,128,0.10)"),
    "PEN":  ("⚫ Tirs au but","#888888", "rgba(128,128,128,0.10)"),
    "LIVE": ("🔴 LIVE",       "#e02424", "rgba(224,36,36,0.12)"),
}


def _status_display(status_short: str) -> tuple:
    return STATUS_LABELS.get(status_short, ("⏳ " + status_short, "#888", "rgba(128,128,128,0.1)"))


def _prob_bar(pct: float, color: str) -> str:
    return (
        f"<div style='background:rgba(255,255,255,0.08);border-radius:4px;"
        f"height:8px;overflow:hidden;margin-top:6px;'>"
        f"<div style='width:{pct}%;height:8px;background:{color};"
        f"border-radius:4px;transition:width 0.4s;'></div></div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bloc prédiction (différent selon état actif / terminé)
# ─────────────────────────────────────────────────────────────────────────────

def _render_pred_block(m: Dict[str, Any]) -> str:
    """
    Pour les matchs actifs (y compris live locked) : affiche prob actuelle.
    Pour les matchs terminés uniquement : affiche la prob initiale de prédiction.
    """
    is_finished = m.get("is_finished", False)
    val         = m.get("validation")
    conf_col    = m.get("conf_color", "#888")
    conf_lbl    = m.get("conf_label", "—")

    # Seulement pour les matchs réellement terminés (FT/AET/PEN)
    if is_finished and val:
        # Prédiction initiale uniquement
        init_pct = m.get("initial_pct", m.get("over25_pct", 0.0))
        return (
            f"<div style='margin-top:10px;padding:10px 12px;"
            f"background:rgba(255,255,255,0.04);border-radius:10px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;'>"
            f"<span style='font-size:0.8rem;color:#aaa;'>Prédiction initiale</span>"
            f"<span style='font-weight:800;color:#00d4ff;font-size:0.95rem;'>OVER 2.5 BUTS</span>"
            f"</div>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:6px;'>"
            f"<span style='font-size:0.78rem;color:#aaa;'>Probabilité estimée</span>"
            f"<span style='font-weight:800;font-size:1.0rem;color:{conf_col};'>{init_pct}%</span>"
            f"</div>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:4px;'>"
            f"<span style='font-size:0.75rem;color:#888;'>Confiance initiale</span>"
            f"<span style='font-size:0.8rem;color:{conf_col};font-weight:600;'>{conf_lbl}</span>"
            f"</div>"
            f"</div>"
        )
    else:
        # Match actif : prob actuelle + barre
        pct = m.get("over25_pct", 0.0)
        return (
            f"<div style='margin-top:10px;padding:10px 12px;"
            f"background:rgba(255,255,255,0.04);border-radius:10px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;'>"
            f"<span style='font-size:0.8rem;color:#aaa;'>Prédiction estimée</span>"
            f"<span style='font-weight:800;color:#00d4ff;font-size:0.95rem;'>OVER 2.5 BUTS</span>"
            f"</div>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:6px;'>"
            f"<span style='font-size:0.8rem;color:#aaa;'>Probabilité</span>"
            f"<span style='font-weight:800;font-size:1.05rem;'>{pct}%</span>"
            f"</div>"
            + _prob_bar(pct, conf_col) +
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:6px;'>"
            f"<span style='font-size:0.78rem;color:#aaa;'>Confiance</span>"
            f"<span style='font-weight:700;color:{conf_col};font-size:0.82rem;'>{conf_lbl}</span>"
            f"</div>"
            f"</div>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Carte individuelle d'un match
# ─────────────────────────────────────────────────────────────────────────────

def _render_match_card(m: Dict[str, Any]) -> None:
    status_short = m.get("status_short", "NS")
    s_label, s_color, s_bg = _status_display(status_short)
    is_live     = m.get("is_live", False)
    is_finished = m.get("is_finished", False)
    validation  = m.get("validation")
    locked      = m.get("locked", False)

    # Couleur de bordure principale
    if validation:
        border_color = validation["border"]
        card_bg      = validation["bg"]
    elif locked:
        border_color = "#22c55e"
        card_bg      = "rgba(34,197,94,0.08)"
    elif is_live:
        border_color = "#f59e0b"
        card_bg      = "rgba(245,158,11,0.06)"
    else:
        border_color = "rgba(255,255,255,0.12)"
        card_bg      = "rgba(255,255,255,0.03)"

    pct      = m.get("over25_pct", 0.0)
    conf_lbl = m.get("conf_label", "—")
    conf_col = m.get("conf_color", "#888")

    # Score live
    score_html = ""
    if is_live or is_finished:
        min_txt = f" {m['minute']}'" if m.get("minute", 0) > 0 else ""
        score_html = (
            f"<div style='font-size:1.5rem;font-weight:900;letter-spacing:2px;"
            f"margin:6px 0;'>"
            f"{m['home_score']} — {m['away_score']}"
            f"<span style='font-size:0.8rem;color:#888;margin-left:8px;'>{min_txt}</span>"
            f"</div>"
        )
    else:
        score_html = (
            f"<div style='font-size:0.85rem;color:#888;margin:6px 0;'>"
            f"📅 {m.get('start_date_display','—')} à {m.get('start_time','—')}</div>"
        )

    # xG si disponible
    xg_html = ""
    hxg = m.get("home_xg", 0.0)
    axg = m.get("away_xg", 0.0)
    if hxg + axg > 0:
        xg_html = (
            f"<div style='font-size:0.72rem;color:#888;margin-top:2px;'>"
            f"xG : {hxg} — {axg}</div>"
        )

    # Validation badge
    val_html = ""
    if validation:
        val_html = (
            f"<div style='margin-top:10px;padding:8px 12px;"
            f"background:{validation['bg']};border-radius:8px;"
            f"border:1px solid {validation['border']};'>"
            f"<span style='font-weight:800;color:{validation['color']};font-size:0.95rem;'>"
            f"{validation['label']}</span>"
            f"<span style='color:#aaa;font-size:0.78rem;margin-left:8px;'>"
            f"{validation['reason']}</span>"
            f"</div>"
        )
    elif locked:
        val_html = (
            f"<div style='margin-top:8px;font-size:0.82rem;color:#22c55e;font-weight:700;'>"
            f"🔒 {m.get('locked_reason','')}</div>"
        )

    # Ligue + pays
    flag = m.get("league_flag", "")
    flag_html = f"<img src='{flag}' style='height:14px;margin-right:4px;vertical-align:middle;'>" if flag else ""
    league_html = (
        f"<div style='font-size:0.75rem;color:#aaa;margin-bottom:6px;'>"
        f"{flag_html}{m.get('league_name','—')} · {m.get('league_country','—')}"
        f"</div>"
    )

    pred_block = _render_pred_block(m)

    # Badge source données
    data_source = m.get("data_source", "estimated")
    if data_source == "real":
        src_badge = (
            "<span style='font-size:0.65rem;background:rgba(34,197,94,0.15);"
            "color:#22c55e;border-radius:10px;padding:2px 7px;"
            "font-weight:700;'>📡 Données réelles</span>"
        )
    else:
        src_badge = (
            "<span style='font-size:0.65rem;background:rgba(245,158,11,0.15);"
            "color:#f59e0b;border-radius:10px;padding:2px 7px;"
            "font-weight:700;'>⚙️ Données estimées</span>"
        )

    card_html = "".join([
        f"<div style='background:{card_bg};border:1px solid {border_color};"
        f"border-radius:14px;padding:16px;margin-bottom:14px;'>",

        # Statut + source badge
        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"margin-bottom:8px;flex-wrap:wrap;gap:6px;'>"
        f"<span style='background:{s_bg};color:{s_color};border-radius:20px;"
        f"padding:3px 10px;font-size:0.75rem;font-weight:700;'>{s_label}</span>"
        f"<div style='display:flex;align-items:center;gap:6px;'>"
        + src_badge +
        f"<span style='font-size:0.72rem;color:#888;'>{m.get('start_time','—')}</span>"
        f"</div>"
        f"</div>",

        # Ligue
        league_html,

        # Équipes
        f"<div style='font-size:1.05rem;font-weight:800;text-align:center;margin:8px 0 4px;'>"
        f"{m['home_name']}"
        f"<span style='color:#888;font-size:0.9rem;margin:0 8px;'>VS</span>"
        f"{m['away_name']}</div>",

        # Score / Heure
        f"<div style='text-align:center;'>{score_html}{xg_html}</div>",

        # Prédiction + prob
        pred_block,

        # Résultat validation
        val_html,

        "</div>",
    ])

    st.markdown(card_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Performance moteur
# ─────────────────────────────────────────────────────────────────────────────

def _perf_card(label: str, m: Dict[str, Any]) -> str:
    won      = m["won"]
    lost     = m["lost"]
    total    = m["total"]
    winrate  = m["winrate"]
    roi      = m["roi"]
    profit   = m["profit"]

    wr_color = "#22c55e" if winrate >= 55 else "#f59e0b" if winrate >= 40 else "#ef4444"
    roi_color = "#22c55e" if roi >= 0 else "#ef4444"
    profit_sign = "+" if profit >= 0 else ""

    if total == 0:
        return (
            f"<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);"
            f"border-radius:12px;padding:14px;text-align:center;'>"
            f"<div style='font-size:0.85rem;font-weight:700;color:#aaa;margin-bottom:8px;'>{label}</div>"
            f"<div style='color:#888;font-size:0.8rem;'>Aucune donnée</div>"
            f"</div>"
        )

    return (
        f"<div style='background:rgba(167,139,250,0.07);border:1px solid rgba(167,139,250,0.2);"
        f"border-radius:12px;padding:14px;'>"
        f"<div style='font-size:0.85rem;font-weight:700;color:#a78bfa;margin-bottom:10px;text-align:center;'>"
        f"{label}</div>"

        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;'>"

        f"<div style='background:rgba(34,197,94,0.1);border-radius:8px;padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:#22c55e;'>{won}</div>"
        f"<div style='font-size:0.68rem;color:#888;'>Validés ✅</div></div>"

        f"<div style='background:rgba(239,68,68,0.1);border-radius:8px;padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:#ef4444;'>{lost}</div>"
        f"<div style='font-size:0.68rem;color:#888;'>Échoués ❌</div></div>"

        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:{wr_color};'>{winrate}%</div>"
        f"<div style='font-size:0.68rem;color:#888;'>Winrate</div></div>"

        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:{roi_color};'>{profit_sign}{roi}%</div>"
        f"<div style='font-size:0.68rem;color:#888;'>ROI simulé</div></div>"

        f"</div>"
        f"<div style='margin-top:8px;font-size:0.72rem;color:#888;text-align:center;'>"
        f"Profit simulé : {profit_sign}{profit}u · Cote {m['odd_used']} · {total} pari(s)"
        f"</div>"
        f"</div>"
    )


def _render_performance_block() -> None:
    try:
        periods = compute_all_periods()
    except Exception:
        st.caption("Historique non disponible (aucune prédiction enregistrée).")
        return

    today = periods["today"]
    week  = periods["week"]
    month = periods["month"]

    # Si aucune donnée dans aucune période
    if today["total"] + week["total"] + month["total"] == 0:
        st.markdown(
            "<div style='text-align:center;padding:16px;color:#aaa;font-size:0.82rem;"
            "border:2px dashed rgba(167,139,250,0.2);border-radius:10px;'>"
            "<div style='font-size:1.1rem;margin-bottom:6px;'>📊</div>"
            "<b style='color:#a78bfa;'>Aucune prédiction enregistrée</b><br>"
            "<span style='font-size:0.78rem;color:#666;'>"
            "Les statistiques réelles (validées / échouées) s'accumuleront automatiquement "
            "dès que des matchs prédits seront terminés aujourd'hui."
            "</span></div>",
            unsafe_allow_html=True,
        )
        return

    html = (
        f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:6px;'>"
        + _perf_card("📅 Aujourd'hui", today)
        + _perf_card("🗓️ 7 jours", week)
        + _perf_card("📆 30 jours", month)
        + f"</div>"
        f"<div style='font-size:0.7rem;color:#888;text-align:center;margin-top:2px;'>"
        f"ROI simulé basé sur une cote fixe de {week['odd_used']} (mise unitaire normalisée)</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Rendu d'une grille de cartes (générique)
# ─────────────────────────────────────────────────────────────────────────────

def _render_cards_grid(matches: List[Dict], empty_msg: str = "Aucun match.") -> None:
    if not matches:
        st.markdown(
            f"<div style='text-align:center;padding:20px;color:#888;"
            f"border:2px dashed rgba(255,255,255,0.08);border-radius:12px;font-size:0.85rem;'>"
            f"{empty_msg}</div>",
            unsafe_allow_html=True,
        )
        return

    n = len(matches)
    cols_count = 1 if n == 1 else 2 if n == 2 else 3
    cols = st.columns(cols_count)
    for i, m in enumerate(matches):
        with cols[i % cols_count]:
            _render_match_card(m)


def _section_header(title: str, count: int, color: str, bg: str) -> None:
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;margin:18px 0 10px;'>"
        f"<div style='height:3px;flex:1;background:rgba(255,255,255,0.07);border-radius:2px;'></div>"
        f"<span style='background:{bg};color:{color};border-radius:20px;"
        f"padding:5px 16px;font-size:0.88rem;font-weight:800;white-space:nowrap;'>"
        f"{title} <span style='opacity:0.7;font-size:0.78rem;'>({count})</span></span>"
        f"<div style='height:3px;flex:1;background:rgba(255,255,255,0.07);border-radius:2px;'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────

def render_top_over25_page(api) -> None:
    """Rendu complet de la page TOP +2.5 BUTS — 3 sections séparées."""
    import time as _time
    import datetime as _dt

    # ── Header ──────────────────────────────────────────────────────────
    st.markdown(
        "<h2 style='font-size:1.6rem;margin-bottom:2px;'>⚽ TOP +2.5 BUTS</h2>"
        "<p style='color:#888;font-size:0.85rem;margin-bottom:14px;'>"
        "Sélection automatique · Matchs du jour · "
        "<span style='color:#f59e0b;'>Probabilités estimées — pas de garantie</span></p>",
        unsafe_allow_html=True,
    )

    # ── Filtres ─────────────────────────────────────────────────────────
    col_cont, col_refresh = st.columns([3, 1])
    with col_cont:
        continent = st.selectbox(
            "Filtre continent",
            CONTINENT_OPTIONS,
            key="over25_continent",
            label_visibility="collapsed",
        )
    with col_refresh:
        force_refresh = st.button("🔄 Actualiser", use_container_width=True, key="over25_refresh")

    # ── Cache session ────────────────────────────────────────────────────
    now_ts       = _time.time()
    CACHE_TTL    = 30
    FULL_TTL     = 300
    cache_key    = "over25_matches"
    cache_ts_key = "over25_last_ts"
    full_ts_key  = "over25_last_full_ts"
    cont_key     = "over25_last_continent"

    cached       = st.session_state.get(cache_key)
    last_full_ts = st.session_state.get(full_ts_key, 0)
    last_ts      = st.session_state.get(cache_ts_key, 0)
    last_cont    = st.session_state.get(cont_key, "Tous")

    need_full = (cached is None or force_refresh
                 or (now_ts - last_full_ts) > FULL_TTL
                 or last_cont != continent)
    need_live = not need_full and (now_ts - last_ts) > CACHE_TTL

    if need_full:
        with st.spinner("Analyse des matchs du jour…"):
            try:
                matches = fetch_top_over25(api, continent_filter=continent)
            except Exception as e:
                st.error(f"Erreur : {e}")
                matches = []
        st.session_state[cache_key]    = matches
        st.session_state[cache_ts_key] = now_ts
        st.session_state[full_ts_key]  = now_ts
        st.session_state[cont_key]     = continent

    elif need_live:
        with st.spinner("Mise à jour live…"):
            try:
                matches = refresh_live_matches(api, cached)
            except Exception:
                matches = cached or []
        st.session_state[cache_key]    = matches
        st.session_state[cache_ts_key] = now_ts
    else:
        matches = cached or []

    # ── Timestamp ────────────────────────────────────────────────────────
    if st.session_state.get(cache_ts_key, 0):
        dt_str = _dt.datetime.fromtimestamp(st.session_state[cache_ts_key]).strftime("%H:%M:%S")
        st.caption(f"⏱️ Màj : {dt_str} · Auto-refresh toutes les 30 s · Filtre : {continent}")

    # ── Catégorisation ────────────────────────────────────────────────────
    cats = categorize_matches(matches)
    active    = cats["active"]
    validated = cats["validated"]
    failed    = cats["failed"]

    # ── Barre résumé ─────────────────────────────────────────────────────
    total = len(active) + len(validated) + len(failed)
    if total == 0:
        st.info("Aucun match ne satisfait les critères (≥ 65%) pour le moment. Revenez plus tard.")
        return

    summary_html = (
        f"<div style='display:grid;grid-template-columns:repeat(4,1fr);"
        f"gap:8px;margin-bottom:18px;'>"
        f"<div style='background:rgba(255,255,255,0.04);border-radius:10px;"
        f"padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;'>{total}</div>"
        f"<div style='font-size:0.72rem;color:#888;'>Total</div></div>"

        f"<div style='background:rgba(0,212,255,0.08);border-radius:10px;"
        f"padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;color:#00d4ff;'>{len(active)}</div>"
        f"<div style='font-size:0.72rem;color:#888;'>Actives 🔵</div></div>"

        f"<div style='background:rgba(34,197,94,0.10);border-radius:10px;"
        f"padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;color:#22c55e;'>{len(validated)}</div>"
        f"<div style='font-size:0.72rem;color:#888;'>Validées ✅</div></div>"

        f"<div style='background:rgba(239,68,68,0.10);border-radius:10px;"
        f"padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;color:#ef4444;'>{len(failed)}</div>"
        f"<div style='font-size:0.72rem;color:#888;'>Échouées ❌</div></div>"
        f"</div>"
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 0 — PERFORMANCE MOTEUR
    # ════════════════════════════════════════════════════════════════════
    _section_header("📊 PERFORMANCE MOTEUR", 0,
                    "#a78bfa", "rgba(167,139,250,0.15)")
    _render_performance_block()

    # ════════════════════════════════════════════════════════════════════
    # SECTION 1 — PRÉDICTIONS ACTIVES
    # ════════════════════════════════════════════════════════════════════
    _section_header("🔵 PRÉDICTIONS ACTIVES", len(active),
                    "#00d4ff", "rgba(0,212,255,0.15)")

    if active:
        nb_live_act = sum(1 for m in active if m.get("is_live"))
        nb_ns_act   = len(active) - nb_live_act
        st.caption(
            f"🔴 {nb_live_act} en cours · ⏳ {nb_ns_act} à venir · "
            f"Seuil : ≥ 65% · Minute ≤ 70 · Total buts < 3"
        )
        _render_cards_grid(
            active,
            "Aucune prédiction active pour le moment."
        )
    else:
        st.markdown(
            "<div style='text-align:center;padding:16px;color:#888;"
            "border:2px dashed rgba(0,212,255,0.15);border-radius:12px;font-size:0.85rem;'>"
            "Aucune prédiction active · Les matchs sélectionnés n'ont pas encore commencé "
            "ou sont au-delà de la minute 70.</div>",
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════
    # SECTION 2 — VALIDÉES ✅
    # ════════════════════════════════════════════════════════════════════
    _section_header("✅ VALIDÉES", len(validated),
                    "#22c55e", "rgba(34,197,94,0.15)")

    if validated:
        st.caption("Matchs terminés avec 3+ buts · ou matchs live ayant déjà atteint Over 2.5")
        _render_cards_grid(validated, "Aucune prédiction validée.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:12px;color:#888;"
            "border:2px dashed rgba(34,197,94,0.15);border-radius:12px;font-size:0.85rem;'>"
            "Aucune validation pour le moment.</div>",
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════
    # SECTION 3 — ÉCHOUÉES ❌
    # ════════════════════════════════════════════════════════════════════
    _section_header("❌ ÉCHOUÉES", len(failed),
                    "#ef4444", "rgba(239,68,68,0.15)")

    if failed:
        st.caption("Matchs terminés avec < 3 buts · ou matchs à > 85 min avec faible probabilité résiduelle")
        _render_cards_grid(failed, "Aucun échec pour le moment.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:12px;color:#888;"
            "border:2px dashed rgba(239,68,68,0.10);border-radius:12px;font-size:0.85rem;'>"
            "Aucun échec pour le moment.</div>",
            unsafe_allow_html=True,
        )

    # ── Indicateur live ──────────────────────────────────────────────────
    if any(m.get("is_live") for m in active):
        st.markdown(
            "<div style='font-size:0.75rem;color:#888;text-align:center;margin-top:10px;'>"
            "🔴 Matchs live détectés — appuyez sur 🔄 pour actualiser</div>",
            unsafe_allow_html=True,
        )
