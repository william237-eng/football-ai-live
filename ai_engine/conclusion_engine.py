"""
Conclusion Engine
Génère des conclusions footballistiquement cohérentes.
Interdit les conclusions absurdes (ex: "match fermé" sur 1-1 à 36').
Produit un VERDICT FINAL clair avec le favori et le marché recommandé.
"""
from typing import Dict, Any, Optional, Tuple


def _pick_market(
    home_name: str,
    away_name: str,
    home_win_prob: float,
    draw_prob: float,
    away_win_prob: float,
    btts_yes_prob: float,
    over25_prob: float,
    is_live: bool,
    home_goals: int,
    away_goals: int,
    minute: int,
) -> Tuple[str, str, float]:
    """
    Choisit le MEILLEUR marché à jouer selon les probabilités.
    Retourne (nom_marché, conseil, probabilité).
    """
    total_goals = home_goals + away_goals
    remaining = max(0, 90 - minute)

    candidates = []

    # Victoire nette (>60%)
    if home_win_prob >= 0.60:
        candidates.append(("Victoire " + home_name, f"Victoire {home_name}", home_win_prob))
    if away_win_prob >= 0.60:
        candidates.append(("Victoire " + away_name, f"Victoire {away_name}", away_win_prob))

    # Double chance (>72%) si pas de victoire franche
    dc_1x = home_win_prob + draw_prob
    dc_x2 = draw_prob + away_win_prob
    dc_12  = home_win_prob + away_win_prob
    if dc_1x >= 0.72 and home_win_prob < 0.60:
        candidates.append((f"{home_name} ou Nul (1X)", f"Double Chance 1X", dc_1x))
    if dc_x2 >= 0.72 and away_win_prob < 0.60:
        candidates.append((f"{away_name} ou Nul (X2)", f"Double Chance X2", dc_x2))
    if dc_12 >= 0.72 and home_win_prob < 0.60 and away_win_prob < 0.60:
        candidates.append((f"{home_name} ou {away_name} (12)", f"Double Chance 12", dc_12))

    # GG / BTTS (>62%)
    if btts_yes_prob >= 0.62 and not (is_live and (home_goals == 0 and minute > 70) or (away_goals == 0 and minute > 70)):
        candidates.append(("Les deux équipes marquent (GG)", "GG — BTTS Oui", btts_yes_prob))

    # Over 2.5 (>60%), conditionnel live
    if not is_live and over25_prob >= 0.60:
        candidates.append(("Over 2.5 buts", "Over 2.5 buts", over25_prob))
    elif is_live and total_goals < 3 and remaining >= 20 and over25_prob >= 0.65:
        candidates.append((f"Over 2.5 buts (encore {3 - total_goals} but(s) requis)", "Over 2.5 buts", over25_prob))

    if not candidates:
        # Fallback : la probabilité maximale
        best_prob = max(home_win_prob, draw_prob, away_win_prob)
        if home_win_prob == best_prob:
            return f"Victoire {home_name}", f"Victoire {home_name}", home_win_prob
        elif away_win_prob == best_prob:
            return f"Victoire {away_name}", f"Victoire {away_name}", away_win_prob
        else:
            return "Match nul", "Match nul", draw_prob

    # Choisir le meilleur candidat
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[0]


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
    home_red_cards: int = 0,
    away_red_cards: int = 0,
    home_red_impact: float = 0.0,
    away_red_impact: float = 0.0,
) -> str:
    """
    Génère une conclusion textuelle cohérente et footballistiquement logique.
    Inclut un VERDICT FINAL avec le marché recommandé.
    """
    total_goals = home_goals + away_goals
    both_scored = home_goals > 0 and away_goals > 0
    score_diff = home_goals - away_goals
    remaining = max(0, 90 - minute)
    conf_label = confidence.get("label", "Moyen")
    conf_score = confidence.get("score", 50)

    btts_yes_prob = btts_result.get("yes_prob", 0.5)
    ou_25 = over_under.get("over_25", over_under.get("over_25", {}))
    over25_prob = ou_25.get("prob", 0.0) if isinstance(ou_25, dict) else 0.0

    lines = []

    # ── Contexte du match ───────────────────────────────────────────────────
    if is_live:
        score_str = f"{home_goals}-{away_goals} à la {minute}'"
        lines.append(f"**Contexte live** : Score {score_str}, {remaining} minutes restantes.")
    else:
        lines.append(f"**Analyse pré-match** : {home_name} (domicile) vs {away_name} (extérieur).")

    # ── Alerte carton rouge — intelligente et temporelle ────────────────────
    if is_live and (home_red_cards > 0 or away_red_cards > 0):
        if home_red_cards > 0 and away_red_cards > 0:
            lines.append(
                f"🟥 **Double expulsion** : {home_name} ({home_red_cards}) et {away_name} ({away_red_cards}) "
                f"jouent à effectifs réduits — match fermé attendu, peu de buts probables."
            )
        elif home_red_cards > 0:
            if remaining >= 40:
                severity, impact_txt = "🚨 Handicap sévère", "impact majeur sur les 40+ minutes restantes"
            elif remaining >= 20:
                severity, impact_txt = "⚠️ Handicap notable", "pèse encore significativement sur le résultat"
            else:
                severity, impact_txt = "🟡 Handicap réduit", f"impact limité ({remaining} min restantes)"
            red_xg_pct = int(min(65, home_red_impact * 1.4 * 100))
            lines.append(
                f"🟥 **{home_name} réduit à {11 - home_red_cards}** — {severity} : {impact_txt}. "
                f"xG dom. réduit de ~{red_xg_pct}% — {away_name} fortement avantagé."
            )
        else:
            if remaining >= 40:
                severity, impact_txt = "🚨 Handicap sévère", "impact majeur sur les 40+ minutes restantes"
            elif remaining >= 20:
                severity, impact_txt = "⚠️ Handicap notable", "pèse encore significativement sur le résultat"
            else:
                severity, impact_txt = "🟡 Handicap réduit", f"impact limité ({remaining} min restantes)"
            red_xg_pct = int(min(65, away_red_impact * 1.4 * 100))
            lines.append(
                f"🟥 **{away_name} réduit à {11 - away_red_cards}** — {severity} : {impact_txt}. "
                f"xG ext. réduit de ~{red_xg_pct}% — {home_name} fortement avantagé."
            )

    # ── Rythme offensif live ────────────────────────────────────────────────
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
        lines.append("✅ BTTS garanti : les deux équipes ont déjà trouvé le filet.")
    elif is_live and minute > 60:
        if away_goals == 0 and home_goals > 0:
            lines.append(f"⚠️ {away_name} n'a pas encore marqué ({remaining} min restantes) — BTTS compromis.")
        elif home_goals == 0 and away_goals > 0:
            lines.append(f"⚠️ {home_name} n'a pas encore marqué ({remaining} min restantes) — BTTS compromis.")

    # ── État du score live ──────────────────────────────────────────────────
    if is_live:
        if score_diff > 1:
            lines.append(f"🛡️ {home_name} mène confortablement ({score_diff} buts d'écart).")
        elif score_diff == 1:
            lines.append(f"⚔️ {home_name} mène d'un but — résultat incertain ({remaining} min).")
        elif score_diff == 0:
            if total_goals == 0:
                lines.append("⚖️ Match nul vierge (0-0). Les deux équipes se neutralisent.")
            else:
                lines.append(f"⚖️ Match nul {home_goals}-{away_goals} — la pression peut tout changer.")
        elif score_diff == -1:
            lines.append(f"⚔️ {away_name} mène d'un but — {home_name} doit réagir.")
        else:
            lines.append(f"🛡️ {away_name} mène confortablement ({abs(score_diff)} buts d'écart).")

    # ── Probabilités 1X2 ────────────────────────────────────────────────────
    max_prob = max(home_win_prob, draw_prob, away_win_prob)
    if home_win_prob == max_prob:
        lines.append(f"🏠 **{home_name} favori** pour la victoire finale ({home_win_prob:.0%}).")
    elif away_win_prob == max_prob:
        lines.append(f"✈️ **{away_name} favori** pour la victoire finale ({away_win_prob:.0%}).")
    else:
        lines.append(f"🤝 **Match nul probable** ({draw_prob:.0%}) — forces équilibrées.")

    # ── Over/Under ──────────────────────────────────────────────────────────
    if isinstance(ou_25, dict):
        if ou_25.get("status") == "won":
            lines.append("📊 Over 2.5 déjà garanti.")
        elif over25_prob >= 0.70:
            lines.append(f"📊 Over 2.5 très probable ({over25_prob:.0%}).")
        elif over25_prob <= 0.30:
            lines.append(f"📊 Under 2.5 attendu ({1-over25_prob:.0%}).")

    # ── Momentum ────────────────────────────────────────────────────────────
    if momentum.get("data_available"):
        lines.append(f"⚡ Momentum : {momentum.get('label', '')}.")

    # ── Confiance ───────────────────────────────────────────────────────────
    lines.append(f"🎯 **Fiabilité du modèle** : {conf_label} ({conf_score}%).")

    # ══════════════════════════════════════════════════════════════════════
    # VERDICT FINAL — Marché recommandé
    # ══════════════════════════════════════════════════════════════════════
    market_label, market_conseil, market_prob = _pick_market(
        home_name, away_name,
        home_win_prob, draw_prob, away_win_prob,
        btts_yes_prob, over25_prob,
        is_live, home_goals, away_goals, minute,
    )

    verdict_parts = [
        f"\n\n---\n\n",
        f"### 🏆 VERDICT FINAL\n\n",
        f"**Marché recommandé** : **{market_conseil}**\n\n",
        f"**Probabilité estimée** : **{market_prob:.0%}**\n\n",
    ]

    # Justification du verdict
    if market_prob >= 0.80:
        verdict_parts.append("💎 Confiance très élevée — signal fort du modèle.")
    elif market_prob >= 0.70:
        verdict_parts.append("✅ Confiance élevée — signal fiable.")
    elif market_prob >= 0.60:
        verdict_parts.append("🟡 Confiance modérée — jouer avec prudence.")
    else:
        verdict_parts.append("⚠️ Signal faible — éviter ou miser symboliquement.")

    lines.append("".join(verdict_parts))

    return "\n\n".join(lines)
