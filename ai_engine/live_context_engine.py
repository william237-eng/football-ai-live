from typing import Any, Dict, List, Tuple


def safe_num(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_live_context(
    home_goals: int,
    away_goals: int,
    minute: int,
    status: str,
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    minute = int(clamp(float(minute or 0), 0.0, 120.0))
    remaining = max(0, 90 - min(minute, 90))
    time_factor = remaining / 90.0

    home_pressure = pressure_index(home_stats)
    away_pressure = pressure_index(away_stats)
    momentum = clamp((home_pressure - away_pressure) / 100.0, -1.0, 1.0)

    home_reds, away_reds = red_cards(events)
    red_card_shift = (away_reds - home_reds) * 0.18
    score_diff = int(home_goals or 0) - int(away_goals or 0)

    if score_diff > 0:
        state = "domicile mène"
    elif score_diff < 0:
        state = "extérieur mène"
    else:
        state = "match nul"

    phase = "Première mi-temps"
    if minute >= 90:
        phase = "Temps additionnel / fin de match"
    elif minute >= 75:
        phase = "Fin de match"
    elif minute >= 46:
        phase = "Seconde période"
    elif minute >= 40:
        phase = "Fin de première mi-temps"

    return {
        "is_live": minute > 0 and status not in {"NS", "TBD", "PST", "CANC"},
        "home_goals": int(home_goals or 0),
        "away_goals": int(away_goals or 0),
        "minute": minute,
        "remaining": remaining,
        "time_factor": time_factor,
        "home_pressure": home_pressure,
        "away_pressure": away_pressure,
        "momentum": momentum,
        "red_card_shift": red_card_shift,
        "score_diff": score_diff,
        "state": state,
        "phase": phase,
        "home_red_cards": home_reds,
        "away_red_cards": away_reds,
    }


def pressure_index(stats: Dict[str, Any]) -> float:
    possession = safe_num(get_stat(stats, ["Ball Possession", "Possession"]))
    shots = safe_num(get_stat(stats, ["Total Shots", "Shots Total", "Total shots"]))
    on_target = safe_num(get_stat(stats, ["Shots on Goal", "Shots on goal", "On Target"]))
    corners = safe_num(get_stat(stats, ["Corner Kicks", "Corners"]))
    attacks = safe_num(get_stat(stats, ["Dangerous Attacks", "Attacks", "Attaques dangereuses"]))
    return clamp((possession * 0.35) + (shots * 2.0) + (on_target * 4.0) + (corners * 2.5) + (attacks * 0.25), 0.0, 100.0)


def get_stat(stats: Dict[str, Any], aliases: List[str]) -> Any:
    normalized = {str(key).lower().strip(): value for key, value in (stats or {}).items()}
    for alias in aliases:
        key = alias.lower().strip()
        if key in normalized and normalized[key] is not None:
            return normalized[key]
    return 0


def red_cards(events: List[Dict[str, Any]]) -> Tuple[int, int]:
    home_reds = away_reds = 0
    for event in events or []:
        detail = str(event.get("detail") or event.get("type") or "").lower()
        if "red" not in detail:
            continue
        team = event.get("team") or {}
        side = str(team.get("name") or "").lower()
        if event.get("team") and event.get("assist") is None:
            if event.get("comments") == "away":
                away_reds += 1
            else:
                home_reds += 1 if not side else 0
    return home_reds, away_reds


def dynamic_lambdas(base_home_xg: float, base_away_xg: float, context: Dict[str, Any]) -> Tuple[float, float]:
    if not context or not context.get("is_live"):
        return base_home_xg, base_away_xg

    time_factor = context.get("time_factor", 1.0)
    momentum = context.get("momentum", 0.0)
    score_diff = context.get("score_diff", 0)
    red_shift = context.get("red_card_shift", 0.0)

    home_remaining = base_home_xg * time_factor
    away_remaining = base_away_xg * time_factor
    home_remaining *= 1.0 + max(momentum, 0.0) * 0.42 + red_shift
    away_remaining *= 1.0 + max(-momentum, 0.0) * 0.42 - red_shift

    if score_diff > 0:
        home_remaining *= 0.86
        away_remaining *= 1.18
    elif score_diff < 0:
        home_remaining *= 1.18
        away_remaining *= 0.86

    return round(clamp(home_remaining, 0.01, 3.5), 2), round(clamp(away_remaining, 0.01, 3.5), 2)
