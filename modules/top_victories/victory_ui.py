"""
victory_ui.py
=============
UI Streamlit — Module 🏆 TOP 10 VICTOIRES IA
Design pro, responsive web & mobile.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

from modules.top_victories.victory_monitor import fetch_top_victories, validate_pending
from modules.top_victories.victory_storage import init_db, get_all_predictions, get_stats, get_daily_stats, get_prediction_history

# ─── Cache ───────────────────────────────────────────────────────────────────
def _fetch_cached(api_key_hash: str, _api) -> List[Dict]:
    return fetch_top_victories(_api)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers HTML
# ─────────────────────────────────────────────────────────────────────────────

def _status_badge(status_short: str, minute: Optional[int]) -> str:
    if status_short in ("1H", "2H", "ET", "BT", "P", "LIVE"):
        min_str = f" {minute}'" if minute else ""
        return (
            f"<span style='background:#dc2626;color:#fff;border-radius:5px;"
            f"padding:2px 8px;font-size:0.68rem;font-weight:900;'>"
            f"● LIVE{min_str}</span>"
        )
    if status_short == "HT":
        return (
            "<span style='background:#f59e0b;color:#000;border-radius:5px;"
            "padding:2px 8px;font-size:0.68rem;font-weight:900;'>⏸ MT</span>"
        )
    if status_short == "FT":
        return (
            "<span style='background:rgba(34,197,94,0.2);color:#4ade80;border-radius:5px;"
            "padding:2px 7px;font-size:0.68rem;font-weight:700;'>✅ FT</span>"
        )
    return (
        "<span style='background:rgba(255,255,255,0.08);color:#9ca3af;border-radius:5px;"
        "padding:2px 7px;font-size:0.68rem;'>🕐 À venir</span>"
    )


def _status_text(status_short: str, minute: Optional[int]) -> str:
    if status_short in ("1H", "2H", "ET", "BT", "P", "LIVE"):
        min_str = f" {minute}'" if minute else ""
        return f"LIVE{min_str}"
    if status_short == "HT":
        return "Mi-temps"
    if status_short == "FT":
        return "Terminé"
    return "À venir"


def _score_display(home_score, away_score, status_short: str) -> str:
    if status_short in ("1H", "2H", "ET", "HT", "FT", "LIVE"):
        h = home_score if home_score is not None else 0
        a = away_score if away_score is not None else 0
        return (
            f"<span style='background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);"
            f"border-radius:8px;padding:4px 14px;font-size:1.1rem;font-weight:900;"
            f"color:#fff;letter-spacing:2px;'>{h} – {a}</span>"
        )
    return ""


def _confidence_badge(label: str, color: str, stars: str) -> str:
    return (
        f"<span style='background:rgba(255,255,255,0.06);border:1px solid {color}33;"
        f"color:{color};border-radius:6px;padding:3px 10px;"
        f"font-size:0.72rem;font-weight:700;'>{stars} {label}</span>"
    )


def _progress_bar(value: float, color: str, max_val: float = 100.0) -> str:
    pct = min(100, value / max_val * 100)
    return (
        f"<div style='height:5px;background:rgba(255,255,255,0.08);"
        f"border-radius:3px;overflow:hidden;margin-top:2px;'>"
        f"<div style='width:{pct:.1f}%;height:100%;background:{color};"
        f"border-radius:3px;'></div></div>"
    )


def _kickoff_str(ko: str) -> str:
    if not ko:
        return "—"
    try:
        dt = datetime.fromisoformat(ko.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return ko[:16]


def _render_match_card(m: Dict, idx: int) -> None:
    wr     = m.get("win_result", {})
    status = m.get("status_short", "NS")
    minute = m.get("minute")
    h_score = m.get("home_score")
    a_score = m.get("away_score")

    win_score = wr.get("win_score", 0)
    win_prob  = wr.get("win_prob", 0)
    conf_label = wr.get("confidence_label", "Élevée")
    conf_color = wr.get("confidence_color", "#f59e0b")
    conf_stars = wr.get("confidence_stars", "★★★☆☆")
    pred_label = wr.get("predicted_label", "—")
    pred_team  = wr.get("predicted_team", "—")
    reasons    = wr.get("reasons", [])
    breakdown  = wr.get("breakdown", {})
    prob_h     = wr.get("prob_score_h", 0)
    prob_a     = wr.get("prob_score_a", 0)

    h_name = m.get("home_name", "—")
    a_name = m.get("away_name", "—")
    h_logo = m.get("home_logo", "")
    a_logo = m.get("away_logo", "")
    league = m.get("league_name", "—")
    flag   = m.get("league_flag", "")
    ko     = _kickoff_str(m.get("kick_off", ""))
    meta_text = f"{league} · {_status_text(status, minute)} · {ko}"

    is_live = status in ("1H", "2H", "ET", "HT", "LIVE")

    # Couleur bordure selon confiance
    if win_score >= 90:
        border_color = "#a855f7"
        glow = "box-shadow:0 0 20px rgba(168,85,247,0.15);"
    elif win_score >= 80:
        border_color = "#22c55e"
        glow = "box-shadow:0 0 16px rgba(34,197,94,0.12);"
    else:
        border_color = "#f59e0b"
        glow = ""

    # ── Logo helpers ──
    def logo_img(url: str, name: str) -> str:
        if url:
            return (
                f"<img src='{url}' style='width:36px;height:36px;object-fit:contain;"
                f"border-radius:4px;' onerror=\"this.style.display='none'\" />"
            )
        initial = name[0].upper() if name else "?"
        return (
            f"<div style='width:36px;height:36px;border-radius:50%;"
            f"background:rgba(0,212,255,0.15);display:flex;align-items:center;"
            f"justify-content:center;font-weight:800;font-size:14px;color:#00d4ff;'>"
            f"{initial}</div>"
        )

    score_html = _score_display(h_score, a_score, status)

    # ── Card HTML ──────────────────────────────────────────────────────────
    card = f"""
