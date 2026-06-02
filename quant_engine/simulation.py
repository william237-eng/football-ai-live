"""
Live Simulation Engine
Runs minute-by-minute Monte Carlo simulations updating lambda values and outputs live probabilities.
"""
import random
import math
from typing import Dict, Any
import numpy as np

class SimulationEngine:
    def __init__(self, modeling):
        self.modeling = modeling

    def minute_update(self, state: Dict[str, Any]):
        # state contains current minute, goals, xG, red cards, fatigue factors
        minute = state.get("minute", 0)
        # must rely on real base lambdas (e.g. derived from live xG). Do not fabricate.
        base_lam_home = state.get("base_lam_home", None)
        base_lam_away = state.get("base_lam_away", None)
        if base_lam_home is None or base_lam_away is None:
            return {"error": "Données insuffisantes: base_lam_home/base_lam_away manquants"}
        # fatigue increases in second half
        fatigue = 1.0 - 0.01 * max(0, minute - 60)
        red_card_factor = 0.9 ** state.get("red_cards_away", 0) if state.get("red_cards_away", 0) else 1.0
        lam_home = max(0.0, base_lam_home * fatigue * red_card_factor)
        lam_away = max(0.0, base_lam_away * fatigue)
        return lam_home, lam_away

    def monte_carlo(self, state: Dict[str, Any], n_sim: int = 2000):
        # Run simplified Monte Carlo: simulate remaining minutes by Poisson scoring with minute-adjusted lambdas
        minute = state.get("minute", 0)
        remaining = max(0, 90 - minute)
        base_lh = state.get("base_lam_home", None)
        base_la = state.get("base_lam_away", None)
        if base_lh is None or base_la is None:
            return {"error": "Données insuffisantes: base_lam_home/base_lam_away manquants"}
        current_home = state.get("goals_home", 0)
        current_away = state.get("goals_away", 0)

        outcomes = {"home": 0, "draw": 0, "away": 0}
        for _ in range(n_sim):
            gh = current_home
            ga = current_away
            for m in range(remaining):
                # small stochastic variation
                lamh = max(0.0, base_lh * (1 + random.gauss(0, 0.05)))
                lama = max(0.0, base_la * (1 + random.gauss(0, 0.05)))
                # probability of scoring in minute ~ poisson with mean lamh/90 per minute; we treat lam as per remaining minute
                if random.random() < 1 - math.exp(-lamh / 10.0):
                    gh += 1
                if random.random() < 1 - math.exp(-lama / 10.0):
                    ga += 1
            if gh > ga:
                outcomes["home"] += 1
            elif gh == ga:
                outcomes["draw"] += 1
            else:
                outcomes["away"] += 1
        total = n_sim
        return {k: v / total for k, v in outcomes.items()}

    def live_probability(self, state: Dict[str, Any]):
        mu = self.minute_update(state)
        if isinstance(mu, dict) and "error" in mu:
            return mu
        lam_home, lam_away = mu
        mc = self.monte_carlo({**state, "base_lam_home": lam_home, "base_lam_away": lam_away}, n_sim=1000)
        return mc

