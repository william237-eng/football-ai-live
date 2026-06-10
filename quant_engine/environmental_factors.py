"""
═══════════════════════════════════════════════════════════════════════════════
PILIER 3 : FROTTEMENT ENVIRONNEMENTAL & MATRICE DE FATIGUE
Matrice de fatigue basée repos (ΔT) + distances | Climat & style de passes
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import sqlite3
from typing import Dict, Optional
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CALCULS FATIGUE & REPOS
# ═══════════════════════════════════════════════════════════════════════════════

class FatigueCalculator:
    """
    Calcule le coefficient de fatigue basé sur:
    - ΔT : Nombre de jours de repos depuis dernier match
    - Distance : Km parcourus en déplacement
    """

    @staticmethod
    def calculate_rest_penalty(days_rest: int, optimal_rest: int = 7) -> float:
        """
        Pénalité de repos : λ penalty basée sur ΔT
        - 7j repos (optimal) → 1.0 (pas pénalité)
        - 3j repos → ~0.85 pénalité
        - 2j repos (midweek) → ~0.70
        Formula: exp(-c * max(0, optimal_rest - days_rest) / optimal_rest)
        """
        if days_rest >= optimal_rest:
            return 1.0

        c = 0.5  # Constante de pénalité (empirical)
        penalty = math.exp(-c * (optimal_rest - days_rest) / optimal_rest)
        return penalty

    @staticmethod
    def calculate_distance_penalty(distance_km: float, threshold_km: float = 1000.0) -> float:
        """
        Pénalité de distance : voyage long fatigue les équipes
        - 0-500 km : ~1.0-0.95
        - 500-1000 km : ~0.95-0.85
        - 1000+ km : 0.80+
        Formula: 1 - (distance / (2 * threshold))
        """
        if distance_km == 0:
            return 1.0

        penalty = 1.0 - (distance_km / (2.0 * threshold_km))
        return max(0.7, min(1.0, penalty))  # Clamp [0.7, 1.0]

    @staticmethod
    def combine_fatigue_factors(rest_penalty: float, distance_penalty: float) -> float:
        """
        Combine les pénalités de repos et distance
        Formula: sqrt(rest_penalty * distance_penalty)  [moyenne géométrique]
        """
        return math.sqrt(rest_penalty * distance_penalty)


# ═══════════════════════════════════════════════════════════════════════════════
# CLIMAT & CORRÉLATION MÉTÉO ⟷ STYLE DE PASSES
# ═══════════════════════════════════════════════════════════════════════════════

class WeatherCorrelationCalculator:
    """
    Calcule corrélation mathématique entre météo et style tactique
    - Pluie → ↓ passes courtes, ↑ passes longues, ↑ pertes
    - Vent → ↑ imprécision long terme
    - Froid → ↓ possession sophistiquée, ↑ physicalité
    """

    # Données météo du match
    PRECIPITATION_THRESHOLD_MM = 2.0  # mm/h => impact tactique
    WIND_SPEED_THRESHOLD_KMH = 20.0  # km/h => imprécision

    @staticmethod
    def calculate_precipitation_impact(precipitation_mm: float) -> Dict[str, float]:
        """
        Impact pluie sur formule Poisson.
        Pluie réduit l'efficacité des attaques sophistiquées (passing build-up).
        """
        if precipitation_mm < WeatherCorrelationCalculator.PRECIPITATION_THRESHOLD_MM:
            return {
                "lambda_reduction": 1.0,  # Pas d'impact
                "pass_accuracy_impact": 1.0,
            }

        # Pour chaque mm au-delà du seuil, réduire λ de 1.5%
        impact_pct = min(0.15, (precipitation_mm - WeatherCorrelationCalculator.PRECIPITATION_THRESHOLD_MM) * 0.015)
        return {
            "lambda_reduction": 1.0 - impact_pct,
            "pass_accuracy_impact": 1.0 - (impact_pct * 0.5),  # Moitié moins d'impact sur précision
        }

    @staticmethod
    def calculate_wind_impact(wind_speed_kmh: float) -> float:
        """
        Impact vent: réduit efficacité des shots long terme (long range shots)
        """
        if wind_speed_kmh < WeatherCorrelationCalculator.WIND_SPEED_THRESHOLD_KMH:
            return 1.0

        # Chaque km/h au-delà du seuil = -0.5% d'efficacité
        impact_pct = min(0.10, (wind_speed_kmh - WeatherCorrelationCalculator.WIND_SPEED_THRESHOLD_KMH) * 0.005)
        return 1.0 - impact_pct


# ═══════════════════════════════════════════════════════════════════════════════
# SEUIL DISCIPLINAIRE & ARBITRE
# ═══════════════════════════════════════════════════════════════════════════════

class RefereeProfileCalculator:
    """
    Modalise le seuil disciplinaire de l'arbitre en croisant:
    - Taux de tacles de l'équipe (agressivité défensive)
    - Ratio de cartons de l'arbitre (strictness)
    - Historique H2H cartons
    """

    @staticmethod
    def calculate_referee_strictness(
        referee_id: int,
        referee_cards_history: Dict[str, int],  # {"yellows": 45, "reds": 2, "matches": 50}
        team_tackles_per_match: float,
        team_fouls_per_match: float
    ) -> float:
        """
        Calcule un coefficient de "rigueur arbitrale" (0.6 - 1.4)
        Affecte la probabilité de cartons.

        Formule:
          strictness = (cartons_ref_per_match / 1.5) * (1 + 0.2 * team_agressivité)
        """
        if referee_cards_history.get("matches", 0) == 0:
            referee_cards_per_match = 1.5  # Default
        else:
            referee_cards_per_match = (
                (referee_cards_history.get("yellows", 0) + referee_cards_history.get("reds", 0) * 2) /
                referee_cards_history.get("matches", 1)
            )

        # Agressivité équipe
        team_aggression_ratio = (team_tackles_per_match / (team_fouls_per_match + 1e-6)) - 1.0
        team_aggression_normalized = min(0.3, max(-0.2, team_aggression_ratio * 0.1))

        strictness = (referee_cards_per_match / 1.5) * (1.0 + team_aggression_normalized)
        return min(1.4, max(0.6, strictness))


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATEUR FACTEURS ENVIRONNEMENTAUX
# ═══════════════════════════════════════════════════════════════════════════════

class EnvironmentalFactorsCalculator:
    """
    Maître orchestrateur des facteurs environnementaux.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def calculate_environmental_impact(self, fixture_data: Dict) -> Dict:
        """
        Calcule l'impact complet des facteurs environnementaux sur λ (lambda).
        """
        logger.info(f"[ENV] Calcul facteurs environnementaux pour fixture {fixture_data.get('fixture_id')}")

        # 1. FATIGUE
        days_rest_home = fixture_data.get("days_rest_home", 7)
        days_rest_away = fixture_data.get("days_rest_away", 7)
        distance_home = fixture_data.get("distance_km_home", 0.0)
        distance_away = fixture_data.get("distance_km_away", 0.0)

        rest_penalty_home = FatigueCalculator.calculate_rest_penalty(days_rest_home)
        rest_penalty_away = FatigueCalculator.calculate_rest_penalty(days_rest_away)

        dist_penalty_home = FatigueCalculator.calculate_distance_penalty(distance_home)
        dist_penalty_away = FatigueCalculator.calculate_distance_penalty(distance_away)

        fatigue_coeff_home = FatigueCalculator.combine_fatigue_factors(rest_penalty_home, dist_penalty_home)
        fatigue_coeff_away = FatigueCalculator.combine_fatigue_factors(rest_penalty_away, dist_penalty_away)

        logger.info(f"[ENV] Fatigue: Home={fatigue_coeff_home:.3f}, Away={fatigue_coeff_away:.3f}")

        # 2. MÉTÉO
        precipitation = fixture_data.get("precipitation_mm", 0.0)
        wind_speed = fixture_data.get("wind_speed_kmh", 0.0)

        weather_impact = WeatherCorrelationCalculator.calculate_precipitation_impact(precipitation)
        wind_impact = WeatherCorrelationCalculator.calculate_wind_impact(wind_speed)

        combined_weather = weather_impact["lambda_reduction"] * wind_impact
        logger.info(f"[ENV] Météo impact λ: {combined_weather:.3f}")

        # 3. ARBITRE
        referee_id = fixture_data.get("referee_id")
        referee_cards = await self._fetch_referee_history(referee_id) if referee_id else {}
        home_tackles = fixture_data.get("home_team_tackles_per_match", 15.0)
        home_fouls = fixture_data.get("home_team_fouls_per_match", 12.0)

        ref_strictness = RefereeProfileCalculator.calculate_referee_strictness(
            referee_id,
            referee_cards,
            home_tackles,
            home_fouls
        )
        logger.info(f"[ENV] Rigueur arbitrale: {ref_strictness:.3f}")

        return {
            "fatigue_coeff_home": fatigue_coeff_home,
            "fatigue_coeff_away": fatigue_coeff_away,
            "weather_lambda_impact": combined_weather,
            "referee_strictness": ref_strictness,
            "days_rest_home": days_rest_home,
            "days_rest_away": days_rest_away,
            "distance_home": distance_home,
            "distance_away": distance_away,
        }

    async def _fetch_referee_history(self, referee_id: int) -> Dict:
        """Récupère historique cartons de l'arbitre (mock)"""
        # En production: requête API ou cache DB
        return {
            "yellows": 45,
            "reds": 2,
            "matches": 50,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN D'TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test fatigue
    rest_pen = FatigueCalculator.calculate_rest_penalty(days_rest=3)
    dist_pen = FatigueCalculator.calculate_distance_penalty(distance_km=2000)
    combined = FatigueCalculator.combine_fatigue_factors(rest_pen, dist_pen)
    print(f"Fatigue: Rest={rest_pen:.3f}, Distance={dist_pen:.3f}, Combined={combined:.3f}")

    # Test météo
    weather = WeatherCorrelationCalculator.calculate_precipitation_impact(5.0)
    print(f"Weather impact (5mm rain): {weather}")

    # Test arbitre
    strictness = RefereeProfileCalculator.calculate_referee_strictness(
        referee_id=1,
        referee_cards_history={"yellows": 45, "reds": 2, "matches": 50},
        team_tackles_per_match=15.0,
        team_fouls_per_match=12.0,
    )
    print(f"Referee strictness: {strictness:.3f}")

