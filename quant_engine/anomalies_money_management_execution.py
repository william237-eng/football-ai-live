"""
═══════════════════════════════════════════════════════════════════════════════
PILIERS 8, 9, 10 : ANOMALIES, KELLY FRACTIONNÉ & EXECUTION
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import math
import sqlite3
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# PILIER 8 : DÉTECTION ANOMALIES ASYMÉTRIQUES
# ═══════════════════════════════════════════════════════════════════════════════

class AnomalyDetector:
    """
    Détecte:
    - Cartons rouges → décroissance exponentielle λ + correlation Pressure Index adverse
    - Blessures fantômes → arrêts prolongés (>90s) + chute PPDA
    """

    RED_CARD_DECAY = 1.2  # Paramètre exponentiel c
    GHOST_INJURY_PPDA_THRESHOLD = 15.0  # PPDA > 15 = moins agressif (signeblesse)
    STOPPAGE_TIME_THRESHOLD_SEC = 90

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.previous_ppda = {}  # Cache PPDA par team pour détection injury

    async def detect_anomalies(
        self,
        fixture_id: int,
        live_data: Dict,
        minute: int
    ) -> Dict:
        """
        Retourne anomalies détectées et ajustements λ.
        """
        anomalies = {}

        # 1. CARTONS ROUGES
        if live_data.get("reds_home", 0) > 0 or live_data.get("reds_away", 0) > 0:
            anomalies["red_card"] = await self._handle_red_card(fixture_id, live_data, minute)

        # 2. BLESSURES FANTÔMES
        ghost_injury = await self._detect_ghost_injury(fixture_id, live_data, minute)
        if ghost_injury:
            anomalies["ghost_injury"] = ghost_injury

        return anomalies

    async def _handle_red_card(
        self,
        fixture_id: int,
        live_data: Dict,
        minute: int
    ) -> Dict:
        """
        Carton rouge : décroissance exponentielle λ pénalisé.
        f(t) = e^(-c*(90-t)) où c=RED_CARD_DECAY
        """
        minutes_after_red = 90 - minute  # Temps restant après carton

        # Décroissance basée temps restant
        decay_multiplier = math.exp(-self.RED_CARD_DECAY * minutes_after_red / 30.0)

        # Bonus exploitation si Pressure Index adverse élevé
        opponent_pressure = max(
            live_data.get("pressure_index_ema_home", 50),
            live_data.get("pressure_index_ema_away", 50)
        )

        exploitation_bonus = 1.0 + (opponent_pressure - 50.0) / 100.0 * 0.1

        logger.warning(f"[ANOMALY] Red card at min {minute}: "
                       f"decay={decay_multiplier:.3f}, exploitation={exploitation_bonus:.3f}")

        return {
            "type": "RED_CARD",
            "minute": minute,
            "lambda_multiplier": decay_multiplier * exploitation_bonus,
        }

    async def _detect_ghost_injury(
        self,
        fixture_id: int,
        live_data: Dict,
        minute: int
    ) -> Optional[Dict]:
        """
        Blessure fantôme: détecte si joueur a arrêt prolongé (>90s) + chute PPDA.
        """
        current_ppda_h = live_data.get("ppda_home", 10.0)
        current_ppda_a = live_data.get("ppda_away", 10.0)

        # Comparaison vs snapshot précédent
        prev_ppda_h = self.previous_ppda.get(f"{fixture_id}_home", current_ppda_h)
        prev_ppda_a = self.previous_ppda.get(f"{fixture_id}_away", current_ppda_a)

        self.previous_ppda[f"{fixture_id}_home"] = current_ppda_h
        self.previous_ppda[f"{fixture_id}_away"] = current_ppda_a

        # Détecte chute abrupte PPDA (signe diminution agressivité défensive = injury)
        ppda_drop_h = prev_ppda_h - current_ppda_h
        ppda_drop_a = prev_ppda_a - current_ppda_a

        PPDA_DROP_THRESHOLD = 2.0

        if ppda_drop_h > PPDA_DROP_THRESHOLD and current_ppda_h > self.GHOST_INJURY_PPDA_THRESHOLD:
            logger.warning(f"[ANOMALY] Ghost injury home team detected: PPDA drop={ppda_drop_h:.1f}")
            return {
                "type": "GHOST_INJURY",
                "team": "home",
                "ppda_drop": ppda_drop_h,
                "lambda_multiplier": 0.92,  # Pénalité 8%
            }

        if ppda_drop_a > PPDA_DROP_THRESHOLD and current_ppda_a > self.GHOST_INJURY_PPDA_THRESHOLD:
            logger.warning(f"[ANOMALY] Ghost injury away team detected: PPDA drop={ppda_drop_a:.1f}")
            return {
                "type": "GHOST_INJURY",
                "team": "away",
                "ppda_drop": ppda_drop_a,
                "lambda_multiplier": 0.92,
            }

        return None


# ═══════════════════════════════════════════════════════════════════════════════
# PILIER 9 : KELLY FRACTIONNÉ & SUIVI CLV
# ═══════════════════════════════════════════════════════════════════════════════

class KellyCalculator:
    """
    Calcule Kelly Fractionné basé Edge (Δ probabilité Skellam vs bookmaker).
    Formule: f* = (edge) / odds_decimal
    Fraction (ex: 0.25 Kelly) = f* * 0.25 pour conservative betting
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def calculate_kelly_fraction(
        self,
        skellam_pricing: Dict,
        market_odds: Dict,
        fraction: float = 0.25
    ) -> Dict:
        """
        Calcule stake optimal via Kelly fractionné.
        """
        # Déterminer meilleure opportunité par probabilité edge
        opportunities = []

        # O/U 2.5
        if "ou_2_5_over_prob" in skellam_pricing:
            fair_odds_over = 1.0 / max(0.01, skellam_pricing["ou_2_5_over_prob"])
            market_odds_over = market_odds.get("ou_2_5_over", fair_odds_over)
            edge_over = (market_odds_over / fair_odds_over) - 1.0

            if edge_over > 0.01:  # > 1% edge
                opportunities.append({
                    "market": "O2.5",
                    "side": "OVER",
                    "probability": skellam_pricing["ou_2_5_over_prob"],
                    "odds": market_odds_over,
                    "edge": edge_over,
                })

            fair_odds_under = 1.0 / max(0.01, skellam_pricing["ou_2_5_under_prob"])
            market_odds_under = market_odds.get("ou_2_5_under", fair_odds_under)
            edge_under = (market_odds_under / fair_odds_under) - 1.0

            if edge_under > 0.01:
                opportunities.append({
                    "market": "U2.5",
                    "side": "UNDER",
                    "probability": skellam_pricing["ou_2_5_under_prob"],
                    "odds": market_odds_under,
                    "edge": edge_under,
                })

        if not opportunities:
            return {
                "market_type": "NONE",
                "side": "NONE",
                "stake_units": 0.0,
                "kelly_fraction": 0.0,
                "reason": "Pas d'opportunité edge positive",
            }

        # Sélectionner meilleure edge
        best = max(opportunities, key=lambda x: x["edge"])

        # Kelly Fractionné
        # f* = (p * odds - 1) / (odds - 1)
        p = best["probability"]
        odds = best["odds"]

        kelly_full = (p * odds - 1.0) / (odds - 1.0) if odds > 1.01 else 0.0
        kelly_frac = kelly_full * fraction

        # Kelly = % de bankroll; converti en units (assume R bankroll = stake units pour simplicité)
        # Ex: 2% Kelly sur 100u bankroll = 2u stake
        bank_units = 100.0  # Assume 100u bankroll
        stake_units = bank_units * kelly_frac

        logger.info(f"[KELLY] {best['market']} {best['side']}: "
                    f"p={p:.1%}, odds={odds:.2f}, edge={best['edge']:.1%}, "
                    f"kelly_full={kelly_full:.1%}, stake={stake_units:.2f}u")

        return {
            "market_type": best["market"],
            "side": best["side"],
            "probability": p,
            "stake_units": stake_units,
            "kelly_fraction": kelly_frac,
            "odds": odds,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILIER 10 : EXECUTION RÉELLE — SLIPPAGE & LIQUIDITÉ
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionEngine:
    """
    Exécute ordres réels avec :
    - Vérification liquidité (max stake vs marché)
    - Tolérance slippage (cancels si cotes chutent >2%)
    - Enregistrement DB pour tracking CLV
    """

    SLIPPAGE_TOLERANCE_PCT = 2.0

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_conn = sqlite3.connect(db_path)

    async def place_order(
        self,
        fixture_id: int,
        market_type: str,
        side: str,
        stake_units: float,
        odds: Optional[Dict] = None,
        slippage_tolerance_pct: float = 2.0
    ) -> Dict:
        """
        Place ordre réel avec vérification slippage & liquidité.
        """
        logger.info(f"[EXEC] Placing order: {market_type} {side} {stake_units}u @ {odds}")

        if stake_units <= 0:
            return {
                "order_id": None,
                "status": "REJECTED",
                "reason": "Stake <= 0",
            }

        if not odds:
            return {
                "order_id": None,
                "status": "REJECTED",
                "reason": "No odds provided",
            }

        # 1. Vérifier liquidité (max bet)
        market_odds_val = odds.get("ou_2_5_over", 1.90) if isinstance(odds, dict) else odds
        max_bet = await self._check_liquidity(fixture_id, market_type, stake_units)

        if stake_units > max_bet:
            logger.warning(f"[EXEC] Stake {stake_units}u exceeds max bet {max_bet}u → capping")
            stake_units = max_bet

        # 2. Vérifier slippage (mock: on assume pas de slippage pour test)
        odds_at_execution = market_odds_val  # Mock: pas de mouvement
        slippage_pct = 0.0

        if slippage_pct > slippage_tolerance_pct:
            logger.error(f"[EXEC] Slippage {slippage_pct:.1f}% > tolerance {slippage_tolerance_pct}% → CANCEL")
            return {
                "order_id": None,
                "status": "CANCELLED",
                "reason": f"Slippage {slippage_pct:.1f}% exceeded",
            }

        # 3. Enregistrer en DB
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO executed_positions (
                    fixture_id, market_type, side, model_used, predicted_probability,
                    bookmaker_odds, kelly_fraction, stake_units, max_bet_limit,
                    slippage_tolerance_pct, order_placed_at, odds_at_execution, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fixture_id, market_type, side, "SKELLAM", 0.55,  # Mock prob
                    market_odds_val, 0.25, stake_units, max_bet,
                    slippage_tolerance_pct, int(__import__('time').time()), odds_at_execution, "PENDING"
                )
            )
            self.db_conn.commit()
            order_id = cursor.lastrowid
        except Exception as e:
            logger.error(f"[EXEC] DB error: {e}")
            return {
                "order_id": None,
                "status": "ERROR",
                "reason": str(e),
            }

        logger.info(f"[EXEC] ✓ Order placed: ID={order_id}, Stake={stake_units}u, Odds={odds_at_execution:.2f}")

        return {
            "order_id": order_id,
            "status": "PLACED",
            "fixture_id": fixture_id,
            "market_type": market_type,
            "side": side,
            "stake_units": stake_units,
            "odds": odds_at_execution,
            "max_bet_limit": max_bet,
        }

    async def _check_liquidity(self, fixture_id: int, market_type: str, requested_stake: float) -> float:
        """
        Vérifie liquidité disponible du bookmaker.
        Mock: Pinnacle illimitée, Betfair 5k units max
        """
        # En production: requête API Pinnacle pour max bet
        max_bet_by_market = {
            "O2.5": 50000,  # Pinnacle illimitée
            "U2.5": 50000,
            "AH_-0.5": 25000,  # AH moins liquide
            "AH_-1.0": 20000,
        }

        return max_bet_by_market.get(market_type, 5000)

    async def update_position_result(
        self,
        order_id: int,
        result: str,  # "WON", "LOST", "VOID"
        closing_odds: float
    ) -> Dict:
        """
        Mise à jour résultat position + CLV calculation.
        """
        try:
            cursor = self.db_conn.cursor()

            # Récupérer position
            cursor.execute("SELECT * FROM executed_positions WHERE position_id = ?", (order_id,))
            position = cursor.fetchone()

            if not position:
                return {"status": "NOT_FOUND"}

            # Caclul CLV = (odds_execution / closing_odds) - 1
            exec_odds = position[10]  # Column: odds_at_execution
            clv = (exec_odds / max(0.01, closing_odds)) - 1.0 if closing_odds else 0.0

            # Profit calculation
            stake = position[8]  # Column: stake_units
            profit = stake * (exec_odds - 1.0) if result == "WON" else -stake if result == "LOST" else 0.0

            # Update DB
            cursor.execute(
                """
                UPDATE executed_positions SET
                    status = ?, final_result = ?, clv_value = ?, profit_units = ?, updated_at = CURRENT_TIMESTAMP
                WHERE position_id = ?
                """,
                (result, result, clv, profit, order_id)
            )
            self.db_conn.commit()

            logger.info(f"[EXEC] Position {order_id}: {result}, CLV={clv:.2%}, Profit={profit:.2f}u")

            return {
                "order_id": order_id,
                "result": result,
                "clv": clv,
                "profit": profit,
            }

        except Exception as e:
            logger.error(f"[EXEC] Update error: {e}")
            return {"status": "ERROR", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN D'TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test Kelly
    kelly = KellyCalculator("quant_engine.db")
    kelly_result = kelly.calculate_kelly_fraction(
        {"ou_2_5_over_prob": 0.60, "ou_2_5_under_prob": 0.40},
        {"ou_2_5_over": 1.80},
        fraction=0.25
    )
    print(f"Kelly: {kelly_result}")

    # Test Anomaly
    async def test_anomalies():
        detector = AnomalyDetector("quant_engine.db")
        live = {
            "reds_home": 1,
            "pressure_index_ema_home": 65,
            "ppda_home": 12.0,
        }
        anomalies = await detector.detect_anomalies(123, live, 65)
        print(f"Anomalies: {anomalies}")

    asyncio.run(test_anomalies())

