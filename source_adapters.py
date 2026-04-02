from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from mappings import get_espn_team_mapping, get_injury_coverage, get_weather_coverage, get_weather_mapping

ESPN_SCOREBOARD_MAP = {
    "basketball_nba": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "americanfootball_nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    "baseball_mlb": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    "icehockey_nhl": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
    "basketball_ncaab": "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard",
    "americanfootball_ncaaf": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
}

ESPN_CORE_LEAGUE_MAP = {
    "americanfootball_nfl": ("football", "nfl"),
    "basketball_nba": ("basketball", "nba"),
    "baseball_mlb": ("baseball", "mlb"),
    "icehockey_nhl": ("hockey", "nhl"),
}


def _norm_team(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    aliases = {
        "st john s": "st johns",
        "saint john s": "st johns",
        "ucf knights": "ucf",
        "uconn": "connecticut",
        "unlv": "nevada las vegas",
    }
    return aliases.get(cleaned, cleaned)


class ESPNScoreboardAdapter:
    """Best-effort adapter for ESPN unofficial scoreboard endpoints."""

    async def fetch_for_sport(self, sport_key: str) -> Dict[str, Any]:
        url = ESPN_SCOREBOARD_MAP.get(sport_key)
        if not url:
            return {"ok": False, "reason": "unsupported-sport", "events": []}
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                res = await client.get(url)
                res.raise_for_status()
                data = res.json()
            return {"ok": True, "url": url, "events": data.get("events", [])}
        except Exception as e:
            return {"ok": False, "reason": str(e), "events": []}

    def match_event(self, game: Dict[str, Any], events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        away = _norm_team(game.get("away_team", ""))
        home = _norm_team(game.get("home_team", ""))
        for event in events:
            comps = event.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue
            names = {c.get("homeAway"): _norm_team(c.get("team", {}).get("displayName", "")) for c in competitors}
            if names.get("away") == away and names.get("home") == home:
                return event
        return None

    def _extract_probables(self, competitor: Dict[str, Any]) -> List[Dict[str, Any]]:
        probables = []
        for item in competitor.get("probables") or []:
            athlete = item.get("athlete") or {}
            probables.append({
                "name": item.get("name"),
                "display_name": item.get("displayName"),
                "abbreviation": item.get("abbreviation"),
                "athlete_id": athlete.get("id"),
                "athlete": athlete.get("displayName") or athlete.get("fullName"),
                "position": athlete.get("position"),
                "statistics": item.get("statistics") or [],
            })
        return probables

    def normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        status = comp.get("status", {})
        out = {
            "event_id": event.get("id"),
            "status": status.get("type", {}).get("description"),
            "state": status.get("type", {}).get("state"),
            "period": status.get("period"),
            "clock": status.get("displayClock"),
            "home_score": None,
            "away_score": None,
            "home_record": None,
            "away_record": None,
            "venue": comp.get("venue", {}).get("fullName"),
            "neutral_site": comp.get("neutralSite"),
        }
        for competitor in competitors:
            side = competitor.get("homeAway")
            records = competitor.get("records") or []
            overall = next((r.get("summary") for r in records if r.get("name") == "overall" or r.get("type") == "total"), None)
            if side == "home":
                out["home_score"] = competitor.get("score")
                out["home_record"] = overall
                out["home_winner"] = competitor.get("winner")
                out["home_probables"] = self._extract_probables(competitor)
            elif side == "away":
                out["away_score"] = competitor.get("score")
                out["away_record"] = overall
                out["away_winner"] = competitor.get("winner")
                out["away_probables"] = self._extract_probables(competitor)
        return out


class ESPNTeamContextAdapter:
    async def _fetch_json(self, client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
        res = await client.get(url)
        res.raise_for_status()
        return res.json()

    def _extract_recent_form(self, team_name: str, events: List[Dict[str, Any]], limit: int = 5) -> Dict[str, Any]:
        recent_games = []
        wins = 0
        losses = 0
        for event in events[: limit * 2]:
            comp = (event.get("competitions") or [{}])[0]
            status = ((comp.get("status") or {}).get("type") or {}).get("state")
            if status != "post":
                continue
            competitors = comp.get("competitors") or []
            team_comp = next((c for c in competitors if c.get("team", {}).get("displayName") == team_name), None)
            opp_comp = next((c for c in competitors if c.get("team", {}).get("displayName") != team_name), None)
            if not team_comp or not opp_comp:
                continue
            won = bool(team_comp.get("winner"))
            wins += 1 if won else 0
            losses += 0 if won else 1
            recent_games.append({
                "event_id": event.get("id"),
                "date": event.get("date"),
                "opponent": opp_comp.get("team", {}).get("displayName"),
                "result": "W" if won else "L",
                "team_score": team_comp.get("score"),
                "opponent_score": opp_comp.get("score"),
            })
            if len(recent_games) >= limit:
                break
        return {
            "record_last_5": f"{wins}-{losses}" if recent_games else None,
            "wins_last_5": wins,
            "losses_last_5": losses,
            "recent_games": recent_games,
        }

    def _extract_key_stats(self, stats_payload: Dict[str, Any], sport_key: str) -> Dict[str, Any]:
        categories = (((stats_payload.get("results") or {}).get("stats") or {}).get("categories") or [])
        flat: Dict[str, Any] = {}
        for category in categories:
            for stat in category.get("stats", []):
                flat[stat.get("name")] = stat.get("value")
                flat[f"display::{stat.get('name')}"] = stat.get("displayValue")

        if sport_key == "baseball_mlb":
            return {
                "runs_per_game": flat.get("runsPerGame") or flat.get("display::runsPerGame"),
                "batting_avg": flat.get("avgBattingAverage") or flat.get("display::avgBattingAverage"),
                "era": flat.get("ERA") or flat.get("display::ERA"),
            }
        if sport_key == "basketball_nba":
            return {
                "points_per_game": flat.get("avgPoints") or flat.get("display::avgPoints"),
                "points_allowed_per_game": flat.get("avgPointsAllowed") or flat.get("display::avgPointsAllowed"),
                "rebounds_per_game": flat.get("avgRebounds") or flat.get("display::avgRebounds"),
            }
        return {}

    async def _fetch_team_context(self, client: httpx.AsyncClient, sport_key: str, team_name: str) -> Dict[str, Any]:
        team_mapping = get_espn_team_mapping(sport_key, team_name)
        league_bits = ESPN_CORE_LEAGUE_MAP.get(sport_key)
        if not team_mapping or not league_bits:
            return {}
        sport_path, league = league_bits
        schedule_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/{league}/teams/{team_mapping['espn_id']}/schedule"
        stats_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/{league}/teams/{team_mapping['espn_id']}/statistics"
        schedule_payload = await self._fetch_json(client, schedule_url)
        stats_payload = await self._fetch_json(client, stats_url)
        recent_form = self._extract_recent_form(team_name, schedule_payload.get("events", []))
        key_stats = self._extract_key_stats(stats_payload, sport_key)
        return {
            "team": team_name,
            "recent_form": recent_form,
            "key_stats": key_stats,
            "schedule_url": schedule_url,
            "stats_url": stats_url,
        }

    async def fetch_for_game(self, game: Dict[str, Any]) -> Dict[str, Any]:
        sport_key = game.get("sport")
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        if sport_key not in ESPN_CORE_LEAGUE_MAP:
            return {"ok": False, "reason": "unsupported-sport", "teams": {}}
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                home_context = await self._fetch_team_context(client, sport_key, home_team)
                away_context = await self._fetch_team_context(client, sport_key, away_team)
            return {
                "ok": True,
                "reason": None,
                "teams": {
                    "home": home_context,
                    "away": away_context,
                },
                "notes": "Fetched ESPN schedule/statistics context for both teams.",
            }
        except Exception as e:
            return {"ok": False, "reason": str(e), "teams": {}, "notes": "ESPN team context fetch failed."}


class ESPNInjuryAdapter:
    async def _fetch_json(self, client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
        res = await client.get(url)
        res.raise_for_status()
        return res.json()

    async def _resolve_athlete(self, client: httpx.AsyncClient, ref: str) -> Dict[str, Any]:
        if not ref:
            return {}
        try:
            data = await self._fetch_json(client, ref.replace("http://", "https://"))
            position = data.get("position", {})
            return {
                "name": data.get("displayName"),
                "position": position.get("abbreviation"),
                "position_name": position.get("displayName"),
                "experience_years": (data.get("experience") or {}).get("years"),
            }
        except Exception:
            return {}

    async def _fetch_team_injuries(self, client: httpx.AsyncClient, sport_key: str, team_name: str) -> List[Dict[str, Any]]:
        team_mapping = get_espn_team_mapping(sport_key, team_name)
        league_bits = ESPN_CORE_LEAGUE_MAP.get(sport_key)
        if not team_mapping or not league_bits:
            return []
        sport_path, league = league_bits
        url = f"https://sports.core.api.espn.com/v2/sports/{sport_path}/leagues/{league}/teams/{team_mapping['espn_id']}/injuries?lang=en&region=us"
        payload = await self._fetch_json(client, url)
        items = payload.get("items", [])[:8]
        normalized = []
        for item in items:
            ref = item.get("$ref")
            if not ref:
                continue
            detail = await self._fetch_json(client, ref.replace("http://", "https://"))
            athlete_info = await self._resolve_athlete(client, detail.get("athlete", {}).get("$ref", ""))
            normalized.append({
                "team": team_name,
                "athlete": athlete_info.get("name"),
                "position": athlete_info.get("position"),
                "position_name": athlete_info.get("position_name"),
                "experience_years": athlete_info.get("experience_years"),
                "status": detail.get("status"),
                "date": detail.get("date"),
                "short_comment": detail.get("shortComment"),
                "long_comment": detail.get("longComment"),
                "type": detail.get("details", {}).get("type"),
                "return_date": detail.get("details", {}).get("returnDate"),
                "source_url": ref.replace("http://", "https://"),
            })
        return normalized

    async def fetch_for_game(self, game: Dict[str, Any]) -> Dict[str, Any]:
        sport_key = game.get("sport")
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        coverage = get_injury_coverage(sport_key, home_team, away_team)
        if coverage == "none":
            return {
                "ok": False,
                "coverage": coverage,
                "reason": "team-mapping-missing",
                "injuries": [],
                "notes": "No explicit team mapping exists yet for this matchup.",
            }
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                home_injuries = await self._fetch_team_injuries(client, sport_key, home_team)
                away_injuries = await self._fetch_team_injuries(client, sport_key, away_team)
            injuries = home_injuries + away_injuries
            return {
                "ok": True,
                "coverage": coverage,
                "reason": None,
                "injuries": injuries,
                "notes": f"Fetched {len(injuries)} injury records from ESPN core API.",
            }
        except Exception as e:
            return {
                "ok": False,
                "coverage": coverage,
                "reason": str(e),
                "injuries": [],
                "notes": "ESPN injury fetch failed.",
            }


class OpenMeteoAdapter:
    async def fetch_for_game(self, game: Dict[str, Any]) -> Dict[str, Any]:
        sport = game.get("sport")
        home_team = game.get("home_team")
        coverage = get_weather_coverage(sport, home_team)
        if coverage == "not_applicable":
            return {
                "ok": False,
                "coverage": coverage,
                "reason": "not-outdoor-priority",
                "weather": None,
                "notes": "Weather is not prioritized for this sport.",
            }

        mapping = get_weather_mapping(sport, home_team)
        if not mapping:
            return {
                "ok": False,
                "coverage": coverage,
                "reason": "weather-anchor-missing",
                "weather": None,
                "notes": "No explicit weather anchor exists yet for this home team.",
            }

        if mapping.get("weather_applicable") is False:
            return {
                "ok": True,
                "coverage": coverage,
                "reason": None,
                "weather": {
                    "anchor_name": mapping.get("anchor_name"),
                    "indoor": mapping.get("indoor"),
                    "weather_applicable": False,
                },
                "notes": "Mapped indoor/dome venue; weather impact suppressed.",
            }

        commence_time = game.get("commence_time")
        target_hour = None
        if commence_time:
            try:
                target_hour = datetime.fromisoformat(commence_time.replace("Z", "+00:00")).replace(minute=0, second=0, microsecond=0)
            except Exception:
                target_hour = None

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                res = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": mapping["lat"],
                        "longitude": mapping["lon"],
                        "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m",
                        "forecast_days": 3,
                        "timezone": "UTC",
                    },
                )
                res.raise_for_status()
                payload = res.json()
            hourly = payload.get("hourly", {})
            times = hourly.get("time", [])
            idx = 0
            if target_hour and times:
                target_str = target_hour.strftime("%Y-%m-%dT%H:%M")
                idx = times.index(target_str) if target_str in times else 0
            weather = {
                "anchor_name": mapping.get("anchor_name"),
                "lat": mapping.get("lat"),
                "lon": mapping.get("lon"),
                "indoor": mapping.get("indoor"),
                "weather_applicable": True,
                "forecast_time": times[idx] if times else None,
                "temperature_c": (hourly.get("temperature_2m") or [None])[idx],
                "precipitation_probability": (hourly.get("precipitation_probability") or [None])[idx],
                "precipitation_mm": (hourly.get("precipitation") or [None])[idx],
                "wind_speed_10m": (hourly.get("wind_speed_10m") or [None])[idx],
            }
            return {
                "ok": True,
                "coverage": coverage,
                "reason": None,
                "weather": weather,
                "notes": "Fetched Open-Meteo hourly forecast for mapped home venue.",
            }
        except Exception as e:
            return {
                "ok": False,
                "coverage": coverage,
                "reason": str(e),
                "weather": None,
                "notes": "Open-Meteo weather fetch failed.",
            }
