"""
Bet Suggestion Engine
Analyse le contexte live et suggère des paris intelligents
"""
from typing import Any, Dict, List, Tuple


def analyze_bet_opportunities(
    live_context: Dict[str, Any],
    ai_result: Dict[str, Any],
    home_form: Dict[str, float],
    away_form: Dict[str, float],
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyse complète pour générer des suggestions de paris
    """
    suggestions = []

    # Récupérer les probabilités
    probs = ai_result.get("probabilities", {})
    home_win_prob = probs.get("home_win", 33.0)
    draw_prob = probs.get("draw", 33.0)
    away_win_prob = probs.get("away_win", 33.0)

    # Récupérer les xG
    home_xg = ai_result.get("home_xg", 1.2)
    away_xg = ai_result.get("away_xg", 1.0)
    total_xg = home_xg + away_xg

    # Contexte live
    is_live = live_context.get("is_live", False)
    current_home = live_context.get("home_goals", 0)
    current_away = live_context.get("away_goals", 0)
    total_goals = current_home + current_away
    minute = live_context.get("minute", 0)
    remaining = max(0, 90 - minute)
    momentum = live_context.get("momentum", 0.0)
    home_pressure = live_context.get("home_pressure", 50.0)
    away_pressure = live_context.get("away_pressure", 50.0)

    # Détection des cartons rouges
    red_cards_home = live_context.get("home_red_cards", 0)
    red_cards_away = live_context.get("away_red_cards", 0)

    # ========== SUGGESTION 1: RÉSULTAT FINAL ==========
    if home_win_prob >= 55:
        suggestions.append({
            "type": "1X2",
            "bet": "Victoire domicile",
            "confidence": home_win_prob,
            "risk": "Moyen" if home_win_prob < 65 else "Faible",
            "logic": f"Domicile fort ({home_win_prob:.0f}% probabilité, Elo avantage)",
        })
    elif away_win_prob >= 55:
        suggestions.append({
            "type": "1X2",
            "bet": "Victoire extérieur",
            "confidence": away_win_prob,
            "risk": "Moyen" if away_win_prob < 65 else "Faible",
            "logic": f"Extérieur favori ({away_win_prob:.0f}% probabilité)",
        })
    elif draw_prob >= 35:
        suggestions.append({
            "type": "1X2",
            "bet": "Double chance: Domicile/Nul",
            "confidence": home_win_prob + draw_prob,
            "risk": "Faible",
            "logic": f"Match équilibré, nul probable ({draw_prob:.0f}%)",
        })

    # ========== SUGGESTION 2: BUTS (OVER/UNDER) ==========
    # Analyser le rythme offensif
    offensive_tempo = analyze_offensive_tempo(
        home_stats, away_stats, minute, total_goals, home_xg + away_xg
    )

    if is_live:
        # En live, analyser le rythme actuel
        if minute > 60 and total_goals == 0 and offensive_tempo["intensity"] > 0.6:
            suggestions.append({
                "type": "Buts",
                "bet": "Over 1.5 buts",
                "confidence": 65.0,
                "risk": "Moyen",
                "logic": f"Match ouvert, {offensive_tempo['shots']} tirs, pression montante",
            })

        if minute > 70 and total_goals >= 2:
            if offensive_tempo["intensity"] > 0.7:
                suggestions.append({
                    "type": "Buts",
                    "bet": "Over 3.5 buts",
                    "confidence": 55.0,
                    "risk": "Élevé",
                    "logic": f"Rythme élevé ({total_goals} buts à {minute}'), match ouvert",
                })
            else:
                suggestions.append({
                    "type": "Buts",
                    "bet": "Under 3.5 buts",
                    "confidence": 70.0,
                    "risk": "Faible",
                    "logic": f"Match se calme, {total_goals} buts mais rythme diminue",
                })

        if total_goals >= 1 and minute > 50 and offensive_tempo["both_attack"]:
            suggestions.append({
                "type": "Buts",
                "bet": "BTTS (Les 2 équipes marquent)",
                "confidence": 60.0,
                "risk": "Moyen",
                "logic": f"Attaque active des 2 côtés à {minute}'",
            })
    else:
        # Pré-match
        if total_xg > 2.8:
            suggestions.append({
                "type": "Buts",
                "bet": "Over 2.5 buts",
                "confidence": min(75.0, total_xg * 25),
                "risk": "Moyen",
                "logic": f"Projection offensive forte (xG total: {total_xg:.1f})",
            })
        elif total_xg < 2.0:
            suggestions.append({
                "type": "Buts",
                "bet": "Under 2.5 buts",
                "confidence": 70.0,
                "risk": "Faible",
                "logic": f"Match probablement fermé (xG total: {total_xg:.1f})",
            })

    # ========== SUGGESTION 3: CORNERS ==========
    corner_pressure = analyze_corner_pressure(home_stats, away_stats, minute)
    if corner_pressure["total_expected"] > 9:
        suggestions.append({
            "type": "Corners",
            "bet": "Over 9.5 corners",
            "confidence": min(70.0, corner_pressure["total_expected"] * 7),
            "risk": "Moyen",
            "logic": f"Pression offensive élevée, {corner_pressure['home']:.0f} corners attendus",
        })

    # ========== SUGGESTION 4: PROCHAIN BUT (LIVE) ==========
    if is_live and minute > 0 and remaining > 15:
        next_goal = analyze_next_goal_probability(
            live_context, home_xg, away_xg, momentum, home_pressure, away_pressure
        )
        if next_goal["probability"] > 50:
            suggestions.append({
                "type": "Live",
                "bet": f"Prochain but: {next_goal['team']}",
                "confidence": next_goal["probability"],
                "risk": "Moyen",
                "logic": next_goal["reason"],
            })

    # ========== SUGGESTION 5: DOUBLE CHANCE ==========
    if home_win_prob + draw_prob >= 70:
        suggestions.append({
            "type": "Double chance",
            "bet": "1X (Domicile ou Nul)",
            "confidence": home_win_prob + draw_prob,
            "risk": "Faible",
            "logic": f"Domicile solide ({home_win_prob:.0f}%) + nul ({draw_prob:.0f}%)",
        })
    elif away_win_prob + draw_prob >= 70:
        suggestions.append({
            "type": "Double chance",
            "bet": "X2 (Extérieur ou Nul)",
            "confidence": away_win_prob + draw_prob,
            "risk": "Faible",
            "logic": f"Extérieur compétitif ({away_win_prob:.0f}%) + nul ({draw_prob:.0f}%)",
        })

    # ========== CONSTRUCTION DE LA CONCLUSION ==========
    conclusion = build_final_conclusion(
        live_context, ai_result, suggestions, offensive_tempo, is_live
    )

    return {
        "suggestions": sorted(suggestions, key=lambda x: x["confidence"], reverse=True),
        "conclusion": conclusion,
        "offensive_tempo": offensive_tempo,
        "confidence_level": calculate_overall_confidence(suggestions, is_live),
    }


def analyze_offensive_tempo(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    minute: int,
    total_goals: int,
    total_xg: float,
) -> Dict[str, Any]:
    """Analyse le rythme offensif actuel"""
    home_shots = get_numeric_stat(home_stats, ["Total Shots", "Shots Total"], 0)
    away_shots = get_numeric_stat(away_stats, ["Total Shots", "Shots Total"], 0)
    home_on_target = get_numeric_stat(home_stats, ["Shots on Goal", "On Target"], 0)
    away_on_target = get_numeric_stat(away_stats, ["Shots on Goal", "On Target"], 0)

    total_shots = home_shots + away_shots
    shots_per_minute = total_shots / max(1, minute) if minute > 0 else total_shots / 90

    # Intensité basée sur les tirs et les buts
    intensity = min(1.0, (shots_per_minute * 10 + total_goals * 0.15))

    # Les 2 équipes attaquent?
    both_attack = home_shots > 2 and away_shots > 2

    return {
        "intensity": intensity,
        "shots": total_shots,
        "shots_on_target": home_on_target + away_on_target,
        "both_attack": both_attack,
        "shots_per_minute": shots_per_minute,
    }


def analyze_corner_pressure(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    minute: int,
) -> Dict[str, Any]:
    """Analyse la pression corner"""
    home_corners = get_numeric_stat(home_stats, ["Corner Kicks", "Corners"], 0)
    away_corners = get_numeric_stat(away_stats, ["Corner Kicks", "Corners"], 0)

    # Projection sur 90 minutes
    factor = 90 / max(minute, 15) if minute > 0 else 1.0

    return {
        "home": home_corners * factor,
        "away": away_corners * factor,
        "total_expected": (home_corners + away_corners) * factor,
    }


def analyze_next_goal_probability(
    live_context: Dict[str, Any],
    home_xg: float,
    away_xg: float,
    momentum: float,
    home_pressure: float,
    away_pressure: float,
) -> Dict[str, Any]:
    """Analyse la probabilité du prochain but"""
    current_home = live_context.get("home_goals", 0)
    current_away = live_context.get("away_goals", 0)
    minute = live_context.get("minute", 0)
    remaining = max(1, 90 - minute)

    # Normaliser les xG restants
    home_remaining = home_xg * (remaining / 90.0)
    away_remaining = away_xg * (remaining / 90.0)

    # Ajustement momentum
    if momentum > 0.2:
        home_remaining *= 1.25
        away_remaining *= 0.85
    elif momentum < -0.2:
        home_remaining *= 0.85
        away_remaining *= 1.25

    total_remaining = home_remaining + away_remaining
    if total_remaining == 0:
        return {"team": "Incertain", "probability": 0, "reason": "Données insuffisantes"}

    home_prob = (home_remaining / total_remaining) * 100
    away_prob = (away_remaining / total_remaining) * 100

    if home_prob > away_prob + 10:
        return {
            "team": "Domicile",
            "probability": home_prob,
            "reason": f"Pression offensive domicile ({home_pressure:.0f}), momentum +{momentum:.0%}",
        }
    elif away_prob > home_prob + 10:
        return {
            "team": "Extérieur",
            "probability": away_prob,
            "reason": f"Pression offensive extérieur ({away_pressure:.0f}), momentum -{abs(momentum):.0%}",
        }
    else:
        return {
            "team": "Équilibré",
            "probability": max(home_prob, away_prob),
            "reason": "Pression équilibrée des 2 côtés",
        }


def build_final_conclusion(
    live_context: Dict[str, Any],
    ai_result: Dict[str, Any],
    suggestions: List[Dict[str, Any]],
    offensive_tempo: Dict[str, Any],
    is_live: bool,
) -> str:
    """Construit la conclusion IA finale"""
    parts = []

    # Analyse du contexte
    minute = live_context.get("minute", 0)
    state = live_context.get("state", "Inconnu")
    momentum = live_context.get("momentum", 0)
    phase = live_context.get("phase", "")

    current_home = live_context.get("home_goals", 0)
    current_away = live_context.get("away_goals", 0)

    # Introduction
    if is_live:
        parts.append(f"**Analyse Live** à la {minute}e minute.")
        parts.append(f"Score actuel: {current_home}-{current_away}. {state}.")
    else:
        parts.append("**Analyse Pré-Match** basée sur les données historiques.")

    # Analyse du rythme
    intensity = offensive_tempo.get("intensity", 0.5)
    if intensity > 0.7:
        parts.append(f"🔥 Match très ouvert avec {offensive_tempo.get('shots', 0)} tirs.")
    elif intensity > 0.4:
        parts.append(f"⚖️ Rythme modéré, {offensive_tempo.get('shots', 0)} tirs enregistrés.")
    else:
        parts.append(f"🛡️ Match fermé, faible activité offensive ({offensive_tempo.get('shots', 0)} tirs).")

    # Analyse momentum
    if abs(momentum) > 0.3:
        direction = "domicile" if momentum > 0 else "extérieur"
        parts.append(f"📈 Momentum favorable à l'équipe {direction} ({abs(momentum):.0%}).")

    # Recommandation principale
    if suggestions:
        top_suggestion = suggestions[0]
        parts.append(f"\n**💡 Recommandation principale:** {top_suggestion['bet']} «{top_suggestion['type']}»")
        parts.append(f"Confiance: {top_suggestion['confidence']:.0f}% | Risque: {top_suggestion['risk']}")
        parts.append(f"🧠 Logique: {top_suggestion['logic']}")

    # Alerte si nécessaire
    if live_context.get("home_red_cards", 0) or live_context.get("away_red_cards", 0):
        parts.append("\n⚠️ **Alerte carton rouge** - La dynamique du match peut changer.")

    return "\n".join(parts)


def calculate_overall_confidence(suggestions: List[Dict[str, Any]], is_live: bool) -> str:
    """Calcule le niveau de confiance global"""
    if not suggestions:
        return "Faible"

    avg_confidence = sum(s["confidence"] for s in suggestions) / len(suggestions)
    max_confidence = max(s["confidence"] for s in suggestions)

    if max_confidence >= 70 and avg_confidence >= 60:
        return "Très fort"
    elif max_confidence >= 60:
        return "Fort"
    elif avg_confidence >= 50:
        return "Moyen"
    else:
        return "Faible"


def get_numeric_stat(stats: Dict[str, Any], aliases: List[str], default: float = 0.0) -> float:
    """Récupère une statistique numérique"""
    if not stats:
        return default
    normalized = {str(k).lower().strip(): v for k, v in stats.items()}
    for alias in aliases:
        key = alias.lower().strip()
        if key in normalized and normalized[key] is not None:
            try:
                val = str(normalized[key]).replace("%", "").strip()
                return float(val) if val else default
            except (ValueError, TypeError):
                continue
    return default
