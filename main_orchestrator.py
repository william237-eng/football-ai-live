"""Orchestrateur principal asynchrone.

Ce fichier démarre les composants : ingestion, stockage, moteur quantitatif et gestion du risque.
Toutes les décisions sont basées sur des calculs mathématiques auditablement commentés.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

from core.trading_engine import TradingEngine
from data_ingestion.sportmonks_client import SportMonksClient
from data_ingestion.pinnacle_client import PinnacleClient
from storage.db import AsyncDB
from risk_management.veto import MarketVeto
from risk_management.money_management import MoneyManager


async def main() -> None:
    """Point d'entrée asynchrone.

    Utilisation:
        export SPORTMONKS_TOKEN=xxx
        export PINNACLE_API_KEY=yyy
        python -m main_orchestrator
    """
    # Configuration (ZÉRO SUPPOSITION HUM. valeurs depuis variables d'environnement)
    sportmonks_token = os.getenv("SPORTMONKS_TOKEN")
    pinnacle_key = os.getenv("PINNACLE_API_KEY")
    db_dsn = os.getenv("QL_DB_DSN", "sqlite:///./quant_engine.db")

    # Initialisation des composants
    db = AsyncDB(dsn=db_dsn)
    await db.connect()
    await db.ensure_schema()

    sm_client = SportMonksClient(api_token=sportmonks_token)
    pin_client = PinnacleClient(api_key=pinnacle_key)

    trading_engine = TradingEngine(db=db, sm_client=sm_client, pin_client=pin_client)
    market_veto = MarketVeto(db=db, pin_client=pin_client)
    money_manager = MoneyManager(db=db)

    # Boucle principale : ingestion périodique + réévaluation des marchés
    async def loop_forever() -> None:
        while True:
            try:
                # 1) Récupérer les matches live et pré-match
                matches = await sm_client.fetch_upcoming_and_live_matches()

                # 2) Mettre à jour la base
                await db.upsert_matches(matches)

                # 3) Calculer signaux pré-match
                for m in matches:
                    # trading_engine s'occupe d'ignorer les cas où il manque des données
                    signal = await trading_engine.evaluate_pre_match(m)
                    if signal is not None:
                        # Veto de marché (sharp money / mouvement asiatique)
                        if market_veto.should_veto(signal):
                            continue
                        # Position sizing
                        stake = await money_manager.stake_for_signal(signal)
                        if stake > 0:
                            await trading_engine.execute(signal, stake)

                # 4) Réévaluer les marchés live (minute par minute)
                live_matches = [m for m in matches if m.get("status") == "live"]
                for m in live_matches:
                    signal = await trading_engine.evaluate_live(m)
                    if signal is not None:
                        if market_veto.should_veto(signal):
                            continue
                        stake = await money_manager.stake_for_signal(signal)
                        if stake > 0:
                            await trading_engine.execute(signal, stake)

            except Exception as e:  # pragma: no cover - top-level resilient loop
                print("Orchestrator error:", e)

            # Attendre 15s entre itérations pour limiter la charge (paramétrable)
            await asyncio.sleep(15)

    # Démarrage
    try:
        await loop_forever()
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())

