from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

STATE_DIR = Path(__file__).resolve().parent / "state"
STATE_DIR.mkdir(exist_ok=True)
SNAPSHOT_PATH = STATE_DIR / "market_snapshots.json"


def _load() -> Dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        return {}
    try:
        return json.loads(SNAPSHOT_PATH.read_text())
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    SNAPSHOT_PATH.write_text(json.dumps(data, indent=2))


def _extract_signature(game: Dict[str, Any]) -> Dict[str, Any]:
    best_ml = game.get("best_moneyline", {})
    return {
        "home_team": game.get("home_team"),
        "away_team": game.get("away_team"),
        "best_moneyline": best_ml,
        "num_books": game.get("num_books"),
        "fetched_at": game.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
    }


def update_snapshot(game: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    game_id = game.get("id")
    current = _extract_signature(game)
    previous = data.get(game_id)
    changed = False
    movement = []

    if previous:
        prev_ml = previous.get("best_moneyline", {})
        curr_ml = current.get("best_moneyline", {})
        for team, price in curr_ml.items():
            prev_price = prev_ml.get(team)
            if prev_price is not None and price != prev_price:
                changed = True
                direction = "improved" if price > prev_price else "worse"
                movement.append({
                    "team": team,
                    "from": prev_price,
                    "to": price,
                    "direction": direction,
                })

    data[game_id] = current
    _save(data)

    return {
        "has_previous": previous is not None,
        "changed": changed,
        "movement": movement,
        "previous_fetched_at": previous.get("fetched_at") if previous else None,
        "current_fetched_at": current.get("fetched_at"),
    }
