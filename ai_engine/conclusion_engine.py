"""
Conclusion Engine
Génère des conclusions footballistiquement cohérentes.
Interdit les conclusions absurdes (ex: "match fermé" sur 1-1 à 36').
"""
from typing import Dict, Any, Optional


def generate_conclusion(
    home_name: str,
    away_name: str,
    home_goals: int,
    away_goals: int,
    minute: int,
    home_win_prob: float,
    draw_prob: float,
    away_win_prob: float,
    btts_result: Dict[str, Any],
    over_under: Dict[str, Any],
    momentum: Dict[str, Any],
    is_live: bool,
    home_xg: float,
    away_xg: float,
    confidence: Dict[str, Any],
) -> str:
    """
    Génère une conclusion textuelle cohérente et footballistiquement logique.
    """
    total_goals = home_goals + away_goals
    both_scored = home_goals > 0 and away_goals > 0
    score_diff = home_goals - away_goals
    remaining = max(0, 90 - minute)
    conf_label = confidence.get("label", "Moyen")

    lines = []

    # ── Contexte du match ───────────────────────────────────────────────────
    if is_live:
        score_str = f"{home_goals}-{away_goals} à la {minute}'"
        lines.append(f"**Contexte live**: Score {score_str}, {remaining} minutes à jouer.")
    else:
        lines.append(f"**Analyse pré-match**: {home_name} (domicile) vs {away_name} (extérieur).")

    # ── Buts déjà marqués ───────────────────────────────────────────────────
    if is_live and total_goals > 0:
        goals_rhythm = total_goals / max(minute, 1) * 90
        if goals_rhythm >= 3.5:
            lines.append(f"⚡ Rythme offensif très élevé ({total_goals} buts en {minute}' — projection {goals_rhythm:.1f} buts/90 min).")
        elif goals_rhythm >= 2.0:
            lines.append(f"🔥 Match ouvert, rythme élevé ({total_goals} buts, projection {goals_rhythm:.1f} buts/90 min).")
        else:
            lines.append(f"⚽ {total_goals} but(s) marqué(s) en {minute} minutes.")

    # ── BTTS ────────────────────────────────────────────────────────────────
    if both_scored:
        lines.append("✅ BTTS garanti: les deux équipes ont déjà trouvé le filet.")
    elif is_live and minute > 60:
        if away_goals == 0 and home_goals > 0:
            lines.append(f"⚠️ {away_name} n'a pas encore marqué avec {remaining} minutes restantes — BTTS en danger.")
        elif home_goals == 0 and away_goals > 0:
            lines.append(f"⚠️ {home_name} n'a pas encore marqué avec {remaining} minutes restantes — BTTS en danger.")

    # ── État du score ───────────────────────────────────────────────────────
    if is_live:
        if score_diff > 1:
            lines.append(f"🛡️ {home_name} mène confortablement ({score_diff} buts d'écart).")
        elif score_diff == 1:
            lines.append(f"⚔️ {home_name} mène d'un but — résultat incertain avec {remaining} min à jouer.")
        elif score_diff == 0:
            if total_goals == 0:
                lines.append(f"⚖️ Match nul vierge (0-0). Les deux équipes se neutralisent.")
            else:
                lines.append(f"⚖️ Match nul {home_goals}-{away_goals} — la pression peut tout changer.")
        elif score_diff == -1:
            lines.append(f"⚔️ {away_name} mène d'un but — {home_name} doit réagir.")
        else:
            lines.append(f"🛡️ {away_name} mène confortablement ({abs(score_diff)} buts d'écart).")

    # ── Probabilités finales ────────────────────────────────────────────────
    max_prob = max(home_win_prob, draw_prob, away_win_prob)
    if home_win_prob == max_prob:
        lines.append(f"🏠 **{home_name} favori** pour la victoire finale ({home_win_prob:.0%}).")
    elif away_win_prob == max_prob:
        lines.append(f"✈️ **{away_name} favori** pour la victoire finale ({away_win_prob:.0%}).")
    else:
        lines.append(f"🤝 **Match nul probable** ({draw_prob:.0%}) — forces en présence équilibrées.")

    # ── Over/Under clé ───────────────────────────────────────────────────────
    ou_25 = over_under.get("over_25", {})
    if ou_25.get("status") == "won":
        lines.append("📊 Over 2.5 déjà garanti.")
    elif ou_25.get("prob", 0) >= 0.70:
        lines.append(f"📊 Over 2.5 très probable ({ou_25['prob']:.0%}).")
    elif ou_25.get("prob", 1) <= 0.30:
        lines.append(f"📊 Under 2.5 attendu ({1 - ou_25.get('prob',0):.0%}).")

    # ── Momentum ────────────────────────────────────────────────────────────
    if momentum.get("data_available"):
        lines.append(f"⚡ Momentum: {momentum.get('label', '')}.")

    # ── Confiance globale ────────────────────────────────────────────────────
    lines.append(f"🎯 **Fiabilité du modèle**: {conf_label}.")

    return "\n\n".join(lines)
