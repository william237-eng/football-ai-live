from typing import Dict, Optional

from ai_engine.live_context_engine import dynamic_lambdas, build_live_context
from ai_engine.poisson_engine import expected_goals, score_matrix_live, top_scores_live


def calculate_probabilities(
    home_form: Dict[str, float],
    away_form: Dict[str, float],
    home_elo: int,
    away_elo: int,
    live_context: Optional[Dict] = None,
) -> Dict[str, object]:
    base_home_xg, base_away_xg = expected_goals(home_form, away_form)

    if live_context and live_context.get("is_live"):
        home_xg, away_xg = dynamic_lambdas(base_home_xg, base_away_xg, live_context)
        current_home = live_context.get("home_goals", 0)
        current_away = live_context.get("away_goals", 0)
        matrix = score_matrix_live(home_xg, away_xg, current_home, current_away)
        top = top_scores_live(home_xg, away_xg, current_home, current_away, 3)
    else:
        home_xg, away_xg = base_home_xg, base_away_xg
        matrix = score_matrix_live(home_xg, away_xg, 0, 0)
        top = top_scores_live(home_xg, away_xg, 0, 0, 3)

    home_win = sum(prob for (home, away), prob in matrix.items() if home > away)
    draw = sum(prob for (home, away), prob in matrix.items() if home == away)
    away_win = sum(prob for (home, away), prob in matrix.items() if home < away)

    elo_delta = max(-350, min(350, home_elo - away_elo))
    elo_shift = elo_delta / 3500.0
    home_win = max(0.01, home_win + elo_shift)
    away_win = max(0.01, away_win - elo_shift)
    total = home_win + draw + away_win

    probabilities = {
        "home_win": round((home_win / total) * 100.0, 1),
        "draw": round((draw / total) * 100.0, 1),
        "away_win": round((away_win / total) * 100.0, 1),
    }

    confidence = max(probabilities.values())
    data_quality = min(1.0, (home_form.get("played", 0) + away_form.get("played", 0)) / 10.0)

    if live_context and live_context.get("is_live"):
        momentum_conf = abs(live_context.get("momentum", 0)) * 15.0
        pressure_conf = (live_context.get("home_pressure", 0) + live_context.get("away_pressure", 0)) / 20.0
        red_penalty = abs(live_context.get("red_card_shift", 0)) * 20.0
        live_factor = clamp((momentum_conf + pressure_conf - red_penalty) / 100.0, 0.0, 0.25)
        confidence = confidence * (1.0 + live_factor)
        confidence_label = "Élevé (Live)" if confidence >= 60 else "Moyen (Live)" if confidence >= 40 else "Faible (Live)"
    else:
        confidence_label = "Élevé" if confidence >= 55 and data_quality >= 0.8 else "Moyen" if data_quality >= 0.5 else "Faible"

    return {
        "home_xg": home_xg,
        "away_xg": away_xg,
        "probabilities": probabilities,
        "top_scores": top,
        "confidence": round(confidence * data_quality, 1),
        "confidence_label": confidence_label,
        "live_context": live_context,
    }


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
