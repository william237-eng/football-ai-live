"""
under25_ui.py
=============
Interface complète pour la section TOP -2.5 BUTS (Under 2.5).
"""
from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from modules.top_under25_live.under25_monitor import (
    fetch_top_under25,
    refresh_live_matches,
    categorize_matches,
)

CONTINENT_OPTIONS = ["Tous", "Europe", "Amériques", "Asie", "Afrique", "Autre"]

STATUS_LABELS = {
    "NS":   ("⏳ À venir",     "#f59e0b", "rgba(245,158,11,0.12)"),
    "1H":   ("🟡 1ère MT",     "#f59e0b", "rgba(245,158,11,0.12)"),
    "HT":   ("🟡 Mi-temps",    "#f59e0b", "rgba(245,158,11,0.12)"),
    "2H":   ("🟡 2ème MT",     "#f59e0b", "rgba(245,158,11,0.12)"),
    "ET":   ("🟡 Prolong.",    "#f59e0b", "rgba(245,158,11,0.12)"),
    "BT":   ("🟡 Pause Prol.", "#f59e0b", "rgba(245,158,11,0.12)"),
    "P":    ("🟡 Tirs au but", "#f59e0b", "rgba(245,158,11,0.12)"),
    "FT":   ("⚫ Terminé",     "#888888", "rgba(128,128,128,0.10)"),
    "AET":  ("⚫ Terminé AET", "#888888", "rgba(128,128,128,0.10)"),
    "PEN":  ("⚫ Tirs au but", "#888888", "rgba(128,128,128,0.10)"),
    "LIVE": ("🔴 LIVE",        "#e02424", "rgba(224,36,36,0.12)"),
}


def _status_display(s: str):
    return STATUS_LABELS.get(s, ("⏳ " + s, "#888", "rgba(128,128,128,0.1)"))


def _prob_bar(pct: float, color: str) -> str:
    return (
        f"<div style='background:rgba(255,255,255,0.08);border-radius:4px;"
        f"height:8px;overflow:hidden;margin-top:6px;'>"
        f"<div style='width:{pct}%;height:8px;background:{color};"
        f"border-radius:4px;transition:width 0.4s;'></div></div>"
    )


def _render_pred_block(m: Dict[str, Any]) -> str:
    is_finished = m.get("is_finished", False)
    val         = m.get("validation")
    conf_col    = m.get("conf_color", "#888")
    conf_lbl    = m.get("conf_label", "—")

    if is_finished and val:
        init_pct = m.get("initial_pct", m.get("under25_pct", 0.0))
        return (
            f"<div style='margin-top:10px;padding:10px 12px;"
            f"background:rgba(255,255,255,0.04);border-radius:10px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<span style='font-size:0.8rem;color:#aaa;'>Prédiction initiale</span>"
            f"<span style='font-weight:800;color:#a855f7;font-size:0.95rem;'>UNDER 2.5 BUTS</span>"
            f"</div>"
            f"<div style='display:flex;justify-content:space-between;margin-top:6px;'>"
            f"<span style='font-size:0.78rem;color:#aaa;'>Probabilité estimée</span>"
            f"<span style='font-weight:800;font-size:1.0rem;color:{conf_col};'>{init_pct}%</span>"
            f"</div>"
            f"<div style='display:flex;justify-content:space-between;margin-top:4px;'>"
            f"<span style='font-size:0.75rem;color:#888;'>Confiance initiale</span>"
            f"<span style='font-size:0.8rem;color:{conf_col};font-weight:600;'>{conf_lbl}</span>"
            f"</div>"
            f"</div>"
        )
    else:
        pct = m.get("under25_pct", 0.0)
        locked = m.get("locked", False)
        if locked:
            reason = m.get("locked_reason", "")
            return (
                f"<div style='margin-top:10px;padding:10px 12px;"
                f"background:rgba(239,68,68,0.08);border-radius:10px;"
                f"border:1px solid rgba(239,68,68,0.3);'>"
                f"<div style='font-weight:800;color:#ef4444;font-size:0.9rem;'>🔒 {reason}</div>"
                f"<div style='font-size:0.75rem;color:#888;margin-top:4px;'>Under 2.5 impossible</div>"
                f"</div>"
            )
        return (
            f"<div style='margin-top:10px;padding:10px 12px;"
            f"background:rgba(255,255,255,0.04);border-radius:10px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<span style='font-size:0.8rem;color:#aaa;'>Prédiction estimée</span>"
            f"<span style='font-weight:800;color:#a855f7;font-size:0.95rem;'>UNDER 2.5 BUTS</span>"
            f"</div>"
            f"<div style='display:flex;justify-content:space-between;margin-top:6px;'>"
            f"<span style='font-size:0.8rem;color:#aaa;'>Probabilité</span>"
            f"<span style='font-weight:800;font-size:1.05rem;'>{pct}%</span>"
            f"</div>"
            + _prob_bar(pct, conf_col) +
            f"<div style='display:flex;justify-content:space-between;margin-top:6px;'>"
            f"<span style='font-size:0.78rem;color:#aaa;'>Confiance</span>"
            f"<span style='font-weight:700;color:{conf_col};font-size:0.82rem;'>{conf_lbl}</span>"
            f"</div>"
            f"</div>"
        )


