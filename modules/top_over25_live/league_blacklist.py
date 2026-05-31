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
    "u20", "u21", "u22", "u23", "u17", "u18", "u19", "u16", "u15",
    "under-20", "under-21", "under-23", "under 20", "under 21",
    # Femmes
    "women", "femmes", "féminin", "feminine", "ladies", "girls", "dames",
    # Réserves / B / II / III
    "reserve", "réserve", "reserves", "b team", " ii", " iii", " b)",
    "segunda b", "segunda división b",
    # Compétitions très mineures / Friendlies
    "friendly", "friendlies", "amical",
    "youth", "junior",
    # Divisions inférieures régionales
    "regional", "régional", "amateur", "amateurs",
    "division 4", "division 5", "division 6", "division 7",
    "4. liga", "5. liga", "6. liga",
    "4ème", "5ème", "6ème", "4e division", "5e division",
    "kreisliga", "bezirksliga", "landesliga",
    "oberliga",
    "cup",  # coupes régionales souvent avec scores aberrants
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


# Score maximum raisonnable par équipe (au-delà = match aberrant de ligue mineure)
MAX_REALISTIC_GOALS_PER_TEAM = 7


def is_blacklisted(fixture_raw: Dict[str, Any]) -> bool:
    """
    Retourne True si le match doit être exclu.
    Vérifie nom de ligue + ID de ligue + noms d'équipes + scores aberrants.
    """
    league = fixture_raw.get("league") or {}
    league_name = str(league.get("name") or "")
    league_id   = league.get("id")

    # Vérifier ID
    if league_id and int(league_id) in BLACKLIST_LEAGUE_IDS:
        return True

    # Vérifier mots-clés dans le nom de la ligue
    if _KEYWORD_PATTERN.search(league_name):
        return True

    # Vérifier les noms d'équipes (réserves II/III dans le nom de l'équipe)
    teams = fixture_raw.get("teams") or {}
    for side in ("home", "away"):
        tname = str((teams.get(side) or {}).get("name") or "")
        if re.search(r"\b(II|III|IV|\bB\b|Reserves?|Reserve|Youth|Junior)\b", tname):
            return True

    # Filtrer les scores aberrants (déjà terminés) — ligues ultra-mineures
    goals = fixture_raw.get("goals") or {}
    try:
        hg = int(goals.get("home") or 0)
        ag = int(goals.get("away") or 0)
        if hg > MAX_REALISTIC_GOALS_PER_TEAM or ag > MAX_REALISTIC_GOALS_PER_TEAM:
            return True
    except (TypeError, ValueError):
        pass

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
