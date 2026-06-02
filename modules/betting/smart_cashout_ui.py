import streamlit as st
import logging
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def render_smart_cashout_card(ticket_id: int, engine) -> Dict[str, Any]:
    """Affiche la carte complète du Smart Cashout."""
    try:
        # Calculer les données du cashout
        cashout_data = engine.calculate_smart_cashout(ticket_id)
        
        if not cashout_data.get("available"):
            st.markdown(f"""
            <div style='background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);
                        border-radius:16px;padding:20px;text-align:center;'>
                <div style='color:#ef4444;font-size:1.1rem;font-weight:700;'>❌ Cashout Indisponible</div>
                <div style='color:#fca5a5;font-size:0.9rem;margin-top:4px;'>{cashout_data.get('reason', 'Erreur inconnue')}</div>
            </div>
            """, unsafe_allow_html=True)
            return cashout_data
        
        # Afficher l'en-tête
        _render_cashout_header(cashout_data)
        
        # Afficher les indicateurs
        _render_indicators(cashout_data)
        
        # Afficher l'offre principale
        _render_cashout_offer(cashout_data)
        
        # Afficher l'analyse détaillée
        _render_detailed_analysis(cashout_data)
        
        # Afficher la recommandation
        _render_recommendation(cashout_data)
        
        return cashout_data
        
    except Exception as e:
        logger.error(f"Erreur render_smart_cashout_card: {e}")
        st.error("❌ Erreur lors de l'affichage du Smart Cashout")
        return {"available": False, "reason": "Erreur affichage"}

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