def _render_match_card(m: Dict[str, Any]) -> None:
    status_short = m.get("status_short", "NS")
    s_label, s_color, s_bg = _status_display(status_short)
    is_live     = m.get("is_live", False)
    is_finished = m.get("is_finished", False)
    validation  = m.get("validation")
    locked      = m.get("locked", False)

    if validation:
        border_color = validation["border"]
        card_bg      = validation["bg"]
    elif locked:
        border_color = "#ef4444"
        card_bg      = "rgba(239,68,68,0.06)"
    elif is_live:
        border_color = "#a855f7"
        card_bg      = "rgba(168,85,247,0.06)"
    else:
        border_color = "rgba(255,255,255,0.12)"
        card_bg      = "rgba(255,255,255,0.03)"

    score_html = ""
    if is_live or is_finished:
        min_txt = f" {m['minute']}'" if m.get("minute", 0) > 0 else ""
        score_html = (
            f"<div style='font-size:1.5rem;font-weight:900;letter-spacing:2px;margin:6px 0;'>"
            f"{m['home_score']} — {m['away_score']}"
            f"<span style='font-size:0.8rem;color:#888;margin-left:8px;'>{min_txt}</span>"
            f"</div>"
        )
    else:
        score_html = (
            f"<div style='font-size:0.85rem;color:#888;margin:6px 0;'>"
            f"📅 {m.get('start_date_display','—')} à {m.get('start_time','—')}</div>"
        )

    xg_html = ""
    hxg, axg = m.get("home_xg", 0.0), m.get("away_xg", 0.0)
    if hxg + axg > 0:
        xg_html = f"<div style='font-size:0.72rem;color:#888;margin-top:2px;'>xG : {hxg} — {axg}</div>"

    val_html = ""
    if validation:
        val_html = (
            f"<div style='margin-top:10px;padding:8px 12px;"
            f"background:{validation['bg']};border-radius:8px;"
            f"border:1px solid {validation['border']};'>"
            f"<span style='font-weight:800;color:{validation['color']};font-size:0.95rem;'>"
            f"{validation['label']}</span>"
            f"<span style='color:#aaa;font-size:0.78rem;margin-left:8px;'>{validation['reason']}</span>"
            f"</div>"
        )

    flag  = m.get("league_flag", "")
    f_img = f"<img src='{flag}' style='height:14px;margin-right:4px;vertical-align:middle;'>" if flag else ""
    league_html = (
        f"<div style='font-size:0.75rem;color:#aaa;margin-bottom:6px;'>"
        f"{f_img}{m.get('league_name','—')} · {m.get('league_country','—')}"
        f"</div>"
    )

    # Badge source
    src = m.get("data_source", "estimated")
    src_badge = (
        "<span style='font-size:0.65rem;background:rgba(34,197,94,0.15);color:#22c55e;"
        "border-radius:10px;padding:2px 7px;font-weight:700;'>📡 Données réelles</span>"
        if src == "real" else
        "<span style='font-size:0.65rem;background:rgba(245,158,11,0.15);color:#f59e0b;"
        "border-radius:10px;padding:2px 7px;font-weight:700;'>⚙️ Données estimées</span>"
    )

    pred_block = _render_pred_block(m)

    card_html = "".join([
        f"<div style='background:{card_bg};border:1px solid {border_color};"
        f"border-radius:14px;padding:16px;margin-bottom:14px;'>",

        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"margin-bottom:8px;flex-wrap:wrap;gap:6px;'>"
        f"<span style='background:{s_bg};color:{s_color};border-radius:20px;"
        f"padding:3px 10px;font-size:0.75rem;font-weight:700;'>{s_label}</span>"
        f"<div style='display:flex;align-items:center;gap:6px;'>"
        + src_badge +
        f"<span style='font-size:0.72rem;color:#888;'>{m.get('start_time','—')}</span>"
        f"</div></div>",

        league_html,

        f"<div style='font-size:1.05rem;font-weight:800;text-align:center;margin:8px 0 4px;'>"
        f"{m['home_name']}"
        f"<span style='color:#888;font-size:0.9rem;margin:0 8px;'>VS</span>"
        f"{m['away_name']}</div>",

        f"<div style='text-align:center;'>{score_html}{xg_html}</div>",

        pred_block,
        val_html,
        "</div>",
    ])

    st.markdown(card_html, unsafe_allow_html=True)


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

