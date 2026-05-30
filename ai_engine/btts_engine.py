"""
BTTS Engine (Both Teams To Score)
Règle absolue: si les deux équipes ont déjà marqué → BTTS = 100%.
Sinon, calcul Poisson conditionnel sur le reste du match.
"""
import math
from typing import Dict, Any, Tuple


def _poisson(lam: float, k: int) -> float:
    lam = max(0.001, min(10.0, lam))
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def compute_btts(
    home_goals: int,
    away_goals: int,
    remaining_home_xg: float,
    remaining_away_xg: float,
    is_live: bool = True,
) -> Dict[str, Any]:
    """
    Calcule BTTS de façon conditionnelle.

    - Si both_scored déjà → BTTS Yes = 100%, locked = True
    - Si temps restant nul → BTTS = état final
    - Sinon → Poisson sur buts restants
    """
    both_scored = home_goals > 0 and away_goals > 0

    if both_scored:
        return {
            "yes_prob": 1.0,
            "no_prob": 0.0,
            "locked": True,
            "reason": "Les deux équipes ont déjà marqué",
        }

    if not is_live:
        # Pré-match: Poisson classique
        p_home = 1.0 - math.exp(-max(0.01, remaining_home_xg))
        p_away = 1.0 - math.exp(-max(0.01, remaining_away_xg))
        yes = p_home * p_away
        return {
            "yes_prob": round(min(1.0, yes), 3),
            "no_prob": round(max(0.0, 1.0 - yes), 3),
            "locked": False,
            "reason": "Prédiction pré-match",
        }

    # Live: conditionnel
    # P(home marque encore | home n'a pas marqué) = 1 - e^(-remaining_xg_home)
    # P(away marque encore | away n'a pas marqué) = 1 - e^(-remaining_xg_away)
    lam_h = max(0.01, remaining_home_xg)
    lam_a = max(0.01, remaining_away_xg)

    if home_goals > 0:
        # Home a marqué, away doit encore marquer
        p_away_scores = 1.0 - math.exp(-lam_a)
        yes = p_away_scores
        reason = f"Domicile a marqué ({home_goals}), attente but extérieur"
    elif away_goals > 0:
        # Away a marqué, home doit encore marquer
        p_home_scores = 1.0 - math.exp(-lam_h)
        yes = p_home_scores
        reason = f"Extérieur a marqué ({away_goals}), attente but domicile"
    else:
        # Personne n'a marqué: les deux doivent marquer
        p_home_scores = 1.0 - math.exp(-lam_h)
        p_away_scores = 1.0 - math.exp(-lam_a)
        yes = p_home_scores * p_away_scores
        reason = "Aucun but marqué, les deux doivent marquer"

    yes = round(min(1.0, max(0.0, yes)), 3)
    return {
        "yes_prob": yes,
        "no_prob": round(1.0 - yes, 3),
        "locked": False,
        "reason": reason,
    }
