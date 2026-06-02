"""
Data Pipeline
Handles ingestion, normalization and integrity checks. This pipeline will
NOT fabricate missing data. When data are unavailable or insufficient we
return clear error messages (in French) so downstream modules can act
accordingly.
"""
import json
import os
from typing import Any, Dict, List

from .api_layer import FootballAPI


class DataPipeline:
    def __init__(self, api: FootballAPI = None, cache_dir: str = None):
        self.api = api or FootballAPI(providers=[])
        self.cache_dir = cache_dir or os.path.join(os.getcwd(), "quant_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_path(self, key: str) -> str:
        safe = key.replace("/", "_")
        return os.path.join(self.cache_dir, f"{safe}.json")

    def fetch_fixtures(self) -> Dict[str, Any]:
        res = self.api.fetch("fixtures", {})
        if res is None:
            # no fabricated fallback: inform caller
            return {"error": "Données live indisponibles", "source": "api", "endpoint": "fixtures"}
        # basic integrity
        if not isinstance(res, list) or not res:
            return {"error": "Données insuffisantes", "details": "fixtures vides"}
        # cache copy for offline inspection
        try:
            with open(self._cache_path("fixtures"), "w", encoding="utf-8") as f:
                json.dump(res, f)
        except Exception:
            pass
        return {"data": res, "last_update": os.path.getmtime(self._cache_path("fixtures"))}

    def _check_live_stats_integrity(self, res: Dict[str, Any]) -> List[str]:
        required = ["minute", "xG_home", "xG_away", "shots_home", "shots_away", "possession_home"]
        missing = [k for k in required if k not in res]
        return missing

    def fetch_live_stats(self, match_id: int, minute: int = 0) -> Dict[str, Any]:
        res = self.api.fetch("live_stats", {"match_id": match_id, "minute": minute})
        if res is None:
            return {"error": "Données live indisponibles", "endpoint": "live_stats", "match_id": match_id}
        missing = self._check_live_stats_integrity(res)
        if missing:
            return {"error": "Données insuffisantes", "missing_fields": missing}
        return {"data": res, "last_update": None}

    def fetch_historical(self, team: str) -> Dict[str, Any]:
        res = self.api.fetch("historical", {"team": team})
        if res is None:
            return {"error": "Données live indisponibles", "endpoint": "historical", "team": team}
        matches = res.get("matches") if isinstance(res, dict) else None
        if not matches:
            return {"error": "Données insuffisantes", "details": "historical matches manquantes", "team": team}
        return {"data": {"matches": matches}}

