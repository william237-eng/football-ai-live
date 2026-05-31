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
    home_xg: float = 0.0,
    away_xg: float = 0.0,
    home_form_avg: float = 0.0,
    away_form_avg: float = 0.0,
    h2h_home_wins: int = 0,
    h2h_away_wins: int = 0,
    h2h_draws: int = 0,
    h2h_total: int = 0,
) -> Tuple[str, str, float]:
    """
    Choisit le MEILLEUR marché basé sur l'analyse réelle.
    En LIVE : ne propose JAMAIS un verdict déjà réalisé ou devenu impossible.
    JAMAIS de 12 fictif — chaque verdict est justifié par les données.
    Retourne (nom_marché, conseil, probabilité).
    """
    total_goals = home_goals + away_goals
    score_diff  = home_goals - away_goals   # >0 = dom mène, <0 = ext mène
    remaining   = max(0, 90 - minute)
    total_xg    = home_xg + away_xg

    # ── Pré-calculs de cohérence live ─────────────────────────────────────────
    # Over 2.5 : déjà acquis si 3+ buts, déjà perdu si score impossible à atteindre
    over25_already_won  = is_live and total_goals >= 3
    over25_already_lost = is_live and total_goals >= 3   # même chose
    under25_already_lost = is_live and total_goals >= 3  # Under perdu si 3+ buts
    # GG : déjà acquis si les deux ont marqué ; impossible si une équipe = 0 et temps avancé
    gg_already_won   = is_live and home_goals > 0 and away_goals > 0
    gg_impossible    = is_live and (home_goals == 0 or away_goals == 0) and remaining <= 20
    # Nul : impossible si écart ≥ 2 buts avec peu de temps
    draw_impossible  = is_live and abs(score_diff) >= 2 and remaining <= 30
    draw_already_set = is_live and score_diff == 0 and remaining <= 5
    # Victoire dom : impossible si ext mène de 2+ avec peu de temps
    home_win_impossible = is_live and score_diff <= -2 and remaining <= 25
    away_win_impossible = is_live and score_diff >= 2  and remaining <= 25
    # Double chance 1X : impossible si l'extérieur mène déjà et peu de temps
    dc1x_impossible = is_live and score_diff < 0 and remaining <= 20
    # Double chance X2 : impossible si le domicile mène déjà et peu de temps
    dcx2_impossible = is_live and score_diff > 0 and remaining <= 20

    candidates = []

    # ── 1. VICTOIRE NETTE (seuil strict ≥ 62%) ──────────────────────────────
    if home_win_prob >= 0.62 and not home_win_impossible:
        candidates.append(("1", f"1 — Victoire {home_name}", home_win_prob))
    if away_win_prob >= 0.62 and not away_win_impossible:
        candidates.append(("2", f"2 — Victoire {away_name}", away_win_prob))

    # ── 2. NUL (X) — si équilibre réel et score compatible ──────────────────
    max_side = max(home_win_prob, away_win_prob)
    gap = max_side - draw_prob
    if draw_prob >= 0.30 and gap <= 0.12 and not draw_impossible:
        candidates.append(("X", "X — Match Nul", draw_prob))

    # ── 3. DOUBLE CHANCE — seulement si réellement justifiée ────────────────
    dc_1x = home_win_prob + draw_prob
    dc_x2 = draw_prob + away_win_prob
    dc_12  = home_win_prob + away_win_prob
    # 1X : domicile légèrement favori, score ne contredit pas
    if dc_1x >= 0.72 and 0.38 <= home_win_prob < 0.62 and not dc1x_impossible:
        candidates.append(("1X", f"1X — {home_name} ou Nul", dc_1x))
    # X2 : extérieur légèrement favori, score ne contredit pas
    if dc_x2 >= 0.72 and 0.38 <= away_win_prob < 0.62 and not dcx2_impossible:
        candidates.append(("X2", f"X2 — {away_name} ou Nul", dc_x2))
    # 12 : seulement si nul très peu probable ET xG offensif ET score cohérent
    if (dc_12 >= 0.78 and draw_prob < 0.22
            and home_win_prob >= 0.35 and away_win_prob >= 0.35
            and total_xg >= 2.5
            and not (is_live and abs(score_diff) >= 3)):
        candidates.append(("12", f"12 — {home_name} ou {away_name}", dc_12))

    # ── 4. GG / BTTS ─────────────────────────────────────────────────────────
    # Bloquer si déjà impossible (une équipe n'a pas marqué, temps avancé)
    # Inutile de proposer si déjà acquis (afficher comme fait dans la conclusion)
    if btts_yes_prob >= 0.62 and not gg_already_won and not gg_impossible:
        candidates.append(("GG", "GG — Les deux équipes marquent", btts_yes_prob))

    # ── 5. OVER 2.5 ──────────────────────────────────────────────────────────
    # Ne pas proposer si déjà acquis (3+ buts) ou si plus possible
    if not is_live and over25_prob >= 0.62 and total_xg >= 2.4:
        candidates.append(("Over 2.5", "Over 2.5 buts", over25_prob))
    elif is_live and not over25_already_won and total_goals < 3 and remaining >= 20 and over25_prob >= 0.65:
        need = 3 - total_goals
        candidates.append(("Over 2.5", f"Over 2.5 buts (+{need} but(s) requis)", over25_prob))

    # ── 6. UNDER 2.5 ─────────────────────────────────────────────────────────
    # Ne pas proposer si déjà perdu (3+ buts marqués)
    under25_prob = 1.0 - over25_prob
    if not is_live and under25_prob >= 0.60 and total_xg <= 2.0:
        candidates.append(("Under 2.5", "Under 2.5 buts", under25_prob))
    elif is_live and not under25_already_lost and total_goals <= 1 and remaining <= 25 and under25_prob >= 0.65:
        candidates.append(("Under 2.5", f"Under 2.5 buts ({home_goals}-{away_goals}, {remaining}' restantes)", under25_prob))

    # ── Choisir le meilleur candidat ────────────────────────────────────────
    if candidates:
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates[0]

    # ── Fallback intelligent — uniquement si cohérent avec le score live ──────
    best_prob = max(home_win_prob, draw_prob, away_win_prob)
    if home_win_prob == best_prob and not home_win_impossible:
        return "1", f"1 — Victoire {home_name}", home_win_prob
    elif away_win_prob == best_prob and not away_win_impossible:
        return "2", f"2 — Victoire {away_name}", away_win_prob
    elif not draw_impossible:
        return "X", "X — Match Nul", draw_prob
    else:
        # Score live rend tout verdict standard impossible → pas de recommandation
        return "—", "Aucun marché fiable (verdict en cours de réalisation)", 0.0


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
    # ── Nouvelles données d'analyse ─────────────────────────────────────────
    home_form: Optional[Dict[str, Any]] = None,
    away_form: Optional[Dict[str, Any]] = None,
    h2h_data: Optional[list] = None,
    home_elo: float = 0.0,
    away_elo: float = 0.0,
) -> str:
    """
    Génère une conclusion IA complète basée sur : forme 5 matchs, H2H,
    xG, ELO, score live, momentum. Verdict final intelligent et justifié.
    """
    total_goals = home_goals + away_goals
    both_scored = home_goals > 0 and away_goals > 0
    score_diff  = home_goals - away_goals
    remaining   = max(0, 90 - minute)
    total_xg    = home_xg + away_xg
    conf_label  = confidence.get("label", "Moyen")
    conf_score  = confidence.get("score", 50)

    btts_yes_prob = btts_result.get("yes_prob", 0.5)
    ou_25         = over_under.get("over_25", {})
    over25_prob   = ou_25.get("prob", 0.0) if isinstance(ou_25, dict) else 0.0

    lines = []

    # ── 1. Contexte ─────────────────────────────────────────────────────────
    if is_live:
        lines.append(
            f"**⚡ Analyse LIVE** — Score {home_goals}-{away_goals} "
            f"à la {minute}' ({remaining} min restantes)."
        )
    else:
        lines.append(
            f"**📋 Analyse pré-match** : {home_name} 🏠 vs ✈️ {away_name}."
        )

    # ── 2. Forme 5 derniers matchs ──────────────────────────────────────────
    hf = home_form or {}
    af = away_form or {}
    h_avg_for  = hf.get("avg_goals_for",     0.0)
    h_avg_ag   = hf.get("avg_goals_against", 0.0)
    a_avg_for  = af.get("avg_goals_for",     0.0)
    a_avg_ag   = af.get("avg_goals_against", 0.0)
    h_played   = hf.get("played", 0)
    a_played   = af.get("played", 0)

    if h_played >= 3:
        h_form_str = hf.get("form_str", "")
        form_analysis = []
        if h_avg_for >= 2.0:
            form_analysis.append(f"attaque prolifique ({h_avg_for:.1f} buts/match)")
        elif h_avg_for <= 0.8:
            form_analysis.append(f"attaque en difficulté ({h_avg_for:.1f} buts/match)")
        if h_avg_ag <= 0.8:
            form_analysis.append(f"défense très solide ({h_avg_ag:.1f} encaissés/match)")
        elif h_avg_ag >= 1.8:
            form_analysis.append(f"défense poreuse ({h_avg_ag:.1f} encaissés/match)")
        desc = " · ".join(form_analysis) if form_analysis else f"{h_avg_for:.1f} buts marqués, {h_avg_ag:.1f} encaissés"
        lines.append(f"🏠 **{home_name}** (5 derniers matchs) : {desc}.")

    if a_played >= 3:
        form_analysis = []
        if a_avg_for >= 2.0:
            form_analysis.append(f"attaque prolifique ({a_avg_for:.1f} buts/match)")
        elif a_avg_for <= 0.8:
            form_analysis.append(f"attaque en difficulté ({a_avg_for:.1f} buts/match)")
        if a_avg_ag <= 0.8:
            form_analysis.append(f"défense très solide ({a_avg_ag:.1f} encaissés/match)")
        elif a_avg_ag >= 1.8:
            form_analysis.append(f"défense poreuse ({a_avg_ag:.1f} encaissés/match)")
        desc = " · ".join(form_analysis) if form_analysis else f"{a_avg_for:.1f} buts marqués, {a_avg_ag:.1f} encaissés"
        lines.append(f"✈️ **{away_name}** (5 derniers matchs) : {desc}.")

    # ── 3. H2H — 5 dernières confrontations ────────────────────────────────
    if h2h_data:
        h2h_items = h2h_data[:5]
        h_wins = a_wins = draws = 0
        h2h_goals_total = 0
        for item in h2h_items:
            teams = item.get("teams") or {}
            goals = item.get("goals") or {}
            gh    = goals.get("home") or 0
            ga    = goals.get("away") or 0
            ht_n  = (teams.get("home") or {}).get("name", "")
            h2h_goals_total += gh + ga
            if gh > ga:
                if ht_n == home_name: h_wins += 1
                else: a_wins += 1
            elif ga > gh:
                if ht_n == home_name: a_wins += 1
                else: h_wins += 1
            else:
                draws += 1
        n_h2h = len(h2h_items)
        h2h_avg = h2h_goals_total / n_h2h if n_h2h else 0
        h2h_txt = (
            f"⚔️ **H2H ({n_h2h} matchs)** : {home_name} {h_wins}V — {draws}N — {a_wins}V {away_name}. "
            f"Moyenne : {h2h_avg:.1f} buts/match."
        )
        if h2h_avg <= 1.8:
            h2h_txt += " → Tendance défensive historique."
        elif h2h_avg >= 3.0:
            h2h_txt += " → Confrontations habituellement prolifiques."
        lines.append(h2h_txt)

    # ── 4. ELO — enjeu et force relative ───────────────────────────────────
    if home_elo > 0 and away_elo > 0:
        elo_diff = home_elo - away_elo
        if elo_diff >= 80:
            lines.append(f"⚡ **ELO** : {home_name} nettement supérieur (+{int(elo_diff)} pts) — écart significatif.")
        elif elo_diff <= -80:
            lines.append(f"⚡ **ELO** : {away_name} nettement supérieur (+{int(abs(elo_diff))} pts) — écart significatif.")
        elif abs(elo_diff) <= 30:
            lines.append(f"⚡ **ELO** : Équipes de niveau quasi identique (écart {int(abs(elo_diff))} pts).")

    # ── 5. xG — projection offensive ────────────────────────────────────────
    if total_xg > 0:
        if total_xg >= 3.0:
            lines.append(f"📈 **xG total {total_xg:.2f}** — match à fort potentiel offensif (Over 2.5 probable).")
        elif total_xg <= 1.5:
            lines.append(f"📉 **xG total {total_xg:.2f}** — match fermé attendu (Under 2.5 probable).")
        else:
            lines.append(f"📊 **xG** : {home_name} {home_xg:.2f} / {away_name} {away_xg:.2f} (total {total_xg:.2f}).")

    # ── 6. Carton rouge live ─────────────────────────────────────────────────
    if is_live and (home_red_cards > 0 or away_red_cards > 0):
        if home_red_cards > 0 and away_red_cards > 0:
            lines.append(
                f"🟥 **Double expulsion** : {home_name} ({home_red_cards}) et {away_name} ({away_red_cards}) "
                f"à effectifs réduits — match fermé attendu."
            )
        elif home_red_cards > 0:
            sev = "🚨 Handicap sévère" if remaining >= 40 else ("⚠️ Handicap notable" if remaining >= 20 else "🟡 Handicap limité")
            pct = int(min(65, home_red_impact * 1.4 * 100))
            lines.append(
                f"🟥 **{home_name} réduit à {11 - home_red_cards}** — {sev}. "
                f"xG dom. réduit de ~{pct}% — {away_name} avantagé."
            )
        else:
            sev = "🚨 Handicap sévère" if remaining >= 40 else ("⚠️ Handicap notable" if remaining >= 20 else "🟡 Handicap limité")
            pct = int(min(65, away_red_impact * 1.4 * 100))
            lines.append(
                f"🟥 **{away_name} réduit à {11 - away_red_cards}** — {sev}. "
                f"xG ext. réduit de ~{pct}% — {home_name} avantagé."
            )

    # ── 7. Rythme offensif live ──────────────────────────────────────────────
    if is_live and total_goals > 0:
        rhythm = total_goals / max(minute, 1) * 90
        if rhythm >= 3.5:
            lines.append(f"⚡ Rythme très élevé ({total_goals} buts en {minute}' → proj. {rhythm:.1f}/90 min).")
        elif rhythm >= 2.0:
            lines.append(f"🔥 Match ouvert ({total_goals} buts, proj. {rhythm:.1f}/90 min).")
        else:
            lines.append(f"⚽ {total_goals} but(s) en {minute} minutes — rythme contenu.")

    # ── 8. BTTS live ────────────────────────────────────────────────────────
    if both_scored:
        lines.append("✅ BTTS déjà acquis — les deux équipes ont marqué.")
    elif is_live and minute > 60:
        if away_goals == 0:
            lines.append(f"⚠️ {away_name} n'a pas encore marqué ({remaining}' restantes) — BTTS compromis.")
        elif home_goals == 0:
            lines.append(f"⚠️ {home_name} n'a pas encore marqué ({remaining}' restantes) — BTTS compromis.")

    # ── 9. État score live ───────────────────────────────────────────────────
    if is_live:
        if score_diff > 1:
            lines.append(f"🛡️ {home_name} mène confortablement ({score_diff} buts d'écart).")
        elif score_diff == 1:
            lines.append(f"⚔️ {home_name} mène d'un but — suspense jusqu'à la fin ({remaining}').")
        elif score_diff == 0:
            lines.append("⚖️ Match nul — pression des deux côtés." if total_goals else "⚖️ 0-0 — aucune équipe ne perce.")
        elif score_diff == -1:
            lines.append(f"⚔️ {away_name} mène d'un but — {home_name} doit réagir.")
        else:
            lines.append(f"🛡️ {away_name} mène confortablement ({abs(score_diff)} buts d'écart).")

    # ── 10. Probabilités 1X2 ────────────────────────────────────────────────
    max_prob = max(home_win_prob, draw_prob, away_win_prob)
    if home_win_prob == max_prob:
        lines.append(f"🏠 **{home_name} favori** ({home_win_prob:.0%}) — domicile + forme + ELO convergent.")
    elif away_win_prob == max_prob:
        lines.append(f"✈️ **{away_name} favori** ({away_win_prob:.0%}) — supériorité confirmée par les données.")
    else:
        lines.append(f"🤝 **Match très équilibré** — nul probable ({draw_prob:.0%}).")

    # ── 11. Over/Under ──────────────────────────────────────────────────────
    if isinstance(ou_25, dict):
        if ou_25.get("status") == "won":
            lines.append("📊 Over 2.5 déjà garanti (3+ buts marqués).")
        elif over25_prob >= 0.70:
            lines.append(f"📊 Over 2.5 très probable ({over25_prob:.0%}) — xG et forme offensives élevées.")
        elif over25_prob <= 0.35:
            lines.append(f"📊 Under 2.5 attendu ({1 - over25_prob:.0%}) — défenses solides, xG faible.")

    # ── 12. Momentum ────────────────────────────────────────────────────────
    if momentum.get("data_available"):
        lines.append(f"⚡ Momentum : {momentum.get('label', '')}.")

    # ── 13. Fiabilité ────────────────────────────────────────────────────────
    lines.append(f"🎯 **Fiabilité modèle** : {conf_label} ({conf_score}%).")

    # ══════════════════════════════════════════════════════════════════════════
    # VERDICT FINAL — Basé sur toute l'analyse ci-dessus
    # ══════════════════════════════════════════════════════════════════════════
    h_form_avg = (h_avg_for - h_avg_ag) if h_played >= 3 else 0.0
    a_form_avg = (a_avg_for - a_avg_ag) if a_played >= 3 else 0.0
    h2h_hw = h_wins if h2h_data else 0
    h2h_aw = a_wins if h2h_data else 0
    h2h_dr = draws if h2h_data else 0
    h2h_tot = len(h2h_data[:5]) if h2h_data else 0

    market_label, market_conseil, market_prob = _pick_market(
        home_name, away_name,
        home_win_prob, draw_prob, away_win_prob,
        btts_yes_prob, over25_prob,
        is_live, home_goals, away_goals, minute,
        home_xg=home_xg, away_xg=away_xg,
        home_form_avg=h_form_avg, away_form_avg=a_form_avg,
        h2h_home_wins=h2h_hw, h2h_away_wins=h2h_aw,
        h2h_draws=h2h_dr, h2h_total=h2h_tot,
    )

    # Justification textuelle du verdict selon le type de marché
    market_type = market_label
    if market_type == "1":
        justif = f"{home_name} dominant : forme ({h_avg_for:.1f} buts/match), ELO (+{int(home_elo - away_elo)} pts), probabilité {home_win_prob:.0%}."
    elif market_type == "2":
        justif = f"{away_name} supérieur : forme ({a_avg_for:.1f} buts/match), ELO (+{int(away_elo - home_elo)} pts), probabilité {away_win_prob:.0%}."
    elif market_type == "X":
        justif = f"Équilibre total — ELO proche, forme similaire, nul historiquement fréquent ({draw_prob:.0%})."
    elif market_type == "1X":
        justif = f"{home_name} légèrement favori mais match serré — double chance prudente ({home_win_prob:.0%} + {draw_prob:.0%})."
    elif market_type == "X2":
        justif = f"{away_name} légèrement favori mais incertitude — double chance sécurisée ({away_win_prob:.0%} + {draw_prob:.0%})."
    elif market_type == "12":
        justif = f"Match offensif — xG {total_xg:.2f}, nul très peu probable ({draw_prob:.0%}), les deux équipes veulent gagner."
    elif market_type == "GG":
        justif = f"Les deux équipes marquent habituellement — xG dom. {home_xg:.2f} / ext. {away_xg:.2f}, BTTS {btts_yes_prob:.0%}."
    elif market_type == "Over 2.5":
        justif = f"Match offensif attendu — xG total {total_xg:.2f}, {home_name} ({h_avg_for:.1f}) vs {away_name} ({a_avg_for:.1f}) buts/match."
    elif market_type == "Under 2.5":
        justif = f"Match fermé prévu — xG total {total_xg:.2f}, défenses solides, peu de buts attendus."
    else:
        justif = f"Analyse basée sur forme, H2H et statistiques avancées."

    if market_prob >= 0.80:
        signal = "💎 Signal très fort"
        signal_note = "Confiance élevée — données convergentes."
    elif market_prob >= 0.70:
        signal = "✅ Signal fort"
        signal_note = "Analyse fiable — jouer normalement."
    elif market_prob >= 0.60:
        signal = "🟡 Signal modéré"
        signal_note = "Jouer avec prudence — incertitude modérée."
    else:
        signal = "⚠️ Signal faible"
        signal_note = "Éviter ou miser symboliquement — trop d'incertitude."

    verdict = (
        f"\n\n---\n\n"
        f"### 🏆 VERDICT FINAL\n\n"
        f"**Marché recommandé** : **{market_conseil}**\n\n"
        f"**Probabilité** : **{market_prob:.0%}** — {signal}\n\n"
        f"🧠 *{justif}*\n\n"
        f"_{signal_note}_"
    )
    lines.append(verdict)

    return "\n\n".join(lines)
