"""Gestion des tailles de position via Kelly fractionné et suivi CLV.

Toutes les décisions sont strictement basées sur la différence entre prob_model
et la prob implicite de la cote (cote décimale).
"""
from __future__ import annotations

from typing import Any, Dict

from storage.db import AsyncDB
from utils.math_utils import kelly_fraction


class MoneyManager:
    def __init__(self, db: AsyncDB, kelly_frac: float = 0.25, bankroll: float = 10000.0) -> None:
        self.db = db
        self.kelly_frac = kelly_frac
        self.bankroll = bankroll

    async def stake_for_signal(self, signal: Any) -> float:
        """Calcule la mise en devise (ex: euros) via Kelly fractionné.

        - signal.prob_model: probabilité estimée
        - signal.odds: cote décimale
        Retourne stake en valeur monétaire. Si <=0 => aucune position.
        """
        p = float(getattr(signal, "prob_model", 0.0))
        odds = float(getattr(signal, "odds", 0.0))
        if p <= 0 or odds <= 1:
            return 0.0
        frac = kelly_fraction(p, odds, fraction=self.kelly_frac)
        stake = self.bankroll * frac
        # Enregistrer CLV sommaire (closing line value to be computed post-facto)
        await self.db.execute(
            "INSERT INTO executed_positions(match_id, side, stake, odds, prob_model, clv, meta) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (getattr(signal, "match_id", ""), getattr(signal, "side", ""), stake, odds, p, None, "{\"queued_by\":\"money_manager\"}"),
        )
        return stake

