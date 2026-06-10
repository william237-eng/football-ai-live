"""Moteur de trading asynchrone - pré-match et in-play.

Contient les transformations mathématiques pour:
- ELO xG (simplifié pour garder auditable)
- Dixon-Coles bivarié
- Update bayésien minute par minute
- Skellam pricing pour Asian Handicap
Toutes les décisions sont tracées par des valeurs numériques explicites.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from storage.db import AsyncDB
from data_ingestion.sportmonks_client import SportMonksClient
from data_ingestion.pinnacle_client import PinnacleClient
from utils.math_utils import (
    bayesian_lambda_update,
    dixon_coles_prob,
    kelly_fraction,
    skellam_cdf_range,
)


@dataclass
class Signal:
    match_id: str
    selection: str
    side: str
    prob_model: float
    odds: float
    meta: Dict[str, Any]


class TradingEngine:
    def __init__(self, db: AsyncDB, sm_client: SportMonksClient, pin_client: PinnacleClient) -> None:
        self.db = db
        self.sm = sm_client
        self.pin = pin_client

    async def evaluate_pre_match(self, match: Dict[str, Any]) -> Optional[Signal]:
        """Évalue signaux pré-match.

        - Calcule lambdas via elo/xG simulé (ici: valeurs extraites si présentes dans `meta`)
        - Applique Dixon-Coles pour estimer distribution des scores
        - Compare avec cotes du bookmaker (si disponibles)
        - Retourne Signal ou None
        """
        mid = str(match.get("id"))
        meta = match.get("meta", {})
        # Extract lambda proxy depuis meta si disponible (Zéro supposition sinon)
        lambda_h = float(meta.get("lambda_home", 1.0))
        lambda_a = float(meta.get("lambda_away", 1.0))
        rho = float(meta.get("dixon_rho", 0.0))

        # Exemple: prob que l'hôte gagne = somme_{h>a} P(h,a)
        prob_home_win = 0.0
        for h in range(0, 6):
            for a in range(0, 6):
                if h > a:
                    prob_home_win += dixon_coles_prob(h, a, lambda_h, lambda_a, rho)

        # Estimer probabilités Skellam pour handicaps centrés (mu1=lambda_h, mu2=lambda_a)
        # Exemple: prob diff >= 1 (home - away >= 1)
        prob_diff_ge_1 = skellam_cdf_range(lambda_h, lambda_a, 1, 10)

        # Requête des lignes du bookmaker (ici : stub -> on utilise meta s'il y en a)
        odds_home = float(meta.get("odds_home", 2.0))

        # Kelly sizing basé sur prob_home_win vs odds
        stake_frac = kelly_fraction(prob_home_win, odds_home)
        if stake_frac <= 0:
            return None

        return Signal(match_id=mid, selection="home_win", side="home", prob_model=prob_home_win, odds=odds_home, meta={"prob_diff_ge_1": prob_diff_ge_1})

    async def evaluate_live(self, match: Dict[str, Any]) -> Optional[Signal]:
        """Évalue signaux In-Play en recalculant lambda via Bayes au fil de l'eau.

        Utilise `bayesian_lambda_update` et recalcule les attentes via Skellam.
        """
        mid = str(match.get("id"))
        meta = match.get("meta", {})

        lambda_pre = float(meta.get("lambda_home", 1.0))
        xg_acc = float(meta.get("xg_home_live_acc", 0.0))
        t_min = float(meta.get("minute", 1.0))
        k = float(meta.get("bayes_k", 1.0))

        lambda_adj = bayesian_lambda_update(lambda_pre, xg_acc, t_min, k)

        # Prob. que home gagne maintenant (approx via Skellam)
        prob_home = sum([skellam_cdf_range(lambda_adj, float(meta.get("lambda_away", 1.0)), d, 10) for d in range(1, 10)])

        odds_home = float(meta.get("odds_home", 2.0))
        stake = kelly_fraction(prob_home, odds_home)
        if stake <= 0:
            return None

        return Signal(match_id=mid, selection="home_win_inplay", side="home", prob_model=prob_home, odds=odds_home, meta={"lambda_adj": lambda_adj})

    async def execute(self, signal: Signal, stake: float) -> None:
        """Enregistre une position exécutée (ne place pas d'ordre réel dans cette version).

        - En production, appelez l'exécution via un broker/API
        - Ici on stocke dans `executed_positions` pour audit.
        """
        # Stockage dans la DB
        await self.db.execute(
            "INSERT INTO executed_positions(match_id, side, stake, odds, prob_model, clv, meta) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                signal.match_id,
                signal.side,
                float(stake),
                float(signal.odds),
                float(signal.prob_model),
                None,
                str(signal.meta),
            ),
        )

        # Log léger
        print(f"EXECUTED: match={signal.match_id} side={signal.side} stake={stake:.4f} odds={signal.odds} p_model={signal.prob_model:.4f}")