def render_top_under25_page(api) -> None:
    import time as _time
    import datetime as _dt

    st.markdown(
        "<h2 style='font-size:1.6rem;margin-bottom:2px;'>🔒 TOP -2.5 BUTS</h2>"
        "<p style='color:#888;font-size:0.85rem;margin-bottom:14px;'>"
        "Sélection automatique · Matchs du jour · "
        "<span style='color:#a855f7;'>Matchs à faible score prévisible</span></p>",
        unsafe_allow_html=True,
    )

    col_cont, col_refresh = st.columns([3, 1])
    with col_cont:
        continent = st.selectbox(
            "Filtre continent",
            CONTINENT_OPTIONS,
            key="under25_continent",
            label_visibility="collapsed",
        )
    with col_refresh:
        force_refresh = st.button("🔄 Actualiser", use_container_width=True, key="under25_refresh")

    now_ts    = _time.time()
    CACHE_TTL = 30
    FULL_TTL  = 300

    cached       = st.session_state.get("under25_matches")
    last_full_ts = st.session_state.get("under25_last_full_ts", 0)
    last_ts      = st.session_state.get("under25_last_ts", 0)
    last_cont    = st.session_state.get("under25_last_continent", "Tous")

    need_full = (cached is None or force_refresh
                 or (now_ts - last_full_ts) > FULL_TTL
                 or last_cont != continent)
    need_live = not need_full and (now_ts - last_ts) > CACHE_TTL

    if need_full:
        with st.spinner("Analyse des matchs à faible score…"):
            try:
                matches = fetch_top_under25(api, continent_filter=continent)
            except Exception as e:
                st.error(f"Erreur : {e}")
                matches = []
        st.session_state["under25_matches"]          = matches
        st.session_state["under25_last_ts"]          = now_ts
        st.session_state["under25_last_full_ts"]     = now_ts
        st.session_state["under25_last_continent"]   = continent
    elif need_live:
        with st.spinner("Mise à jour live…"):
            try:
                matches = refresh_live_matches(api, cached)
            except Exception:
                matches = cached or []
        st.session_state["under25_matches"]  = matches
        st.session_state["under25_last_ts"]  = now_ts
    else:
        matches = cached or []

    if st.session_state.get("under25_last_ts", 0):
        dt_str = _dt.datetime.fromtimestamp(st.session_state["under25_last_ts"]).strftime("%H:%M:%S")
        st.caption(f"⏱️ Màj : {dt_str} · Auto-refresh 30s · Filtre : {continent}")

    cats      = categorize_matches(matches)
    active    = cats["active"]
    validated = cats["validated"]
    failed    = cats["failed"]

    total = len(active) + len(validated) + len(failed)
    if total == 0:
        st.info("Aucun match ne satisfait les critères Under 2.5 (≥ 60%) pour le moment.")
        return

    summary_html = (
        f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:18px;'>"
        f"<div style='background:rgba(255,255,255,0.04);border-radius:10px;padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;'>{total}</div>"
        f"<div style='font-size:0.72rem;color:#888;'>Total</div></div>"

        f"<div style='background:rgba(168,85,247,0.10);border-radius:10px;padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;color:#a855f7;'>{len(active)}</div>"
        f"<div style='font-size:0.72rem;color:#888;'>Actives 🔵</div></div>"

        f"<div style='background:rgba(34,197,94,0.10);border-radius:10px;padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;color:#22c55e;'>{len(validated)}</div>"
        f"<div style='font-size:0.72rem;color:#888;'>Validées ✅</div></div>"

        f"<div style='background:rgba(239,68,68,0.10);border-radius:10px;padding:10px;text-align:center;'>"
        f"<div style='font-size:1.3rem;font-weight:900;color:#ef4444;'>{len(failed)}</div>"
        f"<div style='font-size:0.72rem;color:#888;'>Échouées ❌</div></div>"
        f"</div>"
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    _section_header("🔵 PRÉDICTIONS ACTIVES", len(active), "#a855f7", "rgba(168,85,247,0.15)")
    if active:
        nb_live = sum(1 for m in active if m.get("is_live"))
        nb_ns   = len(active) - nb_live
        st.caption(f"🔴 {nb_live} en cours · ⏳ {nb_ns} à venir · Seuil : ≥ 60% · Total buts < 3")
        _render_cards_grid(active, "Aucune prédiction active.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:16px;color:#888;"
            "border:2px dashed rgba(168,85,247,0.15);border-radius:12px;font-size:0.85rem;'>"
            "Aucune prédiction Under 2.5 active pour le moment.</div>",
            unsafe_allow_html=True,
        )

    _section_header("✅ VALIDÉES", len(validated), "#22c55e", "rgba(34,197,94,0.15)")
    if validated:
        st.caption("Matchs terminés avec ≤ 2 buts")
        _render_cards_grid(validated, "Aucune validation.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:12px;color:#888;"
            "border:2px dashed rgba(34,197,94,0.15);border-radius:12px;font-size:0.85rem;'>"
            "Aucune validation pour le moment.</div>",
            unsafe_allow_html=True,
        )

    _section_header("❌ ÉCHOUÉES", len(failed), "#ef4444", "rgba(239,68,68,0.10)")
    if failed:
        st.caption("Matchs terminés avec 3+ buts")
        _render_cards_grid(failed, "Aucun échec.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:12px;color:#888;"
            "border:2px dashed rgba(239,68,68,0.10);border-radius:12px;font-size:0.85rem;'>"
            "Aucun échec pour le moment.</div>",
            unsafe_allow_html=True,
        )

    if any(m.get("is_live") for m in active):
        st.markdown(
            "<div style='font-size:0.75rem;color:#888;text-align:center;margin-top:10px;'>"
            "🔴 Matchs live détectés — appuyez sur 🔄 pour actualiser</div>",
            unsafe_allow_html=True,
        )
