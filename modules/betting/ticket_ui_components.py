"""
ticket_ui_components.py
=======================
Composants d'interface utilisateur pour l'affichage des tickets
avec progression, statuts visuels et boutons de vente conditionnels.
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.betting.ticket_storage import get_ticket, get_ticket_items, DEFAULT_USER_ID
from modules.betting.live_ticket_processor import LiveTicketProcessor


def get_status_emoji(status: str) -> str:
    """Retourne l'emoji correspondant au statut."""
    status_emojis = {
        "ACTIVE": "🟡",
        "WON": "🟢", 
        "LOST": "🔴",
        "SOLD": "💰",
        "PENDING": "⏳"
    }
    return status_emojis.get(status, "❓")


def get_status_display(status: str) -> str:
    """Retourne le libellé d'affichage du statut."""
    status_labels = {
        "ACTIVE": "EN COURS",
        "WON": "GAGNÉ",
        "LOST": "PERDU", 
        "SOLD": "VENDU",
        "PENDING": "EN ATTENTE"
    }
    return status_labels.get(status, status.upper())


def render_progress_bar(validated: int, total: int) -> str:
    """Génère une barre de progression en texte."""
    if total == 0:
        return "░░░░░░░░░░"
        
    progress_percent = (validated / total) * 100
    filled_blocks = int((progress_percent / 100) * 10)
    empty_blocks = 10 - filled_blocks
    
    return "█" * filled_blocks + "░" * empty_blocks


def render_ticket_status_card(ticket_id: int, processor: Optional[LiveTicketProcessor] = None) -> Dict[str, Any]:
    """
    Affiche une carte de statut complète pour un ticket.
    Retourne les informations de traitement.
    """
    ticket = get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket introuvable")
        return {"error": "Ticket introuvable"}
        
    items = get_ticket_items(ticket_id)
    if not items:
        st.error("Ticket sans items")
        return {"error": "Ticket sans items"}
        
    # Compter les résultats
    won_count = sum(1 for item in items if item.get("result") == "WON")
    lost_count = sum(1 for item in items if item.get("result") == "LOST")
    pending_count = sum(1 for item in items if item.get("result") == "PENDING")
    total_items = len(items)
    validated_count = won_count + lost_count
    
    status = ticket.get("ticket_status", "ACTIVE")
    status_emoji = get_status_emoji(status)
    status_display = get_status_display(status)
    
    # Traitement automatique si processeur fourni
    processing_result = None
    if processor:
        try:
            processing_result = processor.process_single_ticket(ticket_id)
            if processing_result.get("success"):
                # Mettre à jour les compteurs après traitement
                status_update = processing_result.get("status_update", {})
                status = status_update.get("status", status)
                status_emoji = get_status_emoji(status)
                status_display = get_status_display(status)
                won_count = status_update.get("won_count", won_count)
                lost_count = status_update.get("lost_count", lost_count)
                pending_count = status_update.get("pending_count", pending_count)
                validated_count = status_update.get("validated_count", validated_count)
                
                # Afficher une notification si le ticket vient d'être gagné
                if status == "WON" and ticket.get("ticket_status") != "WON":
                    reward_info = processing_result.get("reward_info", {})
                    if reward_info:
                        st.success(f"🎉 **FÉLICITATIONS !** Ticket #{ticket_id} GAGNÉ ! **+{reward_info.get('reward_points', 0)} ⭐** ajoutés à votre solde !")
                        st.balloons()
        except Exception as e:
            st.warning(f"Erreur traitement automatique: {e}")
    
    # Afficher la carte de statut
    st.markdown("---")
    
    # En-tête avec statut
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.markdown(f"### {status_emoji}")
    with col2:
        st.markdown(f"### Ticket #{ticket_id}")
        st.markdown(f"**Statut : {status_emoji} {status_display}**")
    with col3:
        created_at = ticket.get("created_at", "")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                st.markdown(f"*Créé le {dt.strftime('%d/%m %H:%M')}*")
            except:
                pass
    
    # Progression
    progress_bar = render_progress_bar(validated_count, total_items)
    
    col_progress, col_count = st.columns([2, 1])
    with col_progress:
        st.markdown(f"**Progression :** {progress_bar}")
    with col_count:
        st.markdown(f"**{validated_count}/{total_items}** validés")
    
    # Détails des résultats
    col_won, col_lost, col_pending = st.columns(3)
    with col_won:
        st.markdown(f"🟢 **Gagnés :** {won_count}")
    with col_lost:
        st.markdown(f"🔴 **Perdus :** {lost_count}")
    with col_pending:
        st.markdown(f"⏳ **En attente :** {pending_count}")
    
    # Bouton de vente conditionnel
    sell_info = None
    if processor:
        sell_info = processor.can_sell_ticket(ticket_id)
    else:
        # Logique simple sans processeur
        sell_info = {
            "can_sell": status == "ACTIVE" and pending_count > 0,
            "reason": "Vente disponible" if status == "ACTIVE" else f"Ticket {status_display.lower()}",
            "status": status
        }
    
    if sell_info["can_sell"]:
        st.success(f"✅ {sell_info['reason']}")
        return {
            "ticket_id": ticket_id,
            "status": status,
            "can_sell": True,
            "sell_reason": sell_info["reason"],
            "processing_result": processing_result
        }
    else:
        st.warning(f"🚫 Vente indisponible : {sell_info['reason']}")
        return {
            "ticket_id": ticket_id,
            "status": status,
            "can_sell": False,
            "sell_reason": sell_info["reason"],
            "processing_result": processing_result
        }


