from dotenv import load_dotenv
import os
import logging
from typing import List, Dict, Any, Tuple, Optional
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Charger .env seulement si les secrets Streamlit ne sont pas disponibles
try:
    import streamlit as st
    _streamlit_available = True
except ImportError:
    _streamlit_available = False

def get_config(key: str, default: str = None) -> str:
    """
    Récupère une configuration depuis st.secrets (priorité) ou .env (fallback).
    """
    # Priorité 1: Streamlit secrets
    if _streamlit_available:
        try:
            # Essayer d'abord dans la section 'api' si elle existe
            if 'api' in st.secrets and key in st.secrets['api']:
                return st.secrets['api'][key]
            # Sinon, chercher directement dans les secrets
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass  # Streamlit peut ne pas être initialisé
    
    # Priorité 2: Variables d'environnement (.env)
    load_dotenv()  # Charger .env si pas déjà fait
    return os.getenv(key, default)

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    pass


class APIError(Exception):
    pass


class RateLimitError(APIError):
    pass


class NetworkError(Exception):
    pass


class FootballAPI:
    """Robust API-Football client with retries, pagination and logging.

    Methods:
        is_configured() -> bool
        get_live_matches() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]
    """

    def __init__(self, timeout: int = 10, max_retries: int = 3, backoff_factor: float = 0.3, max_pages: int = 10):
        self.api_key = get_config("API_KEY")
        self.api_url = get_config("API_URL")
        self.provider = get_config("API_PROVIDER", "api-football")

        if not self.api_key or not self.api_url:
            raise ConfigError(
                "API_KEY ou API_URL manquant. "
                "Configurez-les dans .env (local) ou st.secrets (Streamlit Cloud)."
            )

        self.timeout = timeout
        self.max_pages = max_pages

        # session with retry strategy
        self.session = requests.Session()
        retries = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "ia-live-dashboard/1.0 (+https://example.com)",
        })

        self.session.headers.update({"x-apisports-key": self.api_key})

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_url)

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout as e:
            logger.error("Timeout when calling %s", url)
            raise
        except requests.exceptions.RequestException as e:
            logger.error("Network error when calling %s: %s", url, e)
            raise NetworkError(str(e)) from e

        if resp.status_code == 429:
            # Rate limit hit
            retry_after = resp.headers.get("Retry-After")
            logger.warning("Rate limit reached (429). Retry-After: %s", retry_after)
            raise RateLimitError("Limite API atteinte")

        if not resp.ok:
            # try parse message
            try:
                data = resp.json()
                msg = data.get("message") or data.get("errors") or data
            except ValueError:
                msg = resp.text

            logger.error("API returned error %s: %s", resp.status_code, msg)
            raise APIError(f"API error {resp.status_code}: {msg}")

        try:
            return resp.json()
        except ValueError as e:
            logger.error("Invalid JSON from API at %s", url)
            raise APIError("Réponse API invalide (JSON attendu)") from e

    def get_live_matches(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Retrieve all live fixtures, handling pagination when available.

        Returns:
            (fixtures_list, meta) where meta contains keys: total, fetched_at (ISO), pages_fetched
        Raises ConfigError, RateLimitError, APIError, NetworkError
        """
        if not self.is_configured():
            raise ConfigError("API non configurée")

        base = f"{self.api_url.rstrip('/')}/fixtures"
        params = {"live": "all"}

        collected: List[Dict[str, Any]] = []
        pages_fetched = 0

        # Pagination: try pages 1..max_pages if API supports 'page' param and 'paging' in response
        page = 1
        while True:
            if page > 1:
                params["page"] = page

            logger.info("Fetching live fixtures page %s", page)
            data = self._get(base, params=params)

            # API-Football typically returns {'response': [...], 'paging': {...}}
            items = []
            if isinstance(data, dict) and "response" in data:
                items = data.get("response") or []
                paging = data.get("paging") or {}
            elif isinstance(data, list):
                items = data
                paging = {}
            else:
                items = []
                paging = {}

            collected.extend(items)
            pages_fetched += 1

            total_expected = paging.get("total") or len(collected)

            logger.info("Page %s fetched: %s items (collected total %s)", page, len(items), len(collected))

            # stop if no items returned
            if not items:
                break

            # stop if paging says we've fetched all
            if paging and int(paging.get("total", 0)) <= len(collected):
                break

            # stop if we reached max pages
            if pages_fetched >= self.max_pages:
                logger.warning("Reached max_pages (%s) while fetching live fixtures", self.max_pages)
                break

            # increment page and continue
            page += 1
            # small sleep to avoid hammering API
            time.sleep(0.1)

        fetched_at = datetime.utcnow().isoformat() + "Z"

        meta = {"total": len(collected), "fetched_at": fetched_at, "pages": pages_fetched}

        if not collected:
            logger.warning("No live fixtures returned by API")

        logger.info("Total live fixtures collected: %s", len(collected))

        return collected, meta

    def get_future_matches(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Retrieve future fixtures (upcoming matches).

        Endpoint (API-Football):
          /fixtures?next=50
        """
        if not self.is_configured():
            raise ConfigError("API non configurée")

        base = f"{self.api_url.rstrip('/')}/fixtures"
        params = {"next": 50}

        data = self._get(base, params=params)

        items: List[Dict[str, Any]] = []
        if isinstance(data, dict) and "response" in data:
            items = data.get("response") or []
        elif isinstance(data, list):
            items = data

        fetched_at = datetime.utcnow().isoformat() + "Z"
        meta = {"total": len(items), "fetched_at": fetched_at}
        return items, meta

    def get_fixture_detail(self, fixture_id: int) -> Dict[str, Any]:
        base = f"{self.api_url.rstrip('/')}/fixtures"
        return self._get(base, params={"id": fixture_id})

    def get_fixture_statistics(self, fixture_id: int) -> Dict[str, Any]:
        base = f"{self.api_url.rstrip('/')}/fixtures/statistics"
        return self._get(base, params={"fixture": fixture_id})

    def get_fixture_events(self, fixture_id: int) -> Dict[str, Any]:
        base = f"{self.api_url.rstrip('/')}/fixtures/events"
        return self._get(base, params={"fixture": fixture_id})

    def get_fixture_lineups(self, fixture_id: int) -> Dict[str, Any]:
        base = f"{self.api_url.rstrip('/')}/fixtures/lineups"
        return self._get(base, params={"fixture": fixture_id})

    def get_team_recent_fixtures(self, team_id: int, count: int = 5) -> Dict[str, Any]:
        base = f"{self.api_url.rstrip('/')}/fixtures"
        return self._get(base, params={"team": team_id, "last": count})

    def get_team_statistics(self, league_id: int, season: int, team_id: int) -> Dict[str, Any]:
        base = f"{self.api_url.rstrip('/')}/teams/statistics"
        return self._get(base, params={"league": league_id, "season": season, "team": team_id})

    def get_head_to_head(self, home_team_id: int, away_team_id: int, count: int = 5) -> Dict[str, Any]:
        base = f"{self.api_url.rstrip('/')}/fixtures/headtohead"
        return self._get(base, params={"h2h": f"{home_team_id}-{away_team_id}", "last": count})

    def get_standings(self, league_id: int, season: int) -> Dict[str, Any]:
        base = f"{self.api_url.rstrip('/')}/standings"
        return self._get(base, params={"league": league_id, "season": season})

    def get_fixtures_by_date(self, date: str, league_id: int = None, season: int = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Get fixtures for a specific date (YYYY-MM-DD format)."""
        if not self.is_configured():
            raise ConfigError("API non configurée")

        base = f"{self.api_url.rstrip('/')}/fixtures"
        params: Dict[str, Any] = {"date": date}
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season

        data = self._get(base, params=params)
        items: List[Dict[str, Any]] = []
        if isinstance(data, dict) and "response" in data:
            items = data.get("response") or []
        elif isinstance(data, list):
            items = data

        fetched_at = datetime.utcnow().isoformat() + "Z"
        meta = {"total": len(items), "fetched_at": fetched_at}
        return items, meta

    def get_leagues(self, country: str = None, season: int = None, current: bool = True) -> Dict[str, Any]:
        """Get available leagues/competitions."""
        if not self.is_configured():
            raise ConfigError("API non configurée")

        base = f"{self.api_url.rstrip('/')}/leagues"
        params: Dict[str, Any] = {}
        if country:
            params["country"] = country
        if season:
            params["season"] = season
        if current:
            params["current"] = "true"

        return self._get(base, params=params)

    def get_fixtures_next_n(self, n: int = 100, league_id: int = None, season: int = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Get next N fixtures globally or for a specific league."""
        if not self.is_configured():
            raise ConfigError("API non configurée")

        base = f"{self.api_url.rstrip('/')}/fixtures"
        params: Dict[str, Any] = {"next": n}
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season

        data = self._get(base, params=params)
        items: List[Dict[str, Any]] = []
        if isinstance(data, dict) and "response" in data:
            items = data.get("response") or []
        elif isinstance(data, list):
            items = data

        fetched_at = datetime.utcnow().isoformat() + "Z"
        meta = {"total": len(items), "fetched_at": fetched_at}
        return items, meta
