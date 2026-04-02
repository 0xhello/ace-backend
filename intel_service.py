from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from market_snapshots import update_snapshot
from source_adapters import ESPNInjuryAdapter, ESPNScoreboardAdapter, ESPNTeamContextAdapter, OpenMeteoAdapter

scoreboard_adapter = ESPNScoreboardAdapter()
injury_adapter = ESPNInjuryAdapter()
team_context_adapter = ESPNTeamContextAdapter()
weather_adapter = OpenMeteoAdapter()


SEVERITY_SCORE = {"high": 3, "medium": 2, "low": 1}
CERTAINTY_SCORE = {"confirmed": 3, "likely": 2, "uncertain": 1}
TYPE_SCORE = {"injury": 4, "market": 3, "weather": 2, "news": 1}


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


HIGH_IMPACT_POSITIONS = {
    "basketball_nba": {"PG", "SG", "SF", "PF", "C"},  # all starters matter in NBA
    "americanfootball_nfl": {"QB"},
    "icehockey_nhl": {"G"},
    "baseball_mlb": {"SP", "RP", "CP"},  # pitching roles
}

STAR_EXPERIENCE_THRESHOLD = 5  # 5+ years = likely established player


def _injury_weight(sport: str, injury: Dict[str, Any]) -> int:
    status = _normalize_status(injury.get("status"))
    position = (injury.get("position") or "").upper()
    experience = injury.get("experience_years") or 0

    base = 1

    # Status weight
    if status in {"out", "doubtful"}:
        base += 2
    elif status == "questionable":
        base += 1

    # Position weight — high-impact positions matter more
    high_positions = HIGH_IMPACT_POSITIONS.get(sport, set())
    if position in high_positions:
        base += 2
    elif position:
        base += 1  # at least a known roster player

    # Experience weight — veteran/established players impact more
    if experience >= STAR_EXPERIENCE_THRESHOLD:
        base += 1

    # Sport baseline — NBA injuries tend to matter more per-player
    if sport == "basketball_nba":
        base += 1

    return base


def _team_side(game: Dict[str, Any], team: Optional[str]) -> str:
    if team == game.get("home_team"):
        return "home"
    if team == game.get("away_team"):
        return "away"
    return "neutral"



def _mlb_probable_pitcher_for_team(scoreboard: Optional[Dict[str, Any]], side: str) -> Optional[str]:
    if not scoreboard:
        return None
    probables = scoreboard.get(f"{side}_probables") or []
    starter = next((p for p in probables if p.get("abbreviation") == "SP" or p.get("name") == "probableStartingPitcher"), None)
    return (starter or {}).get("athlete")



def _injury_freshness(injury: Dict[str, Any]) -> str:
    date_str = injury.get("date")
    if not date_str:
        return "unknown"
    try:
        injury_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_hours = (now - injury_date).total_seconds() / 3600
        if age_hours <= 24:
            return "fresh"
        if age_hours <= 72:
            return "recent"
        if age_hours <= 168:
            return "known"
        return "stale"
    except Exception:
        return "unknown"


def _is_low_materiality_injury(injury: Dict[str, Any]) -> bool:
    text = " ".join([
        str(injury.get("type") or ""),
        str(injury.get("short_comment") or ""),
        str(injury.get("long_comment") or ""),
    ]).lower()
    if "g league" in text or "two-way" in text or "two way" in text or "on assignment" in text:
        return True
    return False



