"""
victory_engine.py
=================
Calcule le WIN_SCORE /100 pour chaque match et sélectionne les TOP victoires.

NOUVELLE FORMULE :
  FINAL_SCORE = 0.30*form + 0.20*elo + 0.15*xg + 0.15*attack + 0.10*defense + 0.10*h2h

Sélection progressive :
  WIN_SCORE >= 55 → trier DESC → TOP 10
  Si moins de 10 : abaisser progressivement 70→65→60→55
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(v, default: float = 0.0) -> float:
    try:
        return float(str(v).replace("%", "").strip())
    except Exception:
        return default


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _coherent_probable_score(winner: str, home_score: int, away_score: int) -> Tuple[int, int]:
    home_score = int(max(0, min(5, home_score)))
    away_score = int(max(0, min(5, away_score)))
    if winner == "home" and home_score <= away_score:
        home_score = min(5, away_score + 1)
    elif winner == "away" and away_score <= home_score:
        away_score = min(5, home_score + 1)
    elif winner == "draw" and home_score != away_score:
        level = max(0, min(5, round((home_score + away_score) / 2)))
        home_score = level
        away_score = level
    return home_score, away_score


def _form_score(recent: List[Dict], team_id: int) -> float:
    """Score de forme 0-100 sur les 5 derniers matchs."""
    if not recent:
        return 50.0
    pts = 0
    total = 0
    for m in recent[:5]:
        teams = m.get("teams") or {}
        goals = m.get("goals") or {}
        home  = teams.get("home") or {}
        away  = teams.get("away") or {}
        is_home = home.get("id") == team_id
        gh, ga = _safe(goals.get("home", 0)), _safe(goals.get("away", 0))
        if is_home:
            scored, conceded = gh, ga
        else:
            scored, conceded = ga, gh
        if scored > conceded:
            pts += 3
        elif scored == conceded:
            pts += 1
        total += 1
    if total == 0:
        return 50.0
    return _clamp((pts / (total * 3)) * 100)


def _attack_score(recent: List[Dict], team_id: int) -> float:
    """Moyenne buts marqués normalisée 0-100."""
    if not recent:
        return 40.0
    scored_list = []
    for m in recent[:5]:
        teams = m.get("teams") or {}
        goals = m.get("goals") or {}
        home  = teams.get("home") or {}
        away  = teams.get("away") or {}
        is_home = home.get("id") == team_id
        gh, ga = _safe(goals.get("home", 0)), _safe(goals.get("away", 0))
        scored_list.append(gh if is_home else ga)
    avg = sum(scored_list) / len(scored_list) if scored_list else 0
    return _clamp(avg / 3.5 * 100)  # 3.5 buts/match = 100%


def _defense_score(recent: List[Dict], team_id: int) -> float:
    """Solidité défensive 0-100 (moins encaissé = mieux)."""
    if not recent:
        return 40.0
    conceded_list = []
    for m in recent[:5]:
        teams = m.get("teams") or {}
        goals = m.get("goals") or {}
        home  = teams.get("home") or {}
        away  = teams.get("away") or {}
        is_home = home.get("id") == team_id
        gh, ga = _safe(goals.get("home", 0)), _safe(goals.get("away", 0))
        conceded_list.append(ga if is_home else gh)
    avg = sum(conceded_list) / len(conceded_list) if conceded_list else 2
    return _clamp((1 - avg / 3.5) * 100)


def _xg_score(recent: List[Dict], team_id: int) -> float:
    """Score xG (Expected Goals) basé sur la forme offensive et défensive récente."""
    if not recent:
        return 50.0
    
    scored_list = []
    conceded_list = []
    
    for m in recent[:5]:
        teams = m.get("teams") or {}
        goals = m.get("goals") or {}
        home  = teams.get("home") or {}
        away  = teams.get("away") or {}
        is_home = home.get("id") == team_id
        gh, ga = _safe(goals.get("home", 0)), _safe(goals.get("away", 0))
        
        scored_list.append(gh if is_home else ga)
        conceded_list.append(ga if is_home else gh)
    
    avg_scored = sum(scored_list) / len(scored_list) if scored_list else 1.0
    avg_conceded = sum(conceded_list) / len(conceded_list) if conceded_list else 1.0
    
    # xG basé sur la moyenne buts marqués + encaissés (forme globale)
    xg = (avg_scored + (2.0 - avg_conceded)) / 2.0
    return _clamp((xg / 2.5) * 100)  # 2.5 xG = 100%


def _elo_component(home_elo: float, away_elo: float, winner: str) -> float:
    """
    Composante ELO : probabilité ELO que 'winner' gagne.
    winner : 'home' | 'away' | 'draw'
    """
    diff = home_elo - away_elo
    expected_home = 1 / (1 + 10 ** (-diff / 400))
    if winner == "home":
        return _clamp(expected_home * 100)
    elif winner == "away":
        return _clamp((1 - expected_home) * 100)
    else:
        draw_prob = 1 - abs(expected_home - 0.5) * 2
        return _clamp(draw_prob * 100)


def _h2h_component(h2h: List[Dict], home_team_id: int, winner: str) -> float:
    """H2H win rate 0-100 pour l'équipe favorisée."""
    if not h2h:
        return 50.0
    home_wins = away_wins = draws = 0
    for m in h2h[:10]:
        teams = m.get("teams") or {}
        home  = teams.get("home") or {}
        score = m.get("score") or m.get("goals") or {}
        fh = _safe(score.get("home", 0))
        fa = _safe(score.get("away", 0))
        if fh > fa:
            if home.get("id") == home_team_id:
                home_wins += 1
            else:
                away_wins += 1
        elif fa > fh:
            if home.get("id") == home_team_id:
                away_wins += 1
            else:
                home_wins += 1
        else:
            draws += 1
    total = home_wins + away_wins + draws or 1
    if winner == "home":
        return _clamp(home_wins / total * 100)
    elif winner == "away":
        return _clamp(away_wins / total * 100)
    else:
        return _clamp(draws / total * 100)