<div style='background:rgba(255,255,255,0.04);border:1px solid {border_color}55;
border-radius:16px;padding:18px;margin-bottom:14px;{glow}position:relative;
overflow:hidden;'>

  <!-- Numéro rang -->
  <div style='position:absolute;top:12px;right:14px;font-size:1.6rem;
  font-weight:900;color:rgba(255,255,255,0.06);line-height:1;'>#{idx}</div>

  <!-- Ligne 1 : Ligue + statut + heure -->
  <div style='font-size:0.72rem;color:#9ca3af;font-weight:600;margin-bottom:10px;'>
    {meta_text}
  </div>

  <!-- Ligne 2 : Équipes + score -->
  <div style='display:flex;align-items:center;justify-content:space-between;
  gap:12px;margin-bottom:12px;flex-wrap:wrap;'>
    <div style='display:flex;align-items:center;gap:10px;flex:1;min-width:120px;'>
      {logo_img(h_logo, h_name)}
      <span style='font-weight:800;font-size:0.95rem;color:#f1f5f9;'>{h_name}</span>
    </div>
    <div style='text-align:center;'>
      {score_html if is_live else
      f"<span style='font-size:0.78rem;color:#6b7280;'>vs</span>"}
    </div>
    <div style='display:flex;align-items:center;gap:10px;flex:1;min-width:120px;justify-content:flex-end;'>
      <span style='font-weight:800;font-size:0.95rem;color:#f1f5f9;text-align:right;'>{a_name}</span>
      {logo_img(a_logo, a_name)}
    </div>
  </div>

  <!-- Ligne 3 : Prédiction + confiance + WIN_SCORE -->
  <div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px;'>
    <span style='background:rgba(0,212,255,0.1);color:#00d4ff;border-radius:8px;
    padding:4px 12px;font-size:0.80rem;font-weight:800;border:1px solid rgba(0,212,255,0.25);'>
    🏆 {pred_label}</span>
    {_confidence_badge(conf_label, conf_color, conf_stars)}
    <span style='margin-left:auto;font-size:0.78rem;color:#9ca3af;'>
    Prob. <b style='color:#00d4ff;'>{win_prob*100:.0f}%</b>
    &nbsp;|&nbsp; Score IA <b style='color:{conf_color};'>{win_score}/100</b></span>
  </div>

  <!-- Ligne 4 : Score probable -->
  <div style='font-size:0.78rem;color:#9ca3af;margin-bottom:10px;'>
    ⚽ Score probable : <b style='color:#e2e8f0;'>{prob_h} – {prob_a}</b>
    &nbsp;·&nbsp; Favori : <b style='color:{conf_color};'>{pred_team}</b>
  </div>
