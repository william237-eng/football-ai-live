"""
prediction_registry.py
======================
Registre persistant des prédictions émises.
Stocke chaque prédiction émise (live ou future) en JSON.
Permet de valider UNIQUEMENT les matchs effectivement prédits.

Fichier : database/prediction_registry.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "database", "prediction_registry.json"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> Dict[str, Any]:
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    if not os.path.exists(REGISTRY_PATH):
        return {"predictions": {}}
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "predictions" not in data:
            return {"predictions": {}}
        return data
    except Exception:
        return {"predictions": {}}


def _save(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def register_prediction(match_data: Dict[str, Any]) -> bool:
    """
    Enregistre une prédiction si elle n'existe pas encore.
    Retourne True si nouvellement enregistrée, False si déjà existante.
    """
    fid = match_data.get("fixture_id")
    if not fid:
        return False

    key = str(fid)
    data = _load()

    if key in data["predictions"]:
        return False

    data["predictions"][key] = {
        "fixture_id":            fid,
        "home_name":             match_data.get("home_name", ""),
        "away_name":             match_data.get("away_name", ""),
        "league_name":           match_data.get("league_name", ""),
        "league_country":        match_data.get("league_country", ""),
        "start_time":            match_data.get("start_time", ""),
        "start_date_display":    match_data.get("start_date_display", ""),
        "prediction":            "OVER_2.5",
        "probability":           match_data.get("over25_prob", 0.0),
        "probability_pct":       match_data.get("over25_pct", 0.0),
        "confidence":            match_data.get("conf_label", ""),
        "score_ia":              match_data.get("over_score", 0.0),
        "match_type":            match_data.get("match_type", "unknown"),
        "status":                "pending",
        "result":                None,
        "home_score_final":      None,
        "away_score_final":      None,
        "total_goals_final":     None,
        "timestamp_prediction":  _now_iso(),
        "timestamp_validated":   None,
    }
    _save(data)
    return True


def prediction_exists(fixture_id: int) -> bool:
    """Retourne True si ce fixture_id a déjà été prédit."""
    key = str(fixture_id)
    data = _load()
    return key in data["predictions"]


def get_prediction(fixture_id: int) -> Optional[Dict[str, Any]]:
    """Récupère la prédiction pour un fixture_id, ou None."""
    key = str(fixture_id)
    data = _load()
    return data["predictions"].get(key)


def validate_prediction(fixture_id: int, result: str,
                        home_score: int, away_score: int) -> bool:
    """
    Met à jour le résultat d'une prédiction existante.
    result = 'VALIDATED' ou 'FAILED'
    Retourne True si mis à jour, False si non trouvé ou déjà validé.
    """
    key = str(fixture_id)
    data = _load()
    if key not in data["predictions"]:
        return False

    pred = data["predictions"][key]
    if pred.get("status") != "pending":
        return False

    pred["status"]              = "validated"
    pred["result"]              = result
    pred["home_score_final"]    = home_score
    pred["away_score_final"]    = away_score
    pred["total_goals_final"]   = home_score + away_score
    pred["timestamp_validated"] = _now_iso()
    _save(data)
    return True


def get_all_predictions() -> List[Dict[str, Any]]:
    """Retourne toutes les prédictions (pending + validated)."""
    data = _load()
    return list(data["predictions"].values())


def get_validated_predictions() -> List[Dict[str, Any]]:
    """Retourne uniquement les prédictions validées (résultat connu)."""
    return [p for p in get_all_predictions() if p.get("status") == "validated"]


def get_pending_predictions() -> List[Dict[str, Any]]:
    """Retourne les prédictions en attente de résultat."""
    return [p for p in get_all_predictions() if p.get("status") == "pending"]


def compute_real_stats(days: int = 30) -> Dict[str, Any]:
    """
    Calcule les vraies statistiques basées UNIQUEMENT sur les prédictions émises.
    Jamais de 100% winrate si 0 pertes (les pending ne comptent pas).
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    SIMULATED_ODD  = 1.85
    STAKE_PER_BET  = 1.0

    all_preds = get_all_predictions()
    validated_in_period = [
        p for p in all_preds
        if p.get("status") == "validated"
        and p.get("timestamp_validated")
        and datetime.fromisoformat(p["timestamp_validated"]) >= cutoff
    ]

    total  = len(validated_in_period)
    won    = sum(1 for p in validated_in_period if p.get("result") == "VALIDATED")
    lost   = sum(1 for p in validated_in_period if p.get("result") == "FAILED")

    winrate      = round(won / total * 100, 1) if total > 0 else 0.0
    total_staked = total * STAKE_PER_BET
    total_return = won * SIMULATED_ODD * STAKE_PER_BET
    profit       = round(total_return - total_staked, 2)
    roi          = round((profit / total_staked) * 100, 1) if total_staked > 0 else 0.0

    # Aussi compter les pending (pour info)
    pending_in_period = [
        p for p in all_preds
        if p.get("status") == "pending"
        and p.get("timestamp_prediction")
        and datetime.fromisoformat(p["timestamp_prediction"]) >= cutoff
    ]

    return {
        "days":           days,
        "total":          total,
        "won":            won,
        "lost":           lost,
        "pending":        len(pending_in_period),
        "winrate":        winrate,
        "profit":         profit,
        "roi":            roi,
        "odd_used":       SIMULATED_ODD,
        "total_emitted":  total + len(pending_in_period),
    }
