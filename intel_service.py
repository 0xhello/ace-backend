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


def _confidence_from_context(game: Dict[str, Any], scoreboard: Dict[str, Any] | None, snapshot: Dict[str, Any]) -> Dict[str, Any]:
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

    pct = max(45, min(92, base))
    if pct >= 85:
        tier, status = "high", "stable"
    elif pct >= 70:
        tier, status = "medium", "stable" if not snapshot.get("changed") else "volatile"
    else:
        tier, status = "low", "degraded"

    return {
        "tier": tier,
        "pct": pct,
        "status": status,
        "label": f"{tier.title()} ({pct}%) — {status.title()}",
        "explanation": reasons[0] if reasons else "baseline confidence from current market structure",
        "factors": reasons,
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
        # more negative favorite wins; among positives, smaller positive is stronger
        return (0 if price < 0 else 1, abs(price))

    side = home if rank(home_price) < rank(away_price) else away
    market = "ml-home" if side == home else "ml-away"
    odds = home_price if side == home else away_price
    return {
        "team": side,
        "market": market,
        "odds": odds,
    }


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
    confidence = _confidence_from_context(game, scoreboard_norm, snapshot)

    signals: List[Dict[str, Any]] = []
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
        })

    recommendation = _recommendation_from_context(game, confidence, signals)

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
        "scoreboard": scoreboard_norm,
        "snapshot": snapshot,
        "signals": signals,
        "confidence": confidence,
        "recommendation": recommendation,
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
            "signals": signals,
            "signals_count": len(signals),
            "top_signal": top_signal,
            "has_high_severity": any(s.get("severity") == "high" for s in signals),
            "is_volatile": confidence.get("status") == "volatile" if confidence else False,
            "summary": top_signal.get("summary") if top_signal else "No internal signals yet",
            "updated_at": intel.get("updated_at"),
        })
    return {
        "count": len(items),
        "items": items,
        "updated_at": _now(),
    }


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
