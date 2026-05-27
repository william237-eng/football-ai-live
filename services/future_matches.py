from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _parse_iso_utc(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime returned by API-Football.

    The API usually returns something like: '2026-05-26T15:00:00Z'
    """
    if not dt_str:
        return None
    try:
        # Handle trailing Z explicitly
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


class FutureMatchesService:
    @staticmethod
    def parse_matches(payload: Any) -> List[Dict[str, Any]]:
        """Normalize API-Football future fixtures into a canonical dict.

        Output per match:
        {
          home_team, away_team,
          home_logo, away_logo,
          start_datetime_local,  # ISO string (timezone-aware)
          start_date,            # YYYY-MM-DD (local)
          start_time,            # HH:MM (local)
          start_date_display,   # DD/MM/YYYY (local)
          league, league_country, league_flag,
          venue
        }
        """
        if isinstance(payload, dict) and "response" in payload:
            items = payload.get("response") or []
        else:
            items = payload or []

        results: List[Dict[str, Any]] = []
        for item in items:
            try:
                fixture = item.get("fixture") or {}
                teams = item.get("teams") or {}
                league = item.get("league") or {}
                venue_obj = fixture.get("venue") or {}

                home = teams.get("home") or {}
                away = teams.get("away") or {}

                home_team = home.get("name") or home.get("team") or None
                away_team = away.get("name") or away.get("team") or None
                home_logo = home.get("logo")
                away_logo = away.get("logo")

                league_name = league.get("name") or None
                league_country = league.get("country") or None
                league_flag = league.get("flag") or None

                venue = venue_obj.get("name") or None

                start_utc = _parse_iso_utc(fixture.get("date"))
                if start_utc is None:
                    continue

                # Convert to local timezone (server/user environment)
                start_local = start_utc.astimezone()  # attach local tz
                start_date = start_local.date().isoformat()
                start_time = start_local.strftime("%H:%M")
                start_date_display = start_local.strftime("%d/%m/%Y")

                results.append(
                    {
                        "fixture_id": fixture.get("id"),
                        "home_team_id": home.get("id"),
                        "away_team_id": away.get("id"),
                        "league_id": league.get("id"),
                        "season": league.get("season"),
                        "home_team": home_team or "—",
                        "away_team": away_team or "—",
                        "home_logo": home_logo,
                        "away_logo": away_logo,
                        "start_datetime_local": start_local.isoformat(),
                        "start_date": start_date,
                        "start_time": start_time,
                        "start_date_display": start_date_display,
                        "league": league_name or "—",
                        "league_country": league_country or "",
                        "league_flag": league_flag or "",
                        "venue": venue or "",
                        "start_ts": start_local.timestamp(),
                    }
                )
            except Exception:
                continue

        return results

