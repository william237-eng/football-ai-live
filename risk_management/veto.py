"""Système de veto basé sur movement de marché (sharp money / Asian Handicap).

Règle: si la ligne asiatique a bougé de > 5% dans la direction opposée de la 'value' détectée,
on veto la position (asymétrie d'information cachée).
"""
from __future__ import annotations

from typing import Any, Dict

from storage.db import AsyncDB
from data_ingestion.pinnacle_client import PinnacleClient


class MarketVeto:
    def __init__(self, db: AsyncDB, pin_client: PinnacleClient) -> None:
        self.db = db
        self.pin = pin_client

    def should_veto(self, signal: Dict[str, Any]) -> bool:
        """Décision synchrone simple: lit le meta du signal.

        signal.meta doit contenir : model_edge_direction ("home"/"away") et pre_market_line et current_line
        La variation relative est calculée et comparée à 5%.
        """
        meta = getattr(signal, "meta", {}) if not isinstance(signal, dict) else signal.get("meta", {})
        pre_line = meta.get("pre_market_line")
        cur_line = meta.get("current_market_line")
        if pre_line is None or cur_line is None:
            return False
        try:
            pre = float(pre_line)
            cur = float(cur_line)
        except Exception:
            return False

        # variation relative
        if pre == 0:
            return False
        rel = (cur - pre) / abs(pre)
        # Si le marché a bougé de plus de 5% dans la direction opposée => veto
        # Direction opposée : le signe de rel est opposé à edge_direction
        edge_dir = meta.get("edge_direction")  # "home" or "away"
        if edge_dir == "home" and rel < -0.05:
            return True
        if edge_dir == "away" and rel > 0.05:
            return True
        return False

