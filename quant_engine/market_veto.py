"""
═══════════════════════════════════════════════════════════════════════════════
PILIER 4 : VETO DU MARCHÉ (SHARP MONEY TRACKING)
Système bidirectionnel : Détecte mouvement cotes > 5% → VETO immédiat
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import sqlite3
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# TRACKING SHARP MONEY (APIs Pinnacle & Asian Bookmakers)
# ═══════════════════════════════════════════════════════════════════════════════

class SharpMoneyTracker:
    """
    Connexion aux marchés asiatiques (Pinnacle, SBR) pour détecter Smart Money.
    Pinnacle = le marché où les "sharpest" bettors jouent → indicateur fiable de value.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def fetch_pinnacle_odds(self, fixture_id: int, market_type: str = "all") -> Optional[Dict]:
        """
        Récupère les cotes Pinnacle en temps réel (pas de limites)
        market_type: 'OU_2_5', 'AH', '1X2', 'all'
        """
        # Mock : en production, utiliser Pinnacle API
        # curl https://api.pinnacle.com/v3/fixtures?leagues=1,2,...&...

        logger.info(f"[SHARP] Fetching Pinnacle odds for fixture {fixture_id}")

        return {
            "fixture_id": fixture_id,
            "ou_2_5_over": 2.00,
            "ou_2_5_under": 1.90,
            "ah_home": -0.5,
            "ah_odds_home": 1.95,
            "ah_odds_away": 1.95,
            "odds_1": 2.20,
            "odds_x": 3.40,
            "odds_2": 3.20,
            "timestamp": int(datetime.now().timestamp()),
        }

    async def track_line_movement(
        self,
        fixture_id: int,
        current_odds: Dict,
        previous_odds: Optional[Dict] = None,
        threshold_pct: float = 5.0
    ) -> Dict:
        """
        Détecte mouvements de cotes > seuil (indiquer Smart Money)
        Retourne: { fixture_id, movements: [], detected: bool }
        """
        if previous_odds is None:
            return {
                "fixture_id": fixture_id,
                "movements": [],
                "detected": False,
            }

        movements = []

        for market_key in current_odds:
            if market_key == "fixture_id" or market_key == "timestamp":
                continue

            current = current_odds.get(market_key)
            previous = previous_odds.get(market_key)

            if current is None or previous is None:
                continue

            # Calcul du mouvement en %
            pct_change = ((current - previous) / previous * 100) if previous != 0 else 0

            if abs(pct_change) > threshold_pct:
                movements.append({
                    "market": market_key,
                    "previous": previous,
                    "current": current,
                    "pct_change": round(pct_change, 2),
                    "direction": "↑" if pct_change > 0 else "↓",
                })

        return {
            "fixture_id": fixture_id,
            "movements": movements,
            "detected": len(movements) > 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIQUE VETO BIDIRECTIONNEL
# ═══════════════════════════════════════════════════════════════════════════════

class MarketVetoEngine:
    """
    Système de Veto bidirectionnel pour annuler trades :

    CAS 1 : Modèle trouve VALUE → cotes Asian Handicap bougent CONTRE nous
    CAS 2 : Modèle veut OVER/UNDER → cotes bougent rapidement contraire

    DÉCISION: Si ligne bouge > 5% direction opposée → VETO immédiat
    """

    def __init__(self, db_path: str, pinnacle_api_key: Optional[str] = None):
        self.db_path = db_path
        self.sharp_tracker = SharpMoneyTracker(api_key=pinnacle_api_key)
        self.previous_lines: Dict[int, Dict] = {}  # Cache des cotes précédentes par fixture

    async def bidirectional_veto(
        self,
        model_prediction: Dict,  # { "side": "OVER", "probability": 0.65, "implied_odds": 1.54 }
        market_lines: Dict,  # Cotes Pinnacle actuelles
        threshold_pct: float = 5.0
    ) -> Dict:
        """
        VETO Bidirectionnel :
        - Détecte mouvement cotes > seuil dans direction OPPOSÉE à prédiction
        - Retourne: { allow_trade: bool, reason: str }
        """
        fixture_id = market_lines.get("fixture_id")
        logger.info(f"[VETO] Evaluation bidirectionnelle pour fixture {fixture_id}")

        # 1. Récupérer cotes Pinnacle previouslystock
        pinnacle_odds = await self.sharp_tracker.fetch_pinnacle_odds(fixture_id)

        # 2. Détecter mouvements
        prev_lines = self.previous_lines.get(fixture_id)
        line_movement = await self.sharp_tracker.track_line_movement(
            fixture_id,
            pinnacle_odds,
            previous_odds=prev_lines,
            threshold_pct=threshold_pct
        )

        # 3. Mettre à jour cache
        self.previous_lines[fixture_id] = pinnacle_odds

        # 4. Vérifier VETO logic
        side = model_prediction.get("side", "").upper()  # "OVER", "UNDER", "HOME", "AWAY"
        probability = model_prediction.get("probability", 0.0)

        if not line_movement["detected"]:
            # Pas de mouvement sharp → Allow trade
            return {
                "allow_trade": True,
                "reason": "Pas de mouvement sharp détecté",
                "veto_reason": "",
            }

        # Vérifier si mouvements vont CONTRE notre prédiction
        veto_triggered = False
        veto_reasons = []

        for movement in line_movement["movements"]:
            market = movement.get("market", "").lower()
            direction = movement.get("direction")  # ↑ ou ↓
            pct = movement.get("pct_change")

            # CAS 1 : On veut OVER → cotes under bougent UP (sharp favour under)
            if side == "OVER" and "under" in market and direction == "↑":
                veto_triggered = True
                veto_reasons.append(f"Sharp taction UNDER: {market} +{pct}%")

            # CAS 2 : On veut UNDER → cotes over bougent UP (sharp favour over)
            elif side == "UNDER" and "over" in market and direction == "↑":
                veto_triggered = True
                veto_reasons.append(f"Sharp action OVER: {market} +{pct}%")

            # CAS 3 : On veut HOME → Away line bougent toward home (sharp fade home = oppose nous)
            elif side == "HOME" and "away" in market and direction == "↑":
                veto_triggered = True
                veto_reasons.append(f"Sharp action AWAY: {market} +{pct}%")

            # CAS 4 : On veut AWAY → Home line bougent toward away
            elif side == "AWAY" and "home" in market and direction == "↑":
                veto_triggered = True
                veto_reasons.append(f"Sharp action HOME: {market} +{pct}%")

        if veto_triggered:
            logger.warning(f"[VETO] VETO TRIGGERED: {'; '.join(veto_reasons)}")
            return {
                "allow_trade": False,
                "reason": "VETO bidirectionnel: Sharp money détecté en sens inverse",
                "veto_reason": "; ".join(veto_reasons),
                "movements": line_movement["movements"],
            }

        return {
            "allow_trade": True,
            "reason": f"Mouvements compatibles avec prédiction (Prob={probability:.1%})",
            "veto_reason": "",
            "movements": line_movement["movements"],
        }

    async def check_liquidity_and_limits(
        self,
        fixture_id: int,
        stake_units: float,
        market_type: str,
        bookmaker: str = "pinnacle"
    ) -> Dict:
        """
        Vérifie que la liquidité du marché peut absorber notre commande.
        Retourne: { allow: bool, max_stake: float, reason: str }
        """
        logger.info(f"[VETO] Vérification liquidité pour {bookmaker} stake={stake_units}u")

        # Mock: en production, requête l'API Pinnacle pour max bet
        max_bet_limit = {
            "pinnacle": 50000,  # Pinnacle très haute limite
            "betfair": 5000,
            "smarkets": 2000,
        }.get(bookmaker, 1000)

        if stake_units > max_bet_limit:
            logger.warning(f"[VETO] Stake {stake_units}u exceed max bet {max_bet_limit}u")
            return {
                "allow": False,
                "max_stake": max_bet_limit,
                "reason": f"Stake dépasse limite liquidité ({stake_units}u > {max_bet_limit}u)",
            }

        return {
            "allow": True,
            "max_stake": max_bet_limit,
            "reason": f"Liquidité OK: {max_bet_limit}u disponible",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN D'TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test_veto():
        veto = MarketVetoEngine(db_path="quant_engine.db")

        # Test 1: VETO not triggered
        model_pred = {"side": "OVER", "probability": 0.65}
        market_lines = {"fixture_id": 123, "ou_2_5_over": 1.90}
        result = await veto.bidirectional_veto(model_pred, market_lines)
        print(f"Test 1 (No VETO): {result}")

        # Test 2: VETO triggered
        veto.previous_lines[123] = {
            "ou_2_5_under": 1.85,  # Prix baiss → sharp favor under
        }
        result2 = await veto.bidirectional_veto(model_pred, market_lines, threshold_pct=2.0)
        print(f"Test 2 (VETO triggered): {result2}")

    asyncio.run(test_veto())

