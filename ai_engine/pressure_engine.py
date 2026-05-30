"""
Pressure Engine
Calcule l'indice de pression de chaque équipe.
Si données absentes → affiche "pression inconnue" au lieu de 0.
"""
from typing import Dict, Any, Tuple, Optional


def safe_num(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def compute_pressure(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calcule les indices de pression domicile/extérieur.
    Retourne unknown=True si données insuffisantes.
    """
    def _get(stats, *aliases) -> Optional[float]:
        normalized = {str(k).lower().strip(): v for k, v in (stats or {}).items()}
        for alias in aliases:
            v = normalized.get(alias.lower().strip())
            result = safe_num(v)
            if result is not None:
                return result
        return None

    home_poss = _get(home_stats, "Ball Possession", "Possession")
    away_poss = _get(away_stats, "Ball Possession", "Possession")
    home_shots = _get(home_stats, "Total Shots", "Shots Total")
    away_shots = _get(away_stats, "Total Shots", "Shots Total")
    home_target = _get(home_stats, "Shots on Goal", "On Target")
    away_target = _get(away_stats, "Shots on Goal", "On Target")
    home_corners = _get(home_stats, "Corner Kicks", "Corners")
    away_corners = _get(away_stats, "Corner Kicks", "Corners")
    home_attacks = _get(home_stats, "Dangerous Attacks", "Attacks")
    away_attacks = _get(away_stats, "Dangerous Attacks", "Attacks")

    # Vérifier si on a au moins 2 indicateurs clés
    home_indicators = [x for x in [home_poss, home_shots, home_target] if x is not None]
    away_indicators = [x for x in [away_poss, away_shots, away_target] if x is not None]

    if len(home_indicators) < 2 and len(away_indicators) < 2:
        return {
            "home_index": None,
            "away_index": None,
            "home_label": "Pression inconnue",
            "away_label": "Pression inconnue",
            "unknown": True,
            "breakdown": {},
        }

    def score(poss, shots, target, corners, attacks):
        p = (poss or 50.0) * 0.25
        s = (shots or 0) * 3.0
        t = (target or 0) * 5.5
        c = (corners or 0) * 2.0
        a = (attacks or 0) * 0.20
        return min(100.0, p + s + t + c + a)

    home_idx = score(home_poss, home_shots, home_target, home_corners, home_attacks)
    away_idx = score(away_poss, away_shots, away_target, away_corners, away_attacks)

    def label(idx: float) -> str:
        if idx >= 70:
            return "Pression très haute"
        elif idx >= 50:
            return "Pression haute"
        elif idx >= 30:
            return "Pression modérée"
        else:
            return "Pression faible"

    return {
        "home_index": round(home_idx, 1),
        "away_index": round(away_idx, 1),
        "home_label": label(home_idx),
        "away_label": label(away_idx),
        "unknown": False,
        "breakdown": {
            "home_possession": home_poss,
            "away_possession": away_poss,
            "home_shots": home_shots,
            "away_shots": away_shots,
            "home_on_target": home_target,
            "away_on_target": away_target,
        },
    }
