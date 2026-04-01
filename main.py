#!/usr/bin/env python3
"""ACE Backend — Sports odds and game data API.

Endpoints:
  GET /health               — status check
  GET /games                — all live + upcoming games with odds
  GET /games/{sport}        — games filtered by sport key
  GET /sports               — list of available sport keys
  GET /odds/{sport}         — raw odds for a sport from all books
  GET /sources/status       — current external source adapter readiness
  GET /intel/game/{game_id} — normalized intelligence payload for one game
  GET /intel/tracked        — tracked index payload scaffold

Data source backbone: The Odds API (the-odds-api.com)
Intelligence adapters: ESPN scoreboard, ESPN injuries (pending team mapping), Open-Meteo (pending venue mapping)
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from intel_service import build_game_intel, build_tracked_index

load_dotenv()

API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_BASE = "https://api.the-odds-api.com/v4"

_cache: Dict[str, Any] = {}
CACHE_TTL = 60

app = FastAPI(title="ACE Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_SPORTS = [
    "basketball_nba",
    "americanfootball_nfl",
    "baseball_mlb",
    "icehockey_nhl",
    "basketball_ncaab",
    "americanfootball_ncaaf",
]

REGIONS = "us"
MARKETS = "h2h,spreads,totals"


def cache_get(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if not entry:
        return None
    if time.time() - entry["ts"] > CACHE_TTL:
        return None
    return entry["data"]


def cache_set(key: str, data: Any) -> None:
    _cache[key] = {"ts": time.time(), "data": data}


async def odds_request(path: str, params: Dict[str, Any] = {}) -> Any:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="ODDS_API_KEY not set. Add it to .env")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{ODDS_BASE}{path}",
            params={"apiKey": API_KEY, **params},
        )
        if r.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid Odds API key")
        if r.status_code == 429:
            raise HTTPException(status_code=429, detail="Odds API quota exceeded")
        r.raise_for_status()
        return r.json()


def normalize_game(raw: Dict[str, Any], sport: str) -> Dict[str, Any]:
    bookmakers = raw.get("bookmakers", [])
    books_odds = []
    for book in bookmakers:
        book_entry = {
            "sportsbook": book.get("key"),
            "title": book.get("title"),
            "last_update": book.get("last_update"),
            "markets": {},
        }
        for market in book.get("markets", []):
            key = market.get("key")
            outcomes = market.get("outcomes", [])
            book_entry["markets"][key] = [
                {"name": o.get("name"), "price": o.get("price"), "point": o.get("point")}
                for o in outcomes
            ]
        books_odds.append(book_entry)

    best_ml: Dict[str, Optional[int]] = {}
    for book in bookmakers:
        for market in book.get("markets", []):
            if market.get("key") == "h2h":
                for o in market.get("outcomes", []):
                    name = o.get("name")
                    price = o.get("price")
                    if name and price is not None:
                        if name not in best_ml or (price > 0 and price > best_ml[name]) or (price < 0 and best_ml[name] is not None and price > best_ml[name]):
                            best_ml[name] = price

    commence = raw.get("commence_time")
    status = "live" if is_live(commence) else "upcoming"

    return {
        "id": raw.get("id"),
        "sport": sport,
        "sport_title": raw.get("sport_title"),
        "home_team": raw.get("home_team"),
        "away_team": raw.get("away_team"),
        "commence_time": commence,
        "status": status,
        "best_moneyline": best_ml,
        "bookmakers": books_odds,
        "num_books": len(books_odds),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def is_live(commence_time: Optional[str]) -> bool:
    if not commence_time:
        return False
    try:
        ct = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (now - ct).total_seconds()
        return 0 <= diff <= 14400
    except Exception:
        return False


async def load_games_payload(
    sports: Optional[str] = None,
    regions: str = REGIONS,
    markets: str = MARKETS,
) -> Dict[str, Any]:
    sport_list = sports.split(",") if sports else DEFAULT_SPORTS
    all_games = []
    for sport in sport_list:
        cache_key = f"games:{sport}:{regions}:{markets}"
        cached = cache_get(cache_key)
        if cached:
            all_games.extend(cached)
            continue
        try:
            raw = await odds_request(
                f"/sports/{sport}/odds",
                {"regions": regions, "markets": markets, "oddsFormat": "american"},
            )
            games = [normalize_game(g, sport) for g in raw]
            cache_set(cache_key, games)
            all_games.extend(games)
        except HTTPException:
            continue
    return {
        "count": len(all_games),
        "sports": sport_list,
        "games": all_games,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "api_key_set": bool(API_KEY),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/sports")
async def get_sports():
    cache_key = "sports"
    cached = cache_get(cache_key)
    if cached:
        return cached
    data = await odds_request("/sports", {"all": "false"})
    result = [
        {"key": s["key"], "title": s["title"], "group": s["group"], "active": s["active"]}
        for s in data
        if s.get("active")
    ]
    cache_set(cache_key, result)
    return result


@app.get("/games")
async def get_games(
    sports: Optional[str] = Query(None, description="Comma-separated sport keys, default is major US sports"),
    regions: str = Query(REGIONS),
    markets: str = Query(MARKETS),
):
    return await load_games_payload(sports=sports, regions=regions, markets=markets)


@app.get("/games/{sport}")
async def get_games_by_sport(
    sport: str,
    regions: str = Query(REGIONS),
    markets: str = Query(MARKETS),
):
    cache_key = f"games:{sport}:{regions}:{markets}"
    cached = cache_get(cache_key)
    if cached:
        return {"count": len(cached), "sport": sport, "games": cached}
    raw = await odds_request(
        f"/sports/{sport}/odds",
        {"regions": regions, "markets": markets, "oddsFormat": "american"},
    )
    games = [normalize_game(g, sport) for g in raw]
    cache_set(cache_key, games)
    return {"count": len(games), "sport": sport, "games": games}


@app.get("/odds/{sport}")
async def get_raw_odds(sport: str, regions: str = Query(REGIONS)):
    return await odds_request(
        f"/sports/{sport}/odds",
        {"regions": regions, "markets": "h2h,spreads,totals,outrights", "oddsFormat": "american"},
    )


@app.get("/sources/status")
async def get_sources_status():
    return {
        "odds_api": {
            "enabled": True,
            "notes": "Current ACE market backbone",
        },
        "espn_scoreboard": {
            "enabled": True,
            "notes": "Unofficial but practical early source for live game state",
        },
        "espn_injuries": {
            "enabled": False,
            "notes": "Adapter scaffolded; requires explicit team ID mapping before safe live use",
        },
        "open_meteo": {
            "enabled": False,
            "notes": "Adapter scaffolded; requires venue coordinate mapping before safe live use",
        },
    }


@app.get("/intel/game/{game_id}")
async def get_game_intel(game_id: str):
    payload = await load_games_payload()
    game = next((g for g in payload["games"] if g["id"] == game_id), None)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return await build_game_intel(game)


@app.get("/intel/tracked")
async def get_tracked_intel(limit: int = Query(10, ge=1, le=25)):
    payload = await load_games_payload()
    return await build_tracked_index(payload["games"], limit=limit)
