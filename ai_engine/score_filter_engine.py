"""
Score Filter Engine
Supprime tous les scores impossibles selon le score actuel.
Ex: score 1-1 -> interdit 0-0, 0-1, 1-0, etc.
"""
from typing import Dict, List, Tuple, Any


def filter_impossible_scores(
    score_matrix: Dict[Tuple[int, int], float],
    current_home: int,
    current_away: int,
) -> Dict[Tuple[int, int], float]:
    """
    Filtre la matrice de scores pour ne garder que les scores possibles.
    Un score est possible si home >= current_home ET away >= current_away.
    """
    filtered = {}
    for (h, a), prob in score_matrix.items():
        if h >= current_home and a >= current_away:
            filtered[(h, a)] = prob
    # Renormaliser
    total = sum(filtered.values())
    if total > 0:
        filtered = {k: v / total for k, v in filtered.items()}
    return filtered


def top_possible_scores(
    score_matrix: Dict[Tuple[int, int], float],
    current_home: int,
    current_away: int,
    count: int = 5,
) -> List[Dict[str, Any]]:
    """
    Retourne les scores finaux les plus probables, en excluant les impossibles.
    """
    filtered = filter_impossible_scores(score_matrix, current_home, current_away)
    ordered = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
    result = []
    for (h, a), prob in ordered[:count]:
        result.append({
            "score": f"{h}-{a}",
            "home_goals": h,
            "away_goals": a,
            "probability": round(prob * 100.0, 1),
            "is_current": h == current_home and a == current_away,
        })
    return result


def is_score_possible(h: int, a: int, current_home: int, current_away: int) -> bool:
    """Retourne True si le score (h, a) est encore atteignable."""
    return h >= current_home and a >= current_away
