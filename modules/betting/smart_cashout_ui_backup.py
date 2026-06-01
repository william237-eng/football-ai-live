"""
smart_cashout_ui.py
==================
Interface utilisateur dynamique pour le Smart Cashout.
Affichage en temps réel des offres, risques et recommandations.
"""
from __future__ import annotations

import streamlit as st
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from modules.betting.smart_cashout import SmartCashoutEngine


def render_smart_cashout_card(ticket_id: int, engine: SmartCashoutEngine) -> Dict[str, Any]:
    """
    Affiche une carte complète de Smart Cashout pour un ticket.
    """
    # Calculer l'offre de cashout
    cashout_data = engine.calculate_smart_cashout(ticket_id)
    
    if not cashout_data.get("available"):
        st.markdown(f"""
        <div style='background:rgba(107,114,128,0.1);border:1px solid rgba(107,114,128,0.3);
                    border-radius:12px;padding:16px;text-align:center;'>
            <div style='font-size:1.2rem;margin-bottom:8px;'>🚫 Cashout Indisponible</div>
            <div style='color:#9ca3af;font-size:0.85rem;'>{cashout_data.get('reason', 'Raison inconnue')}</div>
        </div>
        """, unsafe_allow_html=True)
        return cashout_data
    
    # Afficher l'en-tête
    _render_cashout_header(cashout_data)
    
    # Afficher les indicateurs principaux
    col1, col2, col3 = st.columns(3)
    
    with col1:
        _render_risk_indicator(cashout_data)
    
    with col2:
        _render_confidence_indicator(cashout_data)
    
    with col3:
        _render_progress_indicator(cashout_data)
    
    # Afficher l'offre principale
    st.markdown("---")
    _render_main_offer(cashout_data)
    
    # Afficher les détails
    with st.expander("📊 Analyse détaillée", expanded=False):
        _render_detailed_analysis(cashout_data)
    
    # Afficher la recommandation
    _render_recommendation(cashout_data)
    
    return cashout_data


