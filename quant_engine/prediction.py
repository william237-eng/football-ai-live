"""
Prediction Engine
Computes model probabilities, implied probabilities, expected value and signals for positive EV.
"""
from typing import Dict, Any

class PredictionEngine:
    def __init__(self, modeling, risk_engine=None):
        self.modeling = modeling
        self.risk = risk_engine

    def implied_prob(self, odds: float) -> float:
        if odds <= 1.0:
            return 1.0
        return 1.0 / odds

    def expected_value(self, model_prob: float, odds: float) -> float:
        imp = self.implied_prob(odds)
        ev = model_prob - imp
        return ev

    def recommend(self, model_probs: Dict[str, float], market_odds: Dict[str, float], min_edge: float = 0.03):
        # model_probs: {'home': p, 'draw': p, 'away': p}
        if not model_probs or not isinstance(model_probs, dict):
            return {"error": "Analyse impossible: probabilités du modèle manquantes"}
        if "error" in model_probs:
            return {"error": f"Analyse impossible: {model_probs['error']}"}
        signals = []
        for market in ["home", "draw", "away"]:
            p = model_probs.get(market, None)
            odds = market_odds.get(market, None)
            if p is None or odds is None:
                continue
            ev = self.expected_value(p, odds)
            if ev > min_edge:
                stake = self.risk.stake(p, odds) if self.risk else 0.0
                signals.append({"market": market, "model_prob": p, "odds": odds, "ev": ev, "stake": stake})
        if not signals:
            return {"message": "Aucune opportunité EV positive détectée"}
        return {"signals": signals}

