"""
Confidence Engine
Calcule une confiance globale cohérente selon la qualité des données.
Interdit les contradictions (Très fort + Faible simultanés).
"""
from typing import Dict, Any, Optional, Tuple


CONFIDENCE_THRESHOLDS = [
    (0.78, "Très fort", "💎", "#00d4ff"),
    (0.62, "Fort",      "🟢", "#00cc44"),
    (0.48, "Moyen",     "🟡", "#ffaa00"),
    (0.00, "Faible",    "🔴", "#ff4444"),
]


def get_level(prob: float) -> Tuple[str, str, str]:
    """Retourne (label, icon, color) selon une probabilité."""
    for threshold, label, icon, color in CONFIDENCE_THRESHOLDS:
        if prob >= threshold:
            return label, icon, color
    return "Faible", "🔴", "#ff4444"


def compute_global_confidence(
    home_win_prob: float,
    draw_prob: float,
    away_win_prob: float,
    is_live: bool,
    minute: int,
    has_live_stats: bool,
    has_form_data: bool,
    has_h2h: bool,
    data_quality_score: float = 1.0,
    certainty_override: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calcule la confiance globale du modèle de façon cohérente.

    Règles:
    - Si certainty_override fourni (entropie Shannon), il pilote le score de base
      pour refléter l'incertitude réelle du match, pas juste la prob max
    - Pénalisée si données manquantes
    - En live, bonus modéré avec la minute
    - Une seule confiance globale — jamais de contradiction entre sections
    - Un faible avantage statistique ne peut pas produire Très fort
    """
    import math as _m

    # Score de base: entropie Shannon si dispo, sinon prob max
    if certainty_override is not None:
        # certainty = 1 - entropie_normalisée → mesure réelle de la certitude
        # Régression: même une certitude parfaite → max 0.80 (le modèle reste incertain)
        base_score = min(0.80, certainty_override * 0.85)
    else:
        max_prob = max(home_win_prob, draw_prob, away_win_prob)
        # Régression vers le centre: 33%→0, 100%→0.67 (jamais 1.0 depuis les probs seules)
        base_score = min(0.72, (max_prob - 1/3) / (2/3) * 0.72) if max_prob > 1/3 else 0.0

    # Bonus live modéré: max +10% à 90'
    live_bonus = 0.0
    if is_live and minute > 0:
        live_bonus = min(0.10, minute / 90.0 * 0.12)

    # Pénalité données manquantes
    data_penalty = 0.0
    if not has_live_stats and is_live:
        data_penalty += 0.08
    if not has_form_data:
        data_penalty += 0.05
    if not has_h2h:
        data_penalty += 0.02

    # Qualité données externe
    quality_factor = max(0.5, min(1.0, data_quality_score))

    final_score = (base_score + live_bonus - data_penalty) * quality_factor
    final_score = max(0.0, min(1.0, final_score))

    label, icon, color = get_level(final_score)

    return {
        "score": round(final_score * 100),
        "label": label,
        "icon": icon,
        "color": color,
        "has_live_stats": has_live_stats,
        "data_penalty": round(data_penalty * 100),
        "live_bonus": round(live_bonus * 100),
    }


def uniform_confidence_for_market(market_prob: float, global_conf: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Retourne la confiance d'un marché en cohérence avec la confiance globale.
    Un marché ne peut pas avoir un niveau SUPÉRIEUR à la confiance globale.
    """
    market_label, market_icon, market_color = get_level(market_prob)
    global_label = global_conf.get("label", "Faible")

    order = ["Très fort", "Fort", "Moyen", "Faible"]
    global_rank = order.index(global_label) if global_label in order else 3
    market_rank = order.index(market_label) if market_label in order else 3

    # Le marché ne peut pas être plus fort que la confiance globale
    if market_rank < global_rank:
        capped_label = global_label
        _, capped_icon, capped_color = get_level(global_conf["score"] / 100.0)
        return capped_label, capped_icon, capped_color

    return market_label, market_icon, market_color
