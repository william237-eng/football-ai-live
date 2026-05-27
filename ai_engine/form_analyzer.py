from typing import Any, Dict, List


def analyze_form(fixtures: List[Dict[str, Any]], team_id: int) -> Dict[str, Any]:
    wins = draws = losses = goals_for = goals_against = 0
    weighted_points = 0.0
    rows = []

    for index, item in enumerate((fixtures or [])[:5]):
        teams = item.get("teams") or {}
        goals = item.get("goals") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        is_home = home.get("id") == team_id
        opponent = away if is_home else home
        gf = goals.get("home") if is_home else goals.get("away")
        ga = goals.get("away") if is_home else goals.get("home")
        gf = int(gf or 0)
        ga = int(ga or 0)
        goals_for += gf
        goals_against += ga

        if gf > ga:
            wins += 1
            result = "V"
            points = 3
        elif gf < ga:
            losses += 1
            result = "D"
            points = 0
        else:
            draws += 1
            result = "N"
            points = 1

        weight = max(1.0, 5.0 - index) / 5.0
        weighted_points += points * weight
        rows.append({
            "opponent": opponent.get("name") or "Non disponible",
            "score": f"{gf} - {ga}",
            "result": result,
            "weight": weight,
        })

    played = max(len(rows), 1)
    return {
        "played": len(rows),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "avg_goals_for": goals_for / played,
        "avg_goals_against": goals_against / played,
        "points_per_match": (wins * 3 + draws) / played,
        "weighted_points": weighted_points,
        "form_score": min(100.0, ((wins * 3 + draws) / (played * 3)) * 100.0),
        "rows": rows,
    }
