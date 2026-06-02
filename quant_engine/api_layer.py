"""
Football API Layer

This layer intentionally does NOT fabricate or simulate data. It only wraps
real providers passed by the integrator. If no provider is configured or all
providers fail, the layer returns None so the pipeline can surface a clear
message to the user (e.g. "Données live indisponibles").

Integrators must supply one or more provider callables with the signature:
    provider(endpoint: str, params: dict) -> dict | None

The module contains no demo/local provider to avoid any accidental data
fabrication.
"""
import time
from typing import Optional, Dict, Any, Callable, List


class FootballAPI:
    def __init__(self, providers: Optional[List[Callable]] = None, max_retries: int = 3, backoff: float = 1.0):
        # providers: list of callables or endpoint wrappers in priority order
        self.providers = providers or []
        self.max_retries = int(max_retries)
        self.backoff = float(backoff)

    def _call_provider(self, provider: Callable, endpoint: str, params: Dict[str, Any]):
        return provider(endpoint, params)

    def fetch(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch data from providers with retry and fallback.
        Returns None if all providers fail or no providers are configured.
        No data is ever fabricated here.
        """
        params = params or {}
        if not self.providers:
            return None
        for provider in self.providers:
            attempts = 0
            while attempts < self.max_retries:
                try:
                    res = self._call_provider(provider, endpoint, params)
                    # provider must explicitly return None when unavailable
                    if res is None:
                        raise RuntimeError("provider returned no data")
                    return res
                except Exception:
                    attempts += 1
                    time.sleep(self.backoff * attempts)
                    continue
        # all providers failed
        return None


