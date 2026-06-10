"""
═══════════════════════════════════════════════════════════════════════════════
PILIER 2 : DATA TIER 1 & LISSAGE DU BRUIT
Ingestion Sportmonks v3 + Pinnacle + Application EMA sur Pressure Index
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime
from collections import deque
import os

import aiohttp
import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# EMA (Exponential Moving Average) — Lissage bruit Pressure Index
# ═══════════════════════════════════════════════════════════════════════════════

class ExponentialMovingAverage:
    """
    Calcule l'EMA sur le Live Pressure Index pour filtrer le bruit tactique.
    α = 2 / (N + 1) où N est la fenêtre (ex: N=5 pour 5 minutes)
    """

    def __init__(self, window: int = 5):
        self.window = window
        self.alpha = 2.0 / (window + 1)
        self.ema_value: Optional[float] = None

    def update(self, new_value: float) -> float:
        """Ajoute nouveau point et retourne EMA lissée"""
        if self.ema_value is None:
            self.ema_value = new_value
        else:
            self.ema_value = self.alpha * new_value + (1 - self.alpha) * self.ema_value
        return self.ema_value


# ═══════════════════════════════════════════════════════════════════════════════
# DATA TIER 1 : INGESTION SPORTMONKS v3
# ═══════════════════════════════════════════════════════════════════════════════

class DataTier1Ingestion:
    """
    Connexion asynchrone à Sportmonks v3 API pour :
    - Fixtures (matchs) pré-match
    - Live snapshots minute-by-minute
    - xG, possession, shots, corners
    - Cartons, substitutions
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.sportmonks.com/v3"):
        # Charger depuis .env si pas fourni en argument
        if api_key is None:
            api_key = os.getenv("SPORTMONKS_API_KEY", "")
            if not api_key:
                logger.warning("⚠️ SPORTMONKS_API_KEY non défini en variables d'environnement")

        self.api_key = api_key
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info(f"✓ DataTier1Ingestion initialisé avec Sportmonks v3")

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # ─────────────────────────────────────────────────────────────────────────
    # REQUÊTES ASYNCHRONES À L'API
    # ─────────────────────────────────────────────────────────────────────────

    async def _get(self, endpoint: str, include: str = "") -> Optional[Dict]:
        """Requête GET générique avec gestion erreurs"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.base_url}/{endpoint}?api_token={self.api_key}"
        if include:
            url += f"&include={include}"

        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"API Sportmonks error: {resp.status} - {await resp.text()}")
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout on {endpoint}")
            return None
        except Exception as e:
            logger.error(f"Requête API échouée ({endpoint}): {e}")
            return None

    async def fetch_fixture(self, fixture_id: int) -> Optional[Dict]:
        """Récupère fixture pré-match avec tous les includes"""
        includes = "league,season,teams,statistics,predictions,odds"
        data = await self._get(f"fixtures/{fixture_id}", include=includes)

        if not data or "data" not in data:
            return None

        fixture = data["data"]
        return {
            "fixture_id": fixture.get("id"),
            "kickoff_ts": fixture.get("starting_at"),
            "home_team_id": fixture.get("participants", [{}])[0].get("id"),
            "away_team_id": fixture.get("participants", [{}])[1].get("id"),
            "home_team": fixture.get("participants", [{}])[0].get("name"),
            "away_team": fixture.get("participants", [{}])[1].get("name"),
            "league_id": fixture.get("league_id"),
            "league_name": fixture.get("league", {}).get("name"),
            "venue": fixture.get("venue", {}).get("name"),
            "weather_condition": fixture.get("weather_report", {}).get("condition"),
            "precipitation_mm": fixture.get("weather_report", {}).get("precipitation", 0),
        }

    async def fetch_live_snapshot(self, fixture_id: int, minute: int) -> Optional[Dict]:
        """
        Récupère snapshot LIVE minute-by-minute
        Inclut : score, xG, possession, shots, corners, cartons, substitutions
        """
        data = await self._get(
            f"fixtures/{fixture_id}",
            include="events,statistics,goals,cards,substitutions"
        )

        if not data or "data" not in data:
            return None

        fixture = data["data"]

        # Extraire stats par équipe
        home_stats = fixture.get("statistics", {}).get("home", {})
        away_stats = fixture.get("statistics", {}).get("away", {})

        return {
            "fixture_id": fixture.get("id"),
            "minute_elapsed": minute,
            "home_score": fixture.get("scores", {}).get("home", 0),
            "away_score": fixture.get("scores", {}).get("away", 0),
            "xg_home_accumulated": home_stats.get("xg", 0.0),
            "xg_away_accumulated": away_stats.get("xg", 0.0),
            "xg_home_live": home_stats.get("xg", 0.0),
            "xg_away_live": away_stats.get("xg", 0.0),
            "possession_pct_home": home_stats.get("possession_percentage", 50),
            "possession_pct_away": away_stats.get("possession_percentage", 50),
            "shots_total_home": home_stats.get("shots_total", 0),
            "shots_total_away": away_stats.get("shots_total", 0),
            "shots_on_target_home": home_stats.get("shots_on_target", 0),
            "shots_on_target_away": away_stats.get("shots_on_target", 0),
            "corners_home": home_stats.get("corner_kicks", 0),
            "corners_away": away_stats.get("corner_kicks", 0),
            "yellows_home": len([c for c in fixture.get("cards", []) if c.get("team_id") == fixture.get("participants", [{}])[0].get("id") and c.get("type") == "yellow"]),
            "yellows_away": len([c for c in fixture.get("cards", []) if c.get("team_id") == fixture.get("participants", [{}])[1].get("id") and c.get("type") == "yellow"]),
            "reds_home": len([c for c in fixture.get("cards", []) if c.get("team_id") == fixture.get("participants", [{}])[0].get("id") and c.get("type") == "red"]),
            "reds_away": len([c for c in fixture.get("cards", []) if c.get("team_id") == fixture.get("participants", [{}])[1].get("id") and c.get("type") == "red"]),
            "substitutions": fixture.get("substitutions", []),
            "events": fixture.get("events", []),
        }

    async def fetch_team_stats(self, team_id: int, season_id: int) -> Optional[Dict]:
        """Récupère stats de saison pour calcul Elo"""
        data = await self._get(
            f"teams/{team_id}/statistics/seasons/{season_id}",
            include="goals,xg,tackles,fouls,cards"
        )

        if not data or "data" not in data:
            return None

        stats = data["data"]
        return {
            "team_id": team_id,
            "season_id": season_id,
            "goals_for": stats.get("goals_for", 0),
            "goals_against": stats.get("goals_against", 0),
            "xg_for": stats.get("xg_for", 0.0),
            "xg_against": stats.get("xg_against", 0.0),
            "tackles": stats.get("tackles", 0),
            "fouls_committed": stats.get("fouls_committed", 0),
            "yellow_cards": stats.get("yellow_cards", 0),
            "red_cards": stats.get("red_cards", 0),
        }

    async def fetch_h2h_history(self, home_id: int, away_id: int, limit: int = 10) -> List[Dict]:
        """
        Récupère historique H2H (derniers matchs directs)
        Utile pour calculs Dixon-Coles et motivation
        """
        # Sportmonks v3 : /fixtures?filter[heads_to_head][parametre]=valeur
        data = await self._get(
            f"fixtures?filter[heads_to_head]={home_id},{away_id}&limit={limit}",
            include="statistics"
        )

        if not data or "data" not in data:
            return []

        fixtures = data["data"]
        results = []
        for fixture in fixtures:
            results.append({
                "fixture_id": fixture.get("id"),
                "home_score": fixture.get("scores", {}).get("home", 0),
                "away_score": fixture.get("scores", {}).get("away", 0),
                "xg_home": fixture.get("statistics", {}).get("home", {}).get("xg", 0.0),
                "xg_away": fixture.get("statistics", {}).get("away", {}).get("xg", 0.0),
            })

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # CALCUL PRESSURE INDEX & EMA
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_pressure_index(live_data: Dict, team: str = "home") -> float:
        """
        Calcule le Live Pressure Index (0-100) pour une équipe.
        Formula:
             PI = [Shots/xG ratio] * [Possession %] * [Corners] * [PPDA] / Normalization
        """
        prefix = "home" if team == "home" else "away"

        shots = live_data.get(f"shots_total_{prefix}", 0.0) + 1e-6  # Avoid div by zero
        xg = live_data.get(f"xg_{prefix}_accumulated", 0.0) + 1e-6
        possession = live_data.get(f"possession_pct_{prefix}", 50.0)
        corners = live_data.get(f"corners_{prefix}", 0)
        ppda = live_data.get(f"ppda_{prefix}", 10.0)

        # PPDA: Passes Per Defensive Action — plus bas = plus agressif
        ppda_component = 1.0 / max(ppda, 1.0)

        # Normalised Pressure Index (0-100)
        pressure = (
            (shots / xg) * 0.25 +  # Shot efficiency
            (possession / 100.0) * 0.25 +  # Possession weight
            (corners / 10.0) * 0.25 +  # Corner activity
            ppda_component * 0.25  # Defensive aggression
        ) * 25

        return min(100.0, max(0.0, pressure))

    async def fetch_market_lines(self, fixture_id: int, bookmaker: str = "pinnacle") -> Optional[Dict]:
        """
        Récupère les cotes du marché (O/U 2.5, Asian Handicap, 1X2)
        Source: Sportmonks Odds API (intégration Pinnacle)
        """
        data = await self._get(
            f"fixtures/{fixture_id}/odds",
            include=f"bookmakers={bookmaker}"
        )

        if not data or "data" not in data:
            return None

        odds_data = data["data"]

        # Parser les cotes en fonction du bookmaker
        results = {
            "fixture_id": fixture_id,
            "timestamp": int(datetime.now().timestamp()),
            "bookmaker": bookmaker,
        }

        for market in odds_data.get("markets", []):
            market_name = market.get("name", "").lower()

            if "over/under 2.5" in market_name:
                results["ou_2_5_over_odds"] = market.get("over", {}).get("odds")
                results["ou_2_5_under_odds"] = market.get("under", {}).get("odds")

            elif "asian handicap" in market_name or "handicap" in market_name:
                results["ah_home_line"] = market.get("home", {}).get("line")
                results["ah_home_odds"] = market.get("home", {}).get("odds")
                results["ah_away_odds"] = market.get("away", {}).get("odds")

            elif "1x2" in market_name or "match result" in market_name:
                results["odds_1"] = market.get("home", {}).get("odds")
                results["odds_x"] = market.get("draw", {}).get("odds")
                results["odds_2"] = market.get("away", {}).get("odds")

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# LISSAGE PRESSION LIVE VIA EMA
# ═══════════════════════════════════════════════════════════════════════════════

async def apply_ema_to_pressure_index(
    snapshots: List[Dict],
    window: int = 5
) -> List[Dict]:
    """
    Applique EMA sur le Pressure Index de chaque snapshot pour filtrer le bruit.
    Retourne les snapshots enrichis avec champs EMA.
    """
    ema_home = ExponentialMovingAverage(window=window)
    ema_away = ExponentialMovingAverage(window=window)

    for snapshot in snapshots:
        # Calculer pressures brutes
        pi_home = DataTier1Ingestion.calculate_pressure_index(snapshot, team="home")
        pi_away = DataTier1Ingestion.calculate_pressure_index(snapshot, team="away")

        # Appliquer EMA
        snapshot["pressure_index_home"] = pi_home
        snapshot["pressure_index_away"] = pi_away
        snapshot["pressure_index_ema_home"] = ema_home.update(pi_home)
        snapshot["pressure_index_ema_away"] = ema_away.update(pi_away)

    return snapshots


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN D'TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test_data_tier():
        tier = DataTier1Ingestion(api_key="YOUR_KEY")

        # Test fixture
        fixture = await tier.fetch_fixture(fixture_id=12345)
        print(f"Fixture: {fixture}")

        # Test EMA sur snapshots
        snapshots = [
            {"pressure_index_brut_home": 45.0},
            {"pressure_index_brut_home": 48.0},
            {"pressure_index_brut_home": 50.0},
        ]
        smoothed = await apply_ema_to_pressure_index(snapshots, window=2)
        print(f"EMA Applied: {smoothed}")

    asyncio.run(test_data_tier())

