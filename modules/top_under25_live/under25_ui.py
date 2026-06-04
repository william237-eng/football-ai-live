"""
under25_ui.py
=============
Interface IA UNDER 2.5 STRICT — Règles 1-8.
"""
from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from modules.top_under25_live.under25_monitor import (
    fetch_top_under25,
    refresh_live_matches,
    register_prediction,
    get_prediction_stats,
    get_predictions,
    REF_ODD,
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


def _under_score_bar(score: float) -> str:
    if score >= 90:
        color = "#a78bfa"
    elif score >= 80:
        color = "#22c55e"
    elif score >= 70:
        color = "#84cc16"
    elif score >= 65:
        color = "#f59e0b"
    else:
        color = "#ef4444"
    return (
        f"<div style='margin:6px 0;'>"
        f"<div style='display:flex;justify-content:space-between;margin-bottom:3px;'>"
        f"<span style='font-size:0.72rem;color:#aaa;'>UNDER SCORE</span>"
        f"<span style='font-size:0.82rem;font-weight:800;color:{color};'>{score}/100</span>"
        f"</div>"
        f"<div style='background:rgba(255,255,255,0.07);border-radius:6px;height:10px;overflow:hidden;'>"
        f"<div style='width:{min(score,100)}%;height:10px;background:{color};"
        f"border-radius:6px;transition:width 0.5s;'></div></div></div>"
    )


def _score_breakdown_html(bd: Dict[str, float]) -> str:
    if not bd:
        return ""
    rows = ""
    keys = ["Attack", "Defense", "Form", "H2H", "BTTS", "xG", "Live pressure"]
    maxes = {"Attack": 30, "Defense": 25, "Form": 20, "H2H": 15, "BTTS": 10,
             "xG": 8, "Live pressure": 7}
    labels_fr = {"Attack": "Attaque", "Defense": "Défense", "Form": "Forme",
                 "H2H": "H2H", "BTTS": "BTTS", "xG": "xG", "Live pressure": "Pression live"}
    for k in keys:
        v = bd.get(k, 0.0)
        mx = maxes.get(k, 10)
        pct = min(100, round(v / mx * 100)) if mx else 0
        rows += (
            f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:4px;'>"
            f"<span style='width:90px;font-size:0.68rem;color:#aaa;text-align:right;'>{labels_fr[k]}</span>"
            f"<div style='flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:7px;'>"
            f"<div style='width:{pct}%;height:7px;background:#a855f7;border-radius:4px;'></div></div>"
            f"<span style='width:36px;font-size:0.68rem;color:#a855f7;text-align:right;'>{v}</span>"
            f"</div>"
        )
    total = bd.get("Total", 0.0)
    return (
        f"<div style='margin-top:8px;padding:8px 10px;"
        f"background:rgba(168,85,247,0.05);border-radius:10px;"
        f"border:1px solid rgba(168,85,247,0.12);'>"
        f"<div style='font-size:0.72rem;color:#a855f7;font-weight:700;margin-bottom:6px;'>Détail UNDER SCORE</div>"
        + rows +
        f"<div style='border-top:1px solid rgba(255,255,255,0.06);margin-top:4px;padding-top:4px;"
        f"font-size:0.75rem;font-weight:800;color:#a855f7;text-align:right;'>Total = {total}/100</div>"
        f"</div>"
    )


def _render_match_card(m: Dict[str, Any], section: str = "active") -> None:
    status_short = m.get("status_short", "NS")
    s_label, s_color, s_bg = _status_display(status_short)
    is_live     = m.get("is_live", False)
    is_finished = m.get("is_finished", False)
    validation  = m.get("validation")
    locked      = m.get("locked", False)
    under_score = m.get("under_score", 0.0)
    conf_col    = m.get("conf_color", "#888")
    conf_lbl    = m.get("conf_label", "—")

    if validation:
        border_color = validation["border"]
        card_bg      = validation["bg"]
    elif locked:
        border_color = "#ef4444"
        card_bg      = "rgba(239,68,68,0.06)"
    elif is_live:
        border_color = "#a855f7"
        card_bg      = "rgba(168,85,247,0.08)"
    elif section == "future":
        border_color = "rgba(168,85,247,0.3)"
        card_bg      = "rgba(168,85,247,0.04)"
    else:
        border_color = "rgba(255,255,255,0.12)"
        card_bg      = "rgba(255,255,255,0.03)"

    # ── Score / heure ─────────────────────────────────────────────────────
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
        xg_html = f"<div style='font-size:0.72rem;color:#888;margin-top:2px;'>xG : {hxg:.2f} — {axg:.2f} (total {hxg+axg:.2f})</div>"

    # ── Flag / ligue ──────────────────────────────────────────────────────
    flag  = m.get("league_flag", "")
    f_img = f"<img src='{flag}' style='height:14px;margin-right:4px;vertical-align:middle;'>" if flag else ""
    league_html = (
        f"<div style='font-size:0.75rem;color:#aaa;margin-bottom:6px;'>"
        f"{f_img}{m.get('league_name','—')} · {m.get('league_country','—')}"
        f"</div>"
    )

    # ── Badge source ──────────────────────────────────────────────────────
    src = m.get("data_source", "estimated")
    src_badge = (
        "<span style='font-size:0.65rem;background:rgba(34,197,94,0.15);color:#22c55e;"
        "border-radius:10px;padding:2px 7px;font-weight:700;'>📡 Réelles</span>"
        if src == "real" else
        "<span style='font-size:0.65rem;background:rgba(245,158,11,0.15);color:#f59e0b;"
        "border-radius:10px;padding:2px 7px;font-weight:700;'>⚙️ Estimées</span>"
    )

    # ── UNDER_SCORE bar ───────────────────────────────────────────────────
    score_bar = _under_score_bar(under_score)

    # ── Probabilité + confiance ───────────────────────────────────────────
    pct = m.get("under25_pct", 0.0)
    prob_html = (
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='font-size:0.8rem;color:#aaa;'>Prob. UNDER 2.5</span>"
        f"<span style='font-weight:900;font-size:1.1rem;color:{conf_col};'>{pct}%</span>"
        f"</div>"
        + _prob_bar(pct, conf_col) +
        f"<div style='display:flex;justify-content:space-between;margin-top:6px;'>"
        f"<span style='font-size:0.75rem;color:#aaa;'>Confiance</span>"
        f"<span style='font-weight:700;color:{conf_col};font-size:0.8rem;'>{conf_lbl}</span>"
        f"</div>"
    )

    # ── Score probable + BTTS ─────────────────────────────────────────────
    ps = m.get("probable_score", (1, 0))
    btts_lbl = m.get("btts_label", "—")
    btts_col = "#22c55e" if btts_lbl == "Oui" else "#ef4444" if btts_lbl == "Non" else "#f59e0b"
    extra_html = (
        f"<div style='margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;'>"
        f"<div style='flex:1;background:rgba(168,85,247,0.08);border-radius:8px;"
        f"padding:7px 10px;text-align:center;'>"
        f"<div style='font-size:0.68rem;color:#aaa;'>Score probable</div>"
        f"<div style='font-size:1.0rem;font-weight:900;color:#a855f7;'>{ps[0]} — {ps[1]}</div>"
        f"</div>"
        f"<div style='flex:1;background:rgba(255,255,255,0.04);border-radius:8px;"
        f"padding:7px 10px;text-align:center;'>"
        f"<div style='font-size:0.68rem;color:#aaa;'>BTTS</div>"
        f"<div style='font-size:1.0rem;font-weight:900;color:{btts_col};'>{btts_lbl}</div>"
        f"</div>"
        f"<div style='flex:1;background:rgba(255,255,255,0.04);border-radius:8px;"
        f"padding:7px 10px;text-align:center;'>"
        f"<div style='font-size:0.68rem;color:#aaa;'>xG total</div>"
        f"<div style='font-size:1.0rem;font-weight:900;color:#888;'>{round(hxg+axg,2) if hxg+axg else m.get('lambda_val','—')}</div>"
        f"</div>"
        f"</div>"
    )

    # ── Analyse IA (Règle 5) ──────────────────────────────────────────────
    reasons = m.get("ai_reasons") or []
    reasons_html = ""
    if reasons:
        items = "".join(
            f"<div style='font-size:0.72rem;color:#ccc;margin-bottom:3px;padding-left:4px;'>{r}</div>"
            for r in reasons
        )
        reasons_html = (
            f"<div style='margin-top:8px;padding:8px 10px;"
            f"background:rgba(255,255,255,0.03);border-radius:8px;'>"
            f"<div style='font-size:0.72rem;color:#a855f7;font-weight:700;margin-bottom:4px;'>Analyse IA</div>"
            + items +
            f"</div>"
        )

    # ── Breakdown (Règle 5) ───────────────────────────────────────────────
    breakdown_html = _score_breakdown_html(m.get("score_breakdown") or {})

    # ── Validation (Règle 6) ──────────────────────────────────────────────
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

    card_html = "".join([
        f"<div style='background:{card_bg};border:1px solid {border_color};"
        f"border-radius:14px;padding:16px;margin-bottom:14px;'>",

        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"margin-bottom:6px;flex-wrap:wrap;gap:6px;'>"
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

        f"<div style='margin-top:8px;padding:10px;background:rgba(255,255,255,0.03);"
        f"border-radius:10px;'>"
        + score_bar +
        f"</div>",

        f"<div style='margin-top:8px;padding:10px;background:rgba(255,255,255,0.03);"
        f"border-radius:10px;'>"
        + prob_html +
        f"</div>",

        extra_html,
        reasons_html,
        breakdown_html,
        val_html,
        "</div>",
    ])

    st.markdown(card_html, unsafe_allow_html=True)


def _render_cards_grid(matches: List[Dict], section: str = "active", empty_msg: str = "Aucun match.") -> None:
    if not matches:
        st.markdown(
            f"<div style='text-align:center;padding:20px;color:#888;"
            f"border:2px dashed rgba(255,255,255,0.08);border-radius:12px;font-size:0.85rem;'>"
            f"{empty_msg}</div>",
            unsafe_allow_html=True,
        )
        return
    n = len(matches)
    cols_count = 1 if n == 1 else 2 if n <= 4 else 3
    cols = st.columns(cols_count)
    for i, m in enumerate(matches):
        with cols[i % cols_count]:
            _render_match_card(m, section=section)


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
# Statistiques réelles (Règle 7)
# ─────────────────────────────────────────────────────────────────────────────

def _render_stats_block() -> None:
    """
    Statistiques basées UNIQUEMENT sur prediction_history_db.
    Winrate = '--' si 0 résolu. ROI réel (Problèmes 2, 4, 5).
    """
    stats = get_prediction_stats()
    n       = stats["resolved"]
    wins    = stats["wins"]
    losses  = stats["losses"]
    pending = stats["pending"]
    wr_str  = stats["winrate_str"]   # "--" si 0 résolu
    roi     = stats["roi"]           # None si 0 résolu
    profit  = stats["profit"]

    if n == 0:
        st.markdown(
            "<div style='text-align:center;padding:18px;color:#aaa;"
            "border:2px dashed rgba(168,85,247,0.15);border-radius:12px;'>"
            "<div style='font-size:1.2rem;margin-bottom:6px;'>📊</div>"
            "<b style='color:#a855f7;'>Aucune prédiction résolue</b><br>"
            f"<span style='font-size:0.76rem;color:#666;'>"
            f"{pending} en attente · Winrate : -- · ROI : --"
            "</span></div>",
            unsafe_allow_html=True,
        )
        return

    wr_pct  = stats["winrate_pct"]
    sign    = "+" if (profit or 0) >= 0 else ""
    wr_col  = "#22c55e" if (wr_pct or 0) >= 55 else "#f59e0b" if (wr_pct or 0) >= 40 else "#ef4444"
    roi_col = "#22c55e" if (roi or 0) >= 0 else "#ef4444"
    roi_str = f"{sign}{roi}%" if roi is not None else "--"
    prof_str = f"{sign}{profit}u" if profit is not None else "--"

    html = (
        f"<div style='background:rgba(168,85,247,0.06);border:1px solid rgba(168,85,247,0.18);"
        f"border-radius:12px;padding:14px;'>"
        f"<div style='font-size:0.85rem;font-weight:800;color:#a855f7;text-align:center;margin-bottom:10px;'>"
        f"📊 STATISTIQUES RÉELLES — PRÉDICTIONS ÉMISES</div>"
        f"<div style='display:grid;grid-template-columns:repeat(2,1fr);gap:6px;'>"
        f"<div style='background:rgba(34,197,94,0.1);border-radius:8px;padding:8px;text-align:center;'>"
        f"<div style='font-size:1.2rem;font-weight:900;color:#22c55e;'>{wins}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Gains ✅ (≤2 buts)</div></div>"
        f"<div style='background:rgba(239,68,68,0.1);border-radius:8px;padding:8px;text-align:center;'>"
        f"<div style='font-size:1.2rem;font-weight:900;color:#ef4444;'>{losses}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Pertes ❌ (3+ buts)</div></div>"
        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:8px;text-align:center;'>"
        f"<div style='font-size:1.2rem;font-weight:900;color:{wr_col};'>{wr_str}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Winrate réel</div></div>"
        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:8px;text-align:center;'>"
        f"<div style='font-size:1.2rem;font-weight:900;color:{roi_col};'>{roi_str}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>ROI réel</div></div>"
        f"</div>"
        f"<div style='margin-top:6px;font-size:0.65rem;color:#888;text-align:center;'>"
        f"Profit : {prof_str} · Cote ref. {REF_ODD} · {n} résolues · {pending} en attente"
        f"</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_prediction_tables() -> None:
    """Affiche deux tableaux : prédictions émises aujourd'hui et sur 7 jours.
    Les lignes sont colorées : vert = gain (win), rouge = perte (loss), neutre = pending.
    """
    try:
        today_preds = get_predictions(days=1)
        week_preds = get_predictions(days=7)
    except Exception:
        st.caption("Impossible de récupérer les prédictions.")
        return

    def _table_html(preds):
        if not preds:
            return "<div style='text-align:center;color:#888;padding:10px;'>Aucune prédiction</div>"
        rows = []
        for p in preds:
            status = p.get("status", "pending")
            if status == "win":
                bg = "rgba(34,197,94,0.10)"
                color = "#0f5132"
            elif status == "loss":
                bg = "rgba(239,68,68,0.08)"
                color = "#5f2120"
            else:
                bg = "rgba(255,255,255,0.02)"
                color = "#666"
            time = p.get("timestamp_prediction", "")
            teams = f"{p.get('home_name','—')} — {p.get('away_name','—')}"
            prob = f"{round(p.get('probability', 0)*100, 1)}%" if isinstance(p.get('probability', 0), float) and p.get('probability', 0) <= 1 else f"{p.get('probability', p.get('probability', 0))}"
            # normalize probability display
            try:
                prob_val = float(p.get('probability', 0))
                if prob_val <= 1:
                    prob = f"{round(prob_val*100,1)}%"
            except Exception:
                pass
            status_lbl = "GAGNÉ" if status == "win" else "PERDU" if status == "loss" else "EN ATTENTE"
            rows.append(
                f"<tr style='background:{bg};color:{color};font-weight:700;'>"
                f"<td style='padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.03);'>{time}</td>"
                f"<td style='padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.03);'>{teams}</td>"
                f"<td style='padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.03);text-align:center;'>{prob}</td>"
                f"<td style='padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.03);text-align:center;'>{status_lbl}</td>"
                f"</tr>"
            )
        body = "".join(rows)
        return (
            f"<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
            f"<thead><tr style='color:#aaa;font-weight:800;background:rgba(255,255,255,0.02);'>"
            f"<th style='text-align:left;padding:6px 8px;'>Prédit le</th>"
            f"<th style='text-align:left;padding:6px 8px;'>Match</th>"
            f"<th style='padding:6px 8px;text-align:center;'>Prob.</th>"
            f"<th style='padding:6px 8px;text-align:center;'>Statut</th>"
            f"</tr></thead><tbody>{body}</tbody></table>"
        )

    html = (
        "<div style='display:flex;gap:12px;margin-bottom:12px;'>"
        f"<div style='flex:1;background:rgba(255,255,255,0.02);padding:10px;border-radius:8px;'>"
        f"<div style='font-weight:800;color:#a855f7;margin-bottom:8px;'>Aujourd'hui</div>" + _table_html(today_preds) + "</div>"
        f"<div style='flex:1;background:rgba(255,255,255,0.02);padding:10px;border-radius:8px;'>"
        f"<div style='font-weight:800;color:#a855f7;margin-bottom:8px;'>7 jours</div>" + _table_html(week_preds) + "</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_detailed_tables() -> None:
    """Affiche deux tableaux détaillés : Prédictions du jour et Statistiques cette semaine

    Mise en forme identique au module TOP +2.5 BUTS.
    """
    try:
        from modules.top_under25_live.under25_monitor import get_predictions
        from datetime import datetime, timezone, timedelta
    except Exception:
        st.caption("Impossible de récupérer les prédictions.")
        return

    all_today = get_predictions(days=1)
    all_week = get_predictions(days=7)

    def _row_html(p: dict) -> str:
        status = p.get("status", "pending")
        if status == "win":
            row_bg = "rgba(34,197,94,0.06)"
            left = "#22c55e"
            status_label = "WON"
        elif status == "loss":
            row_bg = "rgba(239,68,68,0.06)"
            left = "#ef4444"
            status_label = "LOST"
        else:
            row_bg = "rgba(255,255,255,0.02)"
            left = "#9ca3af"
            status_label = "PENDING"

        ts = (p.get("timestamp_prediction") or "")[:16].replace("T", " ")
        home = p.get("home_name", "?")
        away = p.get("away_name", "?")
        pred = p.get("predicted_market") or "UNDER 2.5"
        return (
            f"<tr style='background:{row_bg};'>"
            f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);color:{left};font-weight:800;'>{status_label}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{ts}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{home} vs {away}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{pred}</td>"
            f"</tr>"
        )

    # Tableau aujourd'hui
    st.markdown("<div style='margin-top:14px;font-weight:700;'>Prédictions du jour</div>", unsafe_allow_html=True)
    if all_today:
        rows = "".join(_row_html(p) for p in all_today)
        table_html = (
            "<table style='width:100%;border-collapse:collapse;margin-top:8px;'>"
            "<thead><tr>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Statut</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Heure</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Match</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Prédiction</th>"
            "</tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.caption("Aucune prédiction émise aujourd'hui.")

    # Tableau 7 jours
    st.markdown("<div style='margin-top:18px;font-weight:700;'>Statistiques cette semaine</div>", unsafe_allow_html=True)
    if all_week:
        rows = "".join(_row_html(p) for p in all_week)
        table_html = (
            "<table style='width:100%;border-collapse:collapse;margin-top:8px;'>"
            "<thead><tr>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Statut</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Heure</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Match</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Prédiction</th>"
            "</tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.caption("Aucune prédiction émise ces 7 derniers jours.")

    # Historique (dernier 50)
    try:
        history = get_predictions(days=3650)[:50]
    except Exception:
        history = []
    with st.expander("📜 Historique des prédictions (dernier 50)", expanded=False):
        if not history:
            st.caption("Aucune prédiction enregistrée.")
        else:
            for p in history:
                status = p.get("status", "pending")
                if status == "win":
                    s_color = "#22c55e"
                    s_label = "✅ GAGNÉ"
                elif status == "loss":
                    s_color = "#ef4444"
                    s_label = "❌ PERDU"
                else:
                    s_color = "#f59e0b"
                    s_label = "⏳ Attente"

                ts = (p.get("timestamp_prediction") or "")[:16].replace("T", " ")
                home = p.get("home_name", "?")
                away = p.get("away_name", "?")
                pred_lbl = p.get("predicted_market", "UNDER 2.5")
                prob = p.get("probability", 0.0)
                prob_display = f"{round(prob*100,1)}%" if isinstance(prob, float) and prob <= 1 else str(prob)
                row = (
                    f"<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;"
                    f"padding:10px 14px;margin-bottom:6px;background:rgba(255,255,255,0.03);"
                    f"border:1px solid rgba(255,255,255,0.07);border-radius:10px;'>"
                    f"<span style='font-size:0.75rem;color:{s_color};font-weight:800;min-width:72px;'>{s_label}</span>"
                    f"<div style='flex:1;min-width:0;'>"
                    f"<div style='font-size:0.82rem;font-weight:700;color:#e2e8f0;'>{home} vs {away}</div>"
                    f"<div style='font-size:0.70rem;color:#6b7280;'>{pred_lbl}</div>"
                    f"</div>"
                    f"<div style='text-align:right;'>"
                    f"<div style='font-size:0.78rem;color:#00d4ff;font-weight:700;'>{prob_display}</div>"
                    f"<div style='font-size:0.68rem;color:#6b7280;'>{ts}</div>"
                    f"</div></div>"
                )
                st.markdown(row, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────

def render_top_under25_page(api) -> None:
    import time as _time
    import datetime as _dt

    st.markdown(
        "<h2 style='font-size:1.6rem;margin-bottom:2px;'>🔒 TOP -2.5 BUTS INTELLIGENT</h2>"
        "<p style='color:#888;font-size:0.82rem;margin-bottom:16px;'>"
        "Sélection IA stricte · Max 5 Live + 5 Futurs · "
        "<span style='color:#a855f7;'>Qualité avant quantité · UNDER_SCORE ≥55</span></p>",
        unsafe_allow_html=True,
    )

    # Tentative silencieuse : valider les prédictions PENDING via un validateur dédié
    try:
        from modules.top_under25_live.under25_monitor import validate_pending as _validate_pending
        updated = _validate_pending(api)
        if updated:
            st.success(f"Mises à jour : {len(updated)} prédiction(s) résolue(s)")
            st.rerun()
    except Exception:
        pass

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
    cache_key    = "under25_data"
    cache_ts_key = "under25_last_ts"
    full_ts_key  = "under25_last_full_ts"
    cont_key     = "under25_last_continent"

    cached       = st.session_state.get(cache_key)
    last_full_ts = st.session_state.get(full_ts_key, 0)
    last_ts      = st.session_state.get(cache_ts_key, 0)
    last_cont    = st.session_state.get(cont_key, "Tous")

    need_full = (cached is None or force_refresh
                 or (now_ts - last_full_ts) > FULL_TTL
                 or last_cont != continent)
    need_live = not need_full and (now_ts - last_ts) > CACHE_TTL

    if need_full:
        with st.spinner("🔍 Analyse IA des matchs à faible score…"):
            try:
                data = fetch_top_under25(api, continent_filter=continent)
            except Exception as e:
                st.error(f"Erreur : {e}")
                data = {"live": [], "future": [], "resolved": []}
        st.session_state[cache_key]    = data
        st.session_state[cache_ts_key] = now_ts
        st.session_state[full_ts_key]  = now_ts
        st.session_state[cont_key]     = continent
    elif need_live:
        with st.spinner("⚡ Mise à jour live…"):
            try:
                data = refresh_live_matches(api, cached)
            except Exception:
                data = cached or {"live": [], "future": [], "resolved": []}
        st.session_state[cache_key]    = data
        st.session_state[cache_ts_key] = now_ts
    else:
        data = cached or {"live": [], "future": [], "resolved": []}

    live_matches     = data.get("live")     or []
    future_matches   = data.get("future")   or []
    resolved_matches = data.get("resolved") or []

    validated_res = [m for m in resolved_matches if (m.get("validation") or {}).get("result") == "VALIDATED"]
    failed_res    = [m for m in resolved_matches if (m.get("validation") or {}).get("result") == "FAILED"]

    if st.session_state.get(cache_ts_key, 0):
        dt_str = _dt.datetime.fromtimestamp(st.session_state[cache_ts_key]).strftime("%H:%M:%S")
        st.caption(
            f"⏱️ Màj : {dt_str} · Auto-refresh 30s · Filtre : {continent} · "
            f"🔴 {len(live_matches)} live · 🟣 {len(future_matches)} futurs"
        )

    # Barre résumé
    summary_html = (
        f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:20px;'>"
        f"<div style='background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);"
        f"border-radius:12px;padding:12px;text-align:center;'>"
        f"<div style='font-size:1.5rem;font-weight:900;color:#ef4444;'>{len(live_matches)}</div>"
        f"<div style='font-size:0.7rem;color:#aaa;margin-top:2px;'>🔴 Live</div></div>"
        f"<div style='background:rgba(168,85,247,0.08);border:1px solid rgba(168,85,247,0.2);"
        f"border-radius:12px;padding:12px;text-align:center;'>"
        f"<div style='font-size:1.5rem;font-weight:900;color:#a855f7;'>{len(future_matches)}</div>"
        f"<div style='font-size:0.7rem;color:#aaa;margin-top:2px;'>🟣 Futurs</div></div>"
        f"<div style='background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);"
        f"border-radius:12px;padding:12px;text-align:center;'>"
        f"<div style='font-size:1.5rem;font-weight:900;color:#22c55e;'>{len(validated_res)}</div>"
        f"<div style='font-size:0.7rem;color:#aaa;margin-top:2px;'>✅ Validés</div></div>"
        f"<div style='background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.15);"
        f"border-radius:12px;padding:12px;text-align:center;'>"
        f"<div style='font-size:1.5rem;font-weight:900;color:#ef4444;'>{len(failed_res)}</div>"
        f"<div style='font-size:0.7rem;color:#aaa;margin-top:2px;'>❌ Échoués</div></div>"
        f"</div>"
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    total_sel = len(live_matches) + len(future_matches)
    if total_sel == 0 and not resolved_matches:
        st.markdown(
            "<div style='text-align:center;padding:30px;color:#888;"
            "border:2px dashed rgba(255,255,255,0.08);border-radius:16px;'>"
            "<div style='font-size:2rem;margin-bottom:8px;'>🔒</div>"
            "<b style='color:#a855f7;font-size:1.0rem;'>Le moteur préfère ne rien proposer<br>"
            "plutôt que proposer de mauvais UNDER</b><br>"
            "<span style='font-size:0.76rem;color:#666;margin-top:6px;display:block;'>"
            "UNDER_SCORE ≥55 · Prob ≥55% · Qualité avant quantité"
            "</span></div>",
            unsafe_allow_html=True,
        )
        _section_header("📊 STATISTIQUES RÉELLES", 0, "#a855f7", "rgba(168,85,247,0.15)")
        _render_stats_block()
        return

    # ══ SECTION 1 — LIVE ══════════════════════════════════════════════════
    _section_header("🔴 MATCHS LIVE UNDER 2.5", len(live_matches), "#ef4444", "rgba(239,68,68,0.15)")
    if live_matches:
        st.caption(
            "5' ≤ minute ≤ 75' · ≤2 buts · prob ≥55% · "
            "UNDER_SCORE ≥55 · ≥2 tirs · ≥1 corner · ≤1 rouge"
        )
        for _m in live_matches:
            register_prediction(_m)
        _render_cards_grid(live_matches, section="live",
                           empty_msg="Aucun match live ne satisfait les critères.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:16px;color:#888;"
            "border:2px dashed rgba(239,68,68,0.15);border-radius:12px;font-size:0.84rem;'>"
            "🔴 Aucun match live sélectionné · Critères IA stricts non satisfaits</div>",
            unsafe_allow_html=True,
        )

    # ══ SECTION 2 — FUTURS ════════════════════════════════════════════════
    _section_header("🟣 MATCHS FUTURS UNDER 2.5", len(future_matches), "#a855f7", "rgba(168,85,247,0.15)")
    if future_matches:
        st.caption(
            "prob ≥60% · xG ≤2.8 · avg_goals ≤3.2 · BTTS ≤65% · H2H under ≥40% · UNDER_SCORE ≥55"
        )
        for _m in future_matches:
            register_prediction(_m)
        _render_cards_grid(future_matches, section="future",
                           empty_msg="Aucun match futur ne satisfait les critères.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:16px;color:#888;"
            "border:2px dashed rgba(168,85,247,0.15);border-radius:12px;font-size:0.84rem;'>"
            "🟣 Aucun match futur sélectionné pour le moment</div>",
            unsafe_allow_html=True,
        )

    # Afficher les tableaux prédictions après enregistrement des live/futurs
    try:
        # Prefer persistent registry (cross-session) — si vide, utiliser session_state
        try:
            from modules.top_under25_live.prediction_registry import get_all_predictions
            all_preds = get_all_predictions()
        except Exception:
            all_preds = []
        if all_preds:
            preds_today = [p for p in all_preds]
            preds_week = [p for p in all_preds]
        else:
            preds_today = get_predictions(days=1)
            preds_week = get_predictions(days=7)

        def _row_html(p: dict) -> str:
            status = p.get('status', 'pending')
            if status in ('validated',) and p.get('result') == 'VALIDATED':
                row_bg = 'rgba(34,197,94,0.06)'
                left = '#22c55e'
                status_label = 'WON'
            elif status in ('validated',) and p.get('result') == 'FAILED':
                row_bg = 'rgba(239,68,68,0.06)'
                left = '#ef4444'
                status_label = 'LOST'
            elif status == 'win':
                row_bg = 'rgba(34,197,94,0.06)'
                left = '#22c55e'
                status_label = 'WON'
            elif status == 'loss':
                row_bg = 'rgba(239,68,68,0.06)'
                left = '#ef4444'
                status_label = 'LOST'
            else:
                row_bg = 'rgba(255,255,255,0.02)'
                left = '#9ca3af'
                status_label = 'PENDING'
            ts = (p.get('timestamp_prediction') or p.get('timestamp',''))[:16].replace('T', ' ')
            home = p.get('home_name','?')
            away = p.get('away_name','?')
            pred = p.get('prediction') or p.get('predicted_market') or 'UNDER 2.5'
            return (f"<tr style='background:{row_bg};'>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);color:{left};font-weight:800;'>{status_label}</td>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{ts}</td>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{home} vs {away}</td>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{pred}</td>"
                    f"</tr>")

        # render 'Prédictions du jour' table
        st.markdown("<div style='margin-top:14px;font-weight:700;'>Prédictions du jour</div>", unsafe_allow_html=True)
        if preds_today:
            rows = "".join(_row_html(p) for p in sorted(preds_today, key=lambda x: x.get('timestamp_prediction', x.get('timestamp','')), reverse=True))
            table_html = ("<table style='width:100%;border-collapse:collapse;margin-top:8px;'>"
                          "<thead><tr>"
                          "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Statut</th>"
                          "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Heure</th>"
                          "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Match</th>"
                          "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Prédiction</th>"
                          "</tr></thead>"
                          f"<tbody>{rows}</tbody></table>")
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.caption("Aucune prédiction émise aujourd'hui.")

        # render 'Statistiques cette semaine' table
        st.markdown("<div style='margin-top:18px;font-weight:700;'>Statistiques cette semaine</div>", unsafe_allow_html=True)
        if preds_week:
            rows = "".join(_row_html(p) for p in sorted(preds_week, key=lambda x: x.get('timestamp_prediction', x.get('timestamp','')), reverse=True))
            table_html = ("<table style='width:100%;border-collapse:collapse;margin-top:8px;'>"
                          "<thead><tr>"
                          "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Statut</th>"
                          "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Heure</th>"
                          "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Match</th>"
                          "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Prédiction</th>"
                          "</tr></thead>"
                          f"<tbody>{rows}</tbody></table>")
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.caption("Aucune prédiction émise ces 7 derniers jours.")
    except Exception:
        try:
            _render_prediction_tables()
        except Exception:
            pass

    # ══ SECTION 3 — HISTORIQUE ════════════════════════════════════════════
    _section_header(
        "✅ HISTORIQUE VALIDATION", len(resolved_matches),
        "#22c55e", "rgba(34,197,94,0.12)"
    )
    if resolved_matches:
        st.caption(f"Matchs terminés · ✅ {len(validated_res)} validés · ❌ {len(failed_res)} échoués")
        _render_cards_grid(resolved_matches, section="resolved",
                           empty_msg="Aucun match terminé aujourd'hui.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:12px;color:#888;"
            "border:2px dashed rgba(34,197,94,0.15);border-radius:12px;font-size:0.84rem;'>"
            "Aucun match résolu pour le moment</div>",
            unsafe_allow_html=True,
        )

    # ══ SECTION 4 — STATISTIQUES RÉELLES (Problèmes 2, 4, 5) ═══════════════
    stats = get_prediction_stats()
    _section_header(
        "📊 STATISTIQUES RÉELLES",
        stats["resolved"] + stats["pending"],
        "#a855f7", "rgba(168,85,247,0.15)"
    )
    _render_stats_block()

    if live_matches:
        st.markdown(
            "<div style='font-size:0.75rem;color:#888;text-align:center;margin-top:10px;'>"
            "🔴 Matchs live actifs — appuyez sur 🔄 pour actualiser</div>",
            unsafe_allow_html=True,
        )
