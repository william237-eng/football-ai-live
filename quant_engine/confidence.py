"""
Confidence Engine
Compute a discrete confidence level from several signals: data quality, model stability, variance, liquidity.
"""
from typing import Dict

class ConfidenceEngine:
    def __init__(self):
        pass

    def score(self, data_quality: float, model_stability: float, variance: float, liquidity: float) -> str:
        # inputs in [0,1], variance low is good
        # compound score
        variance_score = 1.0 - variance
        s = 0.4 * data_quality + 0.3 * model_stability + 0.2 * variance_score + 0.1 * liquidity
        if s > 0.9:
            return "Exceptionnelle"
        if s > 0.75:
            return "Très élevée"
        if s > 0.6:
            return "Elevée"
        if s > 0.4:
            return "Modérée"
        return "Faible"

