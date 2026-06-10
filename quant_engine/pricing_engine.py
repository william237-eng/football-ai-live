"""
═══════════════════════════════════════════════════════════════════════════════
PILIER 7 : TARIFICATION VIA DISTRIBUTION SKELLAM & ASIAN HANDICAP
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import math
from typing import Dict, Optional
from scipy.special import iv  # Bessel function for Skellam

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# DISTRIBUTION SKELLAM (Différence de deux Poissons)
# ═══════════════════════════════════════════════════════════════════════════════

class SkellamDistribution:
    """
    Distribution Skellam = Différence de deux variables Poisson indépendantes.
    P(X - Y = k) où X ~ Poisson(μ1), Y ~ Poisson(μ2)

    Idéale pour modéliser écarts de buts restants lors matchs en cours.
    Formula:
      P(k) = e^(-(μ1+μ2)) * (μ1/μ2)^(k/2) * I_k(2*sqrt(μ1*μ2))
      où I_k = Bessel function
    """

    @staticmethod
    def skellam_pmf(k: int, mu1: float, mu2: float) -> float:
        """
        Calcule P(X - Y = k) pour Skellam(μ1, μ2).
        μ1 = buts home restants (λ_h * temps_restant/90)
        μ2 = buts away restants
        """
        if mu1 <= 0 or mu2 <= 0:
            return 0.0

        # Évite underflow pour grandes valeurs
        log_factor = -(mu1 + mu2) + (k / 2.0) * math.log(mu1 / mu2)

        # Bessel function I_|k|
        bessel = iv(abs(k), 2.0 * math.sqrt(mu1 * mu2))

        pmf = math.exp(log_factor) * bessel
        return max(0.0, min(1.0, pmf))  # Clamp for stability

    @staticmethod
    def skellam_cdf(k: int, mu1: float, mu2: float) -> float:
        """
        Calcule P(X - Y <= k) cumulée.
        """
        cdf = 0.0
        for i in range(-50, k + 1):  # Intégrer sur plage raisonnable
            cdf += SkellamDistribution.skellam_pmf(i, mu1, mu2)
        return cdf

    @staticmethod
    def asian_handicap_probabilities(
        lambda_home: float,
        lambda_away: float,
        minutes_remaining: int = 90,
        handicap_line: float = -0.5  # ex: -0.5 (Home doit gagner 1+ but net)
    ) -> Dict[str, float]:
        """
        Calcule P(Home +handicap), P(Tie), P(Away +reverse_handicap)
        via Skellam.

        handicap=−0.5: Home doit gagner de 1+ but (winning margin ≥ 1)
        handicap=−1.0: Home doit gagner de 2+ buts
        handicap=+0.5: Home "spotted" 0.5 goal → peut perdre de <1 but
        """
        # Lambdas restants
        time_factor = minutes_remaining / 90.0
        mu_h = lambda_home * time_factor
        mu_a = lambda_away * time_factor

        # Conversion handicap en écart de buts requis
        required_margin = abs(handicap_line)

        # Skellam: μ1 = Home, μ2 = Away
        # Nous besoin P(Home_goals - Away_goals >= required_margin) if handicap < 0
        # C'est P(Skellam >= ceil(required_margin))

        threshold = math.ceil(required_margin) if handicap_line < 0 else -math.ceil(required_margin)

        p_home_covers = 0.0
        p_draw = 0.0
        p_away_covers = 0.0

        # Intégrationprincipale
        for goals_diff in range(-100, 100):
            pmf = SkellamDistribution.skellam_pmf(goals_diff, mu_h, mu_a)

            if handicap_line < 0:  # Home -handicap (doit gagner)
                if goals_diff >= threshold:
                    p_home_covers += pmf
                elif abs(goals_diff - threshold) < 0.1:  # Close to boundary
                    p_draw += pmf
                else:
                    p_away_covers += pmf
            else:  # Away +handicap (peut perdre un peu)
                if goals_diff <= threshold:
                    p_away_covers += pmf
                elif abs(goals_diff - threshold) < 0.1:
                    p_draw += pmf
                else:
                    p_home_covers += pmf

        # Normaliser
        total = p_home_covers + p_draw + p_away_covers
        if total > 0:
            p_home_covers /= total
            p_draw /= total
            p_away_covers /= total

        return {
            "p_home_covers": p_home_covers,
            "p_draw": p_draw,
            "p_away_covers": p_away_covers,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERTISSEUR PROBABILITÉS → COTES ÉQUITABLES
# ═══════════════════════════════════════════════════════════════════════════════

class OddsConverter:
    """
    Convertit probabilités en cotes décimales équitables.
    Cote = 1 / (probabilité + marge_house)
    """

    @staticmethod
    def implied_odds_from_probability(probability: float, margin_pct: float = 2.5) -> float:
        """
        Cote décimale implicite d'une probabilité.
        margin_pct = "surround" bookmaker (ex: 2.5% pour Pinnacle)
        """
        # Ajuster pour marge
        prob_bookmaker = probability * (1.0 - margin_pct / 100.0)
        odds = 1.0 / max(0.01, prob_bookmaker)
        return odds

    @staticmethod
    def fair_value(probability: float) -> float:
        """Cote équitable (0% margin)"""
        return 1.0 / max(0.01, probability)

    @staticmethod
    def calculate_clv_metric(actual_odds: float, fair_odds: float) -> float:
        """
        Closing Line Value (CLV) = indicateur si on a battu la clôture.
        CLV = (actual_odds / fair_odds) - 1
        CLV > 0 = positif (on a eu meilleures cotes que probabilité réelle)
        """
        return (actual_odds / max(0.01, fair_odds)) - 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# MOTEUR DE PRICING COMPLET
# ═══════════════════════════════════════════════════════════════════════════════

class PricingEngine:
    """
    Orchestrateur : Skellam → Cotes équitables → Value Detection
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.skellam = SkellamDistribution()
        self.converter = OddsConverter()

    async def skellam_pricing(
        self,
        bayes_lambda: Dict,
        live_data: Dict,
        minutes_remaining: int = 45
    ) -> Dict:
        """
        Calcule pricing complet via Skellam pour :
        - Over/Under 2.5
        - Asian Handicap (-0.5, -1.0, +0.5, +1.0)
        - 1X2 (via récurrence Poisson)
        """
        logger.info("[PRICING] Skellam-based pricing")

        lambda_h = bayes_lambda["lambda_home"]
        lambda_a = bayes_lambda["lambda_away"]

        # OVER/UNDER 2.5
        # Distribution totale buts restants = Skellam-based cumul
        mu_total = (lambda_h + lambda_a) * (minutes_remaining / 90.0)
        current_total = live_data.get("home_score", 0) + live_data.get("away_score", 0)

        # P(total_final > 2.5) = P(remaining > (2.5 - current))
        needed_goals = max(0, 2.5 - current_total)
        p_over_2_5 = 1.0 - self.skellam.skellam_cdf(int(needed_goals) - 1, lambda_h, lambda_a)

        over_2_5_odds = self.converter.implied_odds_from_probability(p_over_2_5)
        under_2_5_odds = self.converter.implied_odds_from_probability(1.0 - p_over_2_5)

        # ASIAN HANDICAP (-0.5)
        ah_05_probs = self.skellam.asian_handicap_probabilities(
            lambda_h, lambda_a, minutes_remaining, handicap_line=-0.5
        )
        ah_05_home_odds = self.converter.implied_odds_from_probability(ah_05_probs["p_home_covers"])
        ah_05_away_odds = self.converter.implied_odds_from_probability(ah_05_probs["p_away_covers"])

        # ASIAN HANDICAP (-1.0)
        ah_10_probs = self.skellam.asian_handicap_probabilities(
            lambda_h, lambda_a, minutes_remaining, handicap_line=-1.0
        )
        ah_10_home_odds = self.converter.implied_odds_from_probability(ah_10_probs["p_home_covers"])
        ah_10_away_odds = self.converter.implied_odds_from_probability(ah_10_probs["p_away_covers"])

        results = {
            "ou_2_5_over_prob": p_over_2_5,
            "ou_2_5_under_prob": 1.0 - p_over_2_5,
            "ou_2_5_over_odds": over_2_5_odds,
            "ou_2_5_under_odds": under_2_5_odds,

            "ah_05_home_prob": ah_05_probs["p_home_covers"],
            "ah_05_home_odds": ah_05_home_odds,
            "ah_05_away_odds": ah_05_away_odds,

            "ah_10_home_prob": ah_10_probs["p_home_covers"],
            "ah_10_home_odds": ah_10_home_odds,
            "ah_10_away_odds": ah_10_away_odds,
        }

        logger.info(f"[PRICING] O2.5={p_over_2_5:.1%} (odds={over_2_5_odds:.2f}), "
                    f"AH-0.5 Home={ah_05_probs['p_home_covers']:.1%}")

        return results

    async def detect_value_opportunities(
        self,
        skellam_pricing: Dict,
        market_odds: Dict,
        min_edge_pct: float = 2.0  # Minimum 2% edge for trade
    ) -> List[Dict]:
        """
        Détecte opportunities de VALUE en comparant fair odds vs marché.
        """
        opportunities = []

        # O/U 2.5
        fair_over = self.converter.fair_value(skellam_pricing["ou_2_5_over_prob"])
        market_over = market_odds.get("ou_2_5_over", 1.50)
        if market_over > fair_over * (1.0 + min_edge_pct / 100.0):
            edge = ((market_over / fair_over) - 1.0) * 100
            opportunities.append({
                "market": "O2.5",
                "side": "OVER",
                "fair_odds": fair_over,
                "market_odds": market_over,
                "edge_pct": edge,
            })

        fair_under = self.converter.fair_value(skellam_pricing["ou_2_5_under_prob"])
        market_under = market_odds.get("ou_2_5_under", 1.50)
        if market_under > fair_under * (1.0 + min_edge_pct / 100.0):
            edge = ((market_under / fair_under) - 1.0) * 100
            opportunities.append({
                "market": "U2.5",
                "side": "UNDER",
                "fair_odds": fair_under,
                "market_odds": market_under,
                "edge_pct": edge,
            })

        # AH -0.5
        fair_ah_05_home = self.converter.fair_value(skellam_pricing["ah_05_home_prob"])
        market_ah_05_home = market_odds.get("ah_05_home_odds", 1.90)
        if market_ah_05_home > fair_ah_05_home * (1.0 + min_edge_pct / 100.0):
            edge = ((market_ah_05_home / fair_ah_05_home) - 1.0) * 100
            opportunities.append({
                "market": "AH_-0.5",
                "side": "HOME",
                "fair_odds": fair_ah_05_home,
                "market_odds": market_ah_05_home,
                "edge_pct": edge,
            })

        if opportunities:
            logger.info(f"[PRICING] {len(opportunities)} value opportunity(ies) detected")
            for opp in opportunities:
                logger.info(f"  {opp['market']} {opp['side']}: {opp['edge_pct']:.1f}% edge")

        return opportunities


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN D'TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test Skellam PMF
    pmf_0 = SkellamDistribution.skellam_pmf(0, 1.5, 1.2)
    pmf_1 = SkellamDistribution.skellam_pmf(1, 1.5, 1.2)
    print(f"Skellam P(diff=0)={pmf_0:.4f}, P(diff=1)={pmf_1:.4f}")

    # Test Asian Handicap
    ah_probs = SkellamDistribution.asian_handicap_probabilities(1.6, 1.4, 45, handicap_line=-0.5)
    print(f"AH -0.5: Home={ah_probs['p_home_covers']:.1%}, Draw={ah_probs['p_draw']:.1%}, Away={ah_probs['p_away_covers']:.1%}")

    # Test Odds Converter
    prob = 0.55
    fair = OddsConverter.fair_value(prob)
    implied = OddsConverter.implied_odds_from_probability(prob, margin_pct=2.5)
    print(f"Probability {prob:.0%}: Fair odds={fair:.2f}, Implied (2.5% margin)={implied:.2f}")

