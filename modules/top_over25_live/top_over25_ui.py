"""
top_over25_ui.py
================
Interface TOP +2.5 BUTS INTELLIGENT
4 sections : Live · Futurs du jour · Historique · Statistiques
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from modules.top_over25_live.match_monitor import fetch_top_over25, refresh_live_matches
from modules.top_over25_live.metrics_engine import compute_all_periods


# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

CONTINENT_OPTIONS = ["Tous", "Europe", "Amériques", "Asie", "Afrique", "Autre"]

STATUS_LABELS = {
    "NS":   ("⏳ À venir",     "#f59e0b", "rgba(245,158,11,0.12)"),
    "1H":   ("� 1ère MT",     "#ef4444", "rgba(239,68,68,0.12)"),
    "HT":   ("🟡 Mi-temps",    "#f59e0b", "rgba(245,158,11,0.12)"),
    "2H":   ("� 2ème MT",     "#ef4444", "rgba(239,68,68,0.12)"),
    "ET":   ("� Prolong.",    "#ef4444", "rgba(239,68,68,0.12)"),
    "BT":   ("🟡 Pause Prol.", "#f59e0b", "rgba(245,158,11,0.12)"),
    "P":    ("� Tirs au but", "#ef4444", "rgba(239,68,68,0.12)"),
    "FT":   ("⚫ Terminé",     "#888888", "rgba(128,128,128,0.10)"),
    "AET":  ("⚫ Terminé AET", "#888888", "rgba(128,128,128,0.10)"),
    "PEN":  ("⚫ Tirs au but", "#888888", "rgba(128,128,128,0.10)"),
    "LIVE": ("🔴 LIVE",        "#ef4444", "rgba(239,68,68,0.12)"),
}


def _status_display(status_short: str) -> tuple:
    return STATUS_LABELS.get(status_short, ("⏳ " + status_short, "#888", "rgba(128,128,128,0.1)"))


def _prob_bar(pct: float, color: str) -> str:
    return (
        f"<div style='background:rgba(255,255,255,0.08);border-radius:4px;"
        f"height:6px;overflow:hidden;margin-top:4px;'>"
        f"<div style='width:{pct}%;height:6px;background:{color};"
        f"border-radius:4px;transition:width 0.6s ease;'></div></div>"
    )


def _over_score_bar(score: float) -> str:
    if score >= 75:
        color = "#22c55e"
    elif score >= 60:
        color = "#84cc16"
    elif score >= 45:
        color = "#f59e0b"
    else:
        color = "#ef4444"
    return (
        f"<div style='background:rgba(255,255,255,0.06);border-radius:6px;"
        f"height:10px;overflow:hidden;margin-top:4px;position:relative;'>"
        f"<div style='width:{score}%;height:10px;background:linear-gradient(90deg,{color}88,{color});"
        f"border-radius:6px;transition:width 0.6s ease;'></div>"
        f"<span style='position:absolute;right:6px;top:-1px;font-size:0.62rem;"
        f"color:{color};font-weight:800;'>{score:.0f}</span>"
        f"</div>"
    )


def _score_breakdown_html(breakdown: Dict[str, float]) -> str:
    """Affiche l'explication OVER_SCORE composante par composante."""
    if not breakdown:
        return ""
    order = ["Attack", "Defense", "Form", "H2H/BTTS", "Live pressure", "xG"]
    maxes = {"Attack": 30, "Defense": 15, "Form": 15, "H2H/BTTS": 10,
             "Live pressure": 15, "xG": 15}
    rows = ""
    for key in order:
        val = breakdown.get(key, 0.0)
        if val == 0.0 and key in ("Live pressure", "xG"):
            continue
        max_v = maxes.get(key, 15)
        bar_pct = min(100, round(val / max_v * 100))
        if bar_pct >= 70:
            bar_col = "#22c55e"
        elif bar_pct >= 45:
            bar_col = "#f59e0b"
        else:
            bar_col = "#ef4444"
        rows += (
            f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'>"
            f"<span style='font-size:0.62rem;color:#aaa;min-width:88px;'>{key}</span>"
            f"<div style='flex:1;background:rgba(255,255,255,0.06);border-radius:3px;height:5px;'>"
            f"<div style='width:{bar_pct}%;height:5px;background:{bar_col};border-radius:3px;'></div>"
            f"</div>"
            f"<span style='font-size:0.62rem;color:{bar_col};font-weight:700;min-width:26px;text-align:right;'>"
            f"{val:.1f}"
            f"</span>"
            f"</div>"
        )
    total = breakdown.get("Total", 0.0)
    return (
        f"<div style='margin-top:8px;padding:8px 10px;"
        f"background:rgba(255,255,255,0.025);border-radius:8px;"
        f"border:1px solid rgba(255,255,255,0.06);'>"
        f"<div style='font-size:0.63rem;color:#888;margin-bottom:5px;font-weight:700;letter-spacing:0.3px;'>"
        f"📊 OVER SCORE — détail</div>"
        f"{rows}"
        f"<div style='border-top:1px solid rgba(255,255,255,0.07);margin-top:4px;padding-top:4px;"
        f"display:flex;justify-content:flex-end;'>"
        f"<span style='font-size:0.65rem;color:#a78bfa;font-weight:800;'>Total = {total:.0f}/100</span>"
        f"</div>"
        f"</div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Carte match professionnelle
# ─────────────────────────────────────────────────────────────────────────────

def _render_match_card(m: Dict[str, Any], section: str = "active") -> None:
    """Carte match pro avec raisons IA, over_score, BTTS, score probable."""
    status_short = m.get("status_short", "NS")
    s_label, s_color, s_bg = _status_display(status_short)
    is_live     = m.get("is_live", False)
    is_finished = m.get("is_finished", False)
    validation  = m.get("validation")
    over_score  = m.get("over_score", 0.0)
    conf_col    = m.get("conf_color", "#888")
    conf_lbl    = m.get("conf_label", "—")
    pct         = m.get("over25_pct", 0.0)
    btts_label  = m.get("btts_label", "Incertain")
    ai_reasons  = m.get("ai_reasons") or []
    prob_score  = m.get("probable_score", (1, 1))

    # ── Couleurs carte selon section ──────────────────────────────────────
    if validation:
        res = (validation.get("result") or "")
        if res == "VALIDATED":
            border_color = "#22c55e"
            card_bg      = "rgba(34,197,94,0.06)"
            type_badge   = "<span style='background:#22c55e22;color:#22c55e;border-radius:20px;padding:2px 10px;font-size:0.72rem;font-weight:800;'>✅ VALIDÉ</span>"
        else:
            border_color = "#ef4444"
            card_bg      = "rgba(239,68,68,0.06)"
            type_badge   = "<span style='background:#ef444422;color:#ef4444;border-radius:20px;padding:2px 10px;font-size:0.72rem;font-weight:800;'>❌ ÉCHOUÉ</span>"
    elif section == "live":
        border_color = "#ef4444"
        card_bg      = "rgba(239,68,68,0.05)"
        type_badge   = "<span style='background:#ef444433;color:#ef4444;border-radius:20px;padding:2px 10px;font-size:0.72rem;font-weight:800;animation:pulse 1.5s infinite;'>🔴 LIVE</span>"
    elif section == "future":
        border_color = "#a78bfa"
        card_bg      = "rgba(167,139,250,0.05)"
        type_badge   = "<span style='background:#a78bfa22;color:#a78bfa;border-radius:20px;padding:2px 10px;font-size:0.72rem;font-weight:800;'>🟣 FUTUR</span>"
    else:
        border_color = "rgba(255,255,255,0.12)"
        card_bg      = "rgba(255,255,255,0.03)"
        type_badge   = ""

    # ── Ligue ─────────────────────────────────────────────────────────────
    flag = m.get("league_flag", "")
    flag_img = f"<img src='{flag}' style='height:13px;margin-right:4px;vertical-align:middle;'>" if flag else ""
    league_html = (
        f"<div style='font-size:0.72rem;color:#aaa;margin-bottom:8px;'>"
        f"{flag_img}<b>{m.get('league_name','—')}</b> · {m.get('league_country','—')}"
        f"</div>"
    )

    # ── Score / heure ─────────────────────────────────────────────────────
    if is_live:
        min_txt = f"<span style='font-size:0.78rem;color:#ef4444;margin-left:8px;font-weight:600;'>{m.get('minute',0)}'</span>"
        score_html = (
            f"<div style='font-size:1.6rem;font-weight:900;letter-spacing:3px;"
            f"text-align:center;margin:8px 0 2px;'>"
            f"{m['home_score']} — {m['away_score']}{min_txt}"
            f"</div>"
        )
        xg_h = m.get("home_xg", 0.0)
        xg_a = m.get("away_xg", 0.0)
        xg_html = (
            f"<div style='text-align:center;font-size:0.7rem;color:#888;margin-bottom:4px;'>"
            f"xG : {xg_h} – {xg_a}"
            f"</div>"
        ) if xg_h + xg_a > 0 else ""
    elif is_finished:
        score_html = (
            f"<div style='font-size:1.5rem;font-weight:900;letter-spacing:2px;"
            f"text-align:center;margin:8px 0 2px;color:#888;'>"
            f"{m['home_score']} — {m['away_score']}"
            f"<span style='font-size:0.75rem;margin-left:8px;'>FT</span></div>"
        )
        xg_html = ""
    else:
        score_html = (
            f"<div style='text-align:center;font-size:0.85rem;color:#aaa;margin:8px 0 4px;'>"
            f"📅 {m.get('start_date_display','—')} · 🕐 {m.get('start_time','—')}</div>"
        )
        xg_html = ""

    # ── OVER_SCORE barre ──────────────────────────────────────────────────
    score_bar = _over_score_bar(over_score)
    score_label = "OVER SCORE (IA)"

    # ── Probabilité + confiance ──────────────────────────────────────────
    if is_finished and validation:
        init_pct = m.get("initial_pct", pct)
        prob_html = (
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"margin-top:8px;'>"
            f"<span style='font-size:0.75rem;color:#aaa;'>Prédiction initiale</span>"
            f"<div style='display:flex;align-items:center;gap:8px;'>"
            f"<span style='font-weight:900;color:#00d4ff;font-size:1.0rem;'>Over 2.5</span>"
            f"<span style='font-weight:800;color:{conf_col};font-size:0.9rem;'>{init_pct}%</span>"
            f"</div></div>"
            f"<div style='display:flex;justify-content:space-between;margin-top:4px;'>"
            f"<span style='font-size:0.72rem;color:#888;'>Confiance</span>"
            f"<span style='font-size:0.78rem;color:{conf_col};font-weight:700;'>{conf_lbl}</span>"
            f"</div>"
        )
    else:
        prob_html = (
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"margin-top:8px;'>"
            f"<span style='font-size:0.75rem;color:#aaa;'>Prédiction</span>"
            f"<span style='font-weight:900;color:#00d4ff;font-size:0.95rem;'>Over 2.5 BUTS</span>"
            f"</div>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"margin-top:4px;'>"
            f"<span style='font-size:0.75rem;color:#aaa;'>Probabilité</span>"
            f"<span style='font-weight:900;font-size:1.05rem;color:{conf_col};'>{pct}%</span>"
            f"</div>"
            + _prob_bar(pct, conf_col) +
            f"<div style='display:flex;justify-content:space-between;margin-top:6px;'>"
            f"<span style='font-size:0.72rem;color:#888;'>Confiance</span>"
            f"<span style='font-size:0.78rem;color:{conf_col};font-weight:700;'>{conf_lbl}</span>"
            f"</div>"
        )

    # ── Score probable + BTTS ─────────────────────────────────────────────
    ps_h, ps_a = prob_score
    btts_col = "#22c55e" if btts_label == "Oui" else "#ef4444" if btts_label == "Non" else "#f59e0b"
    extra_html = (
        f"<div style='display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;'>"
        f"<div style='flex:1;min-width:100px;background:rgba(255,255,255,0.04);"
        f"border-radius:8px;padding:7px 10px;text-align:center;'>"
        f"<div style='font-size:0.65rem;color:#aaa;margin-bottom:2px;'>Score probable</div>"
        f"<div style='font-size:1.0rem;font-weight:800;color:#e0e0e0;'>{ps_h} \u2013 {ps_a}</div>"
        f"</div>"
        f"<div style='flex:1;min-width:80px;background:rgba(255,255,255,0.04);"
        f"border-radius:8px;padding:7px 10px;text-align:center;'>"
        f"<div style='font-size:0.65rem;color:#aaa;margin-bottom:2px;'>BTTS</div>"
        f"<div style='font-size:0.9rem;font-weight:800;color:{btts_col};'>{btts_label}</div>"
        f"</div>"
        f"</div>"
    ) if not is_finished else ""

    # ── Badges live Partie 7 : Intensité / Danger / Temps / Pression ─────
    urgency   = m.get("urgency_score", 0.0)
    remaining = m.get("remaining_min", 0)
    exp_goals = m.get("expected_goals", 0.0)
    final_ls  = m.get("final_live_score", over_score)
    if urgency >= 70:
        urg_col = "#ef4444"
    elif urgency >= 50:
        urg_col = "#f59e0b"
    else:
        urg_col = "#888"

    live_badges_html = ""
    if is_live and not is_finished:
        live_badges_html = (
            f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:5px;"
            f"margin-top:8px;'>"
            f"<div style='background:rgba(239,68,68,0.07);border-radius:8px;"
            f"padding:6px;text-align:center;'>"
            f"<div style='font-size:0.60rem;color:#aaa;margin-bottom:1px;'>"
            f"🔥 Intensité</div>"
            f"<div style='font-size:0.80rem;font-weight:800;color:{urg_col};'>"
            f"{urgency:.0f}/100</div></div>"
            f"<div style='background:rgba(167,139,250,0.07);border-radius:8px;"
            f"padding:6px;text-align:center;'>"
            f"<div style='font-size:0.60rem;color:#aaa;margin-bottom:1px;'>"
            f"\u26a1 Danger</div>"
            f"<div style='font-size:0.80rem;font-weight:800;color:#a78bfa;'>"
            f"{final_ls:.0f}/100</div></div>"
            f"<div style='background:rgba(245,158,11,0.07);border-radius:8px;"
            f"padding:6px;text-align:center;'>"
            f"<div style='font-size:0.60rem;color:#aaa;margin-bottom:1px;'>"
            f"🎯 Restant</div>"
            f"<div style='font-size:0.80rem;font-weight:800;color:#f59e0b;'>"
            f"{remaining}\u2019</div></div>"
            f"</div>"
            f"<div style='margin-top:4px;font-size:0.63rem;color:#666;"
            f"text-align:center;'>"
            f"📈 xG : {exp_goals:.2f} · "
            f"{int(m.get('shots_total',0))} tirs \u00b7 "
            f"{int(m.get('corners',0))} corners"
            f"</div>"
        )

    # ── Raisons IA numériques + breakdown ────────────────────────────────
    breakdown     = m.get("score_breakdown") or {}
    reasons_html  = ""
    if ai_reasons and not is_finished:
        items = "".join(
            f"<div style='font-size:0.71rem;"
            f"color:{'#a0e4a0' if r.startswith('\u2713') else '#f59e0b'};"
            f"padding:2px 0;line-height:1.4;'>{r}</div>"
            for r in ai_reasons[:6]
        )
        reasons_html = (
            f"<div style='margin-top:8px;padding:8px 10px;"
            f"background:rgba(34,197,94,0.04);border-radius:8px;"
            f"border-left:2px solid #22c55e44;'>"
            f"<div style='font-size:0.65rem;color:#888;margin-bottom:5px;font-weight:700;"
            f"letter-spacing:0.3px;'>🤖 Analyse IA</div>"
            f"{items}"
            f"</div>"
        )
    breakdown_html = _score_breakdown_html(breakdown) if not is_finished else ""

    # ── Résultat validation ───────────────────────────────────────────────
    val_html = ""
    if validation:
        val_html = (
            f"<div style='margin-top:10px;padding:8px 12px;"
            f"background:{validation['bg']};border-radius:8px;"
            f"border:1px solid {validation['border']};'>"
            f"<span style='font-weight:800;color:{validation['color']};font-size:0.9rem;'>"
            f"{validation['label']}</span>"
            f"<span style='color:#aaa;font-size:0.75rem;margin-left:8px;'>"
            f"{validation.get('reason','')}</span>"
            f"</div>"
        )

    # ── Assemblage ───────────────────────────────────────────────────────
    card_html = "".join([
        f"<div style='background:{card_bg};border:1px solid {border_color};"
        f"border-radius:16px;padding:16px;margin-bottom:14px;"
        f"box-shadow:0 2px 12px rgba(0,0,0,0.15);'>",

        # Ligne 1 : type badge + heure + statut
        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"margin-bottom:6px;flex-wrap:wrap;gap:4px;'>"
        f"{type_badge}"
        f"<div style='display:flex;align-items:center;gap:6px;'>"
        f"<span style='background:{s_bg};color:{s_color};border-radius:12px;"
        f"padding:2px 8px;font-size:0.7rem;font-weight:700;'>{s_label}</span>"
        f"<span style='font-size:0.68rem;color:#888;'>{m.get('start_time','—')}</span>"
        f"</div>"
        f"</div>",

        league_html,

        # Équipes
        f"<div style='font-size:1.05rem;font-weight:800;text-align:center;"
        f"margin:6px 0 2px;line-height:1.3;'>"
        f"{m.get('home_name','—')}"
        f"<span style='color:#666;font-size:0.85rem;margin:0 8px;font-weight:400;'>vs</span>"
        f"{m.get('away_name','—')}"
        f"</div>",

        score_html,
        xg_html if not is_finished else "",

        # OVER_SCORE
        f"<div style='margin-top:10px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"margin-bottom:2px;'>"
        f"<span style='font-size:0.65rem;color:#888;font-weight:600;'>{score_label}</span>"
        f"<span style='font-size:0.65rem;color:#888;'>/ 100</span>"
        f"</div>"
        + score_bar +
        f"</div>",

        # Proba + confiance
        f"<div style='margin-top:8px;padding:10px;background:rgba(255,255,255,0.03);"
        f"border-radius:10px;'>"
        + prob_html +
        f"</div>",

        extra_html,
        live_badges_html,
        reasons_html,
        breakdown_html,
        val_html,

        "</div>",
    ])

    st.markdown(card_html, unsafe_allow_html=True)


def _render_cards_grid(
    matches: List[Dict], section: str = "active",
    empty_msg: str = "Aucun match."
) -> None:
    if not matches:
        col_border = {
            "live":   "rgba(239,68,68,0.2)",
            "future": "rgba(167,139,250,0.2)",
            "history":"rgba(34,197,94,0.15)",
        }.get(section, "rgba(255,255,255,0.08)")
        st.markdown(
            f"<div style='text-align:center;padding:20px;color:#888;"
            f"border:2px dashed {col_border};border-radius:12px;font-size:0.85rem;'>"
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
        f"<div style='display:flex;align-items:center;gap:10px;margin:22px 0 12px;'>"
        f"<div style='height:2px;flex:1;background:rgba(255,255,255,0.06);border-radius:2px;'></div>"
        f"<span style='background:{bg};color:{color};border-radius:20px;"
        f"padding:5px 18px;font-size:0.88rem;font-weight:800;white-space:nowrap;letter-spacing:0.3px;'>"
        f"{title}"
        f"<span style='opacity:0.65;font-size:0.78rem;margin-left:6px;'>({count})</span>"
        f"</span>"
        f"<div style='height:2px;flex:1;background:rgba(255,255,255,0.06);border-radius:2px;'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bloc statistiques réelles
# ─────────────────────────────────────────────────────────────────────────────

def _perf_mini(label: str, m: Dict[str, Any]) -> str:
    won     = m["won"]
    lost    = m["lost"]
    total   = m["total"]   # résolus uniquement
    pending = m.get("pending", 0)
    wr      = m["winrate"]
    roi     = m["roi"]
    profit  = m["profit"]
    total_emitted = m.get("total_emitted", total + pending)

    # Winrate color : attention si 0 pertes = pas de vraie donnée suffisante
    if total == 0:
        wr_col = "#888"
    elif lost == 0 and won < 3:
        wr_col = "#f59e0b"  # trop peu pour conclure
    else:
        wr_col = "#22c55e" if wr >= 55 else "#f59e0b" if wr >= 40 else "#ef4444"
    roi_col = "#22c55e" if roi >= 0 else "#ef4444"
    sign    = "+" if profit >= 0 else ""

    if total == 0 and pending == 0:
        return (
            f"<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);"
            f"border-radius:12px;padding:14px;text-align:center;'>"
            f"<div style='font-size:0.82rem;font-weight:700;color:#aaa;'>{label}</div>"
            f"<div style='color:#555;font-size:0.78rem;margin-top:6px;'>Aucune prédiction encore</div>"
            f"</div>"
        )

    # Avertissement si 0 pertes avec peu de matchs
    warning = ""
    if total > 0 and lost == 0 and won < 5:
        warning = (
            f"<div style='font-size:0.62rem;color:#f59e0b;margin-top:4px;text-align:center;'>"
            f"⚠️ Données insuffisantes ({won} prédiction(s))"
            f"</div>"
        )

    pending_html = (
        f"<div style='margin-top:5px;font-size:0.65rem;color:#a78bfa;text-align:center;'>"
        f"⏳ {pending} en attente de résultat"
        f"</div>"
    ) if pending > 0 else ""

    wr_display = f"{wr}%" if total > 0 else "—"
    roi_display = f"{sign}{roi}%" if total > 0 else "—"

    return (
        f"<div style='background:rgba(167,139,250,0.06);border:1px solid rgba(167,139,250,0.18);"
        f"border-radius:12px;padding:14px;'>"
        f"<div style='font-size:0.82rem;font-weight:800;color:#a78bfa;text-align:center;margin-bottom:10px;'>{label}</div>"
        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;'>"
        f"<div style='background:rgba(34,197,94,0.1);border-radius:8px;padding:7px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:#22c55e;'>{won}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Validés ✅</div></div>"
        f"<div style='background:rgba(239,68,68,0.1);border-radius:8px;padding:7px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:#ef4444;'>{lost}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Échoués ❌</div></div>"
        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:7px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:{wr_col};'>{wr_display}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Winrate</div></div>"
        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:7px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:{roi_col};'>{roi_display}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>ROI sim.</div></div>"
        f"</div>"
        f"<div style='margin-top:6px;font-size:0.65rem;color:#888;text-align:center;'>"
        f"Profit : {sign}{profit}u · Cote {m['odd_used']} · {total}/{total_emitted} résolus"
        f"</div>"
        + pending_html
        + warning
        + f"</div>"
    )


def _render_stats_block() -> None:
    try:
        periods = compute_all_periods()
    except Exception:
        st.caption("Historique non disponible.")
        return
    today = periods["today"]
    week  = periods["week"]
    month = periods["month"]

    total_emitted_any = (
        today.get("total_emitted", 0)
        + week.get("total_emitted", 0)
        + month.get("total_emitted", 0)
    )

    if total_emitted_any == 0:
        st.markdown(
            "<div style='text-align:center;padding:18px;color:#aaa;"
            "border:2px dashed rgba(167,139,250,0.15);border-radius:12px;'>"
            "<div style='font-size:1.2rem;margin-bottom:6px;'>📊</div>"
            "<b style='color:#a78bfa;'>Aucune prédiction enregistrée</b><br>"
            "<span style='font-size:0.76rem;color:#666;'>"
            "Les statistiques s'accumulent dès que des matchs sont prédits et terminés."
            "</span></div>",
            unsafe_allow_html=True,
        )
        return

    html = (
        f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px;'>"
        + _perf_mini("📅 Aujourd'hui", today)
        + _perf_mini("🗓️ 7 jours", week)
        + _perf_mini("📆 30 jours", month)
        + f"</div>"
        f"<div style='font-size:0.65rem;color:#666;text-align:center;margin-top:8px;"
        f"border-top:1px solid rgba(255,255,255,0.06);padding-top:6px;'>"
        f"Source : prédictions réellement émises uniquement · "
        f"Cote simulée {week['odd_used']} · "
        f"Winrate calculé sur résultats résolus seulement"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────

def render_top_over25_page(api) -> None:
    """Rendu complet : 4 sections — Live · Futurs · Historique · Statistiques."""
    import time as _time
    import datetime as _dt

    # ── CSS animations ───────────────────────────────────────────────────
    st.markdown(
        "<style>"
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.6}}"
        "</style>",
        unsafe_allow_html=True,
    )

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown(
        "<h2 style='font-size:1.6rem;margin-bottom:2px;'>⚽ TOP +2.5 BUTS INTELLIGENT</h2>"
        "<p style='color:#888;font-size:0.82rem;margin-bottom:16px;'>"
        "Sélection IA stricte · Max 5 Live + 5 Futurs du jour · "
        "<span style='color:#f59e0b;'>Qualité avant quantité</span></p>",
        unsafe_allow_html=True,
    )

    # ── Filtres ──────────────────────────────────────────────────────────
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

    # ── Cache session ─────────────────────────────────────────────────────
    now_ts       = _time.time()
    CACHE_TTL    = 30
    FULL_TTL     = 600
    cache_key    = "over25_data"
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
        with st.spinner("🔍 Analyse intelligente des matchs du jour…"):
            try:
                data = fetch_top_over25(api, continent_filter=continent)
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

    # Séparer validés / échoués dans resolved
    validated = [m for m in resolved_matches
                 if (m.get("validation") or {}).get("result") == "VALIDATED"]
    failed    = [m for m in resolved_matches
                 if (m.get("validation") or {}).get("result") == "FAILED"]

    # ── Timestamp ─────────────────────────────────────────────────────────
    if st.session_state.get(cache_ts_key, 0):
        dt_str = _dt.datetime.fromtimestamp(st.session_state[cache_ts_key]).strftime("%H:%M:%S")
        st.caption(
            f"⏱️ Màj : {dt_str} · Auto-refresh 30s · Filtre : {continent} · "
            f"🔴 {len(live_matches)} live · 🟣 {len(future_matches)} futurs"
        )

    # ── Barre résumé ──────────────────────────────────────────────────────
    total_sel = len(live_matches) + len(future_matches)
    summary_html = (
        f"<div style='display:grid;grid-template-columns:repeat(4,1fr);"
        f"gap:8px;margin-bottom:20px;'>"

        f"<div style='background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);"
        f"border-radius:12px;padding:12px;text-align:center;'>"
        f"<div style='font-size:1.5rem;font-weight:900;color:#ef4444;'>{len(live_matches)}</div>"
        f"<div style='font-size:0.7rem;color:#aaa;margin-top:2px;'>🔴 Live</div></div>"

        f"<div style='background:rgba(167,139,250,0.08);border:1px solid rgba(167,139,250,0.2);"
        f"border-radius:12px;padding:12px;text-align:center;'>"
        f"<div style='font-size:1.5rem;font-weight:900;color:#a78bfa;'>{len(future_matches)}</div>"
        f"<div style='font-size:0.7rem;color:#aaa;margin-top:2px;'>🟣 Futurs</div></div>"

        f"<div style='background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);"
        f"border-radius:12px;padding:12px;text-align:center;'>"
        f"<div style='font-size:1.5rem;font-weight:900;color:#22c55e;'>{len(validated)}</div>"
        f"<div style='font-size:0.7rem;color:#aaa;margin-top:2px;'>✅ Validés</div></div>"

        f"<div style='background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.15);"
        f"border-radius:12px;padding:12px;text-align:center;'>"
        f"<div style='font-size:1.5rem;font-weight:900;color:#ef4444;'>{len(failed)}</div>"
        f"<div style='font-size:0.7rem;color:#aaa;margin-top:2px;'>❌ Échoués</div></div>"

        f"</div>"
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    if total_sel == 0 and not resolved_matches:
        st.markdown(
            "<div style='text-align:center;padding:30px;color:#888;"
            "border:2px dashed rgba(255,255,255,0.08);border-radius:16px;'>"
            "<div style='font-size:2rem;margin-bottom:8px;'>⚽</div>"
            "<b style='color:#aaa;'>Aucun match ne satisfait les critères IA</b><br>"
            "<span style='font-size:0.78rem;color:#555;'>"
            "Le moteur sélectionne peu mais sélectionne intelligemment.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        _section_header("📊 STATISTIQUES RÉELLES", 0, "#a78bfa", "rgba(167,139,250,0.15)")
        _render_stats_block()
        return

    # ════════════════════════════════════════════════════════════════════
    # SECTION 1 — MATCHS LIVE SÉLECTIONNÉS
    # ════════════════════════════════════════════════════════════════════
    _section_header(
        "🔵 MATCHS LIVE SÉLECTIONNÉS", len(live_matches),
        "#ef4444", "rgba(239,68,68,0.15)"
    )
    if live_matches:
        st.caption(
            f"Règles : 5' ≤ minute ≤ 70' · < 3 buts · prob ≥45% · OVER_SCORE ≥45 · "
            f"≥3 tirs · ≥1 corner · ≤1 carton rouge"
        )
        _render_cards_grid(live_matches, section="live",
                           empty_msg="Aucun match live ne satisfait les critères.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:16px;color:#888;"
            "border:2px dashed rgba(239,68,68,0.15);border-radius:12px;font-size:0.84rem;'>"
            "🔴 Aucun match live sélectionné · Critères IA stricts non satisfaits</div>",
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════
    # SECTION 2 — MATCHS FUTURS DU JOUR
    # ════════════════════════════════════════════════════════════════════
    _section_header(
        "🟣 MATCHS FUTURS DU JOUR", len(future_matches),
        "#a78bfa", "rgba(167,139,250,0.15)"
    )
    if future_matches:
        adapted = any(m.get("criteria_adapted") for m in future_matches)
        if adapted:
            st.markdown(
                "<div style='background:rgba(245,158,11,0.10);border:1px solid rgba(245,158,11,0.3);"
                "border-radius:8px;padding:7px 12px;font-size:0.75rem;color:#f59e0b;"
                "margin-bottom:8px;'>"
                "⚠️ Critères adaptés automatiquement pour garantir un minimum de matchs"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("Top 5 matchs du jour · Critères stricts · Triés par OVER_SCORE")
        _render_cards_grid(future_matches, section="future",
                           empty_msg="Aucun match futur ne satisfait les critères.")
    else:
        st.markdown(
            "<div style='text-align:center;padding:16px;color:#888;"
            "border:2px dashed rgba(167,139,250,0.15);border-radius:12px;font-size:0.84rem;'>"
            "🟣 Aucun match futur sélectionné pour le moment</div>",
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════
    # SECTION 3 — HISTORIQUE VALIDATION
    # ════════════════════════════════════════════════════════════════════
    _section_header(
        "✅ HISTORIQUE VALIDATION", len(resolved_matches),
        "#22c55e", "rgba(34,197,94,0.12)"
    )
    if resolved_matches:
        st.caption(
            f"Matchs terminés aujourd'hui · "
            f"✅ {len(validated)} validés · ❌ {len(failed)} échoués"
        )
        if validated:
            st.markdown(
                "<div style='font-size:0.75rem;color:#22c55e;font-weight:700;"
                "margin:6px 0 4px;'>✅ Validés — Over 2.5 atteint</div>",
                unsafe_allow_html=True,
            )
            _render_cards_grid(validated, section="history",
                               empty_msg="")
        if failed:
            st.markdown(
                "<div style='font-size:0.75rem;color:#ef4444;font-weight:700;"
                "margin:10px 0 4px;'>❌ Échoués — Under 2.5 final</div>",
                unsafe_allow_html=True,
            )
            _render_cards_grid(failed, section="history",
                               empty_msg="")
    else:
        st.markdown(
            "<div style='text-align:center;padding:12px;color:#888;"
            "border:2px dashed rgba(34,197,94,0.12);border-radius:12px;font-size:0.84rem;'>"
            "Aucun match terminé aujourd'hui pour le moment.</div>",
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════
    # SECTION 4 — STATISTIQUES RÉELLES
    # ════════════════════════════════════════════════════════════════════
    _section_header(
        "📊 STATISTIQUES RÉELLES", 0,
        "#a78bfa", "rgba(167,139,250,0.15)"
    )
    _render_stats_block()

    # ── Indicateur live ───────────────────────────────────────────────────
    if live_matches:
        st.markdown(
            "<div style='font-size:0.73rem;color:#888;text-align:center;margin-top:12px;'>"
            "🔴 Matchs live détectés — appuyer sur 🔄 pour actualiser les données</div>",
            unsafe_allow_html=True,
        )


