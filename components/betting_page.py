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
import streamlit.components.v1 as components

from modules.betting.ticket_storage import (
    init_db, get_user_tickets, get_ticket_items, delete_ticket, DEFAULT_USER_ID,
)
from modules.betting.points_manager import get_points_info
from modules.betting.ticket_manager import (
    submit_ticket, check_all_active_tickets,
    compute_ticket_sell_offer, sell_ticket_action,
)
from modules.betting.betting_engine import SUPPORTED_MARKETS, MARKET_OPTIONS
from modules.betting.reward_engine import compute_reward


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
    "SOLD":    ("💰 VENDU",     "#a78bfa", "rgba(167,139,250,0.15)"),
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

def _format_kickoff(ko: str) -> str:
    """Formate un kick_off ISO en date/heure lisible."""
    if not ko:
        return ""
    try:
        dt = datetime.fromisoformat(ko.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%d/%m à %H:%M")
    except Exception:
        return ko[:16].replace("T", " ")


def _item_time_badge(item: Dict[str, Any]) -> str:
    """
    Calcule dynamiquement le badge temporel d'un item :
    - LIVE avec temps écoulé estimé si kick_off passé et résultat encore PENDING
    - Countdown si match dans moins de 24h
    - Date/heure sinon
    """
    ko      = (item.get("kick_off") or item.get("start_datetime_local") or "")
    lm_db   = int(item.get("live_minute") or 0)
    result  = item.get("result", "PENDING")
    now_utc = datetime.now(timezone.utc)

    ko_dt = None
    if ko:
        try:
            ko_dt = datetime.fromisoformat(ko.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            pass

    # ── Match terminé : afficher juste la date ──────────────────────────
    if result in ("WON", "LOST"):
        ko_str = _format_kickoff(ko)
        return (
            f"<span style='background:rgba(255,255,255,0.06);color:#888;"
            f"border-radius:6px;padding:1px 7px;font-size:0.70rem;margin-right:6px;'>"
            f"📅 {ko_str}</span>"
        ) if ko_str else ""

    # ── Match en cours (kick_off passé + PENDING) ────────────────────────
    if ko_dt and ko_dt <= now_utc and result == "PENDING":
        elapsed_min = int((now_utc - ko_dt).total_seconds() // 60)
        # Utiliser live_minute de la DB si plus précis (match ajouté en live)
        display_min = lm_db if lm_db > elapsed_min else elapsed_min
        # Plafonner à 90+5 pour ne pas afficher 200'
        if display_min > 95:
            display_min = 90
        return (
            f"<span style='background:rgba(239,68,68,0.20);color:#f87171;"
            f"border-radius:6px;padding:2px 8px;font-size:0.72rem;"
            f"font-weight:800;margin-right:6px;animation:pulse 1.4s infinite;'>"
            f"🔴 EN JEU {display_min}'</span>"
        )

    # ── Match futur ──────────────────────────────────────────────────────
    if ko_dt:
        diff_sec = (ko_dt - now_utc).total_seconds()
        ko_local = _format_kickoff(ko)
        if 0 < diff_sec <= 3600:
            mins_left = int(diff_sec // 60)
            return (
                f"<span style='background:rgba(34,197,94,0.15);color:#4ade80;"
                f"border-radius:6px;padding:2px 8px;font-size:0.70rem;"
                f"font-weight:700;margin-right:6px;'>"
                f"⏰ Dans {mins_left} min</span>"
            )
        elif 0 < diff_sec <= 86400:
            hrs  = int(diff_sec // 3600)
            mins = int((diff_sec % 3600) // 60)
            return (
                f"<span style='background:rgba(245,158,11,0.12);color:#fbbf24;"
                f"border-radius:6px;padding:2px 8px;font-size:0.70rem;"
                f"margin-right:6px;'>"
                f"📅 {ko_local} (dans {hrs}h{mins:02d})</span>"
            )
        else:
            return (
                f"<span style='background:rgba(245,158,11,0.10);color:#f59e0b;"
                f"border-radius:6px;padding:1px 7px;font-size:0.70rem;"
                f"margin-right:6px;'>📅 {ko_local}</span>"
            )

    # ── Pas de kick_off connu ────────────────────────────────────────────
    return ""


def _live_time_badge(minute: int, home_score: int, away_score: int,
                     home: str, away: str) -> str:
    """Badge LIVE professionnel : temps de jeu + score en cours."""
    return (
        f"<div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;'>"
        f"<span style='background:#dc2626;color:#fff;border-radius:5px;"
        f"padding:2px 8px;font-size:0.72rem;font-weight:900;letter-spacing:0.5px;'>"
        f"● LIVE {minute}'</span>"
        f"<span style='background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);"
        f"border-radius:6px;padding:3px 10px;font-size:0.88rem;font-weight:800;"
        f"color:#fff;letter-spacing:1px;'>"
        f"{home_score} – {away_score}</span>"
        f"<span style='font-size:0.70rem;color:#9ca3af;'>{home} vs {away}</span>"
        f"</div>"
    )


def _future_time_badge(ko: str, home: str, away: str) -> str:
    """Badge futur : date/heure + countdown si proche."""
    if not ko:
        return (
            f"<div style='font-size:0.72rem;color:#6b7280;margin-bottom:4px;'>"
            f"⏳ Heure non disponible · {home} vs {away}</div>"
        )
    try:
        ko_dt   = datetime.fromisoformat(ko.replace("Z", "+00:00")).astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        diff    = (ko_dt - now_utc).total_seconds()
        local   = ko_dt.astimezone()
        date_str = local.strftime("%d/%m/%Y")
        time_str = local.strftime("%H:%M")
        if diff <= 0:
            elapsed = int(-diff // 60)
            if elapsed <= 95:
                label = f"● LIVE ∼{elapsed}'"
                bg, col = "#dc2626", "#fff"
            else:
                label = f"✅ Terminé"
                bg, col = "rgba(34,197,94,0.2)", "#4ade80"
        elif diff <= 3600:
            m = int(diff // 60)
            label = f"⏰ Dans {m} min · {time_str}"
            bg, col = "rgba(34,197,94,0.15)", "#4ade80"
        elif diff <= 86400:
            h, m = int(diff // 3600), int((diff % 3600) // 60)
            label = f"📅 {date_str} {time_str} · dans {h}h{m:02d}"
            bg, col = "rgba(245,158,11,0.12)", "#fbbf24"
        else:
            label = f"📅 {date_str} à {time_str}"
            bg, col = "rgba(255,255,255,0.06)", "#9ca3af"
        return (
            f"<div style='display:inline-flex;align-items:center;gap:8px;margin-bottom:4px;'>"
            f"<span style='background:{bg};color:{col};border-radius:5px;"
            f"padding:2px 9px;font-size:0.72rem;font-weight:700;'>{label}</span>"
            f"<span style='font-size:0.70rem;color:#6b7280;'>{home} vs {away}</span>"
            f"</div>"
        )
    except Exception:
        return f"<div style='font-size:0.72rem;color:#6b7280;margin-bottom:4px;'>{home} vs {away}</div>"


def _render_ticket(
    ticket: Dict[str, Any],
    show_sell: bool = True,
    live_ctx: Optional[Dict[int, Dict]] = None,
) -> None:
    """
    live_ctx : {fixture_id: {minute, home_score, away_score, kick_off}} depuis API live.
    """
    tid    = ticket["ticket_id"]
    status = ticket["ticket_status"]
    used   = ticket["points_used"]
    reward = ticket["reward_points"]
    created = ticket.get("created_at", "")[:16].replace("T", " ")
    live_ctx = live_ctx or {}

    s_label, s_color, s_bg = STATUS_CONFIG.get(status, STATUS_CONFIG["ACTIVE"])
    items    = get_ticket_items(tid)
    nb_won   = sum(1 for i in items if i["result"] == "WON")
    nb_total = len(items)

    # Gain potentiel basé sur les cotes réelles
    total_odds = 1.0
    for it in items:
        total_odds *= max(1.0, float(it.get("odds") or 1.0))
    potential_pts = max(round(used * total_odds), compute_reward(used, nb_total)["reward_points"])

    header_html = (
        f"<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;'>"
        f"<span style='font-weight:900;font-size:1.08rem;'>Ticket #{tid}</span>"
        f"{_badge(s_label, s_color, s_bg)}"
        f"<span style='color:#6b7280;font-size:0.75rem;margin-left:auto;'>⏱ {created}</span>"
        f"</div>"
        f"<div style='display:flex;gap:20px;margin-bottom:12px;flex-wrap:wrap;align-items:center;'>"
        f"<span style='font-size:0.82rem;color:#9ca3af;'>💸 Mise : <b style='color:#fff;'>{used} ⭐</b></span>"
        f"<span style='font-size:0.82rem;color:#9ca3af;'>📊 {nb_won}/{nb_total} validé(s)</span>"
    )
    if status == "ACTIVE":
        header_html += (
            f"<span style='font-size:0.88rem;color:#f59e0b;font-weight:700;'>"
            f"🏆 Gain potentiel : {potential_pts} ⭐</span>"
        )
    elif status == "WON":
        header_html += f"<span style='background:linear-gradient(135deg, #22c55e, #16a34a);color:white;font-size:0.95rem;font-weight:900;padding:4px 12px;border-radius:8px;'>🏆 GAGNÉ +{reward} ⭐</span>"
    elif status == "LOST":
        header_html += f"<span style='background:linear-gradient(135deg, #ef4444, #dc2626);color:white;font-size:0.90rem;font-weight:800;padding:4px 12px;border-radius:8px;'>❌ PERDU</span>"
    elif status == "SOLD":
        sold_p = ticket.get("sold_price", 0)
        header_html += f"<span style='color:#a78bfa;font-size:0.85rem;'>💰 Vendu : {sold_p} ⭐</span>"
    header_html += "</div>"

    items_html = ""
    for item in items:
        r        = item.get("result", "PENDING")
        r_label, r_color = ITEM_STATUS_CONFIG.get(r, ITEM_STATUS_CONFIG["PENDING"])
        odds_val = float(item.get("odds") or 1.0)
        fid      = item.get("fixture_id")
        h_team   = item.get("home_team", "?")
        a_team   = item.get("away_team", "?")

        # Enrichissement live depuis API
        lctx    = live_ctx.get(fid) or {}
        minute  = lctx.get("minute")
        h_score = lctx.get("home_score")
        a_score = lctx.get("away_score")
        ko      = lctx.get("kick_off") or item.get("kick_off") or item.get("start_datetime_local") or ""

        # ── Badge temporel + score ──
        if minute is not None and h_score is not None:
            time_row = _live_time_badge(int(minute), int(h_score), int(a_score or 0), h_team, a_team)
        elif r in ("WON", "LOST"):
            ko_str = _format_kickoff(ko)
            # Récupérer le score final depuis l'item
            final_score = item.get("final_score", "")
            if not final_score:
                # Essayer de récupérer depuis les scores home/away si disponibles
                home_goals = item.get("home_goals", 0)
                away_goals = item.get("away_goals", 0)
                if home_goals is not None and away_goals is not None:
                    final_score = f"{home_goals}-{away_goals}"
            
            # Afficher avec le score final et la couleur appropriée
            score_color = "#22c55e" if r == "WON" else "#ef4444"
            status_icon = "✅" if r == "WON" else "❌"
            
            if final_score:
                time_row = (
                    f"<div style='font-size:0.70rem;color:#6b7280;margin-bottom:4px;'>"
                    f"📅 {ko_str} · {h_team} vs {a_team}</div>"
                    f"<div style='font-size:0.75rem;font-weight:700;color:{score_color};margin-bottom:2px;'>"
                    f"{status_icon} Score final : {final_score}</div>"
                ) if ko_str else (
                    f"<div style='font-size:0.70rem;color:#6b7280;margin-bottom:4px;'>{h_team} vs {a_team}</div>"
                    f"<div style='font-size:0.75rem;font-weight:700;color:{score_color};margin-bottom:2px;'>"
                    f"{status_icon} Score final : {final_score}</div>"
                )
            else:
                time_row = (
                    f"<div style='font-size:0.70rem;color:#6b7280;margin-bottom:4px;'>"
                    f"📅 {ko_str} · {h_team} vs {a_team}</div>"
                    f"<div style='font-size:0.70rem;color:{score_color};margin-bottom:2px;'>"
                    f"{status_icon} Match terminé</div>"
                ) if ko_str else (
                    f"<div style='font-size:0.70rem;color:#6b7280;margin-bottom:4px;'>{h_team} vs {a_team}</div>"
                    f"<div style='font-size:0.70rem;color:{score_color};margin-bottom:2px;'>"
                    f"{status_icon} Match terminé</div>"
                )
        else:
            time_row = _future_time_badge(ko, h_team, a_team)

        # Couleur fond selon statut
        if r == "WON":
            item_bg = "rgba(34,197,94,0.07)"
            item_border = "rgba(34,197,94,0.25)"
        elif r == "LOST":
            item_bg = "rgba(239,68,68,0.07)"
            item_border = "rgba(239,68,68,0.25)"
        elif minute is not None:
            item_bg = "rgba(220,38,38,0.06)"
            item_border = "rgba(220,38,38,0.30)"
        else:
            item_bg = "rgba(255,255,255,0.03)"
            item_border = "rgba(255,255,255,0.08)"

        # Badge de statut amélioré pour les matchs terminés
        if r == "WON":
            status_badge = f"<span style='background:#22c55e;color:white;font-weight:800;font-size:0.75rem;white-space:nowrap;padding:2px 8px;border-radius:12px;'>✅ GAGNÉ</span>"
        elif r == "LOST":
            status_badge = f"<span style='background:#ef4444;color:white;font-weight:800;font-size:0.75rem;white-space:nowrap;padding:2px 8px;border-radius:12px;'>❌ PERDU</span>"
        else:
            status_badge = f"<span style='color:{r_color};font-weight:800;font-size:0.80rem;white-space:nowrap;'>{r_label}</span>"

        items_html += (
            f"<div style='border:1px solid {item_border};background:{item_bg};"
            f"border-radius:10px;padding:10px 12px;margin-bottom:6px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:8px;'>"
            f"<div style='flex:1;min-width:0;'>"
            f"{time_row}"
            f"<div style='font-size:0.86rem;font-weight:700;color:#e5e7eb;'>"
            f"<span style='color:#00d4ff;'>{item['market']}</span>"
            f" → {item['prediction']}"
            f"<span style='background:rgba(0,212,255,0.08);color:#67e8f9;border-radius:4px;"
            f"padding:1px 6px;font-size:0.68rem;font-weight:600;margin-left:6px;'>@{odds_val:.2f}</span>"
            f"</div>"
            f"</div>"
            f"<div>{status_badge}</div>"
            f"</div>"
            f"</div>"
        )

    # Barre de progression
    pct = int(nb_won / nb_total * 100) if nb_total > 0 else 0
    bar_color = (
        "#22c55e" if status == "WON" else
        "#a78bfa" if status == "SOLD" else
        "#f59e0b" if status == "ACTIVE" else "#ef4444"
    )
    progress_html = (
        f"<div style='margin-top:10px;'>"
        f"<div style='display:flex;justify-content:space-between;font-size:0.70rem;"
        f"color:#6b7280;margin-bottom:4px;'>"
        f"<span>Progression</span><span>{nb_won}/{nb_total} validé(s)</span></div>"
        f"<div style='height:5px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden;'>"
        f"<div style='width:{pct}%;height:100%;background:{bar_color};"
        f"border-radius:3px;transition:width 0.5s ease;'></div>"
        f"</div>"
        f"</div>"
    )

    border = s_color
    bg = s_bg.replace("0.15", "0.05")
    st.markdown(
        _card(header_html + items_html + progress_html, border_color=border, bg=bg),
        unsafe_allow_html=True,
    )

    # ── Système de Vente Classique (ACTIVE uniquement) ─────────────────────
    if show_sell and status == "ACTIVE":
        # Vérifier s'il reste des événements non terminés
        pending_items = [i for i in items if i.get("result") == "PENDING"]
        
        if pending_items:
            # Utiliser uniquement le système de vente classique simple et stable
            _render_fallback_sell_buttons(tid)
        else:
            # Tous les événements sont terminés
            st.markdown(
                "<div style='background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);"
                "border-radius:8px;padding:10px;text-align:center;'>"
                "<span style='color:#ef4444;font-weight:700;'>🚫 Vente indisponible</span><br>"
                "<span style='color:#fca5a5;font-size:0.75rem;'>Tous les événements sont terminés</span>"
                "</div>",
                unsafe_allow_html=True,
            )
    elif show_sell and status != "ACTIVE":
        # Ticket n'est plus actif
        status_display = {
            "WON": "GAGNÉ",
            "LOST": "PERDU",
            "SOLD": "VENDU"
        }.get(status, status)
        
        st.markdown(
            "<div style='background:rgba(107,114,128,0.1);border:1px solid rgba(107,114,128,0.3);"
            "border-radius:8px;padding:10px;text-align:center;'>"
            f"<span style='color:#9ca3af;font-weight:700;'>🚫 Vente indisponible</span><br>"
            f"<span style='color:#d1d5db;font-size:0.75rem;'>Ticket clôturé ({status_display})</span>"
            "</div>",
            unsafe_allow_html=True,
        )


def _render_fallback_sell_buttons(ticket_id: int) -> None:
    """Affiche les boutons de vente classiques en fallback."""
    offer = compute_ticket_sell_offer(ticket_id)
    sell_cols = st.columns(2)
    with sell_cols[0]:
        if offer["can_sell_full"]:
            if st.button(
                f"💰 Vendre {offer['sell_price_full']} ⭐",
                key=f"sell_full_fallback_{ticket_id}", use_container_width=True,
            ):
                res = sell_ticket_action(ticket_id, mode="full")
                st.success(res["message"]) if res["success"] else st.error(res["message"])
                if res["success"]: st.rerun()
        else:
            st.markdown(
                f"<div style='font-size:0.72rem;color:#4b5563;padding:5px 2px;'>"
                f"🔒 {offer['reason_no_full']}</div>",
                unsafe_allow_html=True,
            )
    with sell_cols[1]:
        if offer["can_sell_half"]:
            if st.button(
                f"⚡ Cash-out ½ ({offer['sell_price_half']} ⭐)",
                key=f"sell_half_fallback_{ticket_id}", use_container_width=True,
            ):
                res = sell_ticket_action(ticket_id, mode="half")
                st.success(res["message"]) if res["success"] else st.error(res["message"])
                if res["success"]: st.rerun()
        else:
            st.markdown(
                f"<div style='font-size:0.72rem;color:#4b5563;padding:5px 2px;'>"
                f"🕐 {offer['reason_no_half']}</div>",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Formulaire création ticket
# ─────────────────────────────────────────────────────────────────────────────

def _market_is_expired(match: Dict, market: str, prediction: str) -> tuple[bool, str]:
    """
    Retourne (True, raison) si le marché sélectionné est devenu invalide
    pour un match en cours (l'événement concerné a déjà eu lieu).
    """
    mtype   = match.get("_type", "")
    minute  = match.get("minute", 0) or 0
    status  = match.get("status_short", "NS")
    home_g  = match.get("home_score", 0) or 0
    away_g  = match.get("away_score", 0) or 0
    total_g = home_g + away_g

    is_live     = "LIVE" in mtype or status in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE")
    is_finished = status in ("FT", "AET", "PEN")
    is_2nd_half = status in ("2H", "ET", "BT") or (status == "HT") or minute > 45

    # Match déjà terminé → aucun marché valide
    if is_finished:
        return True, "Ce match est déjà terminé."

    if not is_live:
        return False, ""

    # ── Marchés 1ère mi-temps uniquement ────────────────────────────────
    if market == "Mi-temps":
        first_half_only = [
            "Domicile marque 1ère MT",
            "Extérieur marque 1ère MT",
            "BTTS 1ère MT",
            "Over 0.5 1ère MT",
        ]
        if prediction in first_half_only and is_2nd_half:
            return True, f"Le marché '{prediction}' concerne la 1ère mi-temps déjà terminée."

    # ── Over/Under Buts : seuil déjà dépassé ────────────────────────────
    if market == "Over/Under Buts":
        try:
            parts = prediction.split()
            direction = parts[0]   # "Over" ou "Under"
            threshold = float(parts[1])  # ex. 2.5
            if direction == "Over" and total_g > threshold:
                return True, f"Le marché '{prediction}' est déjà acquis ({total_g} buts). Sélection interdite."
            if direction == "Under" and total_g > threshold:
                return True, f"Le marché '{prediction}' est déjà raté ({total_g} buts). Sélection interdite."
        except (IndexError, ValueError):
            pass

    # ── BTTS : déjà résolu ───────────────────────────────────────────────
    if market == "BTTS":
        btts_done = home_g >= 1 and away_g >= 1
        if prediction == "GG Oui" and btts_done:
            return True, f"BTTS Oui est déjà acquis ({home_g}-{away_g}). Sélection interdite."
        if prediction == "GG Non" and btts_done:
            return True, f"BTTS Non est déjà impossible ({home_g}-{away_g}). Sélection interdite."

    # ── Score Exact : score actuel dépasse déjà la prédiction ───────────
    if market == "Score Exact":
        try:
            ph, pa = map(int, prediction.split("-"))
            if home_g > ph or away_g > pa:
                return True, f"Score exact '{prediction}' impossible — score actuel {home_g}-{away_g}."
        except (ValueError, AttributeError):
            pass

    # ── Over/Under Corners (>= 70 min, la majorité des corners sont pris) ─
    if market == "Corners" and minute >= 80:
        return True, f"Marché Corners indisponible — match trop avancé ({minute}')."

    # ── Cartons idem ────────────────────────────────────────────────────
    if market == "Cartons" and minute >= 80:
        return True, f"Marché Cartons indisponible — match trop avancé ({minute}')."

    return False, ""


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


def _render_ticket_recap(api) -> None:
    """Affiche le récapitulatif du ticket en cours de construction + boutons valider/vider."""
    nb = len(st.session_state.get("bet_selections", []))

    if nb == 0:
        st.markdown(
            "<div style='text-align:center;color:#888;padding:20px;"
            "border:2px dashed rgba(255,255,255,0.1);border-radius:12px;font-size:0.88rem;'>"
            "Votre ticket est vide.<br>Ajoutez au moins 1 sélection pour valider.</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"<div style='font-weight:700;font-size:1rem;margin-bottom:10px;'>"
        f"🎟️ Votre ticket — {nb} sélection(s)</div>",
        unsafe_allow_html=True,
    )

    total_odds_preview = 1.0
    for i, sel in enumerate(st.session_state.bet_selections):
        ko_disp = _format_kickoff(sel.get("kick_off", ""))
        lm      = int(sel.get("live_minute", 0) or 0)
        odds_v  = float(sel.get("odds", 1.0) or 1.0)
        total_odds_preview *= max(1.0, odds_v)

        if lm > 0:
            time_info  = f"🔴 LIVE {lm}'"
            time_color = "#f87171"
        elif ko_disp:
            time_info  = f"📅 {ko_disp}"
            time_color = "#f59e0b"
        else:
            time_info  = ""
            time_color = "#888"

        cols = st.columns([5, 1])
        with cols[0]:
            st.markdown(
                f"<div style='background:rgba(255,255,255,0.05);border-radius:10px;"
                f"padding:10px 14px;margin-bottom:6px;'>"
                f"<div style='display:flex;gap:8px;align-items:center;margin-bottom:3px;'>"
                f"<span style='font-size:0.70rem;color:{time_color};font-weight:700;'>{time_info}</span>"
                f"<span style='background:rgba(0,212,255,0.1);color:#00d4ff;border-radius:4px;"
                f"padding:1px 6px;font-size:0.70rem;font-weight:700;'>@{odds_v:.2f}</span>"
                f"</div>"
                f"<div style='font-size:0.78rem;color:#aaa;'>⚽ {sel['home_team']} vs {sel['away_team']}</div>"
                f"<div style='font-size:0.88rem;font-weight:600;margin-top:2px;'>"
                f"<span style='color:#00d4ff;'>{sel['market']}</span> → {sel['prediction']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            if st.button("🗑️", key=f"del_sel_{i}_{sel['fixture_id']}", help="Retirer"):
                st.session_state.bet_selections.pop(i)
                st.rerun()

    # Mise
    current_pts = get_points_info(DEFAULT_USER_ID)["points"]
    max_mise    = max(5, current_pts)

    st.markdown(
        "<div style='font-size:0.82rem;color:#9ca3af;margin:14px 0 4px;'>"
        "💰 Choisissez votre mise <span style='color:#f59e0b;font-weight:700;'>(min 5 ⭐)</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    if max_mise > 5:
        mise = st.slider(
            "Mise",
            min_value=5,
            max_value=max_mise,
            value=5,
            step=1,
            key="bet_mise_slider",
            label_visibility="collapsed",
        )
    else:
        mise = 5
        st.markdown(
            "<div style='background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);"
            "border-radius:8px;padding:8px 14px;font-size:0.82rem;color:#f59e0b;'>"
            "Mise fixée à <b>5 ⭐</b> (solde exact)</div>",
            unsafe_allow_html=True,
        )

    reward_table  = compute_reward(mise, nb)
    potential_pts = max(round(mise * total_odds_preview), reward_table["reward_points"])

    st.markdown(
        f"<div style='background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);"
        f"border-radius:12px;padding:14px 18px;margin-top:6px;'>"
        f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:center;'>"
        f"<div><div style='font-size:0.75rem;color:#9ca3af;'>Sélections</div>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#fff;'>{nb}</div></div>"
        f"<div><div style='font-size:0.75rem;color:#9ca3af;'>Mise</div>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#f59e0b;'>{mise} ⭐</div></div>"
        f"<div><div style='font-size:0.75rem;color:#9ca3af;'>Cote combinée</div>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#00d4ff;'>x{total_odds_preview:.2f}</div></div>"
        f"<div><div style='font-size:0.75rem;color:#9ca3af;'>Gain si victoire</div>"
        f"<div style='font-size:1.3rem;font-weight:900;color:#22c55e;'>+{potential_pts} ⭐</div></div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    col_sub, col_clr = st.columns(2)
    with col_sub:
        if st.button(f"✅ Valider le ticket ({mise} ⭐)", type="primary", use_container_width=True):
            if current_pts < mise:
                st.error(f"⭐ Solde insuffisant ({current_pts} ⭐). Minimum requis : {mise} ⭐.")
            else:
                result = submit_ticket(
                    st.session_state.bet_selections,
                    user_id=DEFAULT_USER_ID,
                    points_used=mise,
                )
                if result["success"]:
                    st.success(result["message"])
                    st.session_state.bet_selections = []
                    st.session_state.bet_show_matches = False
                    st.rerun()
                else:
                    st.error(result["message"])
    with col_clr:
        if st.button("🗑️ Vider le ticket", use_container_width=True):
            st.session_state.bet_selections = []
            st.rerun()


@st.dialog("🎰 Mon Ticket de Paris", width="large")
def _ticket_modal(api) -> None:
    """Modal Streamlit natif affichant le ticket complet avec validation."""
    nb = len(st.session_state.get("bet_selections", []))
    if nb == 0:
        st.info("Votre ticket est vide.")
        return
    _render_ticket_recap(api)


def render_floating_bet_button(api=None) -> None:
    """
    Badge flottant compact en bas à droite via components.html (document parent).
    + vrai st.button caché qui déclenche le dialog.
    """
    nb = len(st.session_state.get("bet_selections", []))
    if nb == 0:
        return

    # ── Badge injecté dans le document PARENT (pas une iframe) ────────────
    components.html(
        f"""
        <style>
          @keyframes _pb {{
            0%   {{ box-shadow: 0 0 0 0 rgba(245,158,11,0.7); transform: scale(1); }}
            50%  {{ box-shadow: 0 0 0 14px rgba(245,158,11,0); transform: scale(1.06); }}
            100% {{ box-shadow: 0 0 0 0 rgba(245,158,11,0); transform: scale(1); }}
          }}
          #fbet {{
            position: fixed;
            bottom: 26px; right: 26px;
            z-index: 999999;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: linear-gradient(135deg,#f59e0b,#d97706);
            color: #000;
            border: none;
            border-radius: 50px;
            padding: 11px 20px;
            font-size: 0.92rem;
            font-weight: 900;
            cursor: pointer;
            animation: _pb 1.5s ease-in-out infinite;
            box-shadow: 0 4px 20px rgba(245,158,11,0.5);
            white-space: nowrap;
            font-family: sans-serif;
          }}
          #fbet:hover {{ background: linear-gradient(135deg,#fbbf24,#f59e0b); }}
          #fbet .cnt {{
            background: #dc2626; color: #fff;
            border-radius: 50%; width: 22px; height: 22px;
            display: inline-flex; align-items: center;
            justify-content: center; font-size: 0.75rem; font-weight: 900;
          }}
        </style>
        <button id="fbet" onclick="
          var btns = window.parent.document.querySelectorAll('button');
          for (var i = 0; i < btns.length; i++) {{
            var t = btns[i].innerText || btns[i].textContent;
            if (t && t.trim() === '__FBET__') {{
              btns[i].click();
              break;
            }}
          }}
        ">
          🎰 Mon Ticket <span class="cnt">{nb}</span>
        </button>
        """,
        height=80,
        scrolling=False,
    )

    # Bouton Streamlit caché — texte unique pour le ciblage JS
    st.markdown(
        """<style>
        div[data-testid="stButton"]:has(p) button p { display:inline; }
        </style>""",
        unsafe_allow_html=True,
    )
    if st.button("__FBET__", key="fbet_trigger_btn"):
        _ticket_modal(api)
    # Masquer le bouton via CSS après rendu
    st.markdown(
        """<style>
        div[data-testid="stButton"]:has(button:not([kind])) {
            visibility: hidden; height: 0; overflow: hidden; margin: 0; padding: 0;
        }
        </style>""",
        unsafe_allow_html=True,
    )


def render_inline_bet_panel(match: Dict, match_type: str = "future") -> None:
    """
    Panneau paris inline style 1xbet.
    S'affiche directement sous la carte du match.
    match_type: 'live' | 'future'
    """
    if "bet_selections" not in st.session_state:
        st.session_state.bet_selections = []

    fixture_id = match.get("fixture_id") or match.get("id")
    home       = match.get("home_team", "?")
    away       = match.get("away_team", "?")
    status     = match.get("status_short") or match.get("status", "NS")
    minute     = match.get("minute")
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    kick_off   = (match.get("kick_off") or match.get("start_datetime_local")
                  or match.get("fixture_date", ""))

    # Couleur panneau selon type
    panel_color  = "#dc2626" if match_type == "live" else "#f59e0b"
    panel_border = "rgba(220,38,38,0.3)" if match_type == "live" else "rgba(245,158,11,0.3)"

    # ── Entête panneau ─────────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.03);border:1px solid {panel_border};"
        f"border-top:3px solid {panel_color};border-radius:0 0 12px 12px;"
        f"padding:14px 16px;margin-bottom:8px;margin-top:-4px;'>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div style='font-size:0.78rem;color:#9ca3af;margin-bottom:10px;'>"
        f"🎰 <b style='color:#fff;'>Parier sur :</b> {home} vs {away}</div>",
        unsafe_allow_html=True,
    )

    # ── Grille de marchés style 1xbet ─────────────────────────────────────
    # Marchés disponibles selon statut
    is_live = match_type == "live" or status in ("1H", "2H", "HT", "ET", "LIVE")

    # Marchés rapides (boutons direct)
    QUICK_MARKETS = {
        "1X2": [
            ("1", "Domicile (1)"),
            ("X", "Nul (X)"),
            ("2", "Extérieur (2)"),
        ],
        "Double Chance": [
            ("1X", "1X"),
            ("12", "12"),
            ("X2", "X2"),
        ],
        "BTTS": [
            ("GG Oui", "GG Oui"),
            ("GG Non", "GG Non"),
        ],
        "Over/Under Buts": [
            ("O1.5", "Over 1.5"),
            ("U1.5", "Under 1.5"),
            ("O2.5", "Over 2.5"),
            ("U2.5", "Under 2.5"),
            ("O3.5", "Over 3.5"),
        ],
    }
    if not is_live:
        QUICK_MARKETS["Corners"] = [("O8.5", "Over 8.5"), ("U8.5", "Under 8.5")]
        QUICK_MARKETS["Cartons"] = [("O2.5", "Over 2.5"), ("U2.5", "Under 2.5")]

    fid_key = str(fixture_id)

    for market_name, options in QUICK_MARKETS.items():
        # Vérifier si le marché est compatible
        m_tmp = {**match, "status_short": status}
        if not _market_compatible_with(m_tmp, market_name):
            continue

        st.markdown(
            f"<div style='font-size:0.70rem;color:#6b7280;font-weight:700;"
            f"text-transform:uppercase;letter-spacing:0.05em;margin:8px 0 4px;'>"
            f"{market_name}</div>",
            unsafe_allow_html=True,
        )

        btn_cols = st.columns(len(options))
        for col, (label, pred) in zip(btn_cols, options):
            with col:
                # Vérifier si déjà dans le ticket
                already = any(
                    s.get("fixture_id") == fixture_id and s.get("market") == market_name
                    and s.get("prediction") == pred
                    for s in st.session_state.bet_selections
                )
                # Vérifier si marché expiré pour ce pari précis
                expired, _ = _market_is_expired(
                    {**match, "_type": "🔴 LIVE" if is_live else "📅 Futur",
                     "status_short": status, "minute": minute or 0,
                     "home_score": home_score or 0, "away_score": away_score or 0},
                    market_name, pred
                )

                btn_style = "primary" if already else "secondary"
                btn_label = f"✓ {label}" if already else label

                if expired:
                    st.markdown(
                        f"<div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);"
                        f"border-radius:6px;padding:5px;text-align:center;font-size:0.72rem;"
                        f"color:#4b5563;'>{label}<br><span style='font-size:0.60rem;'>expiré</span></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button(
                        btn_label,
                        key=f"ibp_{fid_key}_{market_name}_{label}",
                        type=btn_style,
                        use_container_width=True,
                    ):
                        if already:
                            # Désélectionner
                            st.session_state.bet_selections = [
                                s for s in st.session_state.bet_selections
                                if not (s.get("fixture_id") == fixture_id
                                        and s.get("market") == market_name
                                        and s.get("prediction") == pred)
                            ]
                        elif len(st.session_state.bet_selections) >= 8:
                            st.warning("Maximum 8 sélections.")
                        elif any(
                            s.get("fixture_id") == fixture_id and s.get("market") == market_name
                            for s in st.session_state.bet_selections
                        ):
                            st.warning(f"Marché {market_name} déjà sélectionné pour ce match.")
                        else:
                            st.session_state.bet_selections.append({
                                "fixture_id":  fixture_id,
                                "home_team":   home,
                                "away_team":   away,
                                "market":      market_name,
                                "prediction":  pred,
                                "kick_off":    kick_off,
                                "live_minute": int(minute or 0),
                                "odds":        1.85,
                            })
                        st.rerun()

    # ── Autres marchés via selectbox ──────────────────────────────────────
    with st.expander("➕ Autres marchés (Mi-temps, Score exact, Corners…)", expanded=False):
        other_markets = [m for m in SUPPORTED_MARKETS if m not in QUICK_MARKETS]
        if not is_live:
            other_markets = SUPPORTED_MARKETS  # tous si futur

        sel_market = st.selectbox(
            "Marché",
            [m for m in other_markets if _market_compatible_with({**match, "status_short": status}, m)],
            key=f"ibp_other_market_{fid_key}",
            label_visibility="collapsed",
        )
        if sel_market:
            opts = MARKET_OPTIONS.get(sel_market, [])
            sel_pred = st.selectbox(
                "Prédiction",
                opts if opts else ["—"],
                key=f"ibp_other_pred_{fid_key}",
                label_visibility="collapsed",
            )
            if sel_pred and sel_pred != "—":
                if st.button(
                    f"➕ Ajouter {sel_market} → {sel_pred}",
                    key=f"ibp_other_add_{fid_key}",
                    use_container_width=True,
                ):
                    expired2, reason2 = _market_is_expired(
                        {**match, "_type": "🔴 LIVE" if is_live else "📅 Futur",
                         "status_short": status, "minute": minute or 0,
                         "home_score": home_score or 0, "away_score": away_score or 0},
                        sel_market, sel_pred
                    )
                    if expired2:
                        st.error(f"🚫 {reason2}")
                    elif any(s.get("fixture_id") == fixture_id and s.get("market") == sel_market
                             for s in st.session_state.bet_selections):
                        st.warning(f"Marché {sel_market} déjà dans le ticket pour ce match.")
                    elif len(st.session_state.bet_selections) >= 8:
                        st.warning("Maximum 8 sélections.")
                    else:
                        st.session_state.bet_selections.append({
                            "fixture_id":  fixture_id,
                            "home_team":   home,
                            "away_team":   away,
                            "market":      sel_market,
                            "prediction":  sel_pred,
                            "kick_off":    kick_off,
                            "live_minute": int(minute or 0),
                            "odds":        1.85,
                        })
                        st.rerun()

    # ── Mini récap ticket ──────────────────────────────────────────────────
    nb = len(st.session_state.bet_selections)
    if nb > 0:
        st.markdown(
            f"<div style='background:rgba(0,212,255,0.07);border:1px solid rgba(0,212,255,0.2);"
            f"border-radius:8px;padding:8px 14px;margin-top:10px;font-size:0.80rem;'>"
            f"🎟️ <b style='color:#00d4ff;'>{nb}</b> sélection(s) dans votre ticket &nbsp;"
            f"<span style='color:#6b7280;'>· Allez sur la page <b>Paris</b> pour valider</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def _market_compatible_with(match: Dict, market: str) -> bool:
    """Retourne True si le marché est encore jouable sur ce match."""
    status = match.get("status_short", "NS")
    minute = int(match.get("minute", 0) or 0)
    if status in ("FT", "AET", "PEN", "CANC", "PST", "ABD"):
        return False
    if market in ("Corners", "Cartons") and minute >= 80:
        return False
    if market == "Mi-temps":
        # Les prédictions 1ère MT ne sont plus jouables après 45'
        if minute > 45 and status not in ("NS", "1H"):
            return False
    return True


def _render_create_ticket(live_matches: List[Dict], future_matches: List[Dict], api) -> None:
    st.markdown("### 🎟️ Créer un ticket")

    # Initialiser les états de session
    if "bet_selections" not in st.session_state:
        st.session_state.bet_selections = []
    if "bet_market_chosen" not in st.session_state:
        st.session_state.bet_market_chosen = None
    if "bet_show_matches" not in st.session_state:
        st.session_state.bet_show_matches = False

    nb_live   = len(live_matches)
    nb_future = len(future_matches)

    if nb_live == 0 and nb_future == 0:
        st.warning("Aucun match disponible actuellement. Revenez plus tard.")
        return

    # ── ÉTAPE 1 : Choisir le marché ───────────────────────────────────────
    st.markdown(
        "<div style='background:rgba(0,212,255,0.07);border-left:3px solid #00d4ff;"
        "border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:12px;'>"
        "<b>Étape 1</b> — Choisissez votre marché de pari</div>",
        unsafe_allow_html=True,
    )

    market = st.selectbox(
        "Marché",
        SUPPORTED_MARKETS,
        key="bet_market_sel",
        label_visibility="collapsed",
    )

    # Décrire le marché sélectionné
    _MARKET_DESC = {
        "1X2":             "Victoire domicile · Nul · Victoire extérieur",
        "Double Chance":   "1X · X2 · 12 — deux résultats couverts",
        "BTTS":            "Les deux équipes marquent (GG Oui / GG Non)",
        "Over/Under Buts": "Nombre total de buts dans le match",
        "Prochain But":    "Quelle équipe marque le prochain but",
        "Mi-temps":        "Résultat ou buts sur une mi-temps spécifique",
        "Corners":         "Nombre total de corners dans le match",
        "Cartons":         "Nombre total de cartons dans le match",
        "Score Exact":     "Score final exact du match",
    }
    desc = _MARKET_DESC.get(market, "")
    if desc:
        st.markdown(
            f"<div style='font-size:0.78rem;color:#9ca3af;margin-bottom:12px;"
            f"padding:6px 12px;background:rgba(255,255,255,0.03);border-radius:8px;'>"
            f"ℹ️ {desc}</div>",
            unsafe_allow_html=True,
        )

    # ── Bouton — Voir les matchs disponibles ─────────────────────────────
    if st.button(
        f"� Voir les matchs disponibles pour « {market} »",
        type="primary",
        use_container_width=True,
        key="btn_show_matches",
    ):
        st.session_state.bet_market_chosen = market
        st.session_state.bet_show_matches  = True
        st.rerun()

    # Réinitialiser si le marché change
    if st.session_state.bet_market_chosen != market:
        st.session_state.bet_show_matches = False

    if not st.session_state.bet_show_matches:
        # Invitation visuelle
        st.markdown(
            "<div style='text-align:center;padding:28px;border:2px dashed rgba(255,255,255,0.08);"
            "border-radius:14px;color:#6b7280;margin-top:8px;'>"
            "Choisissez un marché ci-dessus, puis cliquez sur le bouton<br>"
            "pour découvrir les matchs disponibles.</div>",
            unsafe_allow_html=True,
        )
        # Afficher quand même le récapitulatif du ticket en cours s'il y a des sélections
        _render_ticket_recap(api)
        return

    # ── ÉTAPE 2 : Type de match (Live / Futur) ────────────────────────────
    st.markdown(
        "<div style='background:rgba(0,212,255,0.07);border-left:3px solid #00d4ff;"
        "border-radius:0 8px 8px 0;padding:10px 14px;margin:14px 0 10px;'>"
        "<b>Étape 2</b> — Choisissez le type de match</div>",
        unsafe_allow_html=True,
    )

    filter_options = []
    if nb_live > 0 and nb_future > 0:
        filter_options.append(f"🌐 Tous ({nb_live + nb_future})")
    if nb_live > 0:
        filter_options.append(f"🔴 En direct ({nb_live})")
    if nb_future > 0:
        filter_options.append(f"📅 À venir ({nb_future})")

    match_filter = st.radio(
        "Type",
        filter_options,
        horizontal=True,
        key="bet_match_filter",
        label_visibility="collapsed",
    )

    # Construire le pool de matchs selon le filtre
    all_matches = []
    if "direct" in match_filter or "Tous" in match_filter:
        for m in live_matches:
            all_matches.append({**m, "_type": "🔴 LIVE"})
    if "venir" in match_filter or "Tous" in match_filter:
        for m in future_matches:
            all_matches.append({**m, "_type": "📅 Futur"})

    # Filtrer les matchs compatibles avec le marché choisi
    compatible = [m for m in all_matches if _market_compatible_with(m, market)]
    incompatible_count = len(all_matches) - len(compatible)

    if not compatible:
        st.warning(f"Aucun match disponible pour le marché « {market} » dans cette catégorie.")
        if incompatible_count:
            st.caption(f"{incompatible_count} match(s) exclu(s) car terminé(s) ou marché expiré.")
        _render_ticket_recap(api)
        return

    # Résumé filtrage
    info_parts = [f"<b style='color:#00d4ff;'>{len(compatible)}</b> match(s) compatibles"]
    if incompatible_count:
        info_parts.append(f"<span style='color:#6b7280;'>{incompatible_count} exclu(s)</span>")
    st.markdown(
        f"<div style='font-size:0.78rem;color:#9ca3af;margin-bottom:10px;'>"
        + " · ".join(info_parts) + "</div>",
        unsafe_allow_html=True,
    )

    # ── ÉTAPE 3 : Choisir un match parmi les compatibles ──────────────────
    st.markdown(
        "<div style='background:rgba(0,212,255,0.07);border-left:3px solid #00d4ff;"
        "border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;'>"
        "<b>Étape 3</b> — Choisissez un match</div>",
        unsafe_allow_html=True,
    )

    match_idx = st.selectbox(
        "Choisir un match",
        range(len(compatible)),
        format_func=lambda i: _match_label(compatible[i]),
        key="bet_match_sel",
        label_visibility="collapsed",
    )
    selected_match = compatible[match_idx]

    # Fiche visuelle du match sélectionné
    m_home   = selected_match.get("home_team", "?")
    m_away   = selected_match.get("away_team", "?")
    m_league = selected_match.get("league", "")
    m_type   = selected_match.get("_type", "")
    m_date   = selected_match.get("start_date_display", "")
    m_time   = selected_match.get("start_time", "")
    m_minute = selected_match.get("minute")
    m_hscore = selected_match.get("home_score")
    m_ascore = selected_match.get("away_score")

    status_color = "#e02424" if "LIVE" in m_type else "#f59e0b"
    league_badge = f" · 🏆 {m_league}" if m_league and m_league != "—" else ""

    if "LIVE" in m_type and m_minute is not None and m_hscore is not None:
        time_info = (
            f"<span style='background:#dc2626;color:#fff;border-radius:4px;"
            f"padding:2px 8px;font-size:0.72rem;font-weight:900;'>● LIVE {m_minute}'</span>"
            f"&nbsp;<span style='font-weight:800;font-size:1rem;color:#fff;'>"
            f"{m_hscore} – {m_ascore}</span>"
        )
    elif m_date or m_time:
        time_info = f"<span style='color:#f59e0b;font-size:0.78rem;'>📅 {m_date} à {m_time}</span>"
    else:
        time_info = ""

    st.markdown(
        f"<div style='background:rgba(255,255,255,0.05);border:1px solid {status_color}44;"
        f"border-left:4px solid {status_color};border-radius:0 12px 12px 0;"
        f"padding:12px 16px;margin-bottom:14px;'>"
        f"<div style='font-size:0.72rem;color:#9ca3af;margin-bottom:4px;'>"
        f"{m_type}{league_badge}</div>"
        f"<div style='font-size:1.05rem;font-weight:800;color:#f1f5f9;margin-bottom:6px;'>"
        f"{m_home} <span style='color:#4b5563;'>vs</span> {m_away}</div>"
        f"{time_info}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── ÉTAPE 4 : Choisir la prédiction ───────────────────────────────────
    st.markdown(
        "<div style='background:rgba(0,212,255,0.07);border-left:3px solid #00d4ff;"
        "border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;'>"
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

    # Alerte : marché déjà expiré pour ce match en live
    if prediction != "—":
        _exp, _reason = _market_is_expired(selected_match, market, prediction)
        if _exp:
            st.markdown(
                f"<div style='background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.45);"
                f"border-radius:10px;padding:10px 14px;margin:8px 0;'>"
                f"<b style='color:#ef4444;'>🚫 Marché invalide</b><br>"
                f"<span style='color:#fca5a5;font-size:0.83rem;'>{_reason}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Bouton Ajouter au ticket ──────────────────────────────────────────
    st.markdown("<div style='margin-top:10px;'>", unsafe_allow_html=True)
    if st.button("➕ Ajouter cette sélection au ticket", use_container_width=True, type="secondary"):
        if prediction == "—":
            st.warning("Prédiction invalide pour ce marché.")
        else:
            expired, exp_reason = _market_is_expired(selected_match, market, prediction)
            if expired:
                st.error(f"🚫 Sélection refusée — {exp_reason}")
            elif any(
                s["fixture_id"] == selected_match.get("fixture_id") and s["market"] == market
                for s in st.session_state.bet_selections
            ):
                st.warning(f"Ce marché ({market}) est déjà dans votre ticket pour ce match.")
            elif len(st.session_state.bet_selections) >= 8:
                st.warning("Maximum 8 sélections par ticket.")
            else:
                st.session_state.bet_selections.append({
                    "fixture_id":  selected_match.get("fixture_id"),
                    "home_team":   selected_match.get("home_team", ""),
                    "away_team":   selected_match.get("away_team", ""),
                    "market":      market,
                    "prediction":  prediction,
                    "kick_off":    (selected_match.get("kick_off")
                                   or selected_match.get("start_datetime_local")
                                   or selected_match.get("fixture_date", "")),
                    "live_minute": int(selected_match.get("minute", 0) or 0),
                    "odds":        float(selected_match.get("odds", 1.0) or 1.0),
                })
                st.success(
                    f"✓ Ajouté : {selected_match.get('home_team')} vs "
                    f"{selected_match.get('away_team')} — {market} → {prediction}"
                )
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Récapitulatif du ticket en cours ──────────────────────────────────
    st.markdown("---")
    _render_ticket_recap(api)


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
    
    # Stocker l'API en session pour le Smart Cashout
    st.session_state.current_api = api
    
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
        f"<div style='flex:1;'>"
        f"<div style='font-weight:700;font-size:0.95rem;'>Mes Points</div>"
        f"<div style='color:#888;font-size:0.8rem;'>Mise min : 5 ⭐ &nbsp;|&nbsp; Recharge : +10 ⭐ toutes les 5h</div>"
    )
    if refill_label:
        pts_html += (
            f"<div style='color:#f59e0b;font-size:0.78rem;margin-top:2px;'>"
            f"⏰ Recharge automatique dans <b>{refill_label}</b></div>"
        )
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



    # ── Ouverture directe ticket si venu du badge flottant ──────────────────
    open_ticket_direct = st.session_state.pop("paris_open_ticket", False)
    if open_ticket_direct and st.session_state.get("bet_selections"):
        nb_sel = len(st.session_state["bet_selections"])
        st.markdown(
            f"<div style='background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.35);"
            f"border-radius:12px;padding:14px 18px;margin-bottom:16px;display:flex;"
            f"align-items:center;gap:12px;'>"
            f"<span style='font-size:1.5rem;'>🎰</span>"
            f"<div><div style='font-weight:800;color:#f59e0b;'>Votre sélection — {nb_sel} événement(s)</div>"
            f"<div style='font-size:0.82rem;color:#9ca3af;'>Choisissez votre mise et validez votre ticket ci-dessous</div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
        _render_ticket_recap(api)
        st.markdown("---")

    # ── Tabs ────────────────────────────────────────────────────────────────
    tab_labels = ["🎟️ Créer Ticket", "🟡 Actifs", "✅ Terminés", "📜 Historique"]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        if not info["can_bet"]:
            has_active = info.get("has_active_ticket", False)
            eligible   = info.get("eligible_refill", False)
            refill_secs = info.get("refill_in_seconds", 0)
            total_secs  = 5 * 3600
            elapsed_secs = max(0, total_secs - refill_secs)
            pct_refill   = min(100, int(elapsed_secs / total_secs * 100))
            h_left = int(refill_secs // 3600)
            m_left = int((refill_secs % 3600) // 60)
            s_left = int(refill_secs % 60)
            countdown_str = f"{h_left}h {m_left:02d}m {s_left:02d}s"

            if has_active:
                # Cas : points = 0 mais ticket(s) actif(s) → recharge bloquée
                st.markdown(
                    f"<div style='background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.30);"
                    f"border-radius:16px;padding:24px;text-align:center;margin:8px 0 20px;'>"
                    f"<div style='font-size:2.5rem;margin-bottom:8px;'>🔒</div>"
                    f"<div style='font-size:1.1rem;font-weight:800;color:#fca5a5;margin-bottom:6px;'>"
                    f"Solde épuisé</div>"
                    f"<div style='font-size:0.88rem;color:#9ca3af;margin-bottom:12px;'>"
                    f"Vous avez <b style='color:#fff;'>{pts} ⭐</b> — mise minimum : "
                    f"<b style='color:#f59e0b;'>5 ⭐</b>.</div>"
                    f"<div style='background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);"
                    f"border-radius:12px;padding:14px;'>"
                    f"<div style='font-size:0.82rem;color:#f87171;font-weight:700;margin-bottom:4px;'>"
                    f"⚠️ Recharge automatique indisponible</div>"
                    f"<div style='font-size:0.80rem;color:#9ca3af;'>"
                    f"Vous avez encore <b style='color:#fff;'>des tickets actifs</b> en cours.<br>"
                    f"La recharge de <b style='color:#f59e0b;'>+10 ⭐</b> est accordée uniquement "
                    f"quand le solde est à <b>0 ⭐</b> et qu'aucun ticket n'est placé."
                    f"</div></div></div>",
                    unsafe_allow_html=True,
                )
            else:
                # Cas : points = 0 sans ticket actif → countdown recharge
                st.markdown(
                    f"<div style='background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.30);"
                    f"border-radius:16px;padding:24px;text-align:center;margin:8px 0 20px;'>"
                    f"<div style='font-size:2.5rem;margin-bottom:8px;'>⭐</div>"
                    f"<div style='font-size:1.1rem;font-weight:800;color:#fca5a5;margin-bottom:6px;'>"
                    f"Solde à zéro</div>"
                    f"<div style='font-size:0.88rem;color:#9ca3af;margin-bottom:16px;'>"
                    f"Le système va vous recharger automatiquement <b style='color:#f59e0b;'>+10 ⭐ gratuits</b>."
                    f"</div>"
                    f"<div style='background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);"
                    f"border-radius:12px;padding:16px;margin-bottom:16px;'>"
                    f"<div style='font-size:0.78rem;color:#9ca3af;margin-bottom:4px;'>Recharge dans</div>"
                    f"<div style='font-size:2rem;font-weight:900;color:#f59e0b;letter-spacing:2px;'>"
                    f"{countdown_str}</div>"
                    f"<div style='font-size:0.75rem;color:#6b7280;margin-top:4px;'>"
                    f"→ +10 ⭐ offerts automatiquement</div>"
                    f"</div>"
                    f"<div style='margin:0 auto;max-width:320px;'>"
                    f"<div style='display:flex;justify-content:space-between;font-size:0.70rem;"
                    f"color:#6b7280;margin-bottom:4px;'>"
                    f"<span>Progression</span><span>{pct_refill}%</span></div>"
                    f"<div style='height:8px;background:rgba(255,255,255,0.07);border-radius:4px;overflow:hidden;'>"
                    f"<div style='width:{pct_refill}%;height:100%;background:linear-gradient(90deg,#f59e0b,#fbbf24);"
                    f"border-radius:4px;'></div>"
                    f"</div></div></div>",
                    unsafe_allow_html=True,
                )
        else:
            _render_create_ticket(live_matches, future_matches, api)

    with tabs[1]:
        tickets_active = get_user_tickets(DEFAULT_USER_ID, status="ACTIVE")
        if not tickets_active:
            st.info("Aucun ticket actif.")
        else:
            # Construire live_ctx : fixture_id → {minute, home_score, away_score, kick_off}
            live_ctx: Dict[int, Dict] = {}
            for lm in live_matches:
                fid = lm.get("fixture_id")
                if fid:
                    live_ctx[int(fid)] = {
                        "minute":     lm.get("minute") or lm.get("elapsed"),
                        "home_score": lm.get("home_score"),
                        "away_score": lm.get("away_score"),
                        "kick_off":   lm.get("kick_off", ""),
                    }
            st.caption(f"� {len(tickets_active)} ticket(s) en cours · {len(live_ctx)} match(s) live suivis")
            for t in tickets_active:
                _render_ticket(t, live_ctx=live_ctx)

    with tabs[2]:
        tickets_done = [
            t for t in get_user_tickets(DEFAULT_USER_ID)
            if t["ticket_status"] in ("WON", "LOST", "SOLD")
        ]
        if not tickets_done:
            st.info("Aucun ticket terminé.")
        else:
            won  = [t for t in tickets_done if t["ticket_status"] == "WON"]
            lost = [t for t in tickets_done if t["ticket_status"] == "LOST"]
            sold = [t for t in tickets_done if t["ticket_status"] == "SOLD"]
            col1, col2, col3 = st.columns(3)
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
            with col3:
                st.markdown(
                    f"<div style='text-align:center;background:rgba(167,139,250,0.1);"
                    f"border-radius:10px;padding:10px;'>"
                    f"<div style='font-size:1.4rem;font-weight:800;color:#a78bfa;'>{len(sold)}</div>"
                    f"<div style='font-size:0.8rem;color:#aaa;'>Vendus</div></div>",
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
            
            # Bouton pour supprimer tous les tickets terminés
            finished_tickets = [t for t in all_tickets if t["ticket_status"] in ["WON", "LOST", "SOLD"]]
            if finished_tickets:
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("🗑️ Supprimer tous les tickets terminés", use_container_width=True):
                        if st.checkbox("⚠️ Confirmer la suppression de tous les tickets terminés ?", key="confirm_delete_all"):
                            deleted_count = 0
                            for ticket in finished_tickets:
                                if delete_ticket(ticket['ticket_id'], DEFAULT_USER_ID):
                                    deleted_count += 1
                            st.success(f"✅ {deleted_count} ticket(s) supprimé(s) avec succès")
                            st.rerun()

            # Afficher chaque ticket avec bouton de suppression
            for ticket in all_tickets:
                ticket_id = ticket['ticket_id']
                status = ticket['ticket_status']
                created_date = ticket.get('created_at', '')[:10]
                
                # Déterminer la couleur du statut
                status_colors = {
                    "WON": ("🟢 GAGNÉ", "#22c55e"),
                    "LOST": ("🔴 PERDU", "#ef4444"),
                    "ACTIVE": ("🟡 ACTIF", "#f59e0b"),
                    "SOLD": ("💰 VENDU", "#a78bfa")
                }
                status_text, status_color = status_colors.get(status, ("❓ " + status, "#6b7280"))
                
                # Afficher la carte du ticket
                col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**#{ticket_id}**")
                    
                with col2:
                    st.markdown(f"*{created_date}*")
                    
                with col3:
                    st.markdown(f"<span style='color:{status_color};font-weight:600;'>{status_text}</span>", unsafe_allow_html=True)
                    
                with col4:
                    st.markdown(f"{ticket['points_used']} ⭐")
                    
                with col5:
                    if ticket['reward_points'] > 0:
                        st.markdown(f"+{ticket['reward_points']} ⭐")
                    else:
                        st.markdown("—")
                        
                with col6:
                    # Bouton de suppression (uniquement pour les tickets terminés)
                    if status in ["WON", "LOST", "SOLD"]:
                        if st.button("🗑️", key=f"delete_{ticket_id}", help="Supprimer ce ticket"):
                            if delete_ticket(ticket_id, DEFAULT_USER_ID):
                                st.success(f"✅ Ticket #{ticket_id} supprimé")
                                st.rerun()
                            else:
                                st.error(f"❌ Erreur lors de la suppression du ticket #{ticket_id}")
                    else:
                        st.markdown("*—*")
