"""
betting_engine.py
=================
Construction et validation initiale d'un ticket prédictif.
Marchés supportés : 1X2, Double Chance, BTTS, Over/Under, Prochain But,
                    Mi-temps, Corners, Cartons, Score Exact.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

SUPPORTED_MARKETS = [
    "1X2",
    "Double Chance",
    "BTTS",
    "Over/Under Buts",
    "Prochain But",
    "Mi-temps",
    "Corners",
    "Cartons",
    "Score Exact",
]

# Options par marché
MARKET_OPTIONS: Dict[str, List[str]] = {
    "1X2":            ["Domicile (1)", "Nul (X)", "Extérieur (2)"],
    "Double Chance":  ["1X", "X2", "12"],
    "BTTS":           ["GG Oui", "GG Non"],
    "Over/Under Buts":["Over 0.5", "Under 0.5",
                       "Over 1.5", "Under 1.5",
                       "Over 2.5", "Under 2.5",
                       "Over 3.5", "Under 3.5",
                       "Over 4.5", "Under 4.5"],
    "Prochain But":   ["Domicile", "Extérieur", "Aucun but"],
    "Mi-temps":       ["Domicile marque 1ère MT", "Extérieur marque 1ère MT",
                       "Domicile marque 2ème MT", "Extérieur marque 2ème MT",
                       "BTTS 1ère MT", "Over 0.5 1ère MT"],
    "Corners":        ["Over 7.5", "Under 7.5",
                       "Over 8.5", "Under 8.5",
                       "Over 9.5", "Under 9.5",
                       "Over 10.5", "Under 10.5"],
    "Cartons":        ["Over 2.5", "Under 2.5",
                       "Over 3.5", "Under 3.5",
                       "Over 4.5", "Under 4.5"],
    "Score Exact":    [f"{h}-{a}" for h in range(5) for a in range(5)],
}


def validate_selection(market: str, prediction: str) -> Tuple[bool, str]:
    """Valide qu'un marché + prédiction est cohérent."""
    if market not in SUPPORTED_MARKETS:
        return False, f"Marché inconnu: {market}"
    opts = MARKET_OPTIONS.get(market, [])
    if opts and prediction not in opts:
        return False, f"Prédiction '{prediction}' invalide pour marché '{market}'"
    return True, "OK"


def build_ticket_selections(
    selections: List[Dict[str, Any]],
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Valide et structure les sélections pour un ticket.

    selections: liste de dicts {fixture_id, home_team, away_team, market, prediction}
    Retourne: (valide, message_erreur, selections_nettoyées)
    """
    if not selections:
        return False, "Aucune sélection fournie.", []
    if len(selections) > 8:
        return False, "Maximum 8 sélections par ticket.", []

    cleaned = []
    seen = set()
    for sel in selections:
        fid   = sel.get("fixture_id")
        market = sel.get("market", "")
        pred  = sel.get("prediction", "")

        if not fid:
            return False, "fixture_id manquant dans une sélection.", []

        ok, msg = validate_selection(market, pred)
        if not ok:
            return False, msg, []

        # Anti-doublon : même fixture + même marché
        dedup_key = (fid, market)
        if dedup_key in seen:
            return False, f"Doublon : fixture {fid} / marché {market} sélectionné deux fois.", []
        seen.add(dedup_key)

        cleaned.append({
            "fixture_id": int(fid),
            "home_team":  str(sel.get("home_team", "")),
            "away_team":  str(sel.get("away_team", "")),
            "market":     market,
            "prediction": pred,
        })

    return True, "OK", cleaned
