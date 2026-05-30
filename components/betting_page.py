"""
betting_page.py
===============
Interface utilisateur complète du système de paris prédictifs.
Modulaire — ne modifie aucun composant existant.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

from modules.betting.ticket_storage import (
    init_db, get_user_tickets, get_ticket_items, DEFAULT_USER_ID,
)
from modules.betting.points_manager import get_points_info
from modules.betting.ticket_manager import submit_ticket, check_all_active_tickets
from modules.betting.betting_engine import SUPPORTED_MARKETS, MARKET_OPTIONS


# ─────────────────────────────────────────────────────────────────────────────
# Helpers CSS / thème
# ─────────────────────────────────────────────────────────────────────────────

def _card(content: str, border_color: str = "rgba(255,255,255,0.1)", bg: str = "rgba(255,255,255,0.03)") -> str:
    return (
        f"<div style='background:{bg};border:1px solid {border_color};"
        f"border-radius:14px;padding:16px;margin-bottom:12px;'>{content}</div>"
    )


def _badge(text: str, color: str, bg: str) -> str:
    return (
        f"<span style='background:{bg};color:{color};border-radius:20px;"
        f"padding:3px 10px;font-size:0.75rem;font-weight:700;'>{text}</span>"
    )


STATUS_CONFIG = {
    "ACTIVE":  ("🟡 EN COURS",  "#f59e0b", "rgba(245,158,11,0.15)"),
    "WON":     ("🟢 GAGNÉ",     "#22c55e", "rgba(34,197,94,0.15)"),
    "LOST":    ("🔴 PERDU",     "#ef4444", "rgba(239,68,68,0.15)"),
    "EXPIRED": ("⚫ EXPIRÉ",    "#888888", "rgba(128,128,128,0.15)"),
}

ITEM_STATUS_CONFIG = {
    "PENDING": ("⏳ EN ATTENTE", "#f59e0b"),
    "WON":     ("✓ VALIDÉ",      "#22c55e"),
    "LOST":    ("✗ ÉCHOUÉ",      "#ef4444"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Affichage d'un ticket
# ─────────────────────────────────────────────────────────────────────────────

def _render_ticket(ticket: Dict[str, Any]) -> None:
    tid    = ticket["ticket_id"]
    status = ticket["ticket_status"]
    used   = ticket["points_used"]
    reward = ticket["reward_points"]
    created = ticket.get("created_at", "")[:16].replace("T", " ")

    s_label, s_color, s_bg = STATUS_CONFIG.get(status, STATUS_CONFIG["ACTIVE"])
    items = get_ticket_items(tid)
    nb_won = sum(1 for i in items if i["result"] == "WON")
    nb_total = len(items)

    header_html = (
        f"<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px;'>"
        f"<span style='font-weight:800;font-size:1.05rem;'>Ticket #{tid}</span>"
        f"{_badge(s_label, s_color, s_bg)}"
        f"<span style='color:#888;font-size:0.78rem;margin-left:auto;'>📅 {created}</span>"
        f"</div>"
        f"<div style='display:flex;gap:16px;margin-bottom:12px;flex-wrap:wrap;'>"
        f"<span style='font-size:0.85rem;'>💸 Coût : <b>{used} ⭐</b></span>"
        f"<span style='font-size:0.85rem;'>📊 Progression : <b>{nb_won}/{nb_total}</b></span>"
    )
    if status == "WON":
        header_html += f"<span style='color:#22c55e;font-size:0.85rem;font-weight:700;'>+{reward} ⭐ gagnés</span>"
    elif status == "LOST":
        header_html += f"<span style='color:#ef4444;font-size:0.85rem;'>Perdu</span>"
    header_html += "</div>"

    items_html = ""
    for item in items:
        r = item.get("result", "PENDING")
        r_label, r_color = ITEM_STATUS_CONFIG.get(r, ITEM_STATUS_CONFIG["PENDING"])
        items_html += (
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"padding:7px 10px;margin-bottom:5px;background:rgba(255,255,255,0.04);"
            f"border-radius:8px;flex-wrap:wrap;gap:6px;'>"
            f"<div>"
            f"<span style='font-size:0.78rem;color:#aaa;'>{item['home_team']} vs {item['away_team']}</span><br>"
            f"<span style='font-size:0.82rem;font-weight:600;'>{item['market']} — {item['prediction']}</span>"
            f"</div>"
            f"<span style='color:{r_color};font-weight:700;font-size:0.82rem;'>{r_label}</span>"
            f"</div>"
        )

    # Barre de progression
    pct = int(nb_won / nb_total * 100) if nb_total > 0 else 0
    bar_color = "#22c55e" if status == "WON" else "#f59e0b" if status == "ACTIVE" else "#ef4444"
    progress_html = (
        f"<div style='margin-top:10px;'>"
        f"<div style='height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden;'>"
        f"<div style='width:{pct}%;height:100%;background:{bar_color};border-radius:3px;transition:width 0.4s;'></div>"
        f"</div>"
        f"<div style='font-size:0.72rem;color:#888;margin-top:3px;text-align:right;'>{nb_won}/{nb_total} validés</div>"
        f"</div>"
    )

    border = s_color
    bg = s_bg.replace("0.15", "0.06")
    st.markdown(
        _card(header_html + items_html + progress_html, border_color=border, bg=bg),
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Formulaire création ticket
# ─────────────────────────────────────────────────────────────────────────────

def _match_label(m: Dict) -> str:
    """Génère un label enrichi pour un match dans le selectbox."""
    mtype = m.get("_type", "")
    home  = m.get("home_team", "?")
    away  = m.get("away_team", "?")
    league = m.get("league", "")

    # Infos temporelles pour les matchs futurs
    time_info = ""
    if mtype != "🔴 LIVE":
        date_disp = m.get("start_date_display", "")
        start_time = m.get("start_time", "")
        if date_disp or start_time:
            time_info = f"  [{date_disp} {start_time}]"

    league_short = f" · {league[:25]}" if league and league != "—" else ""
    return f"{mtype}{time_info}  {home} vs {away}{league_short}"


def _render_create_ticket(live_matches: List[Dict], future_matches: List[Dict], api) -> None:
    st.markdown("### 🎟️ Créer un ticket")

    # Initialiser la liste de sélections en session
    if "bet_selections" not in st.session_state:
        st.session_state.bet_selections = []

    # ── Filtre par type de match ──────────────────────────────────────────
    nb_live   = len(live_matches)
    nb_future = len(future_matches)

    if nb_live == 0 and nb_future == 0:
        st.warning("Aucun match disponible actuellement. Revenez plus tard.")
        return

    # Choisir quelle catégorie afficher
    filter_options = []
    if nb_live > 0:
        filter_options.append(f"🔴 Matchs en direct ({nb_live})")
    if nb_future > 0:
        filter_options.append(f"📅 Matchs à venir ({nb_future})")
    if nb_live > 0 and nb_future > 0:
        filter_options.insert(0, f"🌐 Tous les matchs ({nb_live + nb_future})")

    st.markdown(
        "<div style='background:rgba(0,212,255,0.07);border-left:3px solid #00d4ff;"
        "border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;'>"
        "<b>Étape 1</b> — Choisissez le type de match</div>",
        unsafe_allow_html=True,
    )

    match_filter = st.radio(
        "Type de match",
        filter_options,
        horizontal=True,
        key="bet_match_filter",
        label_visibility="collapsed",
    )

    # Construire la liste filtrée
    all_matches = []
    if "Tous" in match_filter or "direct" in match_filter:
        for m in live_matches:
            all_matches.append({**m, "_type": "🔴 LIVE"})
    if "Tous" in match_filter or "venir" in match_filter:
        for m in future_matches:
            all_matches.append({**m, "_type": "📅 Futur"})

    # Afficher un compteur informatif
    if "venir" in match_filter or "Tous" in match_filter:
        st.markdown(
            f"<div style='font-size:0.78rem;color:#888;margin-bottom:8px;'>"
            f"📅 {nb_future} match(s) à venir disponibles · trié(s) par date de début</div>",
            unsafe_allow_html=True,
        )

    # ── ÉTAPE 2 : Choisir un match spécifique ────────────────────────────
    st.markdown(
        "<div style='background:rgba(0,212,255,0.07);border-left:3px solid #00d4ff;"
        "border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;'>"
        "<b>Étape 2</b> — Choisissez un match</div>",
        unsafe_allow_html=True,
    )

    if not all_matches:
        st.info("Aucun match dans cette catégorie.")
        return

    match_idx = st.selectbox(
        "Choisir un match",
        range(len(all_matches)),
        format_func=lambda i: _match_label(all_matches[i]),
        key="bet_match_sel",
        label_visibility="collapsed",
    )
    selected_match = all_matches[match_idx]

    # Afficher la fiche du match sélectionné
    m_home  = selected_match.get("home_team", "?")
    m_away  = selected_match.get("away_team", "?")
    m_league = selected_match.get("league", "")
    m_type  = selected_match.get("_type", "")
    m_date  = selected_match.get("start_date_display", "")
    m_time  = selected_match.get("start_time", "")
    m_venue = selected_match.get("venue", "")

    time_badge = f"📅 {m_date} à {m_time}" if m_date else ""
    venue_badge = f" · 📍 {m_venue}" if m_venue else ""
    league_badge = f" · 🏆 {m_league}" if m_league and m_league != "—" else ""

    status_color = "#e02424" if "LIVE" in m_type else "#f59e0b"
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.05);border:1px solid {status_color}33;"
        f"border-left:4px solid {status_color};border-radius:0 10px 10px 0;"
        f"padding:10px 14px;margin-bottom:12px;'>"
        f"<div style='font-size:0.75rem;color:#aaa;margin-bottom:4px;'>{m_type}{league_badge}{venue_badge}</div>"
        f"<div style='font-size:1rem;font-weight:700;'>{m_home} <span style='color:#888;'>vs</span> {m_away}</div>"
        f"<div style='font-size:0.78rem;color:#f59e0b;margin-top:3px;'>{time_badge}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── ÉTAPE 3 : Choisir un marché ───────────────────────────────────────
    st.markdown(
        "<div style='background:rgba(0,212,255,0.07);border-left:3px solid #00d4ff;"
        "border-radius:0 8px 8px 0;padding:10px 14px;margin:12px 0;'>"
        "<b>Étape 3</b> — Choisissez un marché</div>",
        unsafe_allow_html=True,
    )
    market = st.selectbox(
        "Marché",
        SUPPORTED_MARKETS,
        key="bet_market_sel",
        label_visibility="collapsed",
    )

    # ── ÉTAPE 4 : Choisir une prédiction ─────────────────────────────────
    st.markdown(
        "<div style='background:rgba(0,212,255,0.07);border-left:3px solid #00d4ff;"
        "border-radius:0 8px 8px 0;padding:10px 14px;margin:12px 0;'>"
        "<b>Étape 4</b> — Choisissez votre prédiction</div>",
        unsafe_allow_html=True,
    )
    opts = MARKET_OPTIONS.get(market, [])
    prediction = st.selectbox(
        "Prédiction",
        opts if opts else ["—"],
        key="bet_prediction_sel",
        label_visibility="collapsed",
    )

    # ── Bouton Ajouter ────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:6px;'>", unsafe_allow_html=True)
    if st.button("➕ Ajouter cette sélection au ticket", use_container_width=True, type="secondary"):
        if prediction == "—":
            st.warning("Prédiction invalide pour ce marché.")
        else:
            # Vérifier doublon dans le ticket en cours
            exists = any(
                s["fixture_id"] == selected_match.get("fixture_id") and s["market"] == market
                for s in st.session_state.bet_selections
            )
            if exists:
                st.warning(f"Ce marché ({market}) est déjà dans votre ticket pour ce match.")
            elif len(st.session_state.bet_selections) >= 8:
                st.warning("Maximum 8 sélections par ticket.")
            else:
                st.session_state.bet_selections.append({
                    "fixture_id": selected_match.get("fixture_id"),
                    "home_team":  selected_match.get("home_team", ""),
                    "away_team":  selected_match.get("away_team", ""),
                    "market":     market,
                    "prediction": prediction,
                })
                st.success(f"✓ Ajouté : {selected_match.get('home_team')} vs {selected_match.get('away_team')} — {market} → {prediction}")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Récapitulatif du ticket en cours ──────────────────────────────────
    st.markdown("---")
    nb = len(st.session_state.bet_selections)

    if nb == 0:
        st.markdown(
            "<div style='text-align:center;color:#888;padding:20px;border:2px dashed rgba(255,255,255,0.1);"
            "border-radius:12px;font-size:0.88rem;'>Votre ticket est vide.<br>"
            "Ajoutez au moins 1 sélection pour valider.</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"<div style='font-weight:700;font-size:1rem;margin-bottom:10px;'>"
        f"🎟️ Votre ticket — {nb} sélection(s)</div>",
        unsafe_allow_html=True,
    )

    # Afficher chaque sélection avec bouton suppression individuelle
    for i, sel in enumerate(st.session_state.bet_selections):
        cols = st.columns([5, 1])
        with cols[0]:
            st.markdown(
                f"<div style='background:rgba(255,255,255,0.05);border-radius:10px;"
                f"padding:10px 14px;margin-bottom:6px;'>"
                f"<div style='font-size:0.78rem;color:#888;margin-bottom:2px;'>"
                f"⚽ {sel['home_team']} vs {sel['away_team']}</div>"
                f"<div style='font-size:0.9rem;font-weight:600;'>"
                f"<span style='color:#00d4ff;'>{sel['market']}</span>"
                f" → {sel['prediction']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            if st.button("🗑️", key=f"del_sel_{i}_{sel['fixture_id']}_{market}", help="Retirer"):
                st.session_state.bet_selections.pop(i)
                st.rerun()

    # Résumé coût + boutons action
    st.markdown(
        f"<div style='background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);"
        f"border-radius:10px;padding:12px 16px;margin-top:8px;display:flex;"
        f"justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;'>"
        f"<div>"
        f"<div style='font-weight:700;'>📋 {nb} sélection(s)</div>"
        f"<div style='font-size:0.8rem;color:#aaa;'>Coût : <b>5 ⭐</b> · "
        f"Gain potentiel si gagné : <b>{5 * {1:1,2:2,3:4,4:7,5:12,6:20}.get(nb, 30)} ⭐</b></div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    col_sub, col_clr = st.columns(2)
    with col_sub:
        if st.button("✅ Valider mon ticket (5 ⭐)", type="primary", use_container_width=True):
            result = submit_ticket(st.session_state.bet_selections, user_id=DEFAULT_USER_ID)
            if result["success"]:
                st.success(result["message"])
                st.session_state.bet_selections = []
                st.rerun()
            else:
                st.error(result["message"])
    with col_clr:
        if st.button("🗑️ Vider le ticket", use_container_width=True):
            st.session_state.bet_selections = []
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────

def render_betting_page(
    api,
    live_matches: Optional[List[Dict]] = None,
    future_matches: Optional[List[Dict]] = None,
) -> None:
    """Rendu complet de la page Paris."""
    init_db()
    live_matches   = live_matches   or []
    future_matches = future_matches or []

    # Header
    st.markdown(
        "<h2 style='font-size:1.6rem;margin-bottom:4px;'>🎰 Paris Prédictifs</h2>"
        "<p style='color:#888;font-size:0.88rem;margin-bottom:16px;'>"
        "Système de tickets gamifiés · Prédisez, gagnez des étoiles ⭐</p>",
        unsafe_allow_html=True,
    )

    # ── Points utilisateur ──────────────────────────────────────────────────
    info = get_points_info(DEFAULT_USER_ID)
    pts = info["points"]
    refill_label = info.get("refill_in_label")

    pts_color = "#22c55e" if pts >= 5 else "#ef4444"
    pts_html = (
        f"<div style='display:flex;align-items:center;gap:16px;flex-wrap:wrap;"
        f"background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);"
        f"border-radius:14px;padding:14px 20px;margin-bottom:20px;'>"
        f"<div style='font-size:2rem;font-weight:900;color:{pts_color};'>{pts} ⭐</div>"
        f"<div>"
        f"<div style='font-weight:700;font-size:0.95rem;'>Mes Points</div>"
        f"<div style='color:#888;font-size:0.8rem;'>Coût par ticket : 5 ⭐</div>"
    )
    if not info["can_bet"] and refill_label:
        pts_html += f"<div style='color:#f59e0b;font-size:0.78rem;'>⏰ Recharge dans {refill_label}</div>"
    pts_html += "</div></div>"
    st.markdown(pts_html, unsafe_allow_html=True)

    # ── Vérification automatique des tickets actifs ────────────────────────
    active_tickets = get_user_tickets(DEFAULT_USER_ID, status="ACTIVE")
    if active_tickets and st.button("🔄 Vérifier mes tickets actifs", use_container_width=True):
        with st.spinner("Vérification en cours…"):
            results = check_all_active_tickets(api, DEFAULT_USER_ID)
        for r in results:
            if r.get("status") == "WON":
                st.success(r["message"])
            elif r.get("status") == "LOST":
                st.error(r["message"])
            elif r.get("already_resolved"):
                pass
            else:
                st.info(r.get("message", ""))
        if any(r.get("status") in ("WON", "LOST") for r in results):
            st.rerun()

    # ── Tabs ────────────────────────────────────────────────────────────────
    tab_labels = ["🎟️ Créer Ticket", "🟡 Actifs", "✅ Terminés", "📜 Historique"]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        if not info["can_bet"]:
            st.warning(
                f"⭐ Points insuffisants ({pts} ⭐). "
                + (f"Recharge dans {refill_label}." if refill_label else "Jouez pour en gagner!")
            )
        else:
            _render_create_ticket(live_matches, future_matches, api)

    with tabs[1]:
        tickets_active = get_user_tickets(DEFAULT_USER_ID, status="ACTIVE")
        if not tickets_active:
            st.info("Aucun ticket actif.")
        else:
            st.caption(f"📋 {len(tickets_active)} ticket(s) en cours")
            for t in tickets_active:
                _render_ticket(t)

    with tabs[2]:
        tickets_done = [
            t for t in get_user_tickets(DEFAULT_USER_ID)
            if t["ticket_status"] in ("WON", "LOST")
        ]
        if not tickets_done:
            st.info("Aucun ticket terminé.")
        else:
            won = [t for t in tickets_done if t["ticket_status"] == "WON"]
            lost = [t for t in tickets_done if t["ticket_status"] == "LOST"]
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    f"<div style='text-align:center;background:rgba(34,197,94,0.1);"
                    f"border-radius:10px;padding:10px;'>"
                    f"<div style='font-size:1.4rem;font-weight:800;color:#22c55e;'>{len(won)}</div>"
                    f"<div style='font-size:0.8rem;color:#aaa;'>Gagnés</div></div>",
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    f"<div style='text-align:center;background:rgba(239,68,68,0.1);"
                    f"border-radius:10px;padding:10px;'>"
                    f"<div style='font-size:1.4rem;font-weight:800;color:#ef4444;'>{len(lost)}</div>"
                    f"<div style='font-size:0.8rem;color:#aaa;'>Perdus</div></div>",
                    unsafe_allow_html=True,
                )
            st.markdown("---")
            for t in tickets_done:
                _render_ticket(t)

    with tabs[3]:
        all_tickets = get_user_tickets(DEFAULT_USER_ID)
        if not all_tickets:
            st.info("Aucun ticket dans l'historique.")
        else:
            total_won  = sum(t["reward_points"] for t in all_tickets if t["ticket_status"] == "WON")
            total_used = sum(t["points_used"]   for t in all_tickets)
            nb_won  = sum(1 for t in all_tickets if t["ticket_status"] == "WON")
            nb_lost = sum(1 for t in all_tickets if t["ticket_status"] == "LOST")
            nb_active = sum(1 for t in all_tickets if t["ticket_status"] == "ACTIVE")

            # Stats résumées
            stats_html = (
                f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px;'>"
                f"<div style='background:rgba(255,255,255,0.04);border-radius:10px;padding:10px;text-align:center;'>"
                f"<div style='font-size:1.2rem;font-weight:800;'>{len(all_tickets)}</div>"
                f"<div style='font-size:0.75rem;color:#888;'>Total tickets</div></div>"
                f"<div style='background:rgba(34,197,94,0.1);border-radius:10px;padding:10px;text-align:center;'>"
                f"<div style='font-size:1.2rem;font-weight:800;color:#22c55e;'>{nb_won}</div>"
                f"<div style='font-size:0.75rem;color:#888;'>Gagnés</div></div>"
                f"<div style='background:rgba(239,68,68,0.1);border-radius:10px;padding:10px;text-align:center;'>"
                f"<div style='font-size:1.2rem;font-weight:800;color:#ef4444;'>{nb_lost}</div>"
                f"<div style='font-size:0.75rem;color:#888;'>Perdus</div></div>"
                f"<div style='background:rgba(245,158,11,0.1);border-radius:10px;padding:10px;text-align:center;'>"
                f"<div style='font-size:1.2rem;font-weight:800;color:#f59e0b;'>+{total_won} ⭐</div>"
                f"<div style='font-size:0.75rem;color:#888;'>Gagnés</div></div>"
                f"</div>"
            )
            st.markdown(stats_html, unsafe_allow_html=True)

            # Table historique
            rows_html = "".join(
                f"<tr style='border-bottom:1px solid rgba(255,255,255,0.06);'>"
                f"<td style='padding:8px;font-weight:600;'>#{t['ticket_id']}</td>"
                f"<td style='padding:8px;font-size:0.78rem;color:#aaa;'>{t.get('created_at','')[:10]}</td>"
                f"<td style='padding:8px;'>{STATUS_CONFIG.get(t['ticket_status'],('—','#888',''))[0]}</td>"
                f"<td style='padding:8px;'>{t['points_used']} ⭐</td>"
                f"<td style='padding:8px;color:#22c55e;'>"
                f"{'+' + str(t['reward_points']) + ' ⭐' if t['reward_points'] > 0 else '—'}</td>"
                f"</tr>"
                for t in all_tickets
            )
            st.markdown(
                f"<div style='overflow-x:auto;'><table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
                f"<thead><tr style='border-bottom:2px solid rgba(255,255,255,0.15);'>"
                f"<th style='padding:8px;text-align:left;'>Ticket</th>"
                f"<th style='padding:8px;text-align:left;'>Date</th>"
                f"<th style='padding:8px;text-align:left;'>Statut</th>"
                f"<th style='padding:8px;text-align:left;'>Coût</th>"
                f"<th style='padding:8px;text-align:left;'>Gain</th>"
                f"</tr></thead><tbody>{rows_html}</tbody></table></div>",
                unsafe_allow_html=True,
            )