"""

    # Raisons IA
    if reasons:
        reasons_html = "".join(
            f"<span style='font-size:0.72rem;color:#4ade80;margin-right:8px;'>✓ {r}</span>"
            for r in reasons
        )
        card += f"""
  <div style='background:rgba(34,197,94,0.05);border:1px solid rgba(34,197,94,0.15);
  border-radius:8px;padding:8px 12px;margin-bottom:10px;flex-wrap:wrap;display:flex;gap:4px;'>
    {reasons_html}
  </div>
"""

    # Breakdown barres
    if breakdown:
        bars_html = ""
        colors_map = {
            "Forme":    "#a855f7",
            "ELO":      "#00d4ff",
            "xG":       "#f97316",
            "Attaque":  "#f59e0b",
            "Défense":  "#22c55e",
            "H2H":      "#ec4899",
        }
        for key, val in breakdown.items():
            col = colors_map.get(key, "#9ca3af")
            bars_html += f"""
<div style='margin-bottom:5px;'>
  <div style='display:flex;justify-content:space-between;font-size:0.68rem;
  color:#9ca3af;margin-bottom:2px;'>
    <span>{key}</span><span style='color:{col};font-weight:700;'>{val}</span>
  </div>
  {_progress_bar(val, col)}
</div>"""

        total_bar = _progress_bar(win_score, conf_color)
        card += f"""
  <details style='margin-top:4px;'>
    <summary style='cursor:pointer;font-size:0.72rem;color:#6b7280;
    list-style:none;user-select:none;'>▶ Détails analyse</summary>
    <div style='margin-top:10px;'>
      {bars_html}
      <div style='margin-top:8px;border-top:1px solid rgba(255,255,255,0.08);padding-top:8px;'>
        <div style='display:flex;justify-content:space-between;font-size:0.72rem;
        color:#9ca3af;margin-bottom:2px;'>
          <span style='font-weight:700;color:#e2e8f0;'>Total WIN SCORE</span>
          <span style='font-weight:900;color:{conf_color};font-size:0.90rem;'>{win_score}/100</span>
        </div>
        {total_bar}
      </div>
    </div>
  </details>
