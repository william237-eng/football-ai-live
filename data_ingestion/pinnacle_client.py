"""Client asynchrone minimal pour Pinnacle (marchés asiatiques / sharp money).

Comportement : interface asynchrone, fonctionne sans clé (renvoie listes vides).
Pour production, branchez-vous sur l'API Pinnacle et gérez l'authentification.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

try:
    import aiohttp  # type: ignore
except Exception:  # pragma: no cover
    aiohttp = None  # type: ignore


class PinnacleClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("PINNACLE_API_KEY")
        self.base_url = "https://api.pinnacle.com"

    async def fetch_market_lines(self, match_id: str) -> List[Dict[str, Any]]:
        """Renvoie les lignes de marché pour un match donné.

        Si pas de clé, on renvoie une liste vide pour respecter la règle ZÉRO SUPPOSITION.
        """
        await asyncio.sleep(0)
        if not self.api_key or aiohttp is None:
            return []
        # Placeholder : implémentation réelle nécessite endpoints Pinnacle
        return []

