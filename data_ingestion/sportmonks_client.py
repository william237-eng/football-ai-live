"""Client asynchrone minimal pour SportMonks v3.

Ce client est conçu pour être testé sans clé (ZÉRO SUPPOSITION): s'il manque la clé,
il renvoie des structures vides mais garde l'interface asynchrone.

Pour la production, installez `aiohttp` et fournissez SPORTMONKS_TOKEN.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

try:
    import aiohttp  # type: ignore
except Exception:  # pragma: no cover - fallback
    aiohttp = None  # type: ignore


class SportMonksClient:
    def __init__(self, api_token: Optional[str] = None, session: Optional[Any] = None) -> None:
        self.api_token = api_token or os.getenv("SPORTMONKS_TOKEN")
        self._session = session
        self.base_url = "https://soccer.sportmonks.com/api/v2.0"

    async def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if not self.api_token or aiohttp is None:
            # Retourne une structure vide sans faire d'hypothèse humaine
            await asyncio.sleep(0)
            return {}
        params = params or {}
        params.update({"api_token": self.api_token})
        async with aiohttp.ClientSession() as sess:
            async with sess.get(f"{self.base_url}{path}", params=params) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def fetch_upcoming_and_live_matches(self) -> List[Dict[str, Any]]:
        """Récupère matches pré-match et live. Renvoie une liste de dicts normalisés.

        Si l'API n'est pas disponible, renvoie une liste vide (aucune supposition humaine).
        """
        raw = await self._get("/fixtures", params={"include": "localTeam,visitorTeam,weather"})
        data = raw.get("data") if isinstance(raw, dict) else None
        if not data:
            return []
        res = []
        for it in data:
            res.append(
                {
                    "id": it.get("id"),
                    "home_team": it.get("localTeam", {}).get("data", {}).get("name"),
                    "away_team": it.get("visitorTeam", {}).get("data", {}).get("name"),
                    "start_time": it.get("starting_at"),
                    "status": it.get("time", {}).get("status"),
                    "meta": it,
                }
            )
        return res

