"""
league_blacklist.py
===================
Blacklist configurable des compétitions à exclure du TOP Over 2.5.
Règles :
  - Mots-clés dans le nom de la ligue (insensible à la casse)
  - IDs de ligues spécifiques à exclure
"""
from __future__ import annotations
import re
from typing import Any, Dict, Set

# ─────────────────────────────────────────────────────────────────────────────
# Mots-clés blacklist (nom de ligue)
# ─────────────────────────────────────────────────────────────────────────────
BLACKLIST_KEYWORDS: list[str] = [
    # Jeunes
    "u20", "u21", "u22", "u23", "u17", "u18", "u19",
    "under-20", "under-21", "under-23", "under 20", "under 21",
    # Femmes
    "women", "femmes", "féminin", "feminine", "ladies", "girls",
    # Réserves / B
    "reserve", "réserve", "reserves", "b team", " ii", " iii", " b)",
    "segunda b", "segunda división b",
    # Compétitions très mineures / Friendlies
    "friendly", "friendlies", "amical",
    "youth", "junior",
]

# ─────────────────────────────────────────────────────────────────────────────
# IDs de ligues spécifiques à exclure (API-Football IDs)
# ─────────────────────────────────────────────────────────────────────────────
BLACKLIST_LEAGUE_IDS: Set[int] = {
    # Exemples — à compléter selon besoins
    # 890,  # exemple ID ligue faible
}

# Regex compilée une fois
_KEYWORD_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in BLACKLIST_KEYWORDS),
    re.IGNORECASE,
)


def is_blacklisted(fixture_raw: Dict[str, Any]) -> bool:
    """
    Retourne True si le match doit être exclu.
    Vérifie nom de ligue + ID de ligue.
    """
    league = fixture_raw.get("league") or {}
    league_name = str(league.get("name") or "")
    league_id   = league.get("id")

    # Vérifier ID
    if league_id and int(league_id) in BLACKLIST_LEAGUE_IDS:
        return True

    # Vérifier mots-clés dans le nom
    if _KEYWORD_PATTERN.search(league_name):
        return True

    return False


def blacklist_reason(fixture_raw: Dict[str, Any]) -> str:
    """Retourne la raison de l'exclusion (debug)."""
    league = fixture_raw.get("league") or {}
    league_name = str(league.get("name") or "")
    league_id   = league.get("id")
    if league_id and int(league_id) in BLACKLIST_LEAGUE_IDS:
        return f"League ID {league_id} blacklisté"
    m = _KEYWORD_PATTERN.search(league_name)
    if m:
        return f"Mot-clé '{m.group()}' détecté dans '{league_name}'"
    return ""
