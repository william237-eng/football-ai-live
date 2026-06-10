"""
═══════════════════════════════════════════════════════════════════════════════
ORCHESTRATEUR PRINCIPAL — Moteur de Trading Algorithmique In-Play/Pré-Match
Pilier 1 : Architecture Asynchrone Complète
═══════════════════════════════════════════════════════════════════════════════

Architecture modulaire :
  ├─ data_tier_1.py        : Ingestion Sportmonks v3 + lissage EMA
  ├─ environmental_factors.py  : Fatigue, climat, arbitrage
  ├─ market_veto.py        : Veto bidirectionnel (Pinnacle + Asian Handicap)
  ├─ prematch_engine.py    : ELO, Dixon-Coles, Topologie Tactique
  ├─ live_engine.py        : Bayésien, Monte Carlo Copules, VORP
  ├─ pricing_engine.py     : Skellam, Asian Handicap
  ├─ anomalies.py          : Cartons rouges, blessures fantômes
  ├─ money_management.py   : Kelly fractionné, CLV
  └─ execution.py          : Slippage, liquidité, ordres réels
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sqlite3
import json
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# 3rd party async
import aiohttp
try:
    import asyncpg
except ImportError:
    asyncpg = None  # Fallback: utilise SQLite uniquement

# Modules métier (à importer)
from quant_engine.data_tier_1 import DataTier1Ingestion
from quant_engine.environmental_factors import EnvironmentalFactorsCalculator
from quant_engine.market_veto import MarketVetoEngine
from quant_engine.prematch_engine import PreMatchEngine
from quant_engine.live_engine import LiveEngine
from quant_engine.pricing_engine import PricingEngine
from quant_engine.anomalies_money_management_execution import (
    AnomalyDetector,
    KellyCalculator,
    ExecutionEngine,
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATEUR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

class TradingOrchestrator:
    """
    Orchestrateur central qui coordonne tous les piliers du moteur de trading.
    Gère les boucles ASYNC asynchrones pour :
      1. Ingestion data (Sportmonks + Pinnacle en parallèle)
      2. Analyse pré-match (ELO + Dixon-Coles)
      3. Analyse live minute-by-minute (Bayésien + Monte Carlo)
      4. Décisions trading (Veto, Kelly, Execution)
    """

    def __init__(
        self,
        db_path: str = "quant_engine.db",
        sportmonks_api_key: Optional[str] = None,
        pinnacle_api_user: Optional[str] = None,
        pinnacle_api_token: Optional[str] = None,
    ):
        # Charger les variables d'environnement depuis .env
        load_dotenv()

        self.db_path = db_path
        self.sportmonks_key = sportmonks_api_key or os.getenv("SPORTMONKS_API_KEY")
        self.pinnacle_user = pinnacle_api_user or os.getenv("PINNACLE_API_USER")
        self.pinnacle_token = pinnacle_api_token or os.getenv("PINNACLE_API_TOKEN")

        logger.info(f"✓ TradingOrchestrator loaded with:")
        logger.info(f"  - Sportmonks API: {'✓ Configured' if self.sportmonks_key else '⚠️ Missing'}")
        logger.info(f"  - Pinnacle API: {'✓ Configured' if self.pinnacle_user else '⚠️ Missing'}")
        logger.info(f"  - Database: {db_path}")

        # Modules composants
        self.data_tier = DataTier1Ingestion(sportmonks_api_key)
        self.env_factors = EnvironmentalFactorsCalculator(db_path)
        self.veto_engine = MarketVetoEngine(db_path, pinnacle_api_key=pinnacle_api_user)
        self.prematch = PreMatchEngine(db_path)
        self.live_engine = LiveEngine(db_path)
        self.pricing = PricingEngine(db_path)
        self.anomaly_detector = AnomalyDetector(db_path)
        self.kelly = KellyCalculator(db_path)
        self.execution = ExecutionEngine(db_path)

        # Session HTTP partagée
        self.session: Optional[aiohttp.ClientSession] = None
        self.db_conn: Optional[sqlite3.Connection] = None

    # ─────────────────────────────────────────────────────────────────────────
    # LIFECYCLE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    async def initialize(self):
        """Initialisation : crée la session HTTP et prépare la DB"""
        logger.info("Initialisation du Traders Orchestrator...")
        self.session = aiohttp.ClientSession()
        self._init_sqlite_db()
        logger.info("✓ Orchestrator initialisé")

    async def shutdown(self):
        """Nettoyage gracieux"""
        logger.info("Fermeture du Traders Orchestrator...")
        if self.session:
            await self.session.close()
        if self.db_conn:
            self.db_conn.close()
        logger.info("✓ Orchestrator fermé")

    def _init_sqlite_db(self):
        """Initialise la base de données SQLite avec schéma complet"""
        self.db_conn = sqlite3.connect(self.db_path)
        cursor = self.db_conn.cursor()

        # Charger et exécuter le schéma depuis schema.sql
        schema_path = "quant_engine/schema.sql"
        try:
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            # Split sur -- pour exécuter ligne par ligne
            statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
            for stmt in statements:
                cursor.execute(stmt)
            self.db_conn.commit()
            logger.info(f"✓ Schéma DB initializé depuis {schema_path}")
        except FileNotFoundError:
            logger.warning(f"Schéma SQL non trouvé : {schema_path}. Création manuelle des tables...")
            # Fallback : créer les tables minimales
            cursor.execute("CREATE TABLE IF NOT EXISTS matches (fixture_id INTEGER PRIMARY KEY)")
            cursor.execute("CREATE TABLE IF NOT EXISTS live_snapshots (snapshot_id INTEGER PRIMARY KEY)")
            cursor.execute("CREATE TABLE IF NOT EXISTS market_lines (line_id INTEGER PRIMARY KEY)")
            cursor.execute("CREATE TABLE IF NOT EXISTS executed_positions (position_id INTEGER PRIMARY KEY)")
            self.db_conn.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # BOUCLE PRINCIPALE : PRÉ-MATCH (2h avant kickoff)
    # ─────────────────────────────────────────────────────────────────────────

    async def prematch_pipeline(self, fixture_id: int):
        """
        Pipeline pré-match : ELO + Dixon-Coles + Topologie + Motivation
        Exécuté ~2h avant le match
        """
        logger.info(f"[PREMATCH] Démarrage pipeline pré-match pour fixture {fixture_id}")

        try:
            # 1. Récupérer fixture via Sportmonks
            fixture_data = await self.data_tier.fetch_fixture(fixture_id)
            if not fixture_data:
                logger.error(f"Fixture {fixture_id} non trouvée")
                return

            # 2. Appliquer facteurs environnementaux (Fatigue, Distance, Climat)
            env_adjusted_data = await self.env_factors.calculate_environmental_impact(fixture_data)

            # 3. Calculer Elo Dynamique (basé historique + xG)
            elo_result = await self.prematch.calculate_elo_ratings(fixture_data)
            logger.info(f"[PREMATCH] ELO: Home={elo_result['elo_home']:.1f}, Away={elo_result['elo_away']:.1f}")

            # 4. Appliquer Dixon-Coles avec topologie tactique & motivation
            dixon_coles = await self.prematch.dixon_coles_with_tactics(
                elo_result,
                env_adjusted_data,
                fixture_data
            )
            logger.info(f"[PREMATCH] Dixon-Coles λ: Home={dixon_coles['lambda_home']:.3f}, Away={dixon_coles['lambda_away']:.3f}")

            # 5. Sauvegarder résultats pré-match
            await self._save_prematch_results(fixture_id, dixon_coles, env_adjusted_data)

            logger.info(f"[PREMATCH] ✓ Pipeline complété pour fixture {fixture_id}")
            return dixon_coles

        except Exception as e:
            logger.error(f"[PREMATCH] Erreur pipeline pré-match: {e}", exc_info=True)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # BOUCLE PRINCIPALE : LIVE (Min-by-Min)
    # ─────────────────────────────────────────────────────────────────────────

    async def live_pipeline(self, fixture_id: int, min_interval: int = 60):
        """
        Pipeline LIVE : Récurrence minute par minute pendant le match
        - Récupère snapshot live (score, xG, PPDA, corners, cartons)
        - Recalcule λ via Bayésien
        - Détecte anomalies (cartons rouges, blessures fantômes)
        - Gère VORP substitutions
        - Évalue positions et trading opportunities
        """
        logger.info(f"[LIVE] Démarrage pipeline live pour fixture {fixture_id}")

        # Boucle tout le match (90 min + extra)
        minute = 0
        while minute <= 120:
            try:
                # 1. Récupérer snapshot live Sportmonks
                live_data = await self.data_tier.fetch_live_snapshot(fixture_id, minute)
                if not live_data:
                    await asyncio.sleep(min_interval)
                    minute += 1
                    continue

                logger.debug(f"[LIVE] Minute {minute}: Score {live_data['home_score']}-{live_data['away_score']}")

                # 2. Recalculer λ (Lambda) via Théorème de Bayes
                bayes_lambda = await self.live_engine.bayesian_lambda_update(
                    fixture_id,
                    live_data,
                    minute
                )
                logger.debug(f"[LIVE] Bayesian λ: Home={bayes_lambda['lambda_home']:.3f}, Away={bayes_lambda['lambda_away']:.3f}")

                # 3. Détecter anomalies
                anomalies = await self.anomaly_detector.detect_anomalies(
                    fixture_id,
                    live_data,
                    minute
                )
                if anomalies:
                    logger.warning(f"[LIVE] Anomalies détectées: {anomalies}")

                # 4. Monte Carlo avec Copules Gaussiennes
                mc_scenarios = await self.live_engine.monte_carlo_copula_scenarios(
                    bayes_lambda,
                    live_data,
                    min_remaining=120 - minute,
                    n_simulations=10000
                )

                # 5. Gérer VORP substitutions
                if live_data.get("substitutions"):
                    for sub in live_data["substitutions"]:
                        vorp_adjustment = await self.live_engine.calculate_vorp(sub)
                        logger.info(f"[LIVE] VORP substitution: {sub['player_out']} → {sub['player_in']}: Δλ={vorp_adjustment}")

                # 6. Pricing via Skellam & détection value
                skellam_pricing = await self.pricing.skellam_pricing(bayes_lambda, live_data)

                # 7. Veto bidirectionnel (Pinnacle)
                market_lines = await self.data_tier.fetch_market_lines(fixture_id)
                veto_decision = await self.veto_engine.bidirectional_veto(
                    skellam_pricing,
                    market_lines,
                    threshold_pct=5.0
                )

                if not veto_decision["allow_trade"]:
                    logger.warning(f"[LIVE] VETO: {veto_decision['reason']}")
                    await asyncio.sleep(min_interval)
                    minute += 1
                    continue

                # 8. Kelly Fractionné
                kelly_sizing = await self.kelly.calculate_kelly_fraction(
                    skellam_pricing,
                    market_lines,
                    fraction=0.25  # 25% Kelly
                )

                # 9. Exécution (si stake > 0)
                if kelly_sizing["stake_units"] > 0:
                    execution_result = await self.execution.place_order(
                        fixture_id=fixture_id,
                        market_type=kelly_sizing["market_type"],
                        side=kelly_sizing["side"],
                        stake_units=kelly_sizing["stake_units"],
                        odds=market_lines.get("odds"),
                        slippage_tolerance_pct=2.0
                    )
                    logger.info(f"[LIVE] Ordre placé: {execution_result}")

                # 10. Sauvegarder snapshot + décisions
                await self._save_live_snapshot(
                    fixture_id,
                    minute,
                    live_data,
                    bayes_lambda,
                    skellam_pricing,
                    mc_scenarios
                )

                await asyncio.sleep(min_interval)
                minute += 1

            except Exception as e:
                logger.error(f"[LIVE] Erreur à minute {minute}: {e}", exc_info=True)
                await asyncio.sleep(min_interval)
                minute += 1

        logger.info(f"[LIVE] ✓ Pipeline live complété pour fixture {fixture_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # FONCTIONS UTILITAIRES DB
    # ─────────────────────────────────────────────────────────────────────────

    async def _save_prematch_results(self, fixture_id: int, dixon_coles: Dict, env_data: Dict):
        """Sauvegarde résultats pré-match en DB"""
        cursor = self.db_conn.cursor()
        cursor.execute(
            """
            UPDATE matches SET
                final_lambda_home = ?,
                final_lambda_away = ?,
                fatigue_coeff_home = ?,
                fatigue_coeff_away = ?,
                tactical_vulnerability_home = ?,
                tactical_vulnerability_away = ?,
                motivation_urgency_home = ?,
                motivation_urgency_away = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (
                dixon_coles.get("lambda_home"),
                dixon_coles.get("lambda_away"),
                env_data.get("fatigue_coeff_home", 1.0),
                env_data.get("fatigue_coeff_away", 1.0),
                env_data.get("tactical_vuln_home", 1.0),
                env_data.get("tactical_vuln_away", 1.0),
                env_data.get("urgency_home", 1.0),
                env_data.get("urgency_away", 1.0),
                fixture_id
            )
        )
        self.db_conn.commit()

    async def _save_live_snapshot(
        self,
        fixture_id: int,
        minute: int,
        live_data: Dict,
        bayes_lambda: Dict,
        skellam_pricing: Dict,
        mc_scenarios: Dict
    ):
        """Sauvegarde snapshot live minute-by-minute"""
        cursor = self.db_conn.cursor()
        cursor.execute(
            """
            INSERT INTO live_snapshots (
                fixture_id, minute_elapsed, timestamp,
                home_score, away_score,
                xg_home_accumulated, xg_away_accumulated,
                possession_pct_home, possession_pct_away,
                shots_total_home, shots_total_away,
                corners_home, corners_away,
                yellows_home, yellows_away,
                reds_home, reds_away,
                lambda_home_live, lambda_away_live,
                red_card_home, red_card_away,
                ghost_injury_detected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fixture_id,
                minute,
                int(datetime.now().timestamp()),
                live_data.get("home_score", 0),
                live_data.get("away_score", 0),
                live_data.get("xg_home_accumulated", 0.0),
                live_data.get("xg_away_accumulated", 0.0),
                live_data.get("possession_pct_home", 50),
                live_data.get("possession_pct_away", 50),
                live_data.get("shots_total_home", 0),
                live_data.get("shots_total_away", 0),
                live_data.get("corners_home", 0),
                live_data.get("corners_away", 0),
                live_data.get("yellows_home", 0),
                live_data.get("yellows_away", 0),
                live_data.get("reds_home", 0),
                live_data.get("reds_away", 0),
                bayes_lambda.get("lambda_home"),
                bayes_lambda.get("lambda_away"),
                live_data.get("red_card_home", False),
                live_data.get("red_card_away", False),
                live_data.get("ghost_injury", False)
            )
        )
        self.db_conn.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # POINT D'ENTRÉE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    async def run(self, fixture_ids: List[int]):
        """Exécute l'orchestrateur pour une liste de fixtures"""
        await self.initialize()

        try:
            # Tâches concurrentes : pré-match + live pour plusieurs fixtures
            tasks = []
            for fid in fixture_ids:
                # Pré-match
                tasks.append(self.prematch_pipeline(fid))
                # Live (en parallèle)
                tasks.append(self.live_pipeline(fid))

            # Exécution concurrente
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Orchestrator complet: {len([r for r in results if r])} tâches réussies")

        finally:
            await self.shutdown()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN D'EXÉCUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Exemple d'utilisation
    orchestrator = TradingOrchestrator(
        db_path="quant_engine.db",
        sportmonks_api_key="YOUR_SPORTMONKS_KEY",
        pinnacle_api_user="YOUR_PINNACLE_USER",
        pinnacle_api_token="YOUR_PINNACLE_TOKEN",
    )

    # Lancer pour fixtures 12345, 12346, 12347
    asyncio.run(orchestrator.run([12345, 12346, 12347]))

