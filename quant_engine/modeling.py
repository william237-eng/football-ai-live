"""
Modeling Engine
Implements Dixon-Coles (simplified), adjusted Poisson, and dynamic Elo.
"""
import math
import random
from typing import Tuple, Dict
import numpy as np

class ModelingEngine:
    def __init__(self):
        # Elo table
        self.elo = {}
        self.k_base = 20.0

    # ------------------ ELO ------------------
    def init_elo(self, team: str, base: float = 1500.0):
        self.elo[team] = base

    def get_elo(self, team: str) -> float:
        return float(self.elo.get(team, 1500.0))

    def expected_elo(self, a: float, b: float):
        return 1.0 / (1.0 + 10 ** ((b - a) / 400.0))

    def update_elo(self, home: str, away: str, goals_home: int, goals_away: int, importance: float = 1.0):
        # dynamic K based on importance and margin
        Ra = self.get_elo(home)
        Rb = self.get_elo(away)
        Ea = self.expected_elo(Ra, Rb)
        Sa = 1.0 if goals_home > goals_away else 0.5 if goals_home == goals_away else 0.0
        margin = abs(goals_home - goals_away)
        k = self.k_base * importance * (1 + math.log(1 + margin))
        self.elo[home] = Ra + k * (Sa - Ea)
        self.elo[away] = Rb + k * ((1 - Sa) - (1 - Ea))

    # ------------------ Poisson & Dixon-Coles ------------------
    def poisson_pmf(self, k: int, lam: float):
        if lam is None or lam <= 0:
            raise ValueError("lambda must be positive and based on real data")
        return math.exp(-lam) * (lam ** k) / math.factorial(k)

    def score_matrix_poisson(self, lam_home: float, lam_away: float, max_goals: int = 6):
        if lam_home is None or lam_away is None:
            raise ValueError("lambdas must be provided from real data; cannot compute score matrix")
        mat = np.zeros((max_goals + 1, max_goals + 1))
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                mat[i, j] = self.poisson_pmf(i, lam_home) * self.poisson_pmf(j, lam_away)
        return mat

    def dixon_coles_probs(self, lam_home: float, lam_away: float, rho: float = -0.1, max_goals: int = 6):
        # simplified Dixon-Coles correction
        mat = self.score_matrix_poisson(lam_home, lam_away, max_goals)
        # apply small correction for low-scoring outcomes
        for i in range(0, 2):
            for j in range(0, 2):
                corr = 1.0 + rho * (1.0 if (i == 0 and j == 0) else 0)
                mat[i, j] *= corr
        mat /= mat.sum()
        return mat

    def compute_1x2(self, lam_home: float, lam_away: float):
        try:
            mat = self.score_matrix_poisson(lam_home, lam_away, max_goals=8)
        except ValueError as e:
            return {"error": str(e)}
        home = mat.sum(axis=1).dot((mat.sum(axis=1) > mat.sum(axis=0)).astype(float))
        # simpler: compute margins
        p_home = 0.0
        p_draw = 0.0
        p_away = 0.0
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                if i > j:
                    p_home += mat[i, j]
                elif i == j:
                    p_draw += mat[i, j]
                else:
                    p_away += mat[i, j]
        return {"home": p_home, "draw": p_draw, "away": p_away}

    def expected_score(self, lam_home: float, lam_away: float):
        # expected goals
        maxg = 8
        try:
            mat = self.score_matrix_poisson(lam_home, lam_away, max_goals=maxg)
        except ValueError as e:
            return {"error": str(e)}
        exp_home = sum(i * mat[i, j] for i in range(mat.shape[0]) for j in range(mat.shape[1]))
        exp_away = sum(j * mat[i, j] for i in range(mat.shape[0]) for j in range(mat.shape[1]))
        return exp_home, exp_away

    # simple conversion from Elo to attack/defense multipliers for Poisson
    def elo_to_strengths(self, team_elo: float, league_avg: float = 1500.0):
        # return attack & defense multiplier
        diff = (team_elo - league_avg) / 400.0
        attack = math.exp(diff)
        defense = math.exp(-diff)
        return attack, defense

    def lambdas_from_live_xg(self, live_stats: dict) -> Tuple[float, float]:
        """Compute expected remaining goals (lambdas) for each team from live xG.

        This uses ONLY observed live xG and minute to project expected goals for
        the remaining minutes. It does not fabricate xG values; if required fields
        are missing it raises ValueError.
        """
        if not live_stats or not isinstance(live_stats, dict):
            raise ValueError("live_stats manquantes")
        minute = live_stats.get("minute")
        xg_home = live_stats.get("xG_home")
        xg_away = live_stats.get("xG_away")
        if minute is None or minute <= 0:
            raise ValueError("minute invalide pour projection xG")
        if xg_home is None or xg_away is None:
            raise ValueError("xG manquant dans live_stats")

        remaining = max(0, 90 - minute)
        # rate per minute observed so far
        rate_home_per_min = xg_home / minute
        rate_away_per_min = xg_away / minute

        expected_home_remaining = rate_home_per_min * remaining
        expected_away_remaining = rate_away_per_min * remaining

        # lambdas for remainder of match
        return float(expected_home_remaining), float(expected_away_remaining)

