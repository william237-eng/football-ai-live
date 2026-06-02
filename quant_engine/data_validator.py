"""
Data Validator & Hierarchy Engine

Implémente une hiérarchie de fallback pour maximiser l'utilisation de données
réelles sans jamais les fabriquer.

Niveaux de données :
  Niveau 1 (Idéal) : xG live, tirs, possession, stats événementielles live
  Niveau 2 (Dégradé) : forme récente, historique, buts marqués/encaissés, classement
  Niveau 3 (Min) : pré-match seulement

Jamais de fabrication ; jamais de simulation factice.
"""

from typing import Dict, Any, Tuple, List
from enum import Enum
import time


class DataQuality(Enum):
    """Énumération des niveaux de qualité."""
    EXCELLENT = "Excellent"    # Niveau 1 complet
    BON = "Bon"                # Niveau 1 + Niveau 2 partiel
    LIMITE = "Limité"          # Niveau 2 + Niveau 3
    INSUFFISANT = "Insuffisant"  # Données manquantes ou erreurs


class DataLevel(Enum):
    """Énumération des niveaux de données."""
    LEVEL_1_LIVE = 1      # xG, tirs, possession, live
    LEVEL_2_FORM = 2      # Forme, historique, buts, classement
    LEVEL_3_PREMATCH = 3  # Pré-match seulement


class DataValidator:
    """
    Valide et évalue la qualité des données selon une hiérarchie stricte.
    Jamais de fabrication.
    """

    # Champs essentiels par niveau
    LEVEL_1_LIVE_FIELDS = [
        "minute", "xG_home", "xG_away", "shots_home", "shots_away",
        "shots_on_target_home", "shots_on_target_away",
        "possession_home", "possession_away"
    ]

    LEVEL_2_FORM_FIELDS = [
        "recent_goals_for", "recent_goals_against", "recent_matches",
        "standing_home", "standing_away"
    ]

    LEVEL_3_PREMATCH_FIELDS = [
        "home_historical_goals_for", "home_historical_goals_against",
        "away_historical_goals_for", "away_historical_goals_against"
    ]

    def __init__(self):
        self.last_retrieved = {}  # dict {endpoint: timestamp}

    def check_level_1_live(self, live_stats: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Vérifie si les données Niveau 1 sont complètes.
        Retourne (is_complete, missing_fields)
        """
        if not live_stats or not isinstance(live_stats, dict):
            return False, self.LEVEL_1_LIVE_FIELDS

        missing = [k for k in self.LEVEL_1_LIVE_FIELDS if k not in live_stats]
        is_complete = len(missing) == 0
        return is_complete, missing

    def check_level_2_form(self, form_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Vérifie si les données Niveau 2 (forme/historique) sont disponibles.
        Retourne (is_available, missing_fields)
        """
        if not form_data or not isinstance(form_data, dict):
            return False, self.LEVEL_2_FORM_FIELDS

        missing = [k for k in self.LEVEL_2_FORM_FIELDS if k not in form_data]
        is_available = len(missing) < len(self.LEVEL_2_FORM_FIELDS)  # au moins un champ
        return is_available, missing

    def check_level_3_prematch(self, prematch_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Vérifie si les données Niveau 3 (pré-match) sont disponibles.
        Retourne (is_available, missing_fields)
        """
        if not prematch_data or not isinstance(prematch_data, dict):
            return False, self.LEVEL_3_PREMATCH_FIELDS

        missing = [k for k in self.LEVEL_3_PREMATCH_FIELDS if k not in prematch_data]
        is_available = len(missing) < len(self.LEVEL_3_PREMATCH_FIELDS)
        return is_available, missing

    def assess_data_quality(
        self,
        live_stats: Dict[str, Any] = None,
        form_data: Dict[str, Any] = None,
        prematch_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Évalue la qualité globale des données et retourne un rapport.

        Retourne:
        {
            "level": DataLevel,
            "quality": DataQuality,
            "is_live": bool,
            "sources": [list de sources utilisées],
            "confidence_multiplier": float [0.5 - 1.0],
            "missing_fields": [...],
            "report": "human readable"
        }
        """
        level_1_ok, level_1_missing = self.check_level_1_live(live_stats)
        level_2_ok, level_2_missing = self.check_level_2_form(form_data)
        level_3_ok, level_3_missing = self.check_level_3_prematch(prematch_data)

        # Déterminer le niveau et la qualité
        if level_1_ok:
            active_level = DataLevel.LEVEL_1_LIVE
            if level_2_ok:
                quality = DataQuality.EXCELLENT
                conf_multiplier = 1.0
            else:
                quality = DataQuality.BON
                conf_multiplier = 0.9
            is_live = True
            sources = ["live_stats"]
            if level_2_ok:
                sources.append("form_data")

        elif level_2_ok:
            active_level = DataLevel.LEVEL_2_FORM
            quality = DataQuality.LIMITE
            conf_multiplier = 0.7
            is_live = False
            sources = ["form_data"]
            if level_3_ok:
                sources.append("prematch_data")

        elif level_3_ok:
            active_level = DataLevel.LEVEL_3_PREMATCH
            quality = DataQuality.LIMITE
            conf_multiplier = 0.5
            is_live = False
            sources = ["prematch_data"]

        else:
            # Données insuffisantes
            active_level = None
            quality = DataQuality.INSUFFISANT
            conf_multiplier = 0.0
            is_live = False
            sources = []

        # Rapport lisible
        quality_str = quality.value if quality else "Indéterminé"
        report = f"Qualité: {quality_str}. Niveau: {active_level.value if active_level else 'Aucun'}. Sources: {', '.join(sources)}."

        return {
            "level": active_level,
            "quality": quality,
            "quality_str": quality_str,
            "is_live": is_live,
            "sources": sources,
            "confidence_multiplier": conf_multiplier,
            "missing_fields": (level_1_missing if not level_1_ok else []) +
                            (level_2_missing if not level_2_ok else []) +
                            (level_3_missing if not level_3_ok else []),
            "report": report
        }

    def can_compute_model(self, assessment: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Détermine si un modèle peut être calculé avec la qualité de données donnée.

        Retourne (can_compute, reason)
        """
        if assessment["quality"] == DataQuality.INSUFFISANT:
            return False, "Données insuffisantes pour calculer le modèle."
        # Tous les autres niveaux permettent au moins un calcul dégradé
        return True, ""

    def record_retrieval(self, endpoint: str, timestamp: float = None):
        """Enregistre l'horodatage de la dernière récupération d'un endpoint."""
        self.last_retrieved[endpoint] = timestamp or time.time()

    def get_freshness_info(self, endpoint: str) -> Dict[str, Any]:
        """Retourne les infos de fraîcheur des données pour un endpoint."""
        if endpoint not in self.last_retrieved:
            return {"endpoint": endpoint, "last_update": None, "age_seconds": None}

        ts = self.last_retrieved[endpoint]
        age = time.time() - ts
        return {
            "endpoint": endpoint,
            "last_update": ts,
            "age_seconds": age,
            "is_fresh": age < 60  # Considéré frais si < 1 min
        }