def _injury_signals(
    game: Dict[str, Any],
    injury_resp: Dict[str, Any],
    scoreboard: Optional[Dict[str, Any]] = None,
    team_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    injuries = injury_resp.get("injuries", [])
    if not injuries:
        return []

    sport = game.get("sport")
    relevant = []
    for injury in injuries:
        status = _normalize_status(injury.get("status"))
        weight = _injury_weight(sport, injury)
        freshness = _injury_freshness(injury)
        side = _team_side(game, injury.get("team"))
        probable_pitcher = _mlb_probable_pitcher_for_team(scoreboard, side) if game.get("sport") == "baseball_mlb" else None
        today_relevance = "normal"
        experience = injury.get("experience_years") or 0
        if probable_pitcher and injury.get("athlete") == probable_pitcher:
            weight += 3
            today_relevance = "probable-starter"
        elif game.get("sport") == "baseball_mlb" and (injury.get("position") or "").upper() == "SP":
            weight -= 2
            today_relevance = "rotation-context"

        recent_form = (((team_context or {}).get("teams") or {}).get(side) or {}).get("recent_form", {})
        if recent_form.get("wins_last_5") == 0:
            weight += 1
        elif recent_form.get("wins_last_5", 0) >= 4:
            weight += 1

        # Suppress weak/noisy entries. Board should only surface materially relevant injury context.
        if status not in {"out", "doubtful", "questionable"}:
            continue
        if weight < 5:
            continue
        # Stale injuries (>7 days old) need much higher weight to surface
        if freshness == "stale" and today_relevance != "probable-starter" and weight < 8:
            continue
        # Known injuries (3-7 days) need moderately higher weight
        if freshness == "known" and today_relevance != "probable-starter" and weight < 6:
            continue
        relevant.append((weight, injury, freshness, today_relevance))

    if not relevant:
        return []

    relevant.sort(key=lambda x: x[0], reverse=True)
    top_weight, top, top_freshness, top_relevance = relevant[0]
    team = top.get("team")
    status = _normalize_status(top.get("status"))
    team_burden = sum(weight for weight, injury, _, _ in relevant if injury.get("team") == team)
    experience = top.get("experience_years") or 0
    position = (top.get("position") or "").upper()
    high_positions = HIGH_IMPACT_POSITIONS.get(sport, set())

    # Suppress single weak/questionable injuries unless they are truly material.
    if status == "questionable" and top_weight < 6 and team_burden < 8:
        return []
    if status in {"out", "doubtful"} and top_weight < 5 and team_burden < 7:
        return []
    if team_burden < 7 and experience < 5 and position not in high_positions:
        return []

    severity = "high" if top_weight >= 6 or team_burden >= 8 else "medium"
    # Demote stale/known injuries from high to medium unless they're extremely heavy
    if top_freshness in {"stale", "known"} and severity == "high" and top_weight < 8:
        severity = "medium"

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

    same_team_count = sum(1 for _, injury, _, _ in relevant if injury.get("team") == team)
    pos_label = f" ({top['position']})" if top.get("position") else ""
    athlete_name = top.get("athlete") or team
    freshness_note = ""
    if top_freshness == "stale":
        freshness_note = " (established absence)"
    elif top_freshness == "known":
        freshness_note = " (recent)"

    relevance_note = ""
    if top_relevance == "probable-starter":
        relevance_note = " — directly relevant to today’s probable starter"
    elif top_relevance == "rotation-context":
        relevance_note = " — background rotation context"

    if same_team_count >= 2:
        summary = f"{athlete_name}{pos_label} is {status} for {team}{freshness_note}{relevance_note}; {same_team_count} key injury flags now affect confidence"
    else:
        summary = f"{athlete_name}{pos_label} is {status} for {team}{freshness_note}{relevance_note}"

    details = {
        "athlete": top.get("athlete"),
        "position": top.get("position"),
        "position_name": top.get("position_name"),
        "experience_years": top.get("experience_years"),
        "status": top.get("status"),
        "type": top.get("type"),
        "short_comment": top.get("short_comment"),
        "return_date": top.get("return_date"),
        "source_time": top.get("date"),
        "coverage": injury_resp.get("coverage"),
        "freshness": top_freshness,
        "today_relevance": top_relevance,
        "probable_pitcher": _mlb_probable_pitcher_for_team(scoreboard, _team_side(game, team)) if game.get("sport") == "baseball_mlb" else None,
        "relevant_injury_count": len(relevant),
        "same_team_relevant_count": same_team_count,
        "team_injury_burden": team_burden,
    }

    return [{
        "id": f"injury-{game['id']}",
        "gameId": game["id"],
        "type": "injury",
        "severity": severity,
        "certainty": "confirmed",
        "affectedTeam": affected,
        "direction": "negative",
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



def _team_context_signal(game: Dict[str, Any], team_context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    teams = (team_context or {}).get("teams") or {}
    signals: List[Dict[str, Any]] = []
    for side in ("home", "away"):
        ctx = teams.get(side) or {}
        form = ctx.get("recent_form") or {}
        key_stats = ctx.get("key_stats") or {}
        team_name = ctx.get("team")
        if not team_name:
            continue

        wins = form.get("wins_last_5", 0)
        losses = form.get("losses_last_5", 0)
        rest_days = form.get("rest_days")

        if wins >= 4:
            signals.append({
                "id": f"form-{game['id']}-{side}",
                "gameId": game["id"],
                "type": "news",
                "severity": "low",
                "certainty": "likely",
                "affectedTeam": side,
                "direction": "positive",
                "summary": f"{team_name} has strong recent form ({wins}-{losses} in last five)",
                "details": {"recent_form": form, "key_stats": key_stats},
                "benefits": [team_name],
                "harms": [],
                "sourceCategory": "team_context",
                "isForced": False,
                "isDemo": False,
                "createdAt": _now(),
                "observedAt": _now(),
                "derivedAt": _now(),
            })
        elif losses >= 4:
            signals.append({
                "id": f"form-{game['id']}-{side}",
                "gameId": game["id"],
                "type": "news",
                "severity": "low",
                "certainty": "likely",
                "affectedTeam": side,
                "direction": "negative",
                "summary": f"{team_name} is in poor recent form ({wins}-{losses} in last five)",
                "details": {"recent_form": form, "key_stats": key_stats},
                "benefits": [],
                "harms": [team_name],
                "sourceCategory": "team_context",
                "isForced": False,
                "isDemo": False,
                "createdAt": _now(),
                "observedAt": _now(),
                "derivedAt": _now(),
            })

        if rest_days is not None and rest_days <= 1.0 and game.get("sport") in {"basketball_nba", "icehockey_nhl"}:
            signals.append({
                "id": f"rest-{game['id']}-{side}",
                "gameId": game["id"],
                "type": "news",
                "severity": "low",
                "certainty": "likely",
                "affectedTeam": side,
                "direction": "negative",
                "summary": f"{team_name} is on short rest heading into this game",
                "details": {"recent_form": form, "rest_days": rest_days},
                "benefits": [game.get("away_team") if side == "home" else game.get("home_team")],
                "harms": [team_name],
                "sourceCategory": "team_context",
                "isForced": False,
                "isDemo": False,
                "createdAt": _now(),
                "observedAt": _now(),
                "derivedAt": _now(),
            })
    return signals



def _signal_priority_score(signal: Dict[str, Any], confidence: Dict[str, Any]) -> int:
    severity = SEVERITY_SCORE.get(signal.get("severity"), 0)
    certainty = CERTAINTY_SCORE.get(signal.get("certainty"), 0)
    signal_type = TYPE_SCORE.get(signal.get("type"), 0)
    forced = 1 if signal.get("isForced") else 0
    degraded_bonus = 1 if (confidence or {}).get("pct", 100) <= 64 else 0
    return (signal_type * 10) + (severity * 6) + (certainty * 3) + forced + degraded_bonus



def _rank_signals(signals: List[Dict[str, Any]], confidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    ranked = []
    for signal in signals:
        scored = dict(signal)
        scored["signal_score"] = _signal_priority_score(scored, confidence)
        scored["display_priority"] = "board" if scored["signal_score"] >= 52 else "tracked"
        ranked.append(scored)
    ranked.sort(key=lambda s: (s.get("signal_score", 0), SEVERITY_SCORE.get(s.get("severity"), 0)), reverse=True)
    return ranked



def _synthesize_summary(signals: List[Dict[str, Any]], confidence: Dict[str, Any], snapshot: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    if not signals:
        return "No internal signals yet", None

    top = signals[0]
    signal_types = {s.get("type") for s in signals}
    confidence_pct = (confidence or {}).get("pct", 70)
    changed_market = bool(snapshot.get("changed"))
    top_freshness = top.get("details", {}).get("freshness") if isinstance(top.get("details"), dict) else None

    # Fresh injury + market movement = strong alignment signal
    if "injury" in signal_types and changed_market and top_freshness in {"fresh", "recent", None}:
        return "Confidence shifted after injury context and market movement aligned", "alignment"
    # Fresh injury dragging confidence hard
    if "injury" in signal_types and confidence_pct <= 64 and top_freshness in {"fresh", "recent", None}:
        return "Lineup/injury context is materially dragging confidence", "injury-pressure"
    # Stale injury + no market movement = likely priced in
    if "injury" in signal_types and not changed_market and top_freshness in {"stale", "known"}:
        return "Injury context is established and likely already reflected in market pricing", "priced-in"
    # Weather + market alignment
    if "weather" in signal_types and changed_market:
        return "Environment risk and market movement are pointing the same direction", "alignment"
    # Market volatility
    if changed_market and confidence_pct <= 68:
        return "Market movement is increasing volatility around this game", "market-volatility"
    # Multi-factor uncertainty
    if "injury" in signal_types and "weather" in signal_types:
        return "Multiple external factors are increasing uncertainty", "multi-factor"
    # Signal conflict: injury says one thing, market hasn't reacted
    if "injury" in signal_types and not changed_market and top_freshness in {"fresh", "recent"}:
        return "Fresh injury noted but market hasn't meaningfully reacted yet", "possible-inefficiency"

    return top.get("summary", "No internal signals yet"), None



def _confidence_from_context(
    game: Dict[str, Any],
    scoreboard: Dict[str, Any] | None,
    snapshot: Dict[str, Any],
    injury_resp: Dict[str, Any],
    weather_resp: Dict[str, Any],
    team_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
        sport = game.get("sport")
        fresh_injuries = [i for i in injuries if _injury_freshness(i) in {"fresh", "recent"}]
        known_injuries = [i for i in injuries if _injury_freshness(i) == "known"]
        stale_injuries = [i for i in injuries if _injury_freshness(i) == "stale"]

        if fresh_injuries:
            highest = max(_injury_weight(sport, item) for item in fresh_injuries)
            probable_starter_hit = False
            if sport == "baseball_mlb":
                for item in fresh_injuries:
                    side = _team_side(game, item.get("team"))
                    probable = _mlb_probable_pitcher_for_team(scoreboard, side)
                    if probable and item.get("athlete") == probable:
                        probable_starter_hit = True
                        break
            penalty = min(10, highest * 2) + (3 if probable_starter_hit else 0)
            base -= penalty
            reasons.append("fresh injury context is affecting confidence")
            if probable_starter_hit:
                reasons.append("probable starter status makes the absence more relevant today")
        elif known_injuries:
            highest = max(_injury_weight(sport, item) for item in known_injuries)
            base -= min(5, highest)
            reasons.append("recent injury context noted but partially priced in")
        elif stale_injuries:
            # Stale injuries have minimal confidence impact — market has long adjusted
            base -= 1
            reasons.append("established injury context acknowledged")

    teams = (team_context or {}).get("teams") or {}
    home_form = ((teams.get("home") or {}).get("recent_form") or {})
    away_form = ((teams.get("away") or {}).get("recent_form") or {})
    if home_form.get("wins_last_5", 0) >= 4 or away_form.get("wins_last_5", 0) >= 4:
        base += 1
        reasons.append("recent team form adds a bit more context stability")

    if game.get("sport") in {"basketball_nba", "icehockey_nhl"}:
        short_rest = [form for form in (home_form, away_form) if (form.get("rest_days") is not None and form.get("rest_days") <= 1.0)]
        if short_rest:
            base -= 2
            reasons.append("short-rest schedule spot adds volatility")

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



def _market_tier_status(pct: int) -> Tuple[str, str]:
    if pct >= 72:
        return "high", "supported"
    if pct >= 59:
        return "medium", "mixed"
    return "low", "uncertain"



def _best_spread_side(game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    away = game.get("away_team")
    home = game.get("home_team")
    best = []
    for book in game.get("bookmakers", []):
        for outcome in book.get("markets", {}).get("spreads", []) or []:
            if outcome.get("name") in {away, home} and outcome.get("point") is not None:
                best.append({
                    "team": outcome.get("name"),
                    "point": outcome.get("point"),
                    "price": outcome.get("price"),
                })
    if not best:
        return None
    best.sort(key=lambda x: (abs(x.get("point") or 0), -(x.get("price") or 0)))
    return best[0]



def _best_total_side(game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    totals = []
    for book in game.get("bookmakers", []):
        for outcome in book.get("markets", {}).get("totals", []) or []:
            if outcome.get("name") in {"Over", "Under"} and outcome.get("point") is not None:
                totals.append({
                    "side": outcome.get("name"),
                    "point": outcome.get("point"),
                    "price": outcome.get("price"),
                })
    if not totals:
        return None
    totals.sort(key=lambda x: (x.get("point") or 0, -(x.get("price") or 0)))
    return totals[0]



def _market_signal_split(signals: List[Dict[str, Any]], market_type: str) -> Tuple[List[str], List[str]]:
    supporting: List[str] = []
    opposing: List[str] = []
    for signal in signals:
        summary = signal.get("summary")
        if not summary:
            continue
        signal_type = signal.get("type")
        source_category = signal.get("sourceCategory")
        severity = signal.get("severity")
        direction = signal.get("direction")

        if market_type == "ml":
            if signal_type == "injury" and severity in {"high", "medium"}:
                supporting.append(summary)
            elif source_category == "team_context":
                supporting.append(summary)
            elif signal_type == "weather":
                opposing.append(summary)
        elif market_type == "spread":
            if signal_type == "injury" and severity in {"high", "medium"}:
                supporting.append(summary)
            elif signal_type == "market":
                supporting.append(summary)
            elif source_category == "team_context" and direction == "negative":
                supporting.append(summary)
            elif signal_type == "weather":
                opposing.append(summary)
        elif market_type == "total":
            if signal_type == "weather":
                supporting.append(summary)
            elif signal_type == "market":
                supporting.append(summary)
            elif signal_type == "injury" and severity in {"high", "medium"}:
                supporting.append(summary)
            elif source_category == "team_context" and direction == "positive":
                opposing.append(summary)

    return supporting[:3], opposing[:3]



def _market_contributors(
    game: Dict[str, Any],
    signals: List[Dict[str, Any]],
    snapshot: Dict[str, Any],
    scoreboard: Optional[Dict[str, Any]],
    weather_resp: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    weather = (weather_resp or {}).get("weather") or {}
    live_state = bool(scoreboard and scoreboard.get("state") == "in")
    changed_market = bool(snapshot.get("changed"))

    contrib = {
        "ml": {"support": 0, "oppose": 0, "uncertainty": 0, "priced_in": 0},
        "spread": {"support": 0, "oppose": 0, "uncertainty": 0, "priced_in": 0},
        "total": {"support": 0, "oppose": 0, "uncertainty": 0, "priced_in": 0},
    }

    for signal in signals:
        signal_type = signal.get("type")
        severity = signal.get("severity")
        severity_weight = 3 if severity == "high" else 2 if severity == "medium" else 1
        source_category = signal.get("sourceCategory")
        direction = signal.get("direction")

        if signal_type == "injury":
            contrib["ml"]["support"] += severity_weight * 2
            contrib["spread"]["support"] += severity_weight * 3
            contrib["total"]["support"] += severity_weight
            if (signal.get("details") or {}).get("freshness") in {"fresh", "recent"}:
                contrib["ml"]["uncertainty"] += 1
                contrib["spread"]["uncertainty"] += 1
        elif signal_type == "weather":
            contrib["total"]["support"] += severity_weight * 3
            contrib["ml"]["oppose"] += 1
            contrib["spread"]["oppose"] += 1
        elif signal_type == "market":
            contrib["spread"]["support"] += severity_weight * 2
            contrib["total"]["support"] += severity_weight * 2
            contrib["ml"]["uncertainty"] += 1
        elif source_category == "team_context":
            if direction == "positive":
                contrib["ml"]["support"] += 2
                contrib["spread"]["support"] += 1
                contrib["total"]["oppose"] += 1
            elif direction == "negative":
                contrib["ml"]["support"] += 1
                contrib["spread"]["support"] += 2

    if changed_market:
        contrib["ml"]["priced_in"] += 1
        contrib["spread"]["priced_in"] += 2
        contrib["total"]["priced_in"] += 2
    if live_state:
        contrib["ml"]["uncertainty"] += 2
        contrib["spread"]["uncertainty"] += 3
        contrib["total"]["uncertainty"] += 4
    if weather.get("weather_applicable") and (weather.get("wind_speed_10m") or 0) >= 20:
        contrib["total"]["support"] += 2
    if game.get("num_books", 0) >= 8:
        contrib["ml"]["support"] += 1
        contrib["spread"]["support"] += 1
        contrib["total"]["support"] += 1

    return contrib



def _market_confidence_from_context(
    game: Dict[str, Any],
    signals: List[Dict[str, Any]],
    confidence: Dict[str, Any],
    snapshot: Dict[str, Any],
    scoreboard: Optional[Dict[str, Any]] = None,
    weather_resp: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = confidence.get("pct", 62)
    contributors = _market_contributors(game, signals, snapshot, scoreboard, weather_resp)
    weather_count = sum(1 for s in signals if s.get("type") == "weather")
    injury_count = sum(1 for s in signals if s.get("type") == "injury")

    out: Dict[str, Any] = {}
    for market_type in ("ml", "spread", "total"):
        c = contributors[market_type]
        pct = base + (c["support"] * 2) - (c["oppose"] * 2) - (c["uncertainty"] * 3) - (c["priced_in"] * 2)
        if market_type == "spread":
            pct -= 2
        elif market_type == "total":
            pct += 1 if weather_count or injury_count else -1
        pct = max(45, min(90, pct))

        tier, status = _market_tier_status(pct)
        supporting, opposing = _market_signal_split(signals, market_type)
        lean = None
        if market_type == "ml":
            pick = _pick_side_market(game)
            lean = f"{pick['team']} ML" if pick else None
        elif market_type == "spread":
            spread_pick = _best_spread_side(game)
            if spread_pick:
                point = spread_pick.get("point")
                lean = f"{spread_pick['team']} {('+' if point and point > 0 else '')}{point}"
            else:
                lean = "spread mixed"
        elif market_type == "total":
            total_pick = _best_total_side(game)
            total_side = "under" if weather_count or injury_count else "over" if supporting and not opposing else "mixed"
            if total_pick and total_side in {"under", "over"}:
                lean = f"{total_side} {total_pick.get('point')}"
            else:
                lean = total_side

        if supporting and opposing:
            reason = f"{supporting[0]}, but {opposing[0].lower()}"
        elif supporting:
            reason = supporting[0]
        elif opposing:
            reason = f"mixed read: {opposing[0]}"
        else:
            reason = "limited market-specific signal support so far"

        if market_type == "spread" and c["priced_in"] > 0 and supporting:
            reason = f"{supporting[0]}, but current spread may already reflect much of the edge"
        if market_type == "total" and weather_count and injury_count:
            reason = "Weather and lineup context both support the current total lean"

        credible = bool(lean) and (pct >= 58 or len(supporting) >= 2) and not (pct < 55 and c["priced_in"] > 0)
        out[market_type] = {
            "pct": pct,
            "tier": tier,
            "status": status,
            "lean": lean if credible else None,
            "reason": reason if credible else None,
            "supporting_signals": supporting if credible else [],
            "opposing_signals": opposing if credible else [],
            "priced_in": c["priced_in"] > 0,
            "volatility": "high" if c["uncertainty"] >= 3 else "medium" if c["uncertainty"] >= 1 else "low",
            "credible": credible,
            "contributors": c,
        }
    return out



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
    team_context = await team_context_adapter.fetch_for_game(game)
    weather = await weather_adapter.fetch_for_game(game)
    snapshot = update_snapshot(game)
    confidence = _confidence_from_context(game, scoreboard_norm, snapshot, injuries, weather, team_context)

    signals: List[Dict[str, Any]] = []
    signals.extend(_injury_signals(game, injuries, scoreboard_norm, team_context))
    signals.extend(_weather_signals(game, weather))
    signals.extend(_team_context_signal(game, team_context))

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

    signals = _rank_signals(signals, confidence)
    synthesized_summary, signal_mode = _synthesize_summary(signals, confidence, snapshot)

    recommendation = _recommendation_from_context(game, confidence, signals)
    market_movement = _movement_map(game, snapshot)
    market_confidence = _market_confidence_from_context(game, signals, confidence, snapshot, scoreboard_norm, weather)

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
            "team_context": team_context,
            "weather": weather,
        },
        "coverage": {
            "injury_coverage": injuries.get("coverage", "none"),
            "weather_coverage": weather.get("coverage", "none"),
        },
        "scoreboard": scoreboard_norm,
        "team_context": team_context,
        "snapshot": snapshot,
        "signals": signals,
        "summary": synthesized_summary,
        "signal_mode": signal_mode,
        "confidence": confidence,
        "market_confidence": market_confidence,
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
        raw_signals = intel.get("signals", [])
        confidence = intel.get("confidence")
        # Board should suppress injury noise; keep that depth for tracked/detail views.
        # Only surface injury if it's high severity and confidence is materially degraded.
        signals = [
            s for s in raw_signals
            if not (
                s.get("type") == "injury"
                and not (s.get("severity") == "high" and (confidence or {}).get("pct", 100) <= 64)
            )
        ]
        top_signal = signals[0] if signals else None
        board_summary = top_signal.get("summary") if top_signal else "No board-level signal surfaced"
        board_signal_mode = intel.get("signal_mode") if top_signal else None
        items.append({
            "game_id": game["id"],
            "confidence": confidence,
            "recommendation": intel.get("recommendation"),
            "market_movement": intel.get("market_movement"),
            "scoreboard": intel.get("scoreboard"),
            "signals": signals,
            "signals_count": len(signals),
            "top_signal": top_signal,
            "has_high_severity": any(s.get("severity") == "high" for s in raw_signals),
            "is_volatile": confidence.get("status") == "volatile" if confidence else False,
            "has_new_signal": len(signals) > 0,
            "signal_mode": board_signal_mode,
            "summary": board_summary,
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
