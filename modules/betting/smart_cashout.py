"""
smart_cashout.py
================
Système de Smart Cashout dynamique comme 1xBet/BetPawa.
Calcul intelligent des offres de vente en temps réel basé sur :
- Mise initiale et gain potentiel
- Progression des événements
- Données live (score, minute, stats)
- Analyse de risque IA
- Facteurs temps et probabilité
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import math

logger = logging.getLogger(__name__)


class SmartCashoutEngine:
    """Moteur de Smart Cashout dynamique."""
    
    def __init__(self, api):
        self.api = api
        self.cache = {}
        self.cache_ttl = 15  # 15 secondes de cache
        
    def calculate_smart_cashout(self, ticket_id: int, user_id: int = 1) -> Dict[str, Any]:
        """
        Calcule une offre de Smart Cashout dynamique.
        SYSTÈME ROBUSTE : Ne plante jamais, utilise des fallbacks.
        """
        try:
            # Récupérer les données du ticket
            ticket_data = self._get_ticket_data(ticket_id, user_id)
            if not ticket_data:
                logger.warning(f"Ticket #{ticket_id} introuvable pour user #{user_id}")
                return self._empty_response("Ticket introuvable")
                
            block_reason = self._cashout_block_reason(ticket_data)
            if block_reason:
                logger.info(f"Cashout indisponible pour ticket #{ticket_id}: {block_reason}")
                return self._empty_response(block_reason)
                
            # Calculer les facteurs avec protection
            try:
                factors = self._calculate_factors(ticket_data)
                
                # Si progression faible (<20%), utiliser le fallback plus généreux
                if factors["progress_factor"] < 0.2:
                    logger.info(f"Progression faible ({factors['progress_factor']:.2f}), utilisation du fallback généreux")
                    factors = self._get_fallback_factors(ticket_data)
                    factors["fallback_used"] = True
                    
            except Exception as e:
                logger.error(f"Erreur calcul facteurs ticket #{ticket_id}: {e}")
                factors = self._get_fallback_factors(ticket_data)
                logger.info(f"Fallback activé pour ticket #{ticket_id}")
            
            # Calculer l'offre de cashout avec protection
            try:
                # Si fallback utilisé, utiliser directement le fallback cashout plus généreux
                if factors.get("fallback_used", False):
                    logger.info(f"Fallback cashout utilisé pour ticket #{ticket_id}")
                    cashout_offer = self._get_fallback_cashout(ticket_data)
                else:
                    cashout_offer = self._calculate_cashout_offer(ticket_data, factors)
            except Exception as e:
                logger.error(f"Erreur calcul offre ticket #{ticket_id}: {e}")
                cashout_offer = self._get_fallback_cashout(ticket_data)
                logger.info(f"Fallback cashout activé pour ticket #{ticket_id}")
            
            # Générer les recommandations avec protection
            try:
                recommendations = self._generate_recommendations(ticket_data, factors, cashout_offer)
            except Exception as e:
                logger.error(f"Erreur recommandations ticket #{ticket_id}: {e}")
                recommendations = {"text": "📊 Analyse limitée", "type": "NEUTRAL"}
            
            return {
                "available": True,
                "ticket_id": ticket_id,
                "stake": ticket_data["stake"],
                "potential_gain": ticket_data["potential_gain"],
                "cashout_offer": cashout_offer["amount"],
                "cashout_percentage": cashout_offer["percentage"],
                "risk_level": factors["risk_level"],
                "risk_score": factors["risk_score"],
                "confidence": factors["confidence"],
                "recommendation": recommendations["text"],
                "recommendation_type": recommendations["type"],
                "progress": factors["progress"],
                "validated_events": factors["validated_events"],
                "remaining_events": factors["remaining_events"],
                "live_analysis": factors["live_analysis"],
                "calculated_at": datetime.now(timezone.utc).isoformat(),
                "next_update": (datetime.now(timezone.utc).timestamp() + 15),
                "fallback_used": factors.get("fallback_used", False),
                "sale_allowed": True
            }
            
        except Exception as e:
            logger.error(f"ERREUR CRITIQUE calcul cashout ticket #{ticket_id}: {e}")
            # Retourner une réponse de fallback minimale
            return self._get_emergency_fallback(ticket_id, user_id)
    
    def _get_ticket_data(self, ticket_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Récupère et prépare les données du ticket."""
        from modules.betting.ticket_storage import get_ticket, get_ticket_items
        
        ticket = get_ticket(ticket_id)
        if not ticket or ticket.get("user_id") != user_id:
            return None
            
        items = get_ticket_items(ticket_id)
        if not items:
            return None
            
        # Calculer les statistiques de base
        validated_count = sum(1 for item in items if item.get("result") in ["WON", "LOST"])
        won_count = sum(1 for item in items if item.get("result") == "WON")
        lost_count = sum(1 for item in items if item.get("result") == "LOST")
        pending_count = len(items) - validated_count
        
        # Calculer le gain potentiel
        total_odds = 1.0
        for item in items:
            total_odds *= max(1.0, float(item.get("odds", 1.0)))
        
        potential_gain = max(ticket["points_used"] * total_odds, 45)  # Minimum 45
        
        return {
            "ticket_id": ticket_id,
            "stake": ticket["points_used"],
            "potential_gain": potential_gain,
            "status": ticket.get("ticket_status", "ACTIVE"),
            "items": items,
            "total_events": len(items),
            "validated_events": validated_count,
            "won_events": won_count,
            "lost_events": lost_count,
            "pending_events": pending_count,
            "total_odds": total_odds
        }
    
    def _cashout_block_reason(self, ticket_data: Dict[str, Any]) -> str:
        status = ticket_data["status"]

        if status in ["LOST", "SOLD"]:
            return "Vente bloquée : ticket déjà perdu ou vendu."

        if ticket_data["pending_events"] == 0:
            return "Vente bloquée : tous les événements sont terminés."

        if ticket_data["lost_events"] > 0:
            return "Vente bloquée : une prédiction du ticket est perdue."

        if ticket_data["won_events"] <= 0:
            return "Vente bloquée : aucune prédiction favorable validée pour le moment."

        return ""

    def _is_cashout_available(self, ticket_data: Dict[str, Any]) -> bool:
        """Vérifie si le cashout est disponible pour ce ticket."""
        return not self._cashout_block_reason(ticket_data)
    
    def _calculate_factors(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule tous les facteurs pour le Smart Cashout."""
        
        # 1. Facteur de progression
        progress_factor = ticket_data["validated_events"] / ticket_data["total_events"]
        
        # 2. Analyse des risques live
        live_analysis = self._analyze_live_risks(ticket_data)
        
        # 3. Facteur de temps
        time_factor = self._calculate_time_factor(ticket_data)
        
        # 4. Facteur de probabilité live
        live_probability = self._calculate_live_probability(ticket_data, live_analysis)
        
        # 5. Score de risque global
        risk_score = self._calculate_risk_score(live_analysis, ticket_data)
        
        # 6. Niveau de risque
        risk_level = self._get_risk_level(risk_score)
        
        # 7. Confiance
        confidence = max(0, min(100, (1 - risk_score) * live_probability * 100))
        
        return {
            "progress_factor": progress_factor,
            "time_factor": time_factor,
            "live_probability": live_probability,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "confidence": confidence,
            "progress": progress_factor * 100,
            "validated_events": ticket_data["validated_events"],
            "remaining_events": ticket_data["pending_events"],
            "live_analysis": live_analysis
        }
    
    def _analyze_live_risks(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse les risques basés sur les données live."""
        risks = []
        total_risk = 0.0
        
        for item in ticket_data["items"]:
            if item.get("result") != "PENDING":
                continue
                
            fixture_id = item["fixture_id"]
            item_risk = self._analyze_fixture_risk(fixture_id, item)
            risks.append(item_risk)
            total_risk += item_risk["risk_score"]
        
        avg_risk = total_risk / len(risks) if risks else 0.0
        
        return {
            "individual_risks": risks,
            "average_risk": avg_risk,
            "high_risk_count": sum(1 for r in risks if r["risk_score"] > 0.7),
            "critical_situations": [r for r in risks if r["risk_score"] > 0.8]
        }
    
    def safe_get_match_data(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Récupère les données du match de manière sécurisée.
        Évite les erreurs fixture_id et retourne des valeurs par défaut.
        """
        try:
            # Récupération sécurisée du fixture_id
            fixture_id = (
                event.get("fixture_id") or 
                event.get("fixture", {}).get("id") or 
                event.get("id") or 
                None
            )
            
            if not fixture_id:
                logger.warning("fixture_id absent dans l'événement")
                return {
                    "fixture_id": None,
                    "home": event.get("home_team", "Équipe domicile"),
                    "away": event.get("away_team", "Équipe extérieur"),
                    "minute": 0,
                    "score": "0-0",
                    "status": "NS",
                    "available": False
                }
            
            # Récupération sécurisée des données
            fixture_data = self._get_fixture_data(fixture_id)
            if not fixture_data:
                logger.warning(f"Données fixture indisponibles pour {fixture_id}")
                return {
                    "fixture_id": fixture_id,
                    "home": event.get("home_team", "Équipe domicile"),
                    "away": event.get("away_team", "Équipe extérieur"),
                    "minute": 0,
                    "score": "0-0",
                    "status": "NS",
                    "available": False
                }
            
            fixture = fixture_data.get("fixture", {})
            goals = fixture.get("goals", {})
            status = fixture.get("status", {})
            
            return {
                "fixture_id": fixture_id,
                "home": fixture.get("teams", {}).get("home", {}).get("name", event.get("home_team", "Équipe domicile")),
                "away": fixture.get("teams", {}).get("away", {}).get("name", event.get("away_team", "Équipe extérieur")),
                "minute": status.get("elapsed", 0),
                "score": f"{goals.get('home', 0)}-{goals.get('away', 0)}",
                "status": status.get("short", "NS"),
                "available": True
            }
            
        except Exception as e:
            logger.error(f"Erreur safe_get_match_data: {e}")
            return {
                "fixture_id": event.get("fixture_id"),
                "home": event.get("home_team", "Équipe domicile"),
                "away": event.get("away_team", "Équipe extérieur"),
                "minute": 0,
                "score": "0-0",
                "status": "NS",
                "available": False
            }

    def _analyze_fixture_risk(self, fixture_id: int, item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse le risque pour un match spécifique."""
        try:
            # Utiliser safe_get_match_data pour éviter les erreurs
            match_data = self.safe_get_match_data(item)
            
            if not match_data.get("available"):
                logger.info(f"Données indisponibles pour fixture {fixture_id}, risque moyen par défaut")
                return {
                    "risk_score": 0.5,
                    "factors": {"fallback": True},
                    "fixture_id": fixture_id,
                    "current_score": match_data["score"],
                    "minute": match_data["minute"],
                    "fallback_used": True
                }
            
            # Récupérer les données live
            fixture_data = self._get_fixture_data(fixture_id)
            if not fixture_data:
                return {
                    "risk_score": 0.5, 
                    "factors": {"fallback": True},
                    "fixture_id": fixture_id,
                    "current_score": match_data["score"],
                    "minute": match_data["minute"],
                    "fallback_used": True
                }
            
            fixture = fixture_data.get("fixture", {})
            events = fixture_data.get("events", [])
            statistics = fixture_data.get("statistics", [])
            
            # Facteurs de risque avec protection
            risk_factors = {}
            total_risk = 0.0
            
            try:
                # 1. Score actuel vs prédiction
                score_risk = self._calculate_score_risk(fixture, item)
                risk_factors["score"] = score_risk
                total_risk += score_risk * 0.3
            except Exception as e:
                logger.error(f"Erreur score_risk: {e}")
                total_risk += 0.15  # Valeur moyenne
            
            try:
                # 2. Minute du match
                minute_risk = self._calculate_minute_risk(fixture)
                risk_factors["minute"] = minute_risk
                total_risk += minute_risk * 0.2
            except Exception as e:
                logger.error(f"Erreur minute_risk: {e}")
                total_risk += 0.1
            
            try:
                # 3. Cartons rouges
                red_card_risk = self._calculate_red_card_risk(events)
                risk_factors["red_cards"] = red_card_risk
                total_risk += red_card_risk * 0.25
            except Exception as e:
                logger.error(f"Erreur red_card_risk: {e}")
                total_risk += 0.125
            
            try:
                # 4. Momentum (buts récents)
                momentum_risk = self._calculate_momentum_risk(events, fixture)
                risk_factors["momentum"] = momentum_risk
                total_risk += momentum_risk * 0.15
            except Exception as e:
                logger.error(f"Erreur momentum_risk: {e}")
                total_risk += 0.075
            
            try:
                # 5. Statistiques (tirs, xG)
                stats_risk = self._calculate_stats_risk(statistics, item)
                risk_factors["statistics"] = stats_risk
                total_risk += stats_risk * 0.1
            except Exception as e:
                logger.error(f"Erreur stats_risk: {e}")
                total_risk += 0.05
            
            return {
                "risk_score": min(1.0, total_risk),
                "factors": risk_factors,
                "fixture_id": fixture_id,
                "current_score": match_data["score"],
                "minute": match_data["minute"],
                "fallback_used": not match_data.get("available", True)
            }
            
        except Exception as e:
            logger.error(f"ERREUR CRITIQUE analyse risque fixture {fixture_id}: {e}")
            return {
                "risk_score": 0.5,
                "factors": {"emergency_fallback": True},
                "fixture_id": fixture_id,
                "current_score": "0-0",
                "minute": 0,
                "fallback_used": True
            }
    
    def _get_fixture_data(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Récupère les données complètes d'un match."""
        try:
            # Vérifier si l'API est disponible
            if not self.api:
                logger.warning("API non disponible dans Smart Cashout")
                return None
            
            # Vérifier le cache
            cache_key = f"fixture_{fixture_id}"
            now = datetime.now(timezone.utc).timestamp()
            
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if now - cached["timestamp"] < self.cache_ttl:
                    return cached["data"]
            
            # Récupérer fixture
            fixture_raw = self.api.get_fixture_detail(fixture_id)
            if isinstance(fixture_raw, tuple):
                fixture_raw = fixture_raw[0]
            fixture = (fixture_raw or {}).get("response", [{}])[0]
            
            if not fixture:
                return None
            
            # Récupérer événements
            try:
                events_raw = self.api.get_fixture_events(fixture_id)
                if isinstance(events_raw, tuple):
                    events_raw = events_raw[0]
                events = (events_raw or {}).get("response", [])
            except Exception as e:
                logger.error(f"Erreur récupération événements fixture {fixture_id}: {e}")
                events = []
            
            # Récupérer statistiques
            try:
                stats_raw = self.api.get_fixture_statistics(fixture_id)
                if isinstance(stats_raw, tuple):
                    stats_raw = stats_raw[0]
                statistics = (stats_raw or {}).get("response", [{}])[0]
            except Exception as e:
                logger.error(f"Erreur récupération statistiques fixture {fixture_id}: {e}")
                statistics = {}
            
            data = {
                "fixture": fixture,
                "events": events,
                "statistics": statistics
            }
            
            # Mettre en cache
            self.cache[cache_key] = {
                "data": data,
                "timestamp": now
            }
            
            return data
            
        except Exception as e:
            logger.error(f"Erreur récupération fixture {fixture_id}: {e}")
            return None
    
    def _calculate_score_risk(self, fixture: Dict[str, Any], item: Dict[str, Any]) -> float:
        """Calcule le risque basé sur le score actuel vs la prédiction."""
        try:
            goals = fixture.get("goals", {})
            home_goals = int(goals.get("home", 0))
            away_goals = int(goals.get("away", 0))
            
            market = item["market"]
            prediction = item["prediction"]
            
            # Analyse selon le marché
            if market == "1X2":
                if prediction == "Domicile (1)":
                    return max(0, (away_goals - home_goals) / 3)  # Risque si visiteur mène
                elif prediction == "Extérieur (2)":
                    return max(0, (home_goals - away_goals) / 3)  # Risque si domicile mène
                elif prediction == "Nul (X)":
                    diff = abs(home_goals - away_goals)
                    return min(1.0, diff / 2)  # Risque si écart grand
                    
            elif market == "Over/Under Buts":
                try:
                    direction, threshold = prediction.split(" ", 1)
                    threshold = float(threshold)
                    total_goals = home_goals + away_goals
                    
                    if direction == "Over":
                        if total_goals >= threshold:
                            return 0.0  # Pas de risque, déjà validé
                        else:
                            needed = threshold - total_goals
                            return max(0, min(1.0, needed / 3))
                    else:  # Under
                        if total_goals > threshold:
                            return 1.0  # Risque maximum, déjà perdu
                        else:
                            return max(0, total_goals / threshold)
                except:
                    return 0.5
                    
            return 0.5  # Risque moyen par défaut
            
        except:
            return 0.5
    
    def _calculate_minute_risk(self, fixture: Dict[str, Any]) -> float:
        """Calcule le risque basé sur la minute du match."""
        try:
            status = fixture.get("fixture", {}).get("status", {})
            minute = status.get("elapsed", 0)
            
            if minute < 20:
                return 0.3  # Risque faible début de match
            elif minute < 60:
                return 0.5  # Risque moyen
            elif minute < 80:
                return 0.7  # Risque élevé fin de match
            else:
                return 0.9  # Risque très élevé temps additionnel
                
        except:
            return 0.5
    
    def _calculate_red_card_risk(self, events: List[Dict[str, Any]]) -> float:
        """Calcule le risque basé sur les cartons rouges."""
        try:
            red_cards = [e for e in events if e.get("type") == "Card" and e.get("detail") == "Red Card"]
            return min(1.0, len(red_cards) * 0.4)  # Chaque rouge augmente le risque
        except:
            return 0.0
    
    def _calculate_momentum_risk(self, events: List[Dict[str, Any]], fixture: Dict[str, Any]) -> float:
        """Calcule le risque basé sur le momentum (buts récents)."""
        try:
            goals = [e for e in events if e.get("type") == "Goal"]
            minute = fixture.get("fixture", {}).get("status", {}).get("elapsed", 0)
            
            # Buts dans les 15 dernières minutes
            recent_goals = [g for g in goals if minute - g.get("time", {}).get("elapsed", 0) <= 15]
            
            if len(recent_goals) >= 2:
                return 0.8  # Momentum élevé = risque élevé
            elif len(recent_goals) == 1:
                return 0.5
            else:
                return 0.2  # Peu de buts récents = risque faible
                
        except:
            return 0.5
    
    def _calculate_stats_risk(self, statistics: Dict[str, Any], item: Dict[str, Any]) -> float:
        """Calcule le risque basé sur les statistiques (tirs, xG)."""
        try:
            if not statistics:
                return 0.5
                
            # Analyse basique des tirs
            home_stats = statistics.get("statistics", [])
            away_stats = statistics.get("statistics", [])
            
            # Simplifié : risque basé sur le déséquilibre des tirs
            if home_stats and away_stats:
                home_shots = self._get_stat_value(home_stats, "Shots on Goal")
                away_shots = self._get_stat_value(away_stats, "Shots on Goal")
                
                if home_shots and away_shots:
                    total_shots = home_shots + away_shots
                    if total_shots > 0:
                        imbalance = abs(home_shots - away_shots) / total_shots
                        return min(1.0, imbalance)
            
            return 0.5
            
        except:
            return 0.5
    
    def _get_stat_value(self, stats: List[Dict[str, Any]], stat_name: str) -> Optional[int]:
        """Extrait une valeur statistique."""
        for stat in stats:
            if stat.get("type") == stat_name:
                try:
                    return int(stat.get("value", 0))
                except:
                    return None
        return None
    
    def _calculate_time_factor(self, ticket_data: Dict[str, Any]) -> float:
        """Calcule le facteur temps selon les minutes des matchs."""
        try:
            total_minutes = 0
            match_count = 0
            
            for item in ticket_data["items"]:
                if item.get("result") != "PENDING":
                    continue
                    
                fixture_data = self._get_fixture_data(item["fixture_id"])
                if fixture_data:
                    minute = fixture_data.get("fixture", {}).get("status", {}).get("elapsed", 0)
                    total_minutes += minute
                    match_count += 1
            
            if match_count == 0:
                return 0.6
                
            avg_minute = total_minutes / match_count
            
            if avg_minute < 20:
                return 0.6
            elif avg_minute < 60:
                return 0.8
            elif avg_minute < 80:
                return 1.0
            else:
                return 1.15
                
        except:
            return 0.8
    
    def _calculate_live_probability(self, ticket_data: Dict[str, Any], live_analysis: Dict[str, Any]) -> float:
        """Calcule la probabilité de succès basée sur les données live."""
        try:
            # Base : progression actuelle
            base_prob = ticket_data["validated_events"] / ticket_data["total_events"]
            
            # Ajustement selon les risques
            risk_adjustment = 1.0 - live_analysis["average_risk"]
            
            # Facteur de confiance selon les événements validés
            if ticket_data["validated_events"] > 0:
                confidence_factor = min(1.2, 1.0 + (ticket_data["won_events"] / ticket_data["validated_events"]) * 0.2)
            else:
                confidence_factor = 1.0
            
            live_prob = base_prob * risk_adjustment * confidence_factor
            return max(0.1, min(0.95, live_prob))
            
        except:
            return 0.5
    
    def _calculate_risk_score(self, live_analysis: Dict[str, Any], ticket_data: Dict[str, Any]) -> float:
        """Calcule le score de risque global."""
        try:
            # Risque moyen des matchs restants
            avg_risk = live_analysis["average_risk"]
            
            # Pénalité si situations critiques
            critical_penalty = len(live_analysis["critical_situations"]) * 0.1
            
            # Ajustement selon le nombre d'événements restants
            remaining_factor = ticket_data["remaining_events"] / ticket_data["total_events"]
            
            total_risk = avg_risk + critical_penalty
            return min(1.0, total_risk * remaining_factor)
            
        except:
            return 0.5
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Détermine le niveau de risque."""
        if risk_score < 0.3:
            return "FAIBLE"
        elif risk_score < 0.6:
            return "MOYEN"
        else:
            return "ÉLEVÉ"
    
    def _calculate_cashout_offer(self, ticket_data: Dict[str, Any], factors: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule l'offre de cashout finale avec bénéfice minimum garanti."""
        try:
            stake = ticket_data["stake"]
            potential_gain = ticket_data["potential_gain"]
            
            logger.info(f"PRINCIPAL CASHOUT - stake: {stake}, potential: {potential_gain}")
            logger.info(f"FACTORS - progress: {factors['progress_factor']}, prob: {factors['live_probability']}, time: {factors['time_factor']}, risk: {factors['risk_score']}")
            
            # Formule Smart Cashout améliorée
            progress_bonus = (
                (potential_gain - stake) *
                factors["progress_factor"] *
                factors["live_probability"] *
                factors["time_factor"] *
                (1 - factors["risk_score"])
            )
            
            cashout = stake + progress_bonus
            
            logger.info(f"PRINCIPAL CALCUL - progress_bonus: {progress_bonus}, cashout: {cashout}")
            
            # Limites de sécurité améliorées : minimum 130% de la mise pour un meilleur bénéfice
            min_cashout = stake * 1.3
            max_cashout = potential_gain * 0.8  # Maximum 80% pour conserver une marge raisonnable
            
            cashout = max(min_cashout, min(max_cashout, cashout))
            
            # Arrondir
            cashout = round(cashout)
            percentage = round((cashout / potential_gain) * 100)
            
            logger.info(f"PRINCIPAL FINAL - cashout: {cashout}, percentage: {percentage}")
            
            return {
                "amount": cashout,
                "percentage": percentage
            }
            
        except Exception as e:
            logger.error(f"Erreur calcul cashout: {e}")
            # En cas d'erreur, retourner 120% de la mise
            stake = ticket_data.get("stake", 10)
            logger.info(f"PRINCIPAL ERROR FALLBACK - stake: {stake}, cashout: {stake * 1.2}")
            return {
                "amount": round(stake * 1.2),
                "percentage": 60
            }
    
    def _generate_recommendations(self, ticket_data: Dict[str, Any], factors: Dict[str, Any], cashout_offer: Dict[str, Any]) -> Dict[str, Any]:
        """Génère les recommandations intelligentes."""
        try:
            risk_score = factors["risk_score"]
            confidence = factors["confidence"]
            percentage = cashout_offer["percentage"]
            
            if risk_score > 0.7:
                return {
                    "text": "🔥 Bon moment pour vendre",
                    "type": "SELL_NOW"
                }
            elif confidence > 80 and percentage > 70:
                return {
                    "text": "✅ Ticket très favorable",
                    "type": "KEEP_TICKET"
                }
            elif risk_score > 0.5 and percentage > 50:
                return {
                    "text": "⚠️ Risque augmente",
                    "type": "CONSIDER_SELL"
                }
            elif percentage < 30:
                return {
                    "text": "📉 Offre faible",
                    "type": "WAIT_BETTER"
                }
            else:
                return {
                    "text": "🤔 Analyse en cours",
                    "type": "NEUTRAL"
                }
                
        except:
            return {
                "text": "📊 Analyse indisponible",
                "type": "ERROR"
            }
    
    def _empty_response(self, reason: str) -> Dict[str, Any]:
        """Retourne une réponse vide pour cashout indisponible."""
        return {
            "available": False,
            "sale_allowed": False,
            "reason": reason,
            "calculated_at": datetime.now(timezone.utc).isoformat()
        }

    def _get_fallback_factors(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retourne des facteurs de fallback si le calcul échoue.
        Valeurs conservatrices pour garantir la stabilité.
        """
        try:
            progress = ticket_data["validated_events"] / ticket_data["total_events"]
            
            return {
                "progress_factor": progress,
                "time_factor": 0.8,  # Valeur moyenne
                "live_probability": max(0.5, progress),  # Au moins 50%
                "risk_score": 0.5,  # Risque moyen
                "risk_level": "MOYEN",
                "confidence": 60,  # Confiance moyenne
                "progress": progress * 100,
                "validated_events": ticket_data["validated_events"],
                "remaining_events": ticket_data["pending_events"],
                "live_analysis": {
                    "individual_risks": [],
                    "average_risk": 0.5,
                    "high_risk_count": 0,
                    "critical_situations": []
                },
                "fallback_used": True
            }
        except Exception as e:
            logger.error(f"Erreur fallback factors: {e}")
            return {
                "progress_factor": 0.5,
                "time_factor": 0.8,
                "live_probability": 0.5,
                "risk_score": 0.5,
                "risk_level": "MOYEN",
                "confidence": 50,
                "progress": 50,
                "validated_events": 0,
                "remaining_events": 1,
                "live_analysis": {"average_risk": 0.5},
                "fallback_used": True
            }
    
    def _get_fallback_cashout(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retourne une offre de cashout généreuse même avec progression faible.
        Base : 140% de la mise + bonus selon le nombre de matchs.
        """
        try:
            stake = ticket_data["stake"]
            potential_gain = ticket_data["potential_gain"]
            progress = ticket_data["validated_events"] / ticket_data["total_events"]
            remaining_events = ticket_data["pending_events"]
            
            logger.info(f"FALLBACK CASHOUT - stake: {stake}, potential: {potential_gain}, progress: {progress}, remaining: {remaining_events}")
            
            # Cashout généreux : base 140% de la mise + bonus selon matchs restants
            base_cashout = stake * 1.4
            
            # Bonus supplémentaire selon le nombre de matchs restants
            if remaining_events >= 3:
                bonus_multiplier = 0.3  # 30% du gain potentiel
            elif remaining_events == 2:
                bonus_multiplier = 0.4  # 40% du gain potentiel
            else:  # 1 match restant
                bonus_multiplier = 0.5  # 50% du gain potentiel
            
            progress_bonus = (potential_gain - stake) * bonus_multiplier
            cashout = base_cashout + progress_bonus
            
            logger.info(f"FALLBACK CALCUL - base: {base_cashout}, bonus: {progress_bonus}, total: {cashout}")
            
            # Limites : minimum 140% de la mise, maximum 75% du gain potentiel
            cashout = max(stake * 1.4, min(potential_gain * 0.75, cashout))
            
            logger.info(f"FALLBACK FINAL - cashout: {cashout}, percentage: {(cashout/potential_gain)*100}")
            
            return {
                "amount": round(cashout),
                "percentage": round((cashout / potential_gain) * 100)
            }
        except Exception as e:
            logger.error(f"Erreur fallback cashout: {e}")
            # En cas d'erreur, retourner 150% de la mise
            stake = ticket_data.get("stake", 10)
            logger.info(f"EMERGENCY FALLBACK - stake: {stake}, cashout: {stake * 1.5}")
            return {
                "amount": round(stake * 1.5),
                "percentage": 75
            }
    
    def _get_emergency_fallback(self, ticket_id: int, user_id: int) -> Dict[str, Any]:
        """
        Fallback d'urgence si tout échoue.
        Retourne une réponse minimale mais fonctionnelle.
        """
        try:
            from modules.betting.ticket_storage import get_ticket, get_ticket_items
            ticket = get_ticket(ticket_id)
            
            if not ticket:
                return self._empty_response("Ticket introuvable")

            items = get_ticket_items(ticket_id)
            nb_won = sum(1 for item in items if item.get("result") == "WON")
            nb_lost = sum(1 for item in items if item.get("result") == "LOST")
            if nb_lost > 0:
                return self._empty_response("Vente bloquée : une prédiction du ticket est perdue.")
            if nb_won <= 0:
                return self._empty_response("Vente bloquée : aucune prédiction favorable validée pour le moment.")
            
            stake = ticket.get("points_used", 10)
            cashout = round(stake * 1.6)  # 160% de la mise pour un bon bénéfice
            
            logger.critical(f"Fallback d'urgence activé pour ticket #{ticket_id}")
            
            return {
                "available": True,
                "ticket_id": ticket_id,
                "stake": stake,
                "potential_gain": stake * 2,  # Estimation minimale
                "cashout_offer": cashout,
                "cashout_percentage": 80,  # 80% du gain potentiel estimé
                "risk_level": "MOYEN",
                "risk_score": 0.5,
                "confidence": 50,
                "recommendation": "📊 Analyse limitée",
                "recommendation_type": "NEUTRAL",
                "progress": 0,
                "validated_events": 0,
                "remaining_events": 1,
                "live_analysis": {"average_risk": 0.5},
                "calculated_at": datetime.now(timezone.utc).isoformat(),
                "next_update": (datetime.now(timezone.utc).timestamp() + 15),
                "fallback_used": True,
                "emergency_fallback": True,
                "sale_allowed": True
            }
        except Exception as e:
            logger.critical(f"ERREUR FATALE fallback d'urgence ticket #{ticket_id}: {e}")
            return self._empty_response("Erreur système critique")


def create_smart_cashout_engine(api) -> SmartCashoutEngine:
    """Crée une instance du moteur Smart Cashout."""
    return SmartCashoutEngine(api)
