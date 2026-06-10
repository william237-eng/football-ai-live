"""Transformations de données et lissage du bruit (EMA sur Live Pressure Index).

Fournit une classe légère PressureIndexSmoother qui applique une EMA et expose
la valeur lissée — entièrement déterministe et auditable.
"""
from __future__ import annotations

from typing import Optional

from utils.math_utils import ema


class PressureIndexSmoother:
    def __init__(self, alpha: float = 0.2) -> None:
        # alpha est la vitesse d'oubli (plus grand => plus sensible au bruit)
        self.alpha = alpha
        self.current: Optional[float] = None

    def update(self, value: float) -> float:
        if self.current is None:
            self.current = value
        else:
            self.current = ema(self.current, value, self.alpha)
        return self.current

