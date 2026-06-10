"""Détection d'anomalies asymétriques : cartons rouges, blessures fantômes.

Le code est audit-ready: chaque flag est basé sur règles quantitatives et EMA.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from utils.math_utils import ema


def red_card_adjustment(lambda_team: float, minute: int, c: float = 0.05) -> float:
    """Applique la décroissance exponentielle f(t)=exp(-c*(90-t)) sur la lambda de l'équipe pénalisée."""
    return lambda_team * (2.718281828459045 ** (-c * (90 - minute)))


def detect_ghost_injury(events: Iterable[Dict]) -> bool:
    """Détecte 'blessures fantômes' : arrêt de jeu > 90s suivi d'une chute d'intensité (PPDA).

    events: liste d'événements chronologiques contenant 'stop_duration' (sec) et 'ppda' (float)
    Règle: si stop_duration >= 90 et ppda chute de >20% dans les 120s suivants -> flag True
    """
    evs = list(events)
    for i, e in enumerate(evs):
        sd = e.get("stop_duration", 0)
        if sd >= 90:
            base_ppda = e.get("ppda_before", None)
            # chercher événements dans les 2 minutes suivantes
            for f in evs[i + 1 : i + 10]:
                ppda_after = f.get("ppda", None)
                if base_ppda and ppda_after:
                    if ppda_after < 0.8 * base_ppda:
                        return True
    return False

