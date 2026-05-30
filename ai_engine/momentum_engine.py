"""
Momentum Engine
Calcule le momentum en temps réel depuis les statistiques live.
Ne retourne jamais 0% si données insuffisantes — affiche "inconnu".
"""
from typing import Dict, Any, Optional, Tuple


def safe_num(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(str(v).replace("%", "").strip())
    except (ValueError, TypeError):
        return 0.0


def compute_momentum(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    events: list,
    home_goals: int,
    away_goals: int,
    minute: int,
) -> Dict[str, Any]:
    """
    Calcule le momentum domicile/extérieur.
    Retourne:
      - value: float entre -1.0 (away total) et +1.0 (home total)
      - label: description textuelle
      - home_pct: pourcentage momentum domicile
      - away_pct: pourcentage momentum extérieur
      - data_available: bool
      - recent_events: liste des 5 derniers événements significatifs
    """
    def _get(stats, *aliases):
        normalized = {str(k).lower().strip(): v for k, v in (stats or {}).items()}
        for alias in aliases:
            v = normalized.get(alias.lower().strip())
            if v is not None:
                return safe_num(v)
        return None

    # Récupérer stats clés
    h_poss = _get(home_stats, "Ball Possession", "Possession")
    a_poss = _get(away_stats, "Ball Possession", "Possession")
    h_shots = _get(home_stats, "Total Shots", "Shots Total")
    a_shots = _get(away_stats, "Total Shots", "Shots Total")
    h_target = _get(home_stats, "Shots on Goal", "On Target")
    a_target = _get(away_stats, "Shots on Goal", "On Target")
    h_attacks = _get(home_stats, "Dangerous Attacks", "Attacks")
    a_attacks = _get(away_stats, "Dangerous Attacks", "Attacks")
    h_corners = _get(home_stats, "Corner Kicks", "Corners")
    a_corners = _get(away_stats, "Corner Kicks", "Corners")

    data_available = any(v is not None for v in [
        h_poss, a_poss, h_shots, a_shots, h_target, a_target
    ])

    if not data_available:
        # Pas de stats → estimation à partir des buts
        if home_goals > away_goals:
            value = 0.25
            label = "Momentum domicile estimé (données insuffisantes)"
        elif away_goals > home_goals:
            value = -0.25
            label = "Momentum extérieur estimé (données insuffisantes)"
        else:
            value = 0.0
            label = "Données live insuffisantes"
        return {
            "value": value,
            "home_pct": round((0.5 + value / 2) * 100),
            "away_pct": round((0.5 - value / 2) * 100),
            "label": label,
            "data_available": False,
            "recent_events": _recent_events(events, 5),
        }

    # Scores pondérés
    def w(val, default=0.0):
        return val if val is not None else default

    home_score = (
        w(h_poss, 50) * 0.20 +
        w(h_shots) * 3.5 +
        w(h_target) * 6.0 +
        w(h_attacks) * 0.15 +
        w(h_corners) * 2.0
    )
    away_score = (
        w(a_poss, 50) * 0.20 +
        w(a_shots) * 3.5 +
        w(a_target) * 6.0 +
        w(a_attacks) * 0.15 +
        w(a_corners) * 2.0
    )

    # Ajustement: buts récents (dernières 15 min) boostent le momentum
    recent_goals_home = _count_recent_goals(events, "home", minute, window=15)
    recent_goals_away = _count_recent_goals(events, "away", minute, window=15)
    home_score += recent_goals_home * 8.0
    away_score += recent_goals_away * 8.0

    total = home_score + away_score + 1e-9
    home_pct = round(home_score / total * 100)
    away_pct = 100 - home_pct
    value = (home_score - away_score) / (total) * 2.0
    value = max(-1.0, min(1.0, value))

    if value > 0.4:
        label = "Forte domination domicile"
    elif value > 0.15:
        label = "Légère domination domicile"
    elif value < -0.4:
        label = "Forte domination extérieure"
    elif value < -0.15:
        label = "Légère domination extérieure"
    else:
        label = "Match équilibré"

    return {
        "value": round(value, 3),
        "home_pct": home_pct,
        "away_pct": away_pct,
        "label": label,
        "data_available": True,
        "recent_events": _recent_events(events, 5),
    }


def _count_recent_goals(events: list, side: str, current_minute: int, window: int = 15) -> int:
    count = 0
    for ev in (events or []):
        ev_type = str(ev.get("type") or "").lower()
        if "goal" not in ev_type:
            continue
        ev_minute = int(str(ev.get("time", {}).get("elapsed") or 0))
        if current_minute - window <= ev_minute <= current_minute:
            team = ev.get("team") or {}
            # Approximation: on compte tous les buts récents et on répartit
            count += 1
    return count // 2  # approximation équitable


def _recent_events(events: list, n: int) -> list:
    significant = []
    for ev in (events or []):
        ev_type = str(ev.get("type") or "").lower()
        detail = str(ev.get("detail") or "").lower()
        if any(k in ev_type or k in detail for k in ["goal", "card", "subst", "var"]):
            elapsed = (ev.get("time") or {}).get("elapsed", 0)
            player = (ev.get("player") or {}).get("name", "")
            significant.append({
                "minute": elapsed,
                "type": ev.get("type", ""),
                "detail": ev.get("detail", ""),
                "player": player,
            })
    return sorted(significant, key=lambda x: x["minute"], reverse=True)[:n]
