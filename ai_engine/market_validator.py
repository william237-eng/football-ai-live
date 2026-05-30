"""
Market Validator Engine
Valide les marchés de paris en fonction du score actuel.
Les marchés déjà gagnés = 100%, déjà perdus = 0%. Jamais recalculés.
"""
from typing import Dict, Any, Optional


def validate_markets(
    markets: Dict[str, float],
    home_goals: int,
    away_goals: int,
    is_live: bool = True,
) -> Dict[str, float]:
    """
    Corrige les probabilités des marchés en fonction du score actuel.
    Retourne un dict avec les probabilités corrigées.
    """
    if not is_live:
        return markets

    total_goals = home_goals + away_goals
    both_scored = home_goals > 0 and away_goals > 0
    result = dict(markets)

    # ── BTTS ────────────────────────────────────────────────────────────────
    if both_scored:
        result["btts_yes"] = 1.0
        result["btts_no"] = 0.0
    elif home_goals > 0 or away_goals > 0:
        # Une équipe a marqué, l'autre pas encore — BTTS possible mais pas garanti
        # Ne pas écraser, laisser le moteur Poisson gérer le restant
        pass

    # ── OVER / UNDER ─────────────────────────────────────────────────────────
    for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
        key_over = f"over_{str(threshold).replace('.', '')}"
        key_under = f"under_{str(threshold).replace('.', '')}"
        if total_goals > threshold:
            result[key_over] = 1.0
            result[key_under] = 0.0
        elif total_goals == threshold:
            # Exactement sur le seuil: Under déjà perdu si on depasse
            pass  # Poisson gère le reste du match

    # ── 1X2 : impossible de perdre si on mène ───────────────────────────────
    score_diff = home_goals - away_goals
    minute_passed = markets.get("_minute", 0)
    if minute_passed >= 90:
        # Match terminé
        if score_diff > 0:
            result["home_win"] = 1.0
            result["draw"] = 0.0
            result["away_win"] = 0.0
        elif score_diff < 0:
            result["home_win"] = 0.0
            result["draw"] = 0.0
            result["away_win"] = 1.0
        else:
            result["home_win"] = 0.0
            result["draw"] = 1.0
            result["away_win"] = 0.0

    return result


def get_locked_markets(home_goals: int, away_goals: int, minute: int) -> Dict[str, Any]:
    """
    Retourne les marchés verrouillés (déjà déterminés) avec leur statut.
    status: 'won', 'lost', 'open'
    """
    total = home_goals + away_goals
    both_scored = home_goals > 0 and away_goals > 0
    locked = {}

    for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
        key = f"over_{threshold}"
        if total > threshold:
            locked[key] = {"status": "won", "prob": 1.0, "label": f"Over {threshold}"}
            locked[f"under_{threshold}"] = {"status": "lost", "prob": 0.0, "label": f"Under {threshold}"}
        else:
            locked[key] = {"status": "open"}
            locked[f"under_{threshold}"] = {"status": "open"}

    if both_scored:
        locked["btts_yes"] = {"status": "won", "prob": 1.0, "label": "BTTS Oui"}
        locked["btts_no"] = {"status": "lost", "prob": 0.0, "label": "BTTS Non"}
    else:
        locked["btts_yes"] = {"status": "open"}
        locked["btts_no"] = {"status": "open"}

    return locked
