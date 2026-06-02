"""
Feature Engineering
Compute features used by models: strengths, form, head-to-head summaries, simple xG aggregates.
"""
from typing import Dict, Any
import math

class FeatureEngineer:
    def __init__(self):
        pass

    def compute_team_strengths(self, historical: Dict[str, Any]):
        # Requires real historical data. Do not fabricate when empty.
        if not historical or not isinstance(historical, dict):
            return {"error": "Données insuffisantes"}
        if "error" in historical:
            return {"error": historical["error"]}
        matches = historical.get("matches", [])
        if not matches:
            return {"error": "Données insuffisantes"}
        # crude aggregation
        goals_for = sum(m.get("goals_for", 0) for m in matches)
        goals_against = sum(m.get("goals_against", 0) for m in matches)
        n = max(len(matches), 1)
        attack = (goals_for / n) / 1.3
        defense = (goals_against / n) / 1.3
        return {"attack": max(0.1, attack), "defense": max(0.1, defense)}

    def head_to_head_summary(self, matches):
        # matches: list of dicts
        return {"h2h_matches": len(matches)}

    def home_advantage(self):
        # constant for demo, could be dynamic by league
        return 1.08

    def compute_schedule_strength(self, fixtures):
        # placeholder: return 1.0 neutral
        return 1.0

    def poisson_rate(self, attack, opponent_defense, home_adv=1.0):
        # base rate
        return attack * opponent_defense * home_adv

    def dixon_coles_adjust(self, lam_home, lam_away, rho=0.0):
        # For demo, small correction when low scores
        if lam_home < 1.0 and lam_away < 1.0:
            return rho
        return 0.0

