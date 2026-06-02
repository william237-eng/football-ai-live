"""
Validation Engine
Stores predictions and outcomes and computes metrics: Brier score, calibration, ROI.
For demo, uses an in-memory store and simple computations.
"""
from typing import List, Dict, Any
import math

class ValidationEngine:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def record(self, match_id: int, prediction: Dict[str, float], odds: Dict[str, float], stake: float, outcome: str):
        self.history.append({
            "match_id": match_id,
            "prediction": prediction,
            "odds": odds,
            "stake": stake,
            "outcome": outcome,
        })

    def brier_score(self):
        if not self.history:
            return None
        total = 0.0
        for rec in self.history:
            pred = rec["prediction"]
            outcome = rec["outcome"]
            # one-hot
            for k, p in pred.items():
                y = 1.0 if k == outcome else 0.0
                total += (p - y) ** 2
        return total / (len(self.history) * 3)

    def roi(self):
        bank = 0.0
        total_staked = 0.0
        for rec in self.history:
            stake = rec.get("stake", 0.0)
            total_staked += stake
            if rec.get("outcome"):
                # if prediction chosen, we need to compute actual profit; for demo, assume we only bet on recommended market
                market = max(rec["prediction"], key=rec["prediction"].get)
                if market == rec["outcome"]:
                    bank += stake * (rec["odds"][market] - 1.0)
                else:
                    bank -= stake
        if total_staked == 0:
            return None
        return bank / total_staked

    def hit_rate(self):
        if not self.history:
            return None
        wins = 0
        bets = 0
        for rec in self.history:
            stake = rec.get("stake", 0.0)
            if stake > 0:
                bets += 1
                market = max(rec["prediction"], key=rec["prediction"].get)
                if market == rec["outcome"]:
                    wins += 1
        return wins / bets if bets > 0 else None