def _render_cashout_header(data: Dict[str, Any]) -> None:
    """Affiche l'en-tête de la carte Smart Cashout."""
    st.markdown(f"""
    <div style='background:linear-gradient(135deg, rgba(0,212,255,0.1), rgba(147,51,234,0.1));
                border:1px solid rgba(0,212,255,0.3);border-radius:16px;padding:20px;margin-bottom:16px;'>
        <div style='display:flex;align-items:center;gap:12px;margin-bottom:8px;'>
            <span style='font-size:1.8rem;'>🎯</span>
            <div>
                <div style='font-size:1.4rem;font-weight:900;color:#00d4ff;'>Vente Intelligente</div>
                <div style='color:#9ca3af;font-size:0.85rem;'>Ticket #{data['ticket_id']} • Mis à jour en temps réel</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_risk_indicator(data: Dict[str, Any]) -> None:
    """Affiche l'indicateur de risque."""
    risk_level = data["risk_level"]
    risk_score = data["risk_score"]
    
    colors = {
        "FAIBLE": ("#22c55e", "🟢"),
        "MOYEN": ("#f59e0b", "🟡"),
        "ÉLEVÉ": ("#ef4444", "🔴")
    }
    
    color, icon = colors.get(risk_level, ("#6b7280", "⚪"))
    
    st.markdown(f"""
    <div style='background:rgba(255,255,255,0.05);border:1px solid {color}33;
                border-radius:12px;padding:16px;text-align:center;'>
        <div style='font-size:1.5rem;margin-bottom:4px;'>{icon}</div>
        <div style='font-size:0.85rem;color:#9ca3af;margin-bottom:8px;'>Risque</div>
        <div style='font-size:1.1rem;font-weight:700;color:{color};'>{risk_level}</div>
        <div style='font-size:0.75rem;color:#6b7280;'>Score: {risk_score:.2f}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_confidence_indicator(data: Dict[str, Any]) -> None:
    """Affiche l'indicateur de confiance."""
    confidence = data["confidence"]
    
    # Couleur selon la confiance
    if confidence >= 80:
        color = "#22c55e"
        label = "Élevée"
    elif confidence >= 60:
        color = "#f59e0b"
        label = "Moyenne"
    else:
        color = "#ef4444"
        label = "Faible"
    
    st.markdown(f"""
    <div style='background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
                border-radius:12px;padding:16px;text-align:center;'>
        <div style='font-size:1.5rem;margin-bottom:4px;'>📊</div>
        <div style='font-size:0.85rem;color:#9ca3af;margin-bottom:8px;'>Confiance</div>
        <div style='font-size:1.1rem;font-weight:700;color:{color};'>{confidence:.0f}%</div>
        <div style='font-size:0.75rem;color:#6b7280;'>{label}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_progress_indicator(data: Dict[str, Any]) -> None:
    """Affiche l'indicateur de progression."""
    progress = data["progress"]
    validated = data["validated_events"]
    remaining = data["remaining_events"]
    
    st.markdown(f"""
    <div style='background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
                border-radius:12px;padding:16px;text-align:center;'>
        <div style='font-size:1.5rem;margin-bottom:4px;'>📈</div>
        <div style='font-size:0.85rem;color:#9ca3af;margin-bottom:8px;'>Progression</div>
        <div style='font-size:1.1rem;font-weight:700;'>{progress:.0f}%</div>
        <div style='font-size:0.75rem;color:#6b7280;'>{validated}/{validated + remaining}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_main_offer(data: Dict[str, Any]) -> None:
    """Affiche l'offre principale de cashout."""
    offer = data["cashout_offer"]
    potential = data["potential_gain"]
    percentage = data["cashout_percentage"]
    
    # Calculer la différence
    diff = offer - data["stake"]
    diff_percentage = ((offer - data["stake"]) / data["stake"]) * 100
    
    # Sécurisation du gain
    secured_percentage = (offer / potential) * 100
    
    # Déterminer la couleur du bénéfice
    benefit_color = "#22c55e" if diff > 0 else "#ef4444"
    
    st.markdown(f"""
    <div style='background:linear-gradient(135deg, rgba(34,197,94,0.1), rgba(16,185,129,0.1));
                border:2px solid rgba(34,197,94,0.3);border-radius:16px;padding:20px;'>
        <div style='text-align:center;margin-bottom:16px;'>
            <div style='font-size:0.9rem;color:#22c55e;margin-bottom:4px;'>Gain potentiel</div>
            <div style='font-size:1.8rem;font-weight:900;color:#fff;'>{potential} ⭐</div>
        </div>
        
        <div style='text-align:center;margin-bottom:16px;'>
            <div style='font-size:0.9rem;color:#f59e0b;margin-bottom:4px;'>Vente proposée</div>
            <div style='font-size:2.2rem;font-weight:900;color:#f59e0b;'>{offer} ⭐</div>
            <div style='font-size:0.85rem;color:#9ca3af;'>{percentage}% du gain potentiel</div>
        </div>
        
        <div style='display:flex;justify-content:space-between;align-items:center;'>
            <div>
                <div style='font-size:0.8rem;color:#9ca3af;'>Bénéfice</div>
                <div style='font-size:1.1rem;font-weight:700;color:{benefit_color};'>
                    {'+' if diff > 0 else ''}{diff} ⭐ ({diff_percentage:+.0f}%)
                </div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:0.8rem;color:#9ca3af;'>Sécurisé</div>
                <div style='font-size:1.1rem;font-weight:700;color:#22c55e;'>{secured_percentage:.0f}%</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_detailed_analysis(data: Dict[str, Any]) -> None:
    """Affiche l'analyse détaillée."""
    try:
        live_analysis = data.get("live_analysis", {})
    
        st.markdown("#### 📊 Analyse des Risques par Match")
    
    risks = live_analysis.get("individual_risks", [])
    if risks:
        for i, risk in enumerate(risks):
            # Récupération sécurisée des données avec valeurs par défaut
            fixture_id = risk.get("fixture_id", f"Match #{i+1}")
            score = risk.get("current_score", "N/A")
            minute = risk.get("minute", 0)
            risk_score = risk.get("risk_score", 0.5)
            
            # Couleur du risque
            if risk_score < 0.3:
                risk_color = "#22c55e"
                risk_label = "Faible"
            elif risk_score < 0.6:
                risk_color = "#f59e0b"
                risk_label = "Moyen"
            else:
                risk_color = "#ef4444"
                risk_label = "Élevé"
            
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);
                        border-left:4px solid {risk_color};border-radius:8px;padding:12px;margin-bottom:8px;'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div>
                        <div style='font-weight:600;color:#fff;'>Match #{fixture_id}</div>
                        <div style='font-size:0.85rem;color:#9ca3af;'>Score: {score} • {minute}'</div>
                    </div>
                    <div style='text-align:right;'>
                        <div style='font-size:0.85rem;color:#9ca3af;'>Risque</div>
                        <div style='font-weight:700;color:{risk_color};'>{risk_label}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Aucune donnée live disponible")
    
    # Facteurs de calcul
    st.markdown("#### 🔧 Facteurs de Calcul")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.03);border-radius:8px;padding:12px;'>
            <div style='font-size:0.85rem;color:#9ca3af;margin-bottom:4px;'>Facteur Progression</div>
            <div style='font-size:1.1rem;font-weight:700;'>{data.get('progress_factor', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.03);border-radius:8px;padding:12px;margin-top:8px;'>
            <div style='font-size:0.85rem;color:#9ca3af;margin-bottom:4px;'>Facteur Temps</div>
            <div style='font-size:1.1rem;font-weight:700;'>{data.get('time_factor', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.03);border-radius:8px;padding:12px;'>
            <div style='font-size:0.85rem;color:#9ca3af;margin-bottom:4px;'>Probabilité Live</div>
            <div style='font-size:1.1rem;font-weight:700;'>{data.get('live_probability', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.03);border-radius:8px;padding:12px;margin-top:8px;'>
            <div style='font-size:0.85rem;color:#9ca3af;margin-bottom:4px;'>Score de Risque</div>
            <div style='font-size:1.1rem;font-weight:700;'>{data.get('risk_score', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        # En cas d'erreur dans l'analyse, afficher un message simple
        st.markdown("""
        <div style='background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);
                    border-radius:8px;padding:16px;text-align:center;'>
            <div style='color:#ef4444;font-size:0.9rem;'>⚠️ Analyse temporairement indisponible</div>
            <div style='color:#fca5a5;font-size:0.8rem;margin-top:4px;'>Veuillez réessayer plus tard</div>
        </div>
        """, unsafe_allow_html=True)


def _render_recommendation(data: Dict[str, Any]) -> None:
    """Affiche la recommandation intelligente."""
    try:
        recommendation = data.get("recommendation", "📊 Analyse en cours")
        rec_type = data.get("recommendation_type", "NEUTRAL")
    
    # Style selon le type de recommandation
    styles = {
        "SELL_NOW": ("#ef4444", "🔥", "Vendre Maintenant"),
        "KEEP_TICKET": ("#22c55e", "✅", "Conserver le Ticket"),
        "CONSIDER_SELL": ("#f59e0b", "⚠️", "Considérer la Vente"),
        "WAIT_BETTER": ("#3b82f6", "📉", "Attendre une Meilleure Offre"),
        "NEUTRAL": ("#6b7280", "🤔", "Analyse en Cours"),
        "ERROR": ("#ef4444", "❌", "Erreur d'Analyse")
    }
    
    color, icon, title = styles.get(rec_type, ("#6b7280", "❓", "Recommandation"))
    
    st.markdown(f"""
    <div style='background:{color}15;border:2px solid {color}40;border-radius:16px;padding:20px;margin-top:16px;'>
        <div style='display:flex;align-items:center;gap:12px;margin-bottom:8px;'>
            <span style='font-size:1.5rem;'>{icon}</span>
            <div style='font-size:1.1rem;font-weight:700;color:{color};'>{title}</div>
        </div>
        <div style='color:#fff;font-size:1rem;'>{recommendation}</div>
    </div>
    """, unsafe_allow_html=True)
        
    except Exception as e:
        # En cas d'erreur, afficher une recommandation neutre
        st.markdown("""
        <div style='background:rgba(107,114,128,0.1);border:1px solid rgba(107,114,128,0.3);
                    border-radius:16px;padding:20px;margin-top:16px;'>
            <div style='display:flex;align-items:center;gap:12px;margin-bottom:8px;'>
                <span style='font-size:1.5rem;'>🤔</span>
                <div style='font-size:1.1rem;font-weight:700;color:#6b7280;'>Analyse en Cours</div>
            </div>
            <div style='color:#fff;font-size:1rem;'>📊 Analyse en cours</div>
        </div>
        """, unsafe_allow_html=True)


def render_auto_refresh_cashout(ticket_id: int, engine: SmartCashoutEngine, refresh_interval: int = 15) -> None:
    """
    Affiche le Smart Cashout avec rafraîchissement automatique.
    """
    # Afficher la carte initiale
    cashout_data = render_smart_cashout_card(ticket_id, engine)
    
    if not cashout_data.get("available"):
        return
    
    # Script de rafraîchissement automatique
    refresh_script = f"""
    <script>
        let cashoutInterval = {refresh_interval * 1000};
        let countdown = cashoutInterval / 1000;
        
        function updateCashoutCountdown() {{
            countdown--;
            if (countdown <= 0) {{
                countdown = {refresh_interval};
                // Rafraîchir uniquement la section cashout
                if (typeof window.location !== 'undefined') {{
                    window.location.reload();
                }}
            }}
            
            // Mettre à jour le compteur
            const countdownEl = document.getElementById('cashout-countdown');
            if (countdownEl) {{
                countdownEl.textContent = countdown + 's';
            }}
        }}
        
        // Démarrer le compte à rebours
        setInterval(updateCashoutCountdown, 1000);
        
        // Afficher le compteur initial
        document.addEventListener('DOMContentLoaded', function() {{
            const countdownEl = document.getElementById('cashout-countdown');
            if (countdownEl) {{
                countdownEl.textContent = countdown + 's';
            }}
        }});
    </script>
    """
    
    # Afficher les informations de rafraîchissement
    st.markdown(f"""
    <div style='background:rgba(255,255,255,0.03);border-radius:8px;padding:12px;margin-top:16px;'>
        <div style='display:flex;justify-content:space-between;align-items:center;'>
            <div style='display:flex;align-items:center;gap:8px;'>
                <span style='color:#9ca3af;'>🔄</span>
                <span style='color:#9ca3af;font-size:0.85rem;'>Mise à jour automatique</span>
            </div>
            <div style='color:#f59e0b;font-size:0.85rem;'>
                Prochaine mise à jour : <span id='cashout-countdown'>{refresh_interval}s</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Injecter le script
    st.components.v1.html(refresh_script, height=0)


def render_cashout_button(ticket_id: int, cashout_data: Dict[str, Any]) -> bool:
    """
    Affiche le bouton de vente et retourne True si cliqué.
    """
    if not cashout_data.get("available"):
        return False
    
    offer = cashout_data["cashout_offer"]
    rec_type = cashout_data["recommendation_type"]
    
    # Couleur du bouton selon la recommandation
    button_types = {
        "SELL_NOW": ("secondary", "🔥 Vendre Maintenant"),
        "KEEP_TICKET": ("primary", "💰 Vendre Malgré Tout"),
        "CONSIDER_SELL": ("secondary", "⚠️ Vendre"),
        "WAIT_BETTER": ("primary", "📉 Vendre Maintenant"),
        "NEUTRAL": ("secondary", "💰 Vendre le Ticket"),
        "ERROR": ("secondary", "💰 Vendre")
    }
    
    button_type, button_text = button_types.get(rec_type, ("secondary", "💰 Vendre le Ticket"))
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button(
            f"{button_text} - {offer} ⭐",
            key=f"smart_cashout_{ticket_id}",
            use_container_width=True,
            type=button_type
        ):
            return True
    
    return False
