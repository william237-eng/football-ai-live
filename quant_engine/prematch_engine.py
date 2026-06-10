"""
═══════════════════════════════════════════════════════════════════════════════
PILIER 5 : MOTEUR PRÉ-MATCH — ELO XG, DIXON-COLES & TOPOLOGIE TACTIQUE
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import math
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTÈME ELO DYNAMIQUE (Basé exclusivement sur xG)
# ═══════════════════════════════════════════════════════════════════════════════

class EloRatingSystem:
    """
    Système Elo Dynamique alimenté exclusivement par xG (Expected Goals).
    Règles de mise à jour:
    - Win: +32 * (xG_scored / (xG_scored + xG_conceded))
    - Loss: -32 * (xG_conceded / (xG_scored + xG_conceded))
    """

    K_FACTOR = 32  # Constant Elo adjustment

    @staticmethod
    def update_elo(
        current_elo: float,
        opponent_elo: float,
        xg_scored: float,
        xg_conceded: float
    ) -> float:
        """
        Met à jour Elo basé performance xG réelle (pas le score).
        Reward si xG_scored > xG_conceded, pénalité sinon.
        """
        if xg_scored + xg_conceded == 0:
            return current_elo  # Pas de match → pas d'update

        # Proportion du xG produit vs concédé
        performance_ratio = xg_scored / (xg_scored + xg_conceded)

        # Expected Elo outcome
        expected = 1.0 / (1.0 + math.pow(10, (opponent_elo - current_elo) / 400.0))

        # Actual performance (1.0 = perfect, 0.5 = neutral, 0.0 = poor)
        actual = performance_ratio

        # Update
        delta_elo = EloRatingSystem.K_FACTOR * (actual - expected)
        return current_elo + delta_elo

    @staticmethod
    def elo_to_lambda(elo: float, base_lambda: float = 1.5) -> float:
        """
        Convertit Elo rating en Expected Goals lambda (Poisson).
        Formula: λ = base_λ * (1 + (ELO - 1500) / 1500)
        """
        elo_normalized = (elo - 1500.0) / 1500.0
        lambda_val = base_lambda * (1.0 + 0.3 * elo_normalized)  # 30% variance max
        return max(0.5, min(3.5, lambda_val))  # Clamp [0.5, 3.5]


# ═══════════════════════════════════════════════════════════════════════════════
# MODÈLE DIXON-COLES BIVARIÉ
# ═══════════════════════════════════════════════════════════════════════════════

class DixonColesModel:
    """
    Modèle bivarié Dixon-Coles pour prédiction scores footballistiques.
    Noyau:
      - λ_home, λ_away: Expected Goals Poisson
      - ρ (rho): Paramètre interdépendance (correlation) pour (0,0) et (1,1)

    P(X=i, Y=j) = τ(i,j) * Poisson(i|λ_h) * Poisson(j|λ_a)
    où τ gère la dépendance.
    """

    # Rho par défaut (ajudgé empiriquement à 0.065 pour football)
    DEFAULT_RHO = 0.065

    @staticmethod
    def poisson_pmf(k: int, lam: float) -> float:
        """Calcul probabilité Poisson P(X=k)"""
        return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

    @staticmethod
    def dixon_coles_dep_factor(i: int, j: int, lambda_h: float, lambda_a: float, rho: float = DEFAULT_RHO) -> float:
        """
        Facteur de dépendance Dixon-Coles τ(i,j,rho).
        Affecte les corrélations (0,0), (1,1), (1,0), (0,1).
        """
        if i == 0 and j == 0:
            return 1.0 - rho * lambda_h * lambda_a
        elif i == 1 and j == 1:
            return 1.0 + rho
        elif i == 1 and j == 0:
            return 1.0 - rho * lambda_a
        elif i == 0 and j == 1:
            return 1.0 - rho * lambda_h
        else:
            return 1.0  # Pas d'amortissement pour (i,j) > (1,1)

    @staticmethod
    def match_probability(
        lambda_h: float,
        lambda_a: float,
        max_goals: int = 8,
        rho: float = DEFAULT_RHO
    ) -> Tuple[float, float, float]:
        """
        Calcule probabilités (Home Win, Draw, Away Win) via Dixon-Coles.
        Génère matrice 8x8 de résultats possibles.
        """
        p_home = 0.0
        p_draw = 0.0
        p_away = 0.0

        for i in range(max_goals):
            for j in range(max_goals):
                tau = DixonColesModel.dixon_coles_dep_factor(i, j, lambda_h, lambda_a, rho)
                p_ij = tau * DixonColesModel.poisson_pmf(i, lambda_h) * DixonColesModel.poisson_pmf(j, lambda_a)

                if i > j:
                    p_home += p_ij
                elif i == j:
                    p_draw += p_ij
                else:
                    p_away += p_ij

        # Normaliser si nécessaire
        total = p_home + p_draw + p_away
        if total > 0:
            p_home /= total
            p_draw /= total
            p_away /= total

        return (p_home, p_draw, p_away)

    @staticmethod
    def estimate_rho_from_data(historical_matches: list) -> float:
        """
        Estime ρ empiriquement partir de données historiques.
        ρ = Cov(Score_home > Score_away, Score_away > Score_home)
        """
        # Mock: en production, optimiser via MLE sur matches historiques
        return 0.065  # Valeur standard football


# ═══════════════════════════════════════════════════════════════════════════════
# TOPOLOGIE TACTIQUE — Valnérabilité Spatiale
# ═══════════════════════════════════════════════════════════════════════════════

class TacticalTopologyAnalyzer:
    """
    Modélise l'impact de formations tactiques sur l'espérance de buts.
    Exemples:
    - Équipe avec bloc défensif haut exposée à équipe avec taux atq rapides → ↑ λ
    - Équipe possession contrôlée vs défense réactive → ↓ λ_opponent
    """

    # Multiplicateurs selon formation (empirical)
    FORMATION_MULTIPLIERS = {
        "4-3-3": {"attacking": 1.05, "defensive": 0.95},
        "4-2-3-1": {"attacking": 0.98, "defensive": 1.02},
        "3-5-2": {"attacking": 1.12, "defensive": 1.08},
        "5-3-2": {"attacking": 0.85, "defensive": 1.15},
    }

    @staticmethod
    def calculate_tactical_vulnerability(
        team_formation: Optional[str],
        opponent_attacking_style: str,  # "rapid", "possession", "balanced"
        team_defensive_ppda: float  # Passes per defensive action (lower = more aggressive)
    ) -> float:
        """
        Calcule multiplicateur de vulnérabilité tactique sur λ aggresseur.
        """
        if not team_formation or team_formation not in TacticalTopologyAnalyzer.FORMATION_MULTIPLIERS:
            base_mult = 1.0
        else:
            base_mult = TacticalTopologyAnalyzer.FORMATION_MULTIPLIERS[team_formation].get("defensive", 1.0)

        # Ajustement sur style offensif adverse
        style_mult = {
            "rapid": 1.10,  # Formation défensive → exposée aux attaques rapides
            "possession": 0.95,  # Possession lent → moins dangereux
            "balanced": 1.0,
        }.get(opponent_attacking_style, 1.0)

        # Ajustement sur PPDA (defensive pressure)
        ppda_mult = 1.0 + max(0, (12.0 - team_defensive_ppda) / 12.0) * 0.15  # Si agressif (PPDA bas) → vulnérable

        return base_mult * style_mult * ppda_mult

    @staticmethod
    def calculate_motivation_urgency(
        points_difference: int,  # Différence points avant match
        games_remaining: int,  # Matchs restants saison
        league_position: int  # Classement actuel
    ) -> float:
        """
        Calcule Matrice de Motivation basée urgence mathématique.
        Équipes en position critique (relégation/Champion) jouent + agressif → ↑ λ variance.
        Formula: 1 + 0.2 * urgency_score
        """
        urgency_score = 0.0

        # Situation relégation (bas du classement, matchs finis)
        if league_position > 18 and games_remaining < 5:
            urgency_score += 0.3

        # Lutte pour titre/top-4
        if points_difference <= 3 and games_remaining <= 10:
            urgency_score += 0.2

        # Perte confiance (5+ matches sans victoire)
        if points_difference < -5:
            urgency_score -= 0.15

        compression_mult = 1.0 + min(0.3, urgency_score * 0.1)  # Max +30% variance
        return compression_mult


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATEUR PRÉ-MATCH
# ═══════════════════════════════════════════════════════════════════════════════

class PreMatchEngine:
    """
    Pipeline pré-match complet : ELO → Dixon-Coles → Topologie taxt → Motivation
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.elo = EloRatingSystem()
        self.dixon_coles = DixonColesModel()
        self.tactics = TacticalTopologyAnalyzer()

    async def calculate_elo_ratings(self, fixture_data: Dict) -> Dict:
        """Calcule Elo courant pour les deux équipes"""
        logger.info("[PREMATCH] Calcul Elo Dynamique")

        # Mock: en production, récupérer depuis DB derniers matches
        home_elo = fixture_data.get("elo_home", 1500.0)
        away_elo = fixture_data.get("elo_away", 1500.0)

        return {
            "elo_home": home_elo,
            "elo_away": away_elo,
            "lambda_home_elo": EloRatingSystem.elo_to_lambda(home_elo),
            "lambda_away_elo": EloRatingSystem.elo_to_lambda(away_elo),
        }

    async def dixon_coles_with_tactics(
        self,
        elo_result: Dict,
        env_data: Dict,
        fixture_data: Dict
    ) -> Dict:
        """
        Applique Dixon-Coles avec ajustements tactiques et motivation.
        """
        logger.info("[PREMATCH] Dixon-Coles + Tactique + Motivation")

        # Lambdas de base (Elo + Fatigue)
        lambda_h = elo_result["lambda_home_elo"] * env_data.get("fatigue_coeff_home", 1.0)
        lambda_a = elo_result["lambda_away_elo"] * env_data.get("fatigue_coeff_away", 1.0)

        # Topologie tactique
        vuln_h = self.tactics.calculate_tactical_vulnerability(
            fixture_data.get("home_formation"),
            fixture_data.get("away_attacking_style", "balanced"),
            fixture_data.get("home_ppda", 10.0)
        )
        vuln_a = self.tactics.calculate_tactical_vulnerability(
            fixture_data.get("away_formation"),
            fixture_data.get("home_attacking_style", "balanced"),
            fixture_data.get("away_ppda", 10.0)
        )

        lambda_h *= vuln_a  # Away vulnerability affecte Home λ
        lambda_a *= vuln_h  # Home vulnerability affecte Away λ

        # Motivation urgency
        urgency_h = self.tactics.calculate_motivation_urgency(
            fixture_data.get("home_points_diff", 0),
            fixture_data.get("home_games_remaining", 20),
            fixture_data.get("home_league_position", 10)
        )
        urgency_a = self.tactics.calculate_motivation_urgency(
            fixture_data.get("away_points_diff", 0),
            fixture_data.get("away_games_remaining", 20),
            fixture_data.get("away_league_position", 10)
        )

        lambda_h *= urgency_h
        lambda_a *= urgency_a

        # Météo
        lambda_h *= env_data.get("weather_lambda_impact", 1.0)
        lambda_a *= env_data.get("weather_lambda_impact", 1.0)

        logger.info(f"[PREMATCH] Final lambdas: Home={lambda_h:.3f}, Away={lambda_a:.3f}")

        # Dixon-Coles probabilities
        p_home, p_draw, p_away = self.dixon_coles.match_probability(lambda_h, lambda_a)

        return {
            "lambda_home": lambda_h,
            "lambda_away": lambda_a,
            "p_home_win": p_home,
            "p_draw": p_draw,
            "p_away_win": p_away,
            "tactical_vuln_home": vuln_h,
            "tactical_vuln_away": vuln_a,
            "urgency_home": urgency_h,
            "urgency_away": urgency_a,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN D'TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test Elorating
    elo_new = EloRatingSystem.update_elo(1500, 1400, 2.5, 1.0)
    lambda_from_elo = EloRatingSystem.elo_to_lambda(elo_new)
    print(f"Elo update: 1500 → {elo_new:.1f}, λ={lambda_from_elo:.3f}")

    # Test Dixon-Coles
    p_h, p_d, p_a = DixonColesModel.match_probability(1.8, 1.4)
    print(f"Dixon-Coles probabilities: Home={p_h:.1%}, Draw={p_d:.1%}, Away={p_a:.1%}")

    # Test Tactical
    vuln = TacticalTopologyAnalyzer.calculate_tactical_vulnerability("4-3-3", "rapid", 8.5)
    motivation = TacticalTopologyAnalyzer.calculate_motivation_urgency(2, 5, 20)
    print(f"Tactical vuln={vuln:.3f}, Motivation={motivation:.3f}")