def _render_indicators(data: Dict[str, Any]) -> None:
    """Affiche les indicateurs de risque, confiance et progression."""
    risk_level = data.get("risk_level", "MOYEN")
    risk_score = data.get("risk_score", 0.5)
    confidence = data.get("confidence", 50)
    progress = data.get("progress", 0)
    validated = data.get("validated_events", 0)
    total = validated + data.get("remaining_events", 1)
    
    # Couleurs du risque
    risk_colors = {
        "FAIBLE": ("#22c55e", "🟢"),
        "MOYEN": ("#f59e0b", "🟡"),
        "ÉLEVÉ": ("#ef4444", "🔴")
    }
    risk_color, risk_icon = risk_colors.get(risk_level, ("#f59e0b", "🟡"))
    
    # Couleur de confiance
    if confidence >= 80:
        conf_color = "#22c55e"
        conf_label = "Élevée"
    elif confidence >= 60:
        conf_color = "#f59e0b"
        conf_label = "Moyenne"
    else:
        conf_color = "#ef4444"
        conf_label = "Faible"
    
    st.markdown(f"""
    <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;'>
        <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);
                    border-radius:12px;padding:16px;text-align:center;'>
            <div style='font-size:1.2rem;margin-bottom:4px;'>{risk_icon}</div>
            <div style='font-size:0.8rem;color:#9ca3af;margin-bottom:2px;'>Risque</div>
            <div style='font-size:0.9rem;font-weight:700;color:{risk_color};'>{risk_level}</div>
            <div style='font-size:0.75rem;color:#6b7280;'>Score: {risk_score:.2f}</div>
        </div>
        
        <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);
                    border-radius:12px;padding:16px;text-align:center;'>
            <div style='font-size:1.2rem;margin-bottom:4px;'>📊</div>
            <div style='font-size:0.8rem;color:#9ca3af;margin-bottom:2px;'>Confiance</div>
            <div style='font-size:0.9rem;font-weight:700;color:{conf_color};'>{conf_label}</div>
            <div style='font-size:0.75rem;color:#6b7280;'>{confidence}%</div>
        </div>
        
        <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);
                    border-radius:12px;padding:16px;text-align:center;'>
            <div style='font-size:1.2rem;margin-bottom:4px;'>📈</div>
            <div style='font-size:0.8rem;color:#9ca3af;margin-bottom:2px;'>Progression</div>
            <div style='font-size:0.9rem;font-weight:700;'>{progress:.0f}%</div>
            <div style='font-size:0.75rem;color:#6b7280;'>{validated}/{total}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def _render_cashout_offer(data: Dict[str, Any]) -> None:
    """Affiche l'offre principale de cashout."""
    offer = data["cashout_offer"]
    potential = data["potential_gain"]
    stake = data["stake"]
    percentage = data["cashout_percentage"]
    
    # Calculer la différence
    diff = offer - stake
    diff_percentage = ((offer - stake) / stake) * 100
    
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
                            <div style='font-weight:600;color:#fff;'>{fixture_id}</div>
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

def render_auto_refresh_cashout(ticket_id: int, engine, refresh_interval: int = 15) -> Dict[str, Any]:
    """
    Affiche le Smart Cashout avec rafraîchissement automatique.
    DÉSACTIVÉ pour éviter les ventes involontaires.
    """
    # Afficher la carte initiale
    cashout_data = render_smart_cashout_card(ticket_id, engine)
    
    if not cashout_data.get("available"):
        return cashout_data
    
    # DÉSACTIVÉ : Le rafraîchissement automatique cause des ventes involontaires
    # On affiche juste un message manuel à la place
    st.markdown(f"""
    <div style='text-align:center;margin-top:16px;'>
        <div style='font-size:0.9rem;color:#9ca3af;'>🔄 Mise à jour manuelle</div>
        <div style='font-size:0.8rem;color:#6b7280;'>Actualisez la page pour mettre à jour</div>
    </div>
    """, unsafe_allow_html=True)
    
    return cashout_data

def render_cashout_button(ticket_id: int, cashout_data: Dict[str, Any]) -> bool:
    """Affiche le bouton de vente intelligent avec bouton Streamlit standard.
    Retourne True seulement si une vente confirmée a eu lieu."""
    if not cashout_data.get("available") or not cashout_data.get("sale_allowed", True):
        reason = cashout_data.get("reason", "Vente bloquée : prédiction non favorable.")
        st.markdown(f"""
        <div style='background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);
                    border-radius:10px;padding:12px;text-align:center;margin-top:10px;'>
            <div style='color:#ef4444;font-weight:800;'>🚫 Vente bloquée</div>
            <div style='color:#fca5a5;font-size:0.82rem;margin-top:3px;'>{reason}</div>
        </div>
        """, unsafe_allow_html=True)
        return False
    
    rec_type = cashout_data.get("recommendation_type", "NEUTRAL")
    offer = cashout_data.get("cashout_offer", 0)
    
    # Style selon le type de recommandation
    button_styles = {
        "SELL_NOW": ("🔥 Vendre Maintenant", "primary"),
        "KEEP_TICKET": ("✅ Conserver", "secondary"),
        "CONSIDER_SELL": ("⚠️ Vendre", "secondary"),
        "WAIT_BETTER": ("📉 Attendre", "secondary"),
        "NEUTRAL": ("🤔 Analyser", "secondary"),
        "ERROR": ("❌ Erreur", "secondary")
    }
    
    text, button_type = button_styles.get(rec_type, ("📊 Vendre", "secondary"))
    
    # Utiliser un bouton Streamlit standard pour éviter les conflits JavaScript
    if st.button(f"{text} {offer} ⭐", 
                key=f"smart_cashout_sell_{ticket_id}", 
                type=button_type, 
                use_container_width=True,
                help=f"Vendre le ticket #{ticket_id} pour {offer} ⭐"):
        
        # Confirmer avant de vendre
        if st.session_state.get(f"confirm_sell_{ticket_id}", False):
            # Effectuer la vente
            try:
                from modules.betting.points_manager import credit_points
                from modules.betting.ticket_storage import DEFAULT_USER_ID, get_ticket, get_ticket_items, sell_ticket

                ticket = get_ticket(ticket_id)
                items = get_ticket_items(ticket_id)
                nb_won = sum(1 for item in items if item.get("result") == "WON")
                nb_lost = sum(1 for item in items if item.get("result") == "LOST")
                if not ticket or ticket.get("ticket_status") != "ACTIVE":
                    res = {"success": False, "message": "Ticket non actif."}
                elif nb_lost > 0:
                    res = {"success": False, "message": "Vente bloquée : une prédiction du ticket est perdue."}
                elif nb_won <= 0:
                    res = {"success": False, "message": "Vente bloquée : aucune prédiction favorable validée pour le moment."}
                else:
                    sell_price = max(1, int(offer))
                    sell_ticket(ticket_id, sell_price)
                    credit_points(DEFAULT_USER_ID, sell_price)
                    res = {"success": True, "message": f"Ticket #{ticket_id} vendu pour {sell_price} ⭐."}
                
                if res.get("success"):
                    st.success(f"✅ Ticket #{ticket_id} vendu pour {offer} ⭐ !")
                    st.balloons()
                    # Effacer la confirmation
                    if f"confirm_sell_{ticket_id}" in st.session_state:
                        del st.session_state[f"confirm_sell_{ticket_id}"]
                    st.rerun()
                    return True  # Vente confirmée effectuée
                else:
                    st.error(f"❌ Erreur lors de la vente: {res.get('message', 'Erreur inconnue')}")
            except Exception as e:
                st.error(f"❌ Erreur système lors de la vente: {e}")
        else:
            # Demander confirmation
            st.session_state[f"confirm_sell_{ticket_id}"] = True
            st.warning(f"⚠️ Confirmez la vente du ticket #{ticket_id} pour {offer} ⭐")
            st.rerun()
    
    return False  # Pas de vente confirmée
