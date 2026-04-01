from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from market_snapshots import update_snapshot
from source_adapters import ESPNInjuryAdapter, ESPNScoreboardAdapter, OpenMeteoAdapter

scoreboard_adapter = ESPNScoreboardAdapter()
injury_adapter = ESPNInjuryAdapter()
weather_adapter = OpenMeteoAdapter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_status(status: Optional[str]) -> str:
    s = (status or "").lower()
    if "out" in s:
        return "out"
    if "questionable" in s or "day-to-day" in s:
        return "questionable"
    if "doubtful" in s:
        return "doubtful"
    if "probable" in s:
        return "probable"
    return "unknown"


def _injury_weight(sport: str, injury: Dict[str, Any]) -> int:
    athlete = (injury.get("athlete") or "").lower()
    status = _normalize_status(injury.get("status"))
    injury_type = (injury.get("type") or "").lower()

    base = 1
    if status in {"out", "doubtful"}:
        base += 2
    elif status == "questionable":
        base += 1

    if sport == "basketball_nba":
        base += 1
    if sport == "americanfootball_nfl" and any(pos in athlete for pos in ["qb", "quarterback"]):
        base += 2
    if sport == "icehockey_nhl" and "goalie" in injury_type:
        base += 2
    return base


def _injury_signals(game: Dict[str, Any], injury_resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    injuries = injury_resp.get("injuries", [])
    if not injuries:
        return []

    sport = game.get("sport")
    weighted = sorted(injuries, key=lambda x: _injury_weight(sport, x), reverse=True)
    top = weighted[0]
    team = top.get("team")
    status = _normalize_status(top.get("status"))
    severity = "high" if _injury_weight(sport, top) >= 4 else "medium" if _injury_weight(sport, top) >= 3 else "low"

    if team == game.get("home_team"):
        affected = "home"
        benefits = [game.get("away_team")]
        harms = [game.get("home_team")]
    elif team == game.get("away_team"):
        affected = "away"
        benefits = [game.get("home_team")]
        harms = [game.get("away_team")]
    else:
        affected = "neutral"
        benefits = []
        harms = []

    summary = f"{team} injury uncertainty impacting pregame read"
    if top.get("athlete") and status in {"out", "doubtful", "questionable"}:
        summary = f"{top['athlete']} is {status} for {team}"

    details = {
        "athlete": top.get("athlete"),
        "status": top.get("status"),
        "type": top.get("type"),
        "short_comment": top.get("short_comment"),
        "return_date": top.get("return_date"),
        "source_time": top.get("date"),
        "coverage": injury_resp.get("coverage"),
    }

    return [{
        "id": f"injury-{game['id']}",
        "gameId": game["id"],
        "type": "injury",
        "severity": severity,
        "certainty": "confirmed",
        "affectedTeam": affected,
        "direction": "negative" if status in {"out", "doubtful", "questionable"} else "uncertain",
        "summary": summary,
        "details": details,
        "benefits": benefits or ["impact unclear"],
        "harms": harms or ["impact unclear"],
        "sourceCategory": "injury",
        "isForced": severity == "high",
        "isDemo": False,
        "createdAt": _now(),
        "sourceTimestamp": top.get("date"),
        "observedAt": top.get("date") or _now(),
        "derivedAt": _now(),
    }]



def _weather_signals(game: Dict[str, Any], weather_resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    weather = weather_resp.get("weather") or {}
    if not weather or not weather.get("weather_applicable"):
        return []

    wind = weather.get("wind_speed_10m")
    precip_prob = weather.get("precipitation_probability")
    precip_mm = weather.get("precipitation_mm")
    summary = None
    severity = "low"
    direction = "uncertain"
    benefits: List[str] = []
    harms: List[str] = []

    if wind is not None and wind >= 20:
        summary = "Wind conditions now relevant to total outlook"
        severity = "medium"
        direction = "negative"
        benefits = ["Under"]
        harms = ["Passing and long-ball efficiency"]
    elif precip_prob is not None and precip_prob >= 50:
        summary = "Precipitation risk could affect game environment"
        severity = "medium"
        direction = "negative"
        benefits = ["Under", "ground/control game"]
        harms = ["Explosive offense", "Over"]
    elif precip_mm is not None and precip_mm > 0:
        summary = "Light precipitation on forecast monitor"
        severity = "low"
        direction = "uncertain"
        benefits = ["impact unclear"]
        harms = ["impact unclear"]

    if not summary:
        return []

    return [{
        "id": f"weather-{game['id']}",
        "gameId": game["id"],
        "type": "weather",
        "severity": severity,
        "certainty": "likely",
        "affectedTeam": "neutral",
        "direction": direction,
        "summary": summary,
        "details": {
            "anchor_name": weather.get("anchor_name"),
            "forecast_time": weather.get("forecast_time"),
            "temperature_c": weather.get("temperature_c"),
            "precipitation_probability": precip_prob,
            "precipitation_mm": precip_mm,
            "wind_speed_10m": wind,
            "coverage": weather_resp.get("coverage"),
        },
        "benefits": benefits,
        "harms": harms,
        "sourceCategory": "weather",
        "isForced": False,
        "isDemo": False,
        "createdAt": _now(),
        "sourceTimestamp": weather.get("forecast_time"),
        "observedAt": _now(),
        "derivedAt": _now(),
    }]



def _confidence_from_context(game: Dict[str, Any], scoreboard: Dict[str, Any] | None, snapshot: Dict[str, Any], injury_resp: Dict[str, Any], weather_resp: Dict[str, Any]) -> Dict[str, Any]:
    base = 72
    reasons: List[str] = []

    if snapshot.get("changed"):
        base -= 6
        reasons.append("market moved since last snapshot")
    if scoreboard and scoreboard.get("state") == "in":
        base -= 4
        reasons.append("live game state increases volatility")
    if game.get("num_books", 0) >= 8:
        base += 3
        reasons.append("broad book coverage improves price confidence")

    injuries = injury_resp.get("injuries", [])
    if injuries:
        highest = max(_injury_weight(game.get("sport"), item) for item in injuries)
        base -= min(10, highest * 2)
        reasons.append("injury context is affecting confidence")

    weather = weather_resp.get("weather") or {}
    if weather.get("weather_applicable") and (weather.get("wind_speed_10m") or 0) >= 20:
        base -= 4
        reasons.append("high wind increases environment volatility")
    elif weather.get("weather_applicable") and (weather.get("precipitation_probability") or 0) >= 50:
        base -= 3
        reasons.append("precipitation risk reduces environment confidence")

    pct = max(45, min(92, base))
    if pct >= 85:
        tier, status = "high", "stable"
    elif pct >= 70:
        tier, status = "medium", "stable" if not snapshot.get("changed") else "volatile"
    else:
        tier, status = "low", "degraded"

    previous_pct = snapshot.get("previous_confidence_pct")
    delta = None if previous_pct is None else pct - previous_pct
    trend = "flat" if delta in (None, 0) else "up" if delta > 0 else "down"

    return {
        "tier": tier,
        "pct": pct,
        "status": status,
        "label": f"{tier.title()} ({pct}%) — {status.title()}",
        "explanation": reasons[0] if reasons else "baseline confidence from current market structure",
        "factors": reasons,
        "delta": delta,
        "trend": trend,
    }



def _pick_side_market(game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    best_ml = game.get("best_moneyline", {})
    home = game.get("home_team")
    away = game.get("away_team")
    home_price = best_ml.get(home)
    away_price = best_ml.get(away)
    if home_price is None or away_price is None:
        return None

    def rank(price: int) -> tuple[int, int]:
        return (0 if price < 0 else 1, abs(price))

    side = home if rank(home_price) < rank(away_price) else away
    market = "ml-home" if side == home else "ml-away"
    odds = home_price if side == home else away_price
    return {"team": side, "market": market, "odds": odds}



def _movement_map(game: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {
        "ml-away": None,
        "ml-home": None,
        "sp-away": None,
        "sp-home": None,
        "ov": None,
        "un": None,
    }
    away = game.get("away_team")
    home = game.get("home_team")
    for item in snapshot.get("movement", []):
        direction = item.get("direction")
        ui_direction = "up" if direction == "improved" else "down" if direction == "worse" else None
        if item.get("team") == away:
            result["ml-away"] = ui_direction
        elif item.get("team") == home:
            result["ml-home"] = ui_direction
    return result



def _recommendation_from_context(game: Dict[str, Any], confidence: Dict[str, Any], signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if confidence.get("pct", 0) < 70:
        return None

    side_pick = _pick_side_market(game)
    if not side_pick:
        return None

    top_signal = signals[0] if signals else None
    reasons = [confidence.get("explanation")]
    if top_signal:
        reasons.append(top_signal.get("summary"))

    confidence_pct = min(95, max(60, confidence.get("pct", 72) + (4 if top_signal else 0)))
    tag = "volatile" if confidence.get("status") == "volatile" else "stable"

    return {
        "market": side_pick["market"],
        "confidence": confidence_pct,
        "reason": ". ".join([r for r in reasons if r]),
        "pick": f"{side_pick['team']} ML",
        "market_type": "Moneyline",
        "odds": side_pick["odds"],
        "tag": tag,
        "source": "backend",
    }


async def build_game_intel(game: Dict[str, Any]) -> Dict[str, Any]:
    scoreboard_resp = await scoreboard_adapter.fetch_for_sport(game["sport"])
    scoreboard_match = None
    scoreboard_norm = None
    if scoreboard_resp.get("ok"):
        scoreboard_match = scoreboard_adapter.match_event(game, scoreboard_resp.get("events", []))
        if scoreboard_match:
            scoreboard_norm = scoreboard_adapter.normalize_event(scoreboard_match)

    injuries = await injury_adapter.fetch_for_game(game)
    weather = await weather_adapter.fetch_for_game(game)
    snapshot = update_snapshot(game)
    confidence = _confidence_from_context(game, scoreboard_norm, snapshot, injuries, weather)

    signals: List[Dict[str, Any]] = []
    signals.extend(_injury_signals(game, injuries))
    signals.extend(_weather_signals(game, weather))

    if snapshot.get("changed"):
        signals.append({
            "id": f"market-{game['id']}",
            "gameId": game["id"],
            "type": "market",
            "severity": "medium",
            "certainty": "confirmed",
            "affectedTeam": "neutral",
            "direction": "uncertain",
            "summary": "Market prices changed since the previous snapshot",
            "details": snapshot.get("movement", []),
            "benefits": [m["team"] for m in snapshot.get("movement", []) if m["direction"] == "improved"],
            "harms": [m["team"] for m in snapshot.get("movement", []) if m["direction"] == "worse"],
            "sourceCategory": "market",
            "isForced": False,
            "isDemo": False,
            "createdAt": _now(),
            "observedAt": snapshot.get("current_fetched_at") or _now(),
            "derivedAt": _now(),
        })

    if scoreboard_norm and scoreboard_norm.get("state") == "in":
        signals.append({
            "id": f"live-{game['id']}",
            "gameId": game["id"],
            "type": "news",
            "severity": "low",
            "certainty": "confirmed",
            "affectedTeam": "neutral",
            "direction": "uncertain",
            "summary": "Game is live and intelligence context is updating",
            "details": f"{scoreboard_norm.get('away_score')} - {scoreboard_norm.get('home_score')} · {scoreboard_norm.get('clock')} · period {scoreboard_norm.get('period')}",
            "benefits": [],
            "harms": [],
            "sourceCategory": "ai",
            "isForced": False,
            "isDemo": False,
            "createdAt": _now(),
            "observedAt": _now(),
            "derivedAt": _now(),
        })

    signals.sort(key=lambda s: {"high": 3, "medium": 2, "low": 1}.get(s.get("severity"), 0), reverse=True)

    recommendation = _recommendation_from_context(game, confidence, signals)
    market_movement = _movement_map(game, snapshot)

    return {
        "game": game,
        "source_status": {
            "odds": {"ok": True, "notes": "Current ACE market backbone"},
            "scoreboard": {
                "ok": scoreboard_resp.get("ok", False),
                "matched": scoreboard_match is not None,
                "reason": scoreboard_resp.get("reason"),
                "url": scoreboard_resp.get("url"),
            },
            "injuries": injuries,
            "weather": weather,
        },
        "coverage": {
            "injury_coverage": injuries.get("coverage", "none"),
            "weather_coverage": weather.get("coverage", "none"),
        },
        "scoreboard": scoreboard_norm,
        "snapshot": snapshot,
        "signals": signals,
        "confidence": confidence,
        "recommendation": recommendation,
        "market_movement": market_movement,
        "updated_at": _now(),
    }


async def build_tracked_index(games: List[Dict[str, Any]], limit: int = 10) -> Dict[str, Any]:
    items = []
    for game in games[:limit]:
        intel = await build_game_intel(game)
        items.append({
            "game_id": game["id"],
            "matchup": f"{game['away_team']} @ {game['home_team']}",
            "sport": game["sport_title"],
            "signals_count": len(intel["signals"]),
            "summary": intel["signals"][0]["summary"] if intel["signals"] else "No internal signals yet",
            "confidence": intel["confidence"],
            "coverage": intel.get("coverage", {}),
            "href": f"/dashboard/tracked/{game['id']}",
        })
    return {"count": len(items), "items": items, "updated_at": _now()}


async def build_board_index(games: List[Dict[str, Any]], limit: int = 50) -> Dict[str, Any]:
    items = []
    for game in games[:limit]:
        intel = await build_game_intel(game)
        signals = intel.get("signals", [])
        confidence = intel.get("confidence")
        top_signal = signals[0] if signals else None
        items.append({
            "game_id": game["id"],
            "confidence": confidence,
            "recommendation": intel.get("recommendation"),
            "market_movement": intel.get("market_movement"),
            "scoreboard": intel.get("scoreboard"),
            "signals": signals,
            "signals_count": len(signals),
            "top_signal": top_signal,
            "has_high_severity": any(s.get("severity") == "high" for s in signals),
            "is_volatile": confidence.get("status") == "volatile" if confidence else False,
            "has_new_signal": len(signals) > 0,
            "summary": top_signal.get("summary") if top_signal else "No internal signals yet",
            "coverage": intel.get("coverage", {}),
            "updated_at": intel.get("updated_at"),
        })
    return {"count": len(items), "items": items, "updated_at": _now()}


async def build_top_picks(games: List[Dict[str, Any]], limit: int = 4) -> Dict[str, Any]:
    picks = []
    for game in games:
        intel = await build_game_intel(game)
        rec = intel.get("recommendation")
        conf = intel.get("confidence")
        if not rec or not conf:
            continue
        picks.append({
            "id": f"pick-{game['id']}",
            "gameId": game["id"],
            "type": "ML",
            "pick": rec.get("pick"),
            "game": f"{game['away_team']} @ {game['home_team']}",
            "odds": rec.get("odds"),
            "market": rec.get("market_type"),
            "confidence": conf,
            "reasoning": rec.get("reason"),
            "tag": rec.get("tag", "stable"),
            "edge": f"+{max(1.0, round((conf.get('pct', 70) - 60) / 10, 1))}%",
            "signals": intel.get("signals", []),
        })
    picks.sort(key=lambda p: p.get("confidence", {}).get("pct", 0), reverse=True)
    return {"count": min(limit, len(picks)), "items": picks[:limit], "updated_at": _now()}
