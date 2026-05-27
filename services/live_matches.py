from typing import List, Dict, Any


class LiveMatchesService:
    """Utilities to process live matches payload from the API."""

    @staticmethod
    def parse_matches(payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert API-Football payload to internal canonical format.

        Output per match:
        {
            home_team,
            away_team,
            home_logo,
            away_logo,
            home_score,
            away_score,
            minute,
            league,
            venue,
            elapsed,
            status
        }
        """

        # API may return a dict with key 'response' or a plain list
        if isinstance(payload, dict) and "response" in payload:
            items = payload.get("response") or []
        else:
            items = payload or []

        results: List[Dict[str, Any]] = []

        for item in items:
            try:
                fixture = item.get("fixture", {})
                teams = item.get("teams", {})
                goals = item.get("goals", {})
                league = item.get("league", {})

                home = teams.get("home", {})
                away = teams.get("away", {})

                home_team = home.get("name") or home.get("team") or None
                away_team = away.get("name") or away.get("team") or None

                home_logo = home.get("logo")
                away_logo = away.get("logo")

                home_score = goals.get("home")
                away_score = goals.get("away")

                status_info = fixture.get("status", {})
                minute = status_info.get("elapsed")
                elapsed = status_info.get("elapsed")
                status = status_info.get("short") or status_info.get("long")

                league_name = league.get("name")
                league_country = league.get("country") or None
                league_flag = league.get("flag") or None
                venue = fixture.get("venue", {}).get("name")

                results.append(
                    {
                        "fixture_id": fixture.get("id"),
                        "home_team_id": home.get("id"),
                        "away_team_id": away.get("id"),
                        "league_id": league.get("id"),
                        "season": league.get("season"),
                        "home_team": home_team,
                        "away_team": away_team,
                        "home_logo": home_logo,
                        "away_logo": away_logo,
                        "home_score": home_score,
                        "away_score": away_score,
                        "minute": minute,
                        "league": league_name,
                        "league_country": league_country,
                        "league_flag": league_flag,
                        "venue": venue,
                        "elapsed": elapsed,
                        "status": status,
                    }
                )
            except Exception:
                # skip malformed entries but continue processing others
                continue

        return results