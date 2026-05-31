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

    home_reds, away_reds, red_events = red_cards(events)

    # ─ Impact carton rouge calibré selon le temps restant ─────────────────────
    # Plus le carton est tard, plus il est décisif (fin de match avec 10)
    # Impact par carton : [0-30'] = 0.10 | [30-60'] = 0.18 | [60-75'] = 0.26 | [75'+] = 0.38
    def _card_weight(card_minute: int) -> float:
        if card_minute >= 75:
            return 0.38
        elif card_minute >= 60:
            return 0.26
        elif card_minute >= 30:
            return 0.18
        return 0.10

    home_red_impact = sum(_card_weight(m) for side, m in red_events if side == "home")
    away_red_impact = sum(_card_weight(m) for side, m in red_events if side == "away")

    # red_card_shift > 0 = domicile a l'avantage (ext a un rouge)
    # red_card_shift < 0 = ext a l'avantage (dom a un rouge)
    red_card_shift = away_red_impact - home_red_impact

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
        "home_red_impact": home_red_impact,
        "away_red_impact": away_red_impact,
        "score_diff": score_diff,
        "state": state,
        "phase": phase,
        "home_red_cards": home_reds,
        "away_red_cards": away_reds,
        "red_card_events": red_events,
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


def red_cards(events: List[Dict[str, Any]]) -> Tuple[int, int, List[Tuple[str, int]]]:
    """
    Détecte les cartons rouges depuis les événements API-Football.
    Retourne (home_reds, away_reds, [(side, minute), ...])
    Détecte: Red Card, Yellow Red Card (deuxième jaune = expulsion).
    """
    home_reds = away_reds = 0
    red_event_list: List[Tuple[str, int]] = []

    for event in events or []:
        ev_type   = str(event.get("type")   or "").lower().strip()
        ev_detail = str(event.get("detail") or "").lower().strip()

        # Types carton rouge API-Football:
        # type="Card", detail="Red Card" ou "Yellow Red Card"
        is_red = (
            (ev_type == "card" and ("red card" in ev_detail or "yellow red" in ev_detail))
            or (ev_type == "red card")
            or ("red card" in ev_type)
        )
        if not is_red:
            continue

        team = event.get("team") or {}
        team_id = team.get("id")
        # L'API retourne home/away dans event.get("home") ou via position dans lineup
        # On se base sur le champ "comments" s'il existe, sinon sur l'ordre des équipes
        comments = str(event.get("comments") or "").lower()
        ev_minute = int((event.get("time") or {}).get("elapsed") or 0)

        # Déterminer le camp — l'API met home/away team dans fixture.teams
        # Dans les events, "team" contient l'objet de l'équipe concernée
        # On regarde si c'est l'id domicile ou extérieur
        # Fallback: comments "away" = ext, sinon dom
        if comments == "away" or comments == "visitor":
            side = "away"
            away_reds += 1
        elif comments in ("home", "local"):
            side = "home"
            home_reds += 1
        else:
            # Sans commentaire clair, on cherche "home" dans le nom de l'équipe
            # via la clé 'home' injectée par certaines réponses
            is_home_flag = event.get("is_home")
            if is_home_flag is True:
                side = "home"
                home_reds += 1
            elif is_home_flag is False:
                side = "away"
                away_reds += 1
            else:
                # Défaut : inconnu, on l'ignore plutôt que d'imputer au mauvais camp
                continue

        red_event_list.append((side, ev_minute))

    return home_reds, away_reds, red_event_list


def dynamic_lambdas(base_home_xg: float, base_away_xg: float, context: Dict[str, Any]) -> Tuple[float, float]:
    if not context or not context.get("is_live"):
        return base_home_xg, base_away_xg

    time_factor = context.get("time_factor", 1.0)
    momentum    = context.get("momentum", 0.0)
    score_diff  = context.get("score_diff", 0)

    # ─ Impact carton rouge : multiplicatif, calibré par impact temporel ─────
    # home_red_impact = somme des poids des cartons reçus par le domicile
    # away_red_impact = somme des poids des cartons reçus par l'extérieur
    home_red_impact = context.get("home_red_impact", 0.0)
    away_red_impact = context.get("away_red_impact", 0.0)

    # Réduction xG de l'équipe réduite — plafoné à -65% pour éviter xG=0
    # Formule : réduction = impact * 1.4, clamped [0, 0.65]
    home_red_penalty = clamp(home_red_impact * 1.4, 0.0, 0.65)
    away_red_penalty = clamp(away_red_impact * 1.4, 0.0, 0.65)

    home_remaining = base_home_xg * time_factor
    away_remaining = base_away_xg * time_factor

    # Momentum
    home_remaining *= 1.0 + max(momentum, 0.0) * 0.42
    away_remaining *= 1.0 + max(-momentum, 0.0) * 0.42

    # Carton rouge : réduit xG de l'équipe qui joue à 10
    home_remaining *= (1.0 - home_red_penalty)
    away_remaining *= (1.0 - away_red_penalty)

    # Contexte score
    if score_diff > 0:
        home_remaining *= 0.86
        away_remaining *= 1.18
    elif score_diff < 0:
        home_remaining *= 1.18
        away_remaining *= 0.86

    return round(clamp(home_remaining, 0.01, 3.5), 2), round(clamp(away_remaining, 0.01, 3.5), 2)
