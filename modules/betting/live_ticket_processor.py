"""
live_ticket_processor.py
========================
Système de traitement automatique des tickets en temps réel.
Validation automatique des événements terminés, mise à jour des statuts,
et désactivation de la vente pour les tickets clôturés.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from modules.betting.ticket_storage import (
    get_ticket, get_ticket_items, update_ticket_status, update_item_result,
    get_user_tickets, DEFAULT_USER_ID
)
from modules.betting.ticket_validator import check_item, is_finished
from modules.betting.reward_engine import compute_reward
from modules.betting.points_manager import credit_points

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes de statut
STATUS_PENDING = "PENDING"
STATUS_WON = "WON"
STATUS_LOST = "LOST"
STATUS_ACTIVE = "ACTIVE"

# Statuts de match terminés
FINISHED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO", "FINISHED"}

# Intervalles de vérification (secondes)
CHECK_INTERVAL = 30  # Vérifier toutes les 30 secondes


class LiveTicketProcessor:
    """Processeur de tickets en temps réel."""
    
    def __init__(self, api):
        self.api = api
        self.last_check = {}
        
    def log_debug(self, ticket_id: int, message: str) -> None:
        """Log de debug pour suivre le traitement."""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        logger.info(f"[{timestamp}] Ticket #{ticket_id}: {message}")
        
    def is_match_finished(self, fixture: Dict) -> bool:
        """Vérifie si un match est terminé."""
        status = fixture.get("fixture", {}).get("status", {}).get("short", "").upper()
        return status in FINISHED_STATUSES
        
    def get_final_score(self, fixture: Dict) -> Tuple[int, int]:
        """Récupère le score final d'un match terminé."""
        goals = fixture.get("goals", {})
        home_goals = int(goals.get("home", 0))
        away_goals = int(goals.get("away", 0))
        return home_goals, away_goals
        
    def calculate_prediction_result(self, market: str, prediction: str, 
                                  home_goals: int, away_goals: int,
                                  fixture: Dict, stats: Optional[Dict] = None,
                                  events: Optional[list] = None) -> str:
        """
        Calcule le résultat d'un prédiction pour un match terminé.
        Retourne WON ou LOST.
        """
        try:
            result = check_item(market, prediction, fixture, stats, events)
            return result
        except Exception as e:
            self.log_debug(0, f"Erreur calcul prédiction {market}/{prediction}: {e}")
            return "LOST"
            
    def validate_single_item(self, item: Dict, fixture: Dict,
                           stats: Optional[Dict] = None,
                           events: Optional[list] = None) -> Dict[str, Any]:
        """
        Valide un item de ticket et retourne les informations de validation.
        """
        fixture_id = item["fixture_id"]
        market = item["market"]
        prediction = item["prediction"]
        current_result = item.get("result", STATUS_PENDING)
        
        # Si déjà validé, ne pas retraiter
        if current_result in [STATUS_WON, STATUS_LOST]:
            return {
                "already_validated": True,
                "result": current_result,
                "message": f"Item déjà validé: {current_result}"
            }
            
        # Vérifier si le match est terminé
        if not self.is_match_finished(fixture):
            return {
                "finished": False,
                "result": STATUS_PENDING,
                "message": "Match non terminé"
            }
            
        # Match terminé - calculer le résultat
        home_goals, away_goals = self.get_final_score(fixture)
        new_result = self.calculate_prediction_result(
            market, prediction, home_goals, away_goals, fixture, stats, events
        )
        
        # Mettre à jour en base
        update_item_result(item["id"], new_result)
        
        status_text = "GAGNÉ" if new_result == STATUS_WON else "PERDU"
        self.log_debug(
            item.get("ticket_id", 0),
            f"Match terminé {home_goals}-{away_goals} -> {market}/{prediction} = {status_text}"
        )
        
        return {
            "finished": True,
            "result": new_result,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "message": f"Prédiction validée: {status_text}"
        }
        
    def update_ticket_overall_status(self, ticket_id: int) -> Dict[str, Any]:
        """
        Met à jour le statut global du ticket en fonction des items.
        Retourne les informations de mise à jour.
        """
        ticket = get_ticket(ticket_id)
        if not ticket:
            return {"error": "Ticket introuvable"}
            
        items = get_ticket_items(ticket_id)
        total_items = len(items)
        
        if total_items == 0:
            return {"error": "Ticket sans items"}
            
        # Compter les résultats
        won_count = sum(1 for item in items if item.get("result") == STATUS_WON)
        lost_count = sum(1 for item in items if item.get("result") == STATUS_LOST)
        pending_count = sum(1 for item in items if item.get("result") == STATUS_PENDING)
        validated_count = won_count + lost_count
        
        # Déterminer le statut du ticket
        current_status = ticket.get("ticket_status", STATUS_ACTIVE)
        new_status = current_status
        
        if lost_count >= 1:
            new_status = STATUS_LOST
            self.log_debug(ticket_id, f"Ticket PERDU ({lost_count} perte(s))")
        elif pending_count == 0 and validated_count == total_items:
            # Tous les items sont validés et aucune perte
            new_status = STATUS_WON
            reward_info = compute_reward(ticket["points_used"], total_items)
            self.log_debug(ticket_id, f"Ticket GAGNÉ ! Récompense: {reward_info['label']}")
        elif validated_count > 0:
            new_status = STATUS_ACTIVE  # EN COURS
            self.log_debug(ticket_id, f"Ticket EN COURS ({validated_count}/{total_items} validés)")
            
        # Si le statut a changé vers terminé, mettre à jour en base et créditer les points
        if new_status in [STATUS_WON, STATUS_LOST] and current_status == STATUS_ACTIVE:
            if new_status == STATUS_WON:
                reward_info = compute_reward(ticket["points_used"], total_items)
                update_ticket_status(ticket_id, STATUS_WON, reward_info["reward_points"])
                new_balance = credit_points(DEFAULT_USER_ID, reward_info["reward_points"])
                self.log_debug(ticket_id, f"✅ Points crédités: +{reward_info['reward_points']} ⭐ (Nouveau solde: {new_balance} ⭐)")
            else:
                update_ticket_status(ticket_id, STATUS_LOST, 0)
                self.log_debug(ticket_id, "❌ Ticket PERDU - aucun point crédité")
                
        return {
            "ticket_id": ticket_id,
            "total_items": total_items,
            "validated_count": validated_count,
            "won_count": won_count,
            "lost_count": lost_count,
            "pending_count": pending_count,
            "status": new_status,
            "progress_percent": (validated_count / total_items) * 100 if total_items > 0 else 0
        }
        
    def can_sell_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """
        Détermine si un ticket peut être vendu.
        Un ticket n'est vendable que si son statut est ACTIVE (EN COURS).
        """
        ticket = get_ticket(ticket_id)
        if not ticket:
            return {"can_sell": False, "reason": "Ticket introuvable"}
            
        status = ticket.get("ticket_status", "")
        
        if status != STATUS_ACTIVE:
            status_display = {
                STATUS_WON: "GAGNÉ",
                STATUS_LOST: "PERDU", 
                "SOLD": "VENDU"
            }.get(status, status)
            return {
                "can_sell": False,
                "reason": f"Ticket clôturé ({status_display})",
                "status": status
            }
            
        # Vérifier s'il reste des événements non terminés
        items = get_ticket_items(ticket_id)
        pending_items = [item for item in items if item.get("result") == STATUS_PENDING]
        
        if not pending_items:
            return {
                "can_sell": False,
                "reason": "Tous les événements sont terminés",
                "status": status
            }
            
        return {
            "can_sell": True,
            "reason": "Vente disponible",
            "status": status,
            "pending_items": len(pending_items)
        }
        
    def process_single_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """
        Traite un ticket complet : validation des items et mise à jour du statut.
        """
        self.log_debug(ticket_id, "Début traitement automatique")
        
        ticket = get_ticket(ticket_id)
        if not ticket:
            return {"success": False, "error": "Ticket introuvable"}
            
        if ticket.get("ticket_status") not in [STATUS_ACTIVE]:
            return {
                "success": True,
                "already_resolved": True,
                "status": ticket.get("ticket_status"),
                "message": "Ticket déjà résolu"
            }
            
        items = get_ticket_items(ticket_id)
        if not items:
            return {"success": False, "error": "Ticket sans items"}
            
        # Récupérer les données des fixtures
        fixtures_data = {}
        stats_data = {}
        events_data = {}
        
        for item in items:
            fixture_id = item["fixture_id"]
            
            # Récupérer fixture
            try:
                fixture_raw = self.api.get_fixture_detail(fixture_id)
                if isinstance(fixture_raw, tuple):
                    fixture_raw = fixture_raw[0]
                fixture = (fixture_raw or {}).get("response", [{}])[0]
                if fixture:
                    fixtures_data[fixture_id] = fixture
            except Exception as e:
                self.log_debug(ticket_id, f"Erreur récupération fixture {fixture_id}: {e}")
                continue
                
            # Récupérer stats
            try:
                stats_raw = self.api.get_fixture_statistics(fixture_id)
                if isinstance(stats_raw, tuple):
                    stats_raw = stats_raw[0]
                stats_data[fixture_id] = (stats_raw or {}).get("response", [{}])[0]
            except Exception:
                pass
                
            # Récupérer events
            try:
                events_raw = self.api.get_fixture_events(fixture_id)
                if isinstance(events_raw, tuple):
                    events_raw = events_raw[0]
                events_data[fixture_id] = (events_raw or {}).get("response", [])
            except Exception:
                pass
                
        # Valider chaque item
        validation_results = []
        for item in items:
            fixture_id = item["fixture_id"]
            fixture = fixtures_data.get(fixture_id)
            
            if not fixture:
                validation_results.append({
                    "item_id": item["id"],
                    "error": "Fixture non trouvé"
                })
                continue
                
            result = self.validate_single_item(
                item, fixture, 
                stats_data.get(fixture_id),
                events_data.get(fixture_id)
            )
            validation_results.append(result)
            
        # Mettre à jour le statut global du ticket
        status_update = self.update_ticket_overall_status(ticket_id)
        
        # Vérifier la possibilité de vente
        sell_info = self.can_sell_ticket(ticket_id)
        
        # Ajouter les infos de récompense si le ticket est gagné
        reward_info = None
        if status_update.get("status") == STATUS_WON:
            reward_info = compute_reward(ticket["points_used"], status_update.get("total_items", 0))
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "validation_results": validation_results,
            "status_update": status_update,
            "sell_info": sell_info,
            "reward_info": reward_info,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
    def process_all_active_tickets(self, user_id: int = DEFAULT_USER_ID) -> List[Dict[str, Any]]:
        """
        Traite tous les tickets actifs d'un utilisateur.
        """
        self.log_debug(0, "Traitement de tous les tickets actifs")
        
        tickets = get_user_tickets(user_id, status=STATUS_ACTIVE)
        results = []
        
        for ticket in tickets:
            ticket_id = ticket["ticket_id"]
            try:
                result = self.process_single_ticket(ticket_id)
                results.append(result)
            except Exception as e:
                self.log_debug(ticket_id, f"Erreur traitement: {e}")
                results.append({
                    "success": False,
                    "ticket_id": ticket_id,
                    "error": str(e)
                })
                
        self.log_debug(0, f"Traitement terminé: {len(results)} tickets traités")
        return results


def create_live_processor(api) -> LiveTicketProcessor:
    """Crée une instance du processeur de tickets live."""
    return LiveTicketProcessor(api)