def _home_advantage_component(winner: str) -> float:
    """Bonus domicile standard."""
    if winner == "home":
        return 65.0
    elif winner == "draw":
        return 45.0
    else:
        return 35.0


def _motivation_component(match_raw: Dict) -> float:
    """Heuristique d'importance : coupe > championnat > amical."""
    league = (match_raw.get("league") or {}).get("name", "").lower()
    if any(k in league for k in ["cup", "coupe", "fa cup", "champions", "europa", "final"]):
        return 80.0
    if any(k in league for k in ["premier", "ligue 1", "bundesliga", "serie a", "la liga"]):
        return 70.0
    if any(k in league for k in ["friendly", "amical", "test"]):
        return 30.0
    return 55.0


# ─────────────────────────────────────────────────────────────────────────────
# Calcul du WIN_SCORE principal
# ─────────────────────────────────────────────────────────────────────────────

def compute_win_score(
    match_raw: Dict[str, Any],
    home_recent: List[Dict],
    away_recent: List[Dict],
    h2h: List[Dict],
    home_elo: float = 1500.0,
    away_elo: float = 1500.0,
) -> Dict[str, Any]:
    """
    Calcule le WIN_SCORE avec la nouvelle formule FINAL_SCORE.
    Retourne un dict complet avec le verdict et les composantes.
    """
    teams   = match_raw.get("teams") or {}
    home    = teams.get("home") or {}
    away    = teams.get("away") or {}
    home_id = home.get("id")
    away_id = away.get("id")

    # ── Composantes ────────────────────────────────────────────────────────
    elo_diff  = home_elo - away_elo
    exp_home  = 1 / (1 + 10 ** (-elo_diff / 400))
    exp_away  = 1 - exp_home
    exp_draw  = max(0.05, 0.30 - abs(elo_diff) / 1000)
    # Renormalize
    tot = exp_home + exp_away + exp_draw
    p_home = exp_home / tot
    p_away = exp_away / tot
    p_draw = exp_draw / tot

    # Déterminer le favori
    if p_home >= p_away and p_home >= p_draw:
        winner = "home"
        win_prob = p_home
        predicted_team = home.get("name", "Domicile")
        predicted_label = "Victoire Domicile"
    elif p_away > p_home and p_away >= p_draw:
        winner = "away"
        win_prob = p_away
        predicted_team = away.get("name", "Extérieur")
        predicted_label = "Victoire Extérieur"
    else:
        winner = "draw"
        win_prob = p_draw
        predicted_team = "Match Nul"
        predicted_label = "Match Nul"

    # Composantes détaillées
    elo_c  = _elo_component(home_elo, away_elo, winner)
    form_h = _form_score(home_recent, home_id)
    form_a = _form_score(away_recent, away_id)
    form_c = form_h if winner == "home" else (form_a if winner == "away" else (form_h + form_a) / 2)

    atk_h  = _attack_score(home_recent, home_id)
    atk_a  = _attack_score(away_recent, away_id)
    atk_c  = atk_h if winner == "home" else atk_a

    def_h  = _defense_score(home_recent, home_id)
    def_a  = _defense_score(away_recent, away_id)
    def_c  = def_h if winner == "home" else def_a

    xg_h   = _xg_score(home_recent, home_id)
    xg_a   = _xg_score(away_recent, away_id)
    xg_c   = xg_h if winner == "home" else xg_a

    h2h_c  = _h2h_component(h2h, home_id, winner)

    # NOUVELLE FORMULE : FINAL_SCORE = 0.30*form + 0.20*elo + 0.15*xg + 0.15*attack + 0.10*defense + 0.10*h2h
    final_score = (
        form_c * 0.30 +
        elo_c  * 0.20 +
        xg_c   * 0.15 +
        atk_c  * 0.15 +
        def_c  * 0.10 +
        h2h_c  * 0.10
    )
    final_score = _clamp(final_score)

    # DEBUG : Afficher les détails du calcul
    print(f"🧮 DEBUG WIN_SCORE: {home.get('name', 'N/A')} vs {away.get('name', 'N/A')}")
    print(f"   Forme: {form_c:.1f} | ELO: {elo_c:.1f} | xG: {xg_c:.1f} | Atk: {atk_c:.1f} | Def: {def_c:.1f} | H2H: {h2h_c:.1f}")
    print(f"   FINAL_SCORE: {final_score:.1f} | Winner: {winner} | Prob: {win_prob:.2f}")

    # Toujours valide (pas de seuil strict ici, la sélection progressive gérera ça)
    win_score = final_score

    # Confiance
    if win_score >= 90:
        confidence_label = "Exceptionnelle"
        confidence_color = "#a855f7"
        confidence_stars = "★★★★★"
    elif win_score >= 80:
        confidence_label = "Très élevée"
        confidence_color = "#22c55e"
        confidence_stars = "★★★★☆"
    elif win_score >= 70:
        confidence_label = "Élevée"
        confidence_color = "#f59e0b"
        confidence_stars = "★★★☆☆"
    else:
        confidence_label = "Modérée"
        confidence_color = "#fb923c"
        confidence_stars = "★★☆☆☆"

    # Score probable (très simplifié)
    avg_h_scored = (sum(
        _safe((m.get("goals") or {}).get("home" if (m.get("teams") or {}).get("home", {}).get("id") == home_id else "away", 0))
        for m in home_recent[:5]
    ) / max(1, len(home_recent[:5])))
    avg_a_scored = (sum(
        _safe((m.get("goals") or {}).get("away" if (m.get("teams") or {}).get("home", {}).get("id") == away_id else "home", 0))
        for m in away_recent[:5]
    ) / max(1, len(away_recent[:5])))
    prob_score_h = round(max(0, min(5, avg_h_scored)))
    prob_score_a = round(max(0, min(5, avg_a_scored)))
    prob_score_h, prob_score_a = _coherent_probable_score(winner, prob_score_h, prob_score_a)

    # Raisons IA
    reasons = []
    if form_c >= 70:
        reasons.append("Excellente forme récente")
    elif form_c >= 60:
        reasons.append("Bonne forme récente")
    
    if xg_c >= 70:
        reasons.append("xG offensif élevé")
    elif xg_c >= 60:
        reasons.append("Bon potentiel offensif")
    
    if atk_c >= 70:
        reasons.append("Attaque très efficace")
    elif atk_c >= 60:
        reasons.append("Bonne attaque")
    
    if def_c >= 70:
        reasons.append("Défense solide")
    elif def_c >= 60:
        reasons.append("Défense correcte")
    
    if h2h_c >= 65:
        reasons.append("Historique favorable")
    elif h2h_c >= 55:
        reasons.append("Historique neutre")
    
    if elo_c >= 70:
        reasons.append("Supériorité ELO nette")
    elif elo_c >= 60:
        reasons.append("Avantage ELO")

    return {
        "valid":             True,
        "winner":            winner,
        "win_prob":          win_prob,
        "win_score":         round(win_score, 1),
        "predicted_team":    predicted_team,
        "predicted_label":   predicted_label,
        "confidence_label":  confidence_label,
        "confidence_color":  confidence_color,
        "confidence_stars":  confidence_stars,
        "prob_score_h":      prob_score_h,
        "prob_score_a":      prob_score_a,
        "reasons":           reasons,
        "breakdown": {
            "Forme":    round(form_c, 1),
            "ELO":      round(elo_c, 1),
            "xG":       round(xg_c, 1),
            "Attaque":  round(atk_c, 1),
            "Défense":  round(def_c, 1),
            "H2H":      round(h2h_c, 1),
        },
        "home_name":  home.get("name", ""),
        "away_name":  away.get("name", ""),
        "home_logo":  home.get("logo", ""),
        "away_logo":  away.get("logo", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sélection TOP (max 10)
# ─────────────────────────────────────────────────────────────────────────────

def select_top_victories(enriched: List[Dict], max_n: int = 10) -> List[Dict]:
    """
    Sélection progressive GARANTIE pour toujours avoir des matchs.
    LOGIQUE : Toujours retourner les meilleurs matchs disponibles.
    """
    if not enriched:
        return []
    
    # ÉTAPE 1: Essayer avec seuils élevés pour la qualité
    thresholds = [70, 65, 60, 55]
    
    for threshold in thresholds:
        # Filtrer les matchs avec WIN_SCORE >= seuil actuel
        valid = [m for m in enriched if m.get("win_result", {}).get("win_score", 0) >= threshold]
        
        # Trier par WIN_SCORE décroissant
        valid.sort(key=lambda m: m["win_result"]["win_score"], reverse=True)
        
        # Si on a assez de matchs, on retourne le TOP
        if len(valid) >= max_n:
            return valid[:max_n]
    
    # ÉTAPE 2: Si aucun seuil ne donne assez de matchs, prendre TOUS les matchs valides
    all_valid = [m for m in enriched if m.get("win_result", {}).get("valid")]
    all_valid.sort(key=lambda m: m["win_result"]["win_score"], reverse=True)
    
    # ÉTAPE 3: Si toujours pas assez, prendre les meilleurs même avec win_score plus bas
    if len(all_valid) < max_n:
        # Prendre tous les matchs enrichis (même ceux avec win_score faible)
        all_enriched = sorted(enriched, key=lambda m: m.get("win_result", {}).get("win_score", 0), reverse=True)
        return all_enriched[:max_n]
    
    return all_valid[:max_n]
