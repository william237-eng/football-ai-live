"""
Smart Stats Fallback Engine
Estime les statistiques manquantes à partir des données disponibles
"""
from typing import Any, Dict, List


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return default


def estimate_missing_stats(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    home_form: Dict[str, float],
    away_form: Dict[str, float],
    home_team_stats: Dict[str, Any],
    away_team_stats: Dict[str, Any],
    events: List[Dict[str, Any]],
    minute: int,
) -> Dict[str, Dict[str, float]]:
    """
    Estime les statistiques manquantes basées sur:
    - Forme récente
    - Moyennes historiques
    - Événements match
    - Minute actuelle
    """
    estimated_home = dict(home_stats)
    estimated_away = dict(away_stats)

    # Récupérer les moyennes des équipes depuis team statistics
    home_avg_for = get_team_avg_goals(home_team_stats, "for")
    home_avg_against = get_team_avg_goals(home_team_stats, "against")
    away_avg_for = get_team_avg_goals(away_team_stats, "for")
    away_avg_against = get_team_avg_goals(away_team_stats, "against")

    # Estimer possession si manquante
    if not has_stat(estimated_home, ["Ball Possession", "Possession"]):
        home_possession = estimate_possession(
            home_form, away_form, home_avg_for, away_avg_for, minute
        )
        estimated_home["Ball Possession"] = f"{home_possession}%"
        estimated_away["Ball Possession"] = f"{100 - home_possession}%"

    # Estimer tirs si manquants
    if not has_stat(estimated_home, ["Total Shots", "Shots Total"]):
        home_shots = estimate_shots(home_form, home_avg_for, minute, True)
        away_shots = estimate_shots(away_form, away_avg_for, minute, False)
        estimated_home["Total Shots"] = home_shots
        estimated_away["Total Shots"] = away_shots

    # Estimer tirs cadrés si manquants
    if not has_stat(estimated_home, ["Shots on Goal", "On Target"]):
        home_on_target = max(1, int(safe_float(estimated_home.get("Total Shots"), 0) * 0.42))
        away_on_target = max(1, int(safe_float(estimated_away.get("Total Shots"), 0) * 0.38))
        estimated_home["Shots on Goal"] = home_on_target
        estimated_away["Shots on Goal"] = away_on_target

    # Estimer corners si manquants
    if not has_stat(estimated_home, ["Corner Kicks", "Corners"]):
        home_corners = estimate_corners(home_form, minute, safe_float(estimated_home.get("Total Shots"), 0))
        away_corners = estimate_corners(away_form, minute, safe_float(estimated_away.get("Total Shots"), 0))
        estimated_home["Corner Kicks"] = home_corners
        estimated_away["Corner Kicks"] = away_corners

    # Estimer fautes si manquantes
    if not has_stat(estimated_home, ["Fouls"]):
        home_fouls = estimate_fouls(home_form, minute)
        away_fouls = estimate_fouls(away_form, minute)
        estimated_home["Fouls"] = home_fouls
        estimated_away["Fouls"] = away_fouls

    # Estimer xG si manquant
    if not has_stat(estimated_home, ["expected_goals", "xG", "Expected Goals"]):
        home_xg = estimate_xg(home_form, home_avg_for, minute, safe_float(estimated_home.get("Total Shots"), 0))
        away_xg = estimate_xg(away_form, away_avg_for, minute, safe_float(estimated_away.get("Total Shots"), 0))
        estimated_home["expected_goals"] = round(home_xg, 2)
        estimated_away["expected_goals"] = round(away_xg, 2)

    return {"home": estimated_home, "away": estimated_away}


def has_stat(stats: Dict[str, Any], aliases: List[str]) -> bool:
    normalized = {str(k).lower().strip(): v for k, v in stats.items()}
    for alias in aliases:
        if alias.lower().strip() in normalized:
            val = normalized[alias.lower().strip()]
            if val is not None and str(val) not in ["", "0", "0%", "Non disponible"]:
                return True
    return False


def get_stat_value(stats: Dict[str, Any], aliases: List[str], default: Any = 0) -> Any:
    normalized = {str(k).lower().strip(): v for k, v in stats.items()}
    for alias in aliases:
        key = alias.lower().strip()
        if key in normalized and normalized[key] is not None:
            return normalized[key]
    return default


