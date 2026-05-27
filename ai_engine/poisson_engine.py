import math
from typing import Dict, List, Tuple


def _poisson_probability(lam: float, goals: int) -> float:
    lam = max(0.05, min(5.0, lam))
    return (math.exp(-lam) * (lam ** goals)) / math.factorial(goals)


def expected_goals(home_form: Dict[str, float], away_form: Dict[str, float]) -> Tuple[float, float]:
    home_attack = max(0.1, home_form.get("avg_goals_for", 0.0))
    home_defense = max(0.1, home_form.get("avg_goals_against", 0.0))
    away_attack = max(0.1, away_form.get("avg_goals_for", 0.0))
    away_defense = max(0.1, away_form.get("avg_goals_against", 0.0))
    home_xg = ((home_attack + away_defense) / 2.0) * 1.08
    away_xg = ((away_attack + home_defense) / 2.0) * 0.94
    return round(max(0.05, home_xg), 2), round(max(0.05, away_xg), 2)


def score_matrix(home_xg: float, away_xg: float, max_goals: int = 6) -> Dict[Tuple[int, int], float]:
    matrix = {}
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            matrix[(home_goals, away_goals)] = _poisson_probability(home_xg, home_goals) * _poisson_probability(away_xg, away_goals)
    return matrix


def score_matrix_live(home_xg: float, away_xg: float, current_home: int, current_away: int, max_goals: int = 6) -> Dict[Tuple[int, int], float]:
    matrix = {}
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            # Filtrer les scores impossibles (inférieurs au score actuel)
            if home_goals < current_home or away_goals < current_away:
                continue
            # Calculer les buts restants à marquer
            remaining_home = home_goals - current_home
            remaining_away = away_goals - current_away
            prob = _poisson_probability(home_xg, remaining_home) * _poisson_probability(away_xg, remaining_away)
            matrix[(home_goals, away_goals)] = prob
    return matrix


def top_scores(home_xg: float, away_xg: float, count: int = 3) -> List[Dict[str, float]]:
    matrix = score_matrix(home_xg, away_xg)
    ordered = sorted(matrix.items(), key=lambda item: item[1], reverse=True)
    return [{"score": f"{score[0]}-{score[1]}", "probability": round(probability * 100.0, 1)} for score, probability in ordered[:count]]


def top_scores_live(home_xg: float, away_xg: float, current_home: int, current_away: int, count: int = 3) -> List[Dict[str, float]]:
    matrix = score_matrix_live(home_xg, away_xg, current_home, current_away)
    ordered = sorted(matrix.items(), key=lambda item: item[1], reverse=True)
    return [{"score": f"{score[0]}-{score[1]}", "probability": round(probability * 100.0, 1)} for score, probability in ordered[:count]]