def render_auto_refresh_section(refresh_interval: int = 30) -> bool:
    """
    Affiche une section de rafraîchissement automatique.
    Retourne True si l'utilisateur demande un rafraîchissement manuel.
    """
    st.markdown("---")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if st.button("🔄 Rafraîchir tickets", key="manual_refresh"):
            return True
            
    with col2:
        if st.button("💰 Mettre à jour solde", key="refresh_balance"):
            st.rerun()
            
    with col3:
        st.markdown(f"""
        <div style='text-align: center; padding: 8px;'>
            🕐 Auto-refresh {refresh_interval}s
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        # Timer visuel simple
        if "last_refresh" in st.session_state:
            last = st.session_state.last_refresh
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                seconds_since = int((now - last_dt).total_seconds())
                st.markdown(f"*Il y a {seconds_since}s*")
            except:
                pass
        else:
            st.markdown("*En attente...*")
    
    return False


def render_debug_logs(logs: List[str]) -> None:
    """Affiche les logs de debug dans un expander."""
    if not logs:
        return
        
    with st.expander("🔍 Logs de debug", expanded=False):
        for log in logs[-20:]:  # Afficher les 20 derniers logs
            st.code(log, language=None)


def create_auto_refresh_script(refresh_interval: int = 30) -> str:
    """
    Crée le JavaScript pour le rafraîchissement automatique.
    """
    return f"""
    <script>
        let refreshInterval = {refresh_interval * 1000};
        let countdown = refreshInterval / 1000;
        
        function updateCountdown() {{
            countdown--;
            if (countdown <= 0) {{
                countdown = {refresh_interval};
                // DÉSACTIVÉ : Rafraîchissement automatique cause des ventes involontaires
                // window.location.reload();
            }}
            
            // Mettre à jour l'affichage du compte à rebours
            const countdownEl = document.getElementById('refresh-countdown');
            if (countdownEl) {{
                countdownEl.textContent = countdown + 's';
            }}
        }}
        
        // Démarrer le compte à rebours
        setInterval(updateCountdown, 1000);
        
        // Afficher le compte à rebours initial
        document.addEventListener('DOMContentLoaded', function() {{
            const countdownEl = document.getElementById('refresh-countdown');
            if (countdownEl) {{
                countdownEl.textContent = countdown + 's';
            }}
        }});
    </script>
    """


def render_ticket_list_with_auto_refresh(
    tickets: List[Dict], 
    processor: LiveTicketProcessor,
    refresh_interval: int = 30
) -> List[Dict[str, Any]]:
    """
    Affiche une liste de tickets avec rafraîchissement automatique.
    Retourne les résultats de traitement.
    """
    # Section de rafraîchissement
    manual_refresh = render_auto_refresh_section(refresh_interval)
    
    # Script de rafraîchissement automatique
    auto_refresh_script = create_auto_refresh_script(refresh_interval)
    st.components.v1.html(auto_refresh_script, height=0)
    
    # Mettre à jour le timestamp de rafraîchissement
    st.session_state.last_refresh = datetime.now(timezone.utc).isoformat()
    
    results = []
    
    # Traiter et afficher chaque ticket
    for ticket in tickets:
        ticket_id = ticket["ticket_id"]
        
        # Traitement automatique
        try:
            if manual_refresh or True:  # Toujours traiter pour l'instant
                result = processor.process_single_ticket(ticket_id)
                results.append(result)
        except Exception as e:
            st.error(f"Erreur traitement ticket #{ticket_id}: {e}")
            results.append({
                "success": False,
                "ticket_id": ticket_id,
                "error": str(e)
            })
        
        # Afficher la carte du ticket
        render_ticket_status_card(ticket_id, processor)
    
    # Afficher les logs de debug si disponibles
    if hasattr(processor, 'debug_logs'):
        render_debug_logs(processor.debug_logs)
    
    return results
