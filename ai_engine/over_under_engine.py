"""
Over/Under Engine
Comprend les marchés déjà terminés.
Si X buts déjà marqués > seuil → Over = 100%, Under = 0%.
Calcule uniquement les buts RESTANTS via Poisson.
"""
import math
from typing import Dict, Any, List, Tuple


def _poisson_prob(lam: float, k: int) -> float:
    lam = max(0.001, min(15.0, lam))
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _remaining_over_prob(remaining_lam: float, need: int) -> float:
    """
    P(buts restants >= need) avec lambda = remaining_lam.
    need = max(0, threshold - goals_already)
    """
    if need <= 0:
        return 1.0  # déjà dépassé
    if remaining_lam <= 0:
        return 0.0
    # P(X >= need) = 1 - P(X <= need-1)
    prob_under = sum(_poisson_prob(remaining_lam, k) for k in range(need))
    return round(max(0.0, min(1.0, 1.0 - prob_under)), 4)


def compute_over_under(
    home_goals: int,
    away_goals: int,
    remaining_home_xg: float,
    remaining_away_xg: float,
    thresholds: List[float] = None,
    is_live: bool = True,
) -> Dict[str, Any]:
    """
    Calcule Over/Under pour chaque seuil, conditionnel au score actuel.

    Retourne un dict de marchés avec:
    - prob: probabilité
    - locked: True si déjà déterminé
    - need: buts restants nécessaires
    - status: 'won', 'lost', 'open'
    """
    if thresholds is None:
        thresholds = [0.5, 1.5, 2.5, 3.5, 4.5]

    total_goals = home_goals + away_goals
    remaining_lam = max(0.0, remaining_home_xg + remaining_away_xg)

    markets = {}

    for threshold in thresholds:
        key = str(threshold).replace(".", "")

        if total_goals > threshold:
            # DÉJÀ GAGNÉ: Over = 100%
            markets[f"over_{key}"] = {
                "threshold": threshold,
                "prob": 1.0,
                "locked": True,
                "status": "won",
                "label": f"Over {threshold}",
                "reason": f"{total_goals} buts > {threshold} — marché gagné",
            }
            markets[f"under_{key}"] = {
                "threshold": threshold,
                "prob": 0.0,
                "locked": True,
                "status": "lost",
                "label": f"Under {threshold}",
                "reason": f"{total_goals} buts > {threshold} — marché perdu",
            }
        elif total_goals == threshold:
            # Sur le seuil exact: Over nécessite encore 1 but
            need_for_over = 1
            over_prob = _remaining_over_prob(remaining_lam, need_for_over)
            under_prob = 1.0 - over_prob
            markets[f"over_{key}"] = {
                "threshold": threshold,
                "prob": over_prob,
                "locked": False,
                "status": "open",
                "label": f"Over {threshold}",
                "reason": f"Exactement {total_goals} buts, 1 but restant nécessaire",
            }
            markets[f"under_{key}"] = {
                "threshold": threshold,
                "prob": under_prob,
                "locked": False,
                "status": "open",
                "label": f"Under {threshold}",
                "reason": f"Exactement {total_goals} buts, 1 but restant interdit",
            }
        else:
            # Sous le seuil: combien de buts restants nécessaires
            need_for_over = math.ceil(threshold - total_goals + 0.001)
            need_for_over = max(1, int(need_for_over))
            over_prob = _remaining_over_prob(remaining_lam, need_for_over)
            under_prob = 1.0 - over_prob
            markets[f"over_{key}"] = {
                "threshold": threshold,
                "prob": over_prob,
                "locked": False,
                "status": "open",
                "label": f"Over {threshold}",
                "reason": f"{total_goals} buts, besoin de {need_for_over} but(s) restant(s)",
            }
            markets[f"under_{key}"] = {
                "threshold": threshold,
                "prob": under_prob,
                "locked": False,
                "status": "open",
                "label": f"Under {threshold}",
                "reason": f"{total_goals} buts, sous le seuil",
            }

    return markets
