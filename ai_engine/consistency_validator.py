"""
Consistency Validator
=====================
Valide et corrige les prédictions finales pour qu'elles soient
mathématiquement et footballistiquement cohérentes.

Règles bloquées:
- home_win 60% + away favorite 80% = INTERDIT
- Over 2.5 70% + scores 1-0/1-1 seulement = INTERDIT
- Confiance "Très fort" avec probabilité max < 55% = INTERDIT
- BTTS Oui 100% si les deux n'ont pas marqué = INTERDIT
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple


# ─────────────────────────────────────────────────────────────────────────────

def validate_and_fix(final_prediction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Point d'entrée: valide le final_prediction du fusion engine.
    Retourne le dict corrigé + warnings listant les incohérences détectées.
    """
    result = dict(final_prediction)
    warnings = []

    fp = result.get("final_probabilities", {})
    hw = fp.get("home_win", 33.3) / 100.0
    d  = fp.get("draw", 33.3) / 100.0
    aw = fp.get("away_win", 33.3) / 100.0
    conf = result.get("final_confidence", {})
    home_goals = result.get("home_goals", 0)
    away_goals = result.get("away_goals", 0)
    total_goals = home_goals + away_goals
    is_live = result.get("is_live", False)

    # ── 1. Cohérence 1X2 + favori ────────────────────────────────────────────
    max_prob = max(hw, d, aw)
    if hw == max_prob and aw > 0.60:
        warnings.append(f"Contradiction 1X2: domicile favori ({hw:.0%}) mais extérieur à {aw:.0%} — corrigé")
        aw = min(aw, 1.0 - hw - d)
        result["final_probabilities"]["away_win"] = round(aw * 100, 1)

    if aw == max_prob and hw > 0.60:
        warnings.append(f"Contradiction 1X2: extérieur favori ({aw:.0%}) mais domicile à {hw:.0%} — corrigé")
        hw = min(hw, 1.0 - aw - d)
        result["final_probabilities"]["home_win"] = round(hw * 100, 1)

    # ── 2. Cohérence Over/Under avec scores disponibles ───────────────────────
    scores = result.get("final_score_predictions", [])
    ou = result.get("ou_markets", {})
    if scores and ou:
        max_score_total = max((s.get("home_goals", 0) + s.get("away_goals", 0)) for s in scores)
        ov25 = ou.get("over_25", {}).get("prob", 0.0)
        if ov25 > 0.70 and max_score_total <= 1:
            warnings.append(f"Contradiction Over 2.5 ({ov25:.0%}) avec scores max {max_score_total} but(s) — incohérence détectée")

    # ── 3. Confiance vs probabilité max ──────────────────────────────────────
    conf_label = conf.get("label", "Moyen")
    conf_score = conf.get("score", 50)
    if conf_label == "Très fort" and max_prob < 0.55:
        warnings.append(f"Confiance 'Très fort' mais prob max {max_prob:.0%} < 55% — dégradé à Fort")
        result["final_confidence"]["label"] = "Fort"
        result["final_confidence"]["icon"] = "🟢"
        result["final_confidence"]["color"] = "#00cc44"

    if conf_label in ("Très fort", "Fort") and conf_score < 45:
        warnings.append(f"Confiance {conf_label} mais score {conf_score} < 45 — dégradé à Moyen")
        result["final_confidence"]["label"] = "Moyen"
        result["final_confidence"]["icon"] = "🟡"
        result["final_confidence"]["color"] = "#ffaa00"

    # ── 4. BTTS live conditionnel ────────────────────────────────────────────
    btts = result.get("btts", {})
    if is_live:
        both_scored = home_goals > 0 and away_goals > 0
        if both_scored and btts.get("yes_prob", 0) < 1.0:
            warnings.append("BTTS: les deux équipes ont marqué mais BTTS Oui < 100% — corrigé")
            result["btts"]["yes_prob"] = 1.0
            result["btts"]["no_prob"] = 0.0
            result["btts"]["locked"] = True

    # ── 5. Over/Under live conditionnel ──────────────────────────────────────
    if is_live and total_goals > 0:
        for threshold_str, m_over in [("over_05", 0.5), ("over_15", 1.5), ("over_25", 2.5)]:
            th_key = threshold_str.replace("over_", "")
            ov_key = f"over_{th_key}"
            un_key = f"under_{th_key}"
            if total_goals > m_over:
                if ou.get(ov_key, {}).get("prob", 1.0) < 1.0:
                    warnings.append(f"Over {m_over} déjà garanti ({total_goals} buts) mais prob < 100% — corrigé")
                    if ov_key in ou: ou[ov_key]["prob"] = 1.0; ou[ov_key]["locked"] = True
                    if un_key in ou: ou[un_key]["prob"] = 0.0; ou[un_key]["locked"] = True

    # ── 6. Scores impossibles (déjà filtrés mais vérification défensive) ─────
    filtered_scores = []
    for sc in scores:
        h = sc.get("home_goals", 0)
        a = sc.get("away_goals", 0)
        if h >= home_goals and a >= away_goals:
            filtered_scores.append(sc)
        else:
            warnings.append(f"Score impossible {sc.get('score')} éliminé (score actuel {home_goals}-{away_goals})")
    if filtered_scores:
        result["final_score_predictions"] = filtered_scores

    result["consistency_warnings"] = warnings
    return result


def get_favorite(final_probabilities: Dict[str, float], home_name: str, away_name: str) -> Tuple[str, float]:
    """Retourne (nom_favori, probabilité) depuis final_probabilities."""
    hw = final_probabilities.get("home_win", 33.3)
    d  = final_probabilities.get("draw", 33.3)
    aw = final_probabilities.get("away_win", 33.3)
    if hw >= d and hw >= aw:
        return home_name, hw
    if aw >= d and aw >= hw:
        return away_name, aw
    return "Nul", d