"""

    card += "</div>"
    st.markdown(card, unsafe_allow_html=True)


def _render_history_row(pred: Dict) -> str:
    status = pred.get("status", "PENDING")
    if status == "WON":
        s_color = "#22c55e"
        s_label = "✅ GAGNÉ"
    elif status == "LOST":
        s_color = "#ef4444"
        s_label = "❌ PERDU"
    else:
        s_color = "#f59e0b"
        s_label = "⏳ Attente"

    try:
        bd = json.loads(pred.get("breakdown") or "{}")
    except Exception:
        bd = {}

    ts = pred.get("timestamp", "")[:16].replace("T", " ")
    win_score = pred.get("win_score", 0)
    win_prob  = round((pred.get("win_prob") or 0) * 100)

    return (
        f"<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;"
        f"padding:10px 14px;margin-bottom:6px;background:rgba(255,255,255,0.03);"
        f"border:1px solid rgba(255,255,255,0.07);border-radius:10px;'>"
        f"<span style='font-size:0.75rem;color:{s_color};font-weight:800;min-width:72px;'>{s_label}</span>"
        f"<div style='flex:1;min-width:0;'>"
        f"<div style='font-size:0.82rem;font-weight:700;color:#e2e8f0;'>"
        f"{pred.get('home_team','')} vs {pred.get('away_team','')}</div>"
        f"<div style='font-size:0.70rem;color:#6b7280;'>"
        f"{pred.get('league','')} · {pred.get('prediction','')}</div>"
        f"</div>"
        f"<div style='text-align:right;'>"
        f"<div style='font-size:0.78rem;color:#00d4ff;font-weight:700;'>{win_score}/100</div>"
        f"<div style='font-size:0.68rem;color:#6b7280;'>Prob {win_prob}% · {ts}</div>"
        f"</div>"
        f"</div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def render_top_victories_page(api) -> None:
    init_db()

    # Vérification automatique silencieuse des prédictions PENDING à l'ouverture de la page
    try:
        pending_list = get_pending_predictions()
        if pending_list:
            # Appel silencieux : si des mises à jour ont lieu, recharger l'interface
            updated = validate_pending(api)
            if updated:
                # Afficher un message puis recharger pour montrer les statuts mis à jour
                st.success(f"Mises à jour : {len(updated)} prédiction(s) résolue(s)")
                st.rerun()
    except Exception:
        # Ne pas bloquer la page si l'API est indisponible
        pass

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(
        "<h2 style='font-size:1.6rem;margin-bottom:2px;'>🏆 TOP 10 VICTOIRES IA</h2>"
        "<p style='color:#888;font-size:0.85rem;margin-bottom:16px;'>"
        "Sélection automatique · Forme 30% · ELO 20% · xG 15% · Attaque 15% · Défense 10% · H2H 10%</p>",
        unsafe_allow_html=True,
    )

    # ── Bouton principal ──────────────────────────────────────────────────────
    col_btn, col_val = st.columns([2, 1])
    with col_btn:
        run = st.button(
            "🏆 TOP 10 VICTOIRES IA — Analyser maintenant",
            type="primary",
            use_container_width=True,
        )
    with col_val:
        validate = st.button(
            "🔄 Vérifier résultats",
            use_container_width=True,
        )

    # ── Validation automatique ────────────────────────────────────────────────
    if validate:
        with st.spinner("Vérification des prédictions en attente…"):
            updated = validate_pending(api)
        if updated:
            for u in updated:
                result = u.get("result", "")
                home   = u.get("home_team", "")
                away   = u.get("away_team", "")
                if result == "WON":
                    st.success(f"✅ GAGNÉ — {home} vs {away}")
                else:
                    st.error(f"❌ PERDU — {home} vs {away}")
            st.rerun()
        else:
            st.info("Aucune prédiction terminée à mettre à jour.")

    # ── Chargement AUTOMATIQUE au démarrage ───────────────────────────────────────
    # Lancer l'analyse automatiquement pour la sélection selon forme/ELO/xG
    auto_analyze = run or not st.session_state.get("victories_analyzed", False)
    
    if auto_analyze:
        st.session_state["victories_analyzed"] = True
        st.session_state["victories_loaded"] = True

        if run:
            st.cache_data.clear()

        with st.spinner("🧠 Analyse IA des matchs en cours... Forme 30% · ELO 20% · xG 15%"):
            try:
                api_key = getattr(api, "api_key", None) or getattr(api, "_api_key", "default") or "default"
                matches = _fetch_cached(str(api_key), api)
                
                # Debug : afficher les résultats de l'analyse automatique
                if matches:
                    st.success(f"✅ Analyse automatique réussie : {len(matches)} match(s) sélectionné(s)")
                else:
                    st.session_state["victories_analyzed"] = False
                    st.session_state["victories_loaded"] = False
                    st.warning("⚠️ Aucun match ne répond aux critères de sélection automatique")
                    
            except Exception as e:
                st.error(f"❌ Erreur lors de l'analyse automatique : {e}")
                matches = []
    elif st.session_state.get("victories_loaded"):
        # Si déjà analysé, récupérer depuis le cache
        try:
            api_key = getattr(api, "api_key", None) or getattr(api, "_api_key", "default") or "default"
            matches = _fetch_cached(str(api_key), api)
        except Exception as e:
            st.error(f"Erreur lors du chargement : {e}")
            matches = []
    else:
        matches = []

    # ── Résultats ──────────────────────────────────────────────────────
    # TOUJOURS afficher les résultats, jamais d'écran vide
    if not matches:
        # Message de recherche active au lieu de "aucun match"
        st.markdown(
            "<div style='background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.25);"
            "border-radius:14px;padding:24px;text-align:center;margin:16px 0;'>"
            "<div style='font-size:2rem;margin-bottom:8px;'>🔍</div>"
            "<div style='font-size:1rem;font-weight:700;color:#60a5fa;'>Recherche des prochaines rencontres...</div>"
            "<div style='font-size:0.85rem;color:#9ca3af;margin-top:6px;'>"
            "Analyse des matchs LIVE et des prochaines 24 heures.<br>"
            "Le système trouve toujours les meilleures opportunités.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        
        # Bouton de recherche étendue
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔍 Étendre la recherche (48h)", type="secondary", use_container_width=True):
                st.session_state["victories_analyzed"] = False
                st.rerun()
    else:
        # Afficher toujours TOP 10 avec indication de confiance
        confidence_text = "confiance élevée" if len(matches) >= 8 else "confiance variable" if len(matches) >= 5 else "confiance modérée"
        confidence_color = "#22c55e" if len(matches) >= 8 else "#f59e0b" if len(matches) >= 5 else "#fb923c"
        
        st.markdown(
            f"<div style='font-size:0.82rem;color:#9ca3af;margin-bottom:14px;'>"
            f"<b style='color:#fff;'>TOP 10 VICTOIRES IA</b> — "
            f"<b style='color:{confidence_color};'>{len(matches)}</b> match(s) sélectionné(s) "
            f"<span style='color:#6b7280;'>· {confidence_text}</span></div>",
            unsafe_allow_html=True,
        )
        for i, m in enumerate(matches, 1):
            _render_match_card(m, i)

    # État initial : seulement si aucune analyse n'a encore été lancée
    if not st.session_state.get("victories_analyzed", False) and not run:
        st.markdown(
            "<div style='background:rgba(255,255,255,0.03);border:2px dashed rgba(255,255,255,0.1);"
            "border-radius:16px;padding:40px;text-align:center;margin:16px 0;'>"
            "<div style='font-size:3rem;margin-bottom:12px;'>🏆</div>"
            "<div style='font-size:1.1rem;font-weight:700;color:#e2e8f0;margin-bottom:8px;'>"
            "Analyse automatique en cours...</div>"
            "<div style='font-size:0.85rem;color:#9ca3af;'>"
            "L'IA analyse automatiquement les matchs selon :<br>"
            "<b style='color:#fff;'>Forme 30% · ELO 20% · xG 15% · Attaque 15% · Défense 10% · H2H 10%</b></div>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Statistiques journalières ──────────────────────────────────────────────
    st.markdown(
        "<div style='border-top:1px solid rgba(255,255,255,0.08);margin:24px 0 16px;'></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-weight:700;font-size:0.95rem;margin-bottom:10px;'>"
        "📊 Statistiques journalières</div>",
        unsafe_allow_html=True,
    )

    daily_stats = get_daily_stats()
    c1, c2, c3, c4, c5 = st.columns(5)
    cells = [
        (c1, "Sélectionnés", str(daily_stats["selected"]),   "#00d4ff"),
        (c2, "✅ Gagnés",    str(daily_stats["won"]),      "#22c55e"),
        (c3, "❌ Perdus",    str(daily_stats["lost"]),     "#ef4444"),
        (c4, "Winrate",      f"{daily_stats['winrate']}%", "#a855f7"),
        (c5, "ROI",          f"{daily_stats['roi']}%",      "#f59e0b"),
    ]
    for col, label, value, color in cells:
        with col:
            st.markdown(
                f"<div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);"
                f"border-radius:12px;padding:12px;text-align:center;'>"
                f"<div style='font-size:1.4rem;font-weight:900;color:{color};'>{value}</div>"
                f"<div style='font-size:0.70rem;color:#9ca3af;margin-top:2px;'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    
    # Afficher le profit
    profit_color = "#22c55e" if daily_stats["profit"] >= 0 else "#ef4444"
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);"
        f"border-radius:12px;padding:12px;text-align:center;margin-top:8px;'>"
        f"<div style='font-size:1.2rem;font-weight:900;color:{profit_color};'>"
        f"{'+' if daily_stats['profit'] >= 0 else ''}{daily_stats['profit']} unités</div>"
        f"<div style='font-size:0.70rem;color:#9ca3af;margin-top:2px;'>Profit journalier</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Tableau détaillé des prédictions du jour (avec coloration selon résultat)
    preds = daily_stats.get("predictions", [])
    if preds:
        rows_html = ""
        for p in preds:
            status = p.get("status", "PENDING")
            if status == "WON":
                row_bg = "rgba(34,197,94,0.08)"
                left = "#22c55e"
            elif status == "LOST":
                row_bg = "rgba(239,68,68,0.08)"
                left = "#ef4444"
            else:
                row_bg = "rgba(255,255,255,0.02)"
                left = "#9ca3af"

            ts = (p.get("timestamp") or "")[:16].replace("T", " ")
            home = p.get("home_team", "?")
            away = p.get("away_team", "?")
            pred = p.get("prediction", "—")
            rows_html += (
                f"<tr style='background:{row_bg};'>"
                f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);color:{left};font-weight:800;'>{status}</td>"
                f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{ts}</td>"
                f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{home} vs {away}</td>"
                f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{pred}</td>"
                f"</tr>"
            )

        table_html = (
            "<table style='width:100%;border-collapse:collapse;margin-top:12px;'>"
            "<thead><tr>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Statut</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Heure</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Match</th>"
            "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Prédiction</th>"
            "</tr></thead>"
            f"<tbody>{rows_html}</tbody></table>"
        )

        st.markdown("<div style='margin-top:12px;'><b>Prédictions du jour</b></div>", unsafe_allow_html=True)
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.caption("Aucune prédiction enregistrée aujourd'hui.")

    # ── STATISTIQUES SEMAINE EN COURS ─────────────────────────────────────
    weekly = None
    try:
        from modules.top_victories.victory_storage import get_weekly_stats
        weekly = get_weekly_stats()
    except Exception:
        weekly = None

    if weekly:
        st.markdown("<div style='margin-top:18px;font-weight:700;'>Statistiques cette semaine</div>", unsafe_allow_html=True)
        w_cells = [
            ("Sélectionnés", str(weekly["selected"]), "#00d4ff"),
            ("✅ Gagnés", str(weekly["won"]), "#22c55e"),
            ("❌ Perdus", str(weekly["lost"]), "#ef4444"),
            ("Winrate", f"{weekly['winrate']}%", "#a855f7"),
            ("Profit", f"{weekly['profit']}", "#22c55e" if weekly['profit']>=0 else "#ef4444"),
        ]
        cols = st.columns(len(w_cells))
        for col, (label, value, color) in zip(cols, w_cells):
            with col:
                st.markdown(
                    f"<div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;text-align:center;'>"
                    f"<div style='font-size:1.1rem;font-weight:900;color:{color};'>{value}</div>"
                    f"<div style='font-size:0.72rem;color:#9ca3af;margin-top:4px;'>{label}</div></div>",
                    unsafe_allow_html=True,
                )

        # Tableau hebdomadaire
        preds_w = weekly.get("predictions", [])
        if preds_w:
            rows_html = ""
            for p in preds_w:
                status = p.get("status", "PENDING")
                if status == "WON":
                    row_bg = "rgba(34,197,94,0.06)"
                    left = "#22c55e"
                elif status == "LOST":
                    row_bg = "rgba(239,68,68,0.06)"
                    left = "#ef4444"
                else:
                    row_bg = "rgba(255,255,255,0.02)"
                    left = "#9ca3af"
                ts = (p.get("timestamp") or "")[:16].replace("T", " ")
                rows_html += (
                    f"<tr style='background:{row_bg};'>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);color:{left};font-weight:800;'>{status}</td>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{ts}</td>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{p.get('home_team','')} vs {p.get('away_team','')}</td>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);'>{p.get('prediction','')}</td>"
                    f"</tr>"
                )
            table_html = (
                "<table style='width:100%;border-collapse:collapse;margin-top:12px;'>"
                "<thead><tr>"
                "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Statut</th>"
                "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Heure</th>"
                "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Match</th>"
                "<th style='text-align:left;padding:8px 10px;color:#9ca3af;'>Prédiction</th>"
                "</tr></thead>"
                f"<tbody>{rows_html}</tbody></table>"
            )
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.caption("Aucune prédiction enregistrée cette semaine.")

    # ── Statistiques globales ──────────────────────────────────────────────────
    st.markdown(
        "<div style='border-top:1px solid rgba(255,255,255,0.08);margin:20px 0 16px;'></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-weight:700;font-size:0.95rem;margin-bottom:10px;'>"
        "📈 Statistiques globales</div>",
        unsafe_allow_html=True,
    )

    global_stats = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    cells = [
        (c1, "Total",       str(global_stats["total"]),   "#00d4ff"),
        (c2, "✅ Gagnés",    str(global_stats["won"]),      "#22c55e"),
        (c3, "❌ Perdus",    str(global_stats["lost"]),     "#ef4444"),
        (c4, "Winrate",     f"{global_stats['winrate']}%", "#a855f7"),
    ]
    for col, label, value, color in cells:
        with col:
            st.markdown(
                f"<div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);"
                f"border-radius:12px;padding:12px;text-align:center;'>"
                f"<div style='font-size:1.3rem;font-weight:900;color:{color};'>{value}</div>"
                f"<div style='font-size:0.70rem;color:#9ca3af;margin-top:2px;'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Historique ────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='border-top:1px solid rgba(255,255,255,0.08);margin:20px 0 14px;'></div>",
        unsafe_allow_html=True,
    )
    with st.expander("📜 Historique des prédictions", expanded=False):
        history = get_prediction_history(limit=50)
        if not history:
            st.caption("Aucune prédiction enregistrée.")
        else:
            for pred in history:
                st.markdown(_render_history_row(pred), unsafe_allow_html=True)
