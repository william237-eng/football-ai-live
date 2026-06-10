"""Asynchronous Sportmonks v3 minimal client used for ingestion.

This module reads the API key from the environment variable
`SPORTMONKS_API_KEY` and exposes small helpers to fetch fixtures by date.

Do NOT commit API keys into the repository. Use environment variables
or a secrets manager in production.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any, Dict, List, Optional

import aiohttp


DEFAULT_BASE = "https://soccer.sportmonks.com/api/v3"


def _get_api_key() -> Optional[str]:
    """Read API key from env.

    Returns None if not set.
    """
    return os.environ.get("SPORTMONKS_API_KEY")


async def fetch_fixtures_by_date(target_date: str, *, session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Fetch fixtures for a given date (YYYY-MM-DD) from Sportmonks.

    This is intentionally minimal: it returns the JSON list of fixtures
    (the raw payload under the usual `data`/`response` key depending on the API)
    or an empty list on failures.

    Parameters:
    - target_date: ISO date string 'YYYY-MM-DD'.
    - session: optional aiohttp.ClientSession to reuse.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("SPORTMONKS_API_KEY not set in environment")

    url = f"{DEFAULT_BASE}/fixtures/date/{target_date}"
    params = {"api_token": api_key}

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(url, params=params, timeout=30) as resp:
            if resp.status != 200:
                text = await resp.text()
                # Provide useful debug info but don't raise on purpose here
                raise RuntimeError(f"Sportmonks fetch failed: {resp.status} - {text}")
            payload = await resp.json()
            # Sportmonks v3 typically returns payload['data'] or payload['response']
            if isinstance(payload, dict):
                for key in ("data", "response", "result"):
                    if key in payload:
                        return payload[key] or []
            # Fallback
            return []
    finally:
        if close_session:
            await session.close()


async def health_check() -> Dict[str, Any]:
    """Quick health check that tries to fetch today's fixtures and returns status info."""
    try:
        today = date.today().isoformat()
        fixtures = await fetch_fixtures_by_date(today)
        return {"ok": True, "count": len(fixtures), "date": today}
    except Exception as exc:  # pragma: no cover - surface errors to caller
        return {"ok": False, "error": str(exc)}


async def fetch_fixture_detail(fixture_id: int, *, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
    """Fetch fixture detail. Try common Sportmonks v3 patterns and return dict or empty dict on failure."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("SPORTMONKS_API_KEY not set in environment")

    candidates = [
        f"{DEFAULT_BASE}/fixtures/{fixture_id}",
        f"{DEFAULT_BASE}/fixtures",
    ]

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        for url in candidates:
            params = {"api_token": api_key}
            # second candidate requires fixture param
            if url.endswith('/fixtures'):
                params = {"api_token": api_key, "id": fixture_id}
            try:
                async with session.get(url, params=params, timeout=20) as resp:
                    if resp.status != 200:
                        continue
                    payload = await resp.json()
                    if isinstance(payload, dict):
                        for key in ("data", "response", "result"):
                            if key in payload and payload[key]:
                                val = payload[key]
                                if isinstance(val, list) and val:
                                    return val[0]
                                if isinstance(val, dict):
                                    return val
                    if isinstance(payload, dict):
                        return payload
            except Exception:
                continue
        return {}
    finally:
        if close_session:
            await session.close()


async def fetch_fixture_events(fixture_id: int, *, session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Attempt to fetch events for a fixture. Try a couple of common Sportmonks URL patterns.

    Returns a list of event dicts or empty list on failure.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("SPORTMONKS_API_KEY not set in environment")

    candidates = [
        f"{DEFAULT_BASE}/fixtures/{fixture_id}/events",
        f"{DEFAULT_BASE}/fixtures/events",
        f"{DEFAULT_BASE}/fixtures/{fixture_id}/timeline",
    ]

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        for url in candidates:
            params = {"api_token": api_key}
            # second candidate may require fixture param
            if url.endswith('/fixtures/events'):
                params = {"api_token": api_key, "fixture": fixture_id}

            # perform a guarded request to avoid CancelledError bubbling
            resp = None
            try:
                resp = await session.get(url, params=params, timeout=30)
            except asyncio.TimeoutError:
                # try next candidate
                continue
            except Exception:
                # client errors / connection reset etc.: try next candidate
                continue

            try:
                async with resp:
                    if resp.status != 200:
                        # try next candidate
                        try:
                            await resp.text()
                        except Exception:
                            pass
                        continue
                    payload = await resp.json()
                    if isinstance(payload, dict):
                        for key in ("data", "response", "result"):
                            if key in payload and payload[key]:
                                return payload[key]
                    if isinstance(payload, list):
                        return payload
            except asyncio.CancelledError:
                # propagate cancellation
                raise
            except Exception:
                # unexpected parse error: try next candidate
                continue

        return []
    finally:
        if close_session:
            await session.close()


if __name__ == "__main__":
    # quick manual run
    async def _main() -> None:
        print("Sportmonks async client quick test")
        res = await health_check()
        print(res)

    asyncio.run(_main())

