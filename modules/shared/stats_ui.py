"""
stats_ui.py
=================
Bloc réutilisable d'affichage des statistiques réelles (Aujourd'hui / 7j / 30j)
Permet d'homogénéiser l'affichage entre les pages (+2.5, -2.5, cartons, victoires, ...)
"""
from typing import Dict, Any, List
import streamlit as st


def _perf_mini(label: str, m: Dict[str, Any]) -> str:
    # Normalize keys from different modules
    won = m.get("won") or m.get("wins") or 0
    lost = m.get("lost") or m.get("losses") or 0
    total = m.get("total") or m.get("resolved") or m.get("total_emitted") or m.get("selected") or 0
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


def render_prediction_history(title: str, preds: List[Dict[str, Any]], max_items: int = 50) -> None:
    """Affiche un tableau d'historique des prédictions résolues (validées / échouées).
    La fonction est tolérante aux différentes structures de registres.
    """
    # Filtrer les prédictions résolues
    resolved = []
    for p in preds:
        status = str(p.get("status", "") or "").lower()
        result = str(p.get("result", "") or "").lower()
        if status in ("validated", "validated", "won", "lost", "won", "lost"):
            resolved.append(p)
        elif result in ("validated", "failed", "won", "lost"):
            resolved.append(p)
        elif p.get("timestamp_validated"):
            resolved.append(p)

    def _ts_key(item: Dict[str, Any]) -> str:
        return item.get("timestamp_validated") or item.get("timestamp_prediction") or item.get("timestamp") or ""

    resolved_sorted = sorted(resolved, key=lambda i: _ts_key(i) or "", reverse=True)[:max_items]

    if not resolved_sorted:
        st.markdown(f"<div style='text-align:center;color:#888;padding:10px;'>Aucun historique résolu pour {title}</div>", unsafe_allow_html=True)
        return

    rows_html = []
    for p in resolved_sorted:
        # statut lisible
        r = p.get("result") or p.get("status") or ""
        r_low = str(r).lower()
        if "valid" in r_low or r_low in ("won", "win", "validated"):
            status_label = "✅ VALIDÉ"
            status_col = "#22c55e"
        elif "fail" in r_low or r_low in ("lost", "loss", "failed"):
            status_label = "❌ ÉCHOUÉ"
            status_col = "#ef4444"
        else:
            status_label = str(r).upper() if r else (str(p.get("status", "")).upper() or "?")
            status_col = "#9ca3af"

        ts = (p.get("timestamp_validated") or p.get("timestamp_prediction") or p.get("timestamp") or "")[:19].replace("T", " ")
        home = p.get("home_name") or p.get("home_team") or p.get("home") or "?"
        away = p.get("away_name") or p.get("away_team") or p.get("away") or "?"

        # détecter score final
        score_display = ""
        if p.get("home_score_final") is not None and p.get("away_score_final") is not None:
            score_display = f"{p.get('home_score_final')} — {p.get('away_score_final')}"
        elif p.get("total_goals_final") is not None:
            score_display = f"Total buts: {p.get('total_goals_final')}"
        elif p.get("total_reds_final") is not None:
            score_display = f"Total rouges: {p.get('total_reds_final')}"
        elif p.get("total_cards_final") is not None:
            score_display = f"Total cartons: {p.get('total_cards_final')}"
        elif p.get("winner"):
            score_display = str(p.get("winner"))
        else:
            score = p.get("score") or p.get("final_score") or p.get("final") or ""
            if score:
                score_display = str(score)

        pred_lbl = p.get("prediction") or p.get("predicted_market") or p.get("prediction_label") or p.get("market") or ""

        rows_html.append(
            f"<tr style='background:rgba(255,255,255,0.02);'>"
            f"<td style='padding:8px 10px;color:{status_col};font-weight:800;'>{status_label}</td>"
            f"<td style='padding:8px 10px;'>{ts}</td>"
            f"<td style='padding:8px 10px;'>{home} vs {away}</td>"
            f"<td style='padding:8px 10px;'>{pred_lbl}</td>"
            f"<td style='padding:8px 10px;text-align:right;'>{score_display}</td>"
            f"</tr>"
        )

    table_html = (
        "<table style='width:100%;border-collapse:collapse;margin-top:8px;font-size:0.9rem;'>"
        "<thead><tr>"
        "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Statut</th>"
        "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Heure</th>"
        "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Match</th>"
        "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Prédiction</th>"
        "<th style='text-align:right;padding:8px 10px;color:#9ca3af;'>Score final</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
    )

    st.markdown(f"<div style='margin-top:12px;font-weight:700;color:#a855f7;'>{title}</div>", unsafe_allow_html=True)
    st.markdown(table_html, unsafe_allow_html=True)

