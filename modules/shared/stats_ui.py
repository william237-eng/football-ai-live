"""
stats_ui.py
=================
Bloc réutilisable d'affichage des statistiques réelles (Aujourd'hui / 7j / 30j)
Permet d'homogénéiser l'affichage entre les pages (+2.5, -2.5, cartons, victoires, ...)
"""
from typing import Dict, Any
import streamlit as st


def _perf_mini(label: str, m: Dict[str, Any]) -> str:
    # Normalize keys from different modules
    won = m.get("won") or m.get("wins") or 0
    lost = m.get("lost") or m.get("losses") or 0
    total = m.get("total") or m.get("resolved") or m.get("total_emitted") or 0
    pending = m.get("pending", 0)
    wr = None
    roi = None
    profit = m.get("profit")
    odd_used = m.get("odd_used") or m.get("odd")

    # Winrate string/percent handling
    if "winrate" in m:
        wr = m.get("winrate")
    elif "winrate_str" in m:
        wr = m.get("winrate_str")
    elif "winrate_pct" in m:
        wr = f"{m.get('winrate_pct')}%"
    elif "winrate_pct" not in m and total:
        # fallback percent if raw numbers provided
        try:
            wr = f"{round((won/total)*100)}%"
        except Exception:
            wr = "--"
    else:
        wr = "--"

    if "roi" in m:
        roi = m.get("roi")

    # Format displays
    wr_display = wr if wr is not None else "--"
    roi_display = (f"+{roi}%" if isinstance(roi, (int, float)) and roi >= 0 else f"{roi}%") if roi is not None else "--"
    sign = "+" if profit is not None and profit >= 0 else ""
    profit_display = f"{sign}{profit}u" if profit is not None else "--"

    # Colors
    try:
        wr_val = int(str(wr_display).replace('%','')) if isinstance(wr_display, str) and wr_display != '--' else None
    except Exception:
        wr_val = None
    if wr_val is None:
        wr_col = "#888"
    else:
        wr_col = "#22c55e" if wr_val >= 55 else "#f59e0b" if wr_val >= 40 else "#ef4444"
    roi_col = "#22c55e" if (isinstance(roi, (int, float)) and roi >= 0) else "#ef4444"

    return (
        f"<div style='background:rgba(167,139,250,0.06);border:1px solid rgba(167,139,250,0.18);"
        f"border-radius:12px;padding:14px;'>"
        f"<div style='font-size:0.82rem;font-weight:800;color:#a78bfa;text-align:center;margin-bottom:10px;'>{label}</div>"
        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;'>"
        f"<div style='background:rgba(34,197,94,0.1);border-radius:8px;padding:7px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:#22c55e;'>{won}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Validés ✅</div></div>"  # won
        f"<div style='background:rgba(239,68,68,0.1);border-radius:8px;padding:7px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:#ef4444;'>{lost}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Échoués ❌</div></div>"  # lost
        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:7px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:{wr_col};'>{wr_display}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Winrate réel</div></div>"  # winrate
        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;padding:7px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;color:{roi_col};'>{roi_display}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>ROI réel</div></div>"  # roi
        f"</div>"
        f"<div style='margin-top:6px;font-size:0.65rem;color:#888;text-align:center;'>"
        f"Profit : {profit_display} · Cote ref. {odd_used if odd_used is not None else '--'} · {total} résolus · {pending} en attente"
        f"</div></div>"
    )


def render_stats_block(title: str, today: Dict[str, Any], week: Dict[str, Any], month: Dict[str, Any], odd_used: Any = None) -> None:
    """Affiche le bloc 3 périodes + texte explicatif.
    Les dicts fournis peuvent provenir de différents modules ; la fonction tente de normaliser.
    """
    html = (
        f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px;'>"
        + _perf_mini(f"📅 Aujourd'hui", today)
        + _perf_mini(f"🗓️ 7 jours", week)
        + _perf_mini(f"📆 30 jours", month)
        + f"</div>"
        + f"<div style='font-size:0.65rem;color:#666;text-align:center;margin-top:8px;border-top:1px solid rgba(255,255,255,0.06);padding-top:6px;'>"
        f"Source : prédictions réellement émises uniquement · Cote simulée {odd_used if odd_used is not None else '--'} · Winrate calculé sur résultats résolus seulement"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)

