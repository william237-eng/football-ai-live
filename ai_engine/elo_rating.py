from typing import Dict


def calculate_elo(form: Dict[str, float], home_advantage: bool = False) -> int:
    base = 1500.0
    result_component = (form.get("wins", 0) * 28.0) + (form.get("draws", 0) * 8.0) - (form.get("losses", 0) * 24.0)
    goal_component = (form.get("goals_for", 0) - form.get("goals_against", 0)) * 11.0
    attack_component = form.get("avg_goals_for", 0.0) * 22.0
    defense_component = -form.get("avg_goals_against", 0.0) * 18.0
    recency_component = form.get("weighted_points", 0.0) * 9.0
    home_component = 45.0 if home_advantage else 0.0
    elo = base + result_component + goal_component + attack_component + defense_component + recency_component + home_component
    return int(round(max(900.0, min(2200.0, elo))))
