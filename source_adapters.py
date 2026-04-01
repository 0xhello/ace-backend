from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

ESPN_SCOREBOARD_MAP = {
    "basketball_nba": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "americanfootball_nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    "baseball_mlb": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    "icehockey_nhl": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
    "basketball_ncaab": "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard",
    "americanfootball_ncaaf": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
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
            "venue": comp.get("venue", {}).get("fullName"),
            "neutral_site": comp.get("neutralSite"),
        }
        for competitor in competitors:
            side = competitor.get("homeAway")
            if side == "home":
                out["home_score"] = competitor.get("score")
            elif side == "away":
                out["away_score"] = competitor.get("score")
        return out


class ESPNInjuryAdapter:
    """Architecture placeholder.

    We are intentionally not guessing team->ESPN ID mappings. This adapter is the integration seam.
    """

    async def fetch_for_game(self, game: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": False,
            "reason": "team-id-mapping-required",
            "injuries": [],
            "notes": "ESPN injury integration requires explicit team ID mapping before safe live use.",
        }


class OpenMeteoAdapter:
    """Architecture placeholder.

    We are intentionally not guessing venue coordinates from team names.
    """

    async def fetch_for_game(self, game: Dict[str, Any]) -> Dict[str, Any]:
        sport = game.get("sport")
        if sport not in {"americanfootball_nfl", "americanfootball_ncaaf", "baseball_mlb"}:
            return {
                "ok": False,
                "reason": "not-outdoor-priority",
                "weather": None,
                "notes": "Weather only prioritized for outdoor sports.",
            }
        return {
            "ok": False,
            "reason": "venue-coordinates-required",
            "weather": None,
            "notes": "Open-Meteo integration requires explicit venue coordinate mapping before safe live use.",
        }