def get_team_avg_goals(team_stats: Dict[str, Any], side: str) -> float:
    """Récupère la moyenne de buts depuis les statistiques équipe"""
    if not isinstance(team_stats, dict):
        return 0.0
    response = team_stats.get("response") or {}
    if isinstance(response, list) and response:
        response = response[0]
    goals = response.get("goals") or {}
    section = goals.get("for" if side == "for" else "against") or {}
    average = section.get("average") or {}
    return safe_float(average.get("total"), 0.0)


def estimate_possession(
    home_form: Dict[str, float],
    away_form: Dict[str, float],
    home_avg_for: float,
    away_avg_for: float,
    minute: int,
) -> float:
    """Estime la possession basée sur la forme et les moyennes"""
    base_home = 52.0  # Avantage domicile

    # Ajustement basé sur la forme offensive
    home_attack = home_form.get("avg_goals_for", 0.0) * 3.0
    away_attack = away_form.get("avg_goals_for", 0.0) * 3.0

    # Ajustement basé sur les moyennes historiques
    if home_avg_for > 0 and away_avg_for > 0:
        ratio = home_avg_for / (home_avg_for + away_avg_for)
        base_home += (ratio - 0.5) * 20.0

    # Ajustement basé sur les points de forme
    home_points = home_form.get("points_per_match", 1.5)
    away_points = away_form.get("points_per_match", 1.5)
    if home_points + away_points > 0:
        base_home += (home_points / (home_points + away_points) - 0.5) * 15.0

    return max(35.0, min(65.0, base_home))


def estimate_shots(form: Dict[str, float], avg_goals: float, minute: int, is_home: bool) -> int:
    """Estime le nombre de tirs basé sur la forme et le temps de jeu"""
    base = 9.0 if is_home else 7.5

    # Ajustement basé sur la forme offensive
    attack_factor = form.get("avg_goals_for", 1.0) / 1.2
    base *= attack_factor

    # Ajustement basé sur les moyennes historiques
    if avg_goals > 0:
        base *= (avg_goals / 1.3)

    # Ajustement temporel (pro-rata minute)
    time_factor = max(0.3, minute / 90.0) if minute > 0 else 1.0
    if minute > 0:
        base = base * time_factor + (2.0 if form.get("momentum", 0) > 0.2 else 0.0)

    return max(1, int(round(base)))


def estimate_corners(form: Dict[str, float], minute: int, shots: float) -> int:
    """Estime les corners basé sur les tirs et la forme"""
    # Ratio corners/tirs typique ~0.25
    base = shots * 0.22

    # Ajustement basé sur la pression offensive
    pressure = form.get("avg_goals_for", 1.0) / 1.4
    base *= pressure

    return max(0, int(round(base)))


def estimate_fouls(form: Dict[str, float], minute: int) -> int:
    """Estime les fautes basées sur la forme défensive"""
    base = 10.0

    # Plus de fautes si l'équipe subit des buts
    defense_pressure = form.get("avg_goals_against", 1.0)
    base += defense_pressure * 2.0

    # Ajustement temporel
    if minute > 0:
        base = base * max(0.4, minute / 90.0)

    return max(2, int(round(base)))


def estimate_xg(form: Dict[str, float], avg_goals: float, minute: int, shots: float) -> float:
    """Estime les xG basés sur les tirs et la qualité offensive"""
    # xG par tir typique ~0.1-0.12
    xg_per_shot = 0.095

    # Ajustement qualité
    quality = form.get("avg_goals_for", 1.0) / 1.3
    xg_per_shot *= quality

    if minute > 0:
        # En live, on estime les xG accumulés
        return shots * xg_per_shot * 0.85
    else:
        # Pré-match, projection sur 90min
        return avg_goals * 0.92 if avg_goals > 0 else shots * xg_per_shot


def mark_estimated(stats: Dict[str, Any], original_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Marque les statistiques estimées pour l'affichage"""
    result = {}
    for key, value in stats.items():
        was_missing = key not in original_stats or original_stats.get(key) in [None, "", "0", "0%", "Non disponible"]
        if was_missing and value:
            result[key] = f"{value}*"
        else:
            result[key] = value
    return result
