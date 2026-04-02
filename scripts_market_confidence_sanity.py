import asyncio
from intel_service import _market_confidence_from_context

SAMPLES = [
    {
        "name": "injury + weather + market total",
        "game": {
            "home_team": "Home",
            "away_team": "Away",
            "num_books": 9,
            "bookmakers": [
                {"markets": {"spreads": [{"name": "Home", "point": -4.5, "price": -110}, {"name": "Away", "point": 4.5, "price": -110}], "totals": [{"name": "Over", "point": 223.5, "price": -110}, {"name": "Under", "point": 223.5, "price": -110}]}}
            ],
        },
        "signals": [
            {"type": "injury", "severity": "high", "summary": "Starter out — negative for Away", "affectedTeam": "away", "details": {"freshness": "fresh"}, "sourceCategory": "injury"},
            {"type": "weather", "severity": "medium", "summary": "Wind supports lower-scoring environment", "direction": "negative", "sourceCategory": "weather"},
            {"type": "market", "severity": "medium", "summary": "Total dropping across books", "direction": "uncertain", "sourceCategory": "market"},
            {"type": "news", "severity": "low", "summary": "Away is in poor recent form (1-4 in last five)", "direction": "negative", "sourceCategory": "team_context"},
        ],
        "confidence": {"pct": 66},
        "snapshot": {"changed": True},
        "scoreboard": {"state": "pre"},
        "weather_resp": {"weather": {"weather_applicable": True, "wind_speed_10m": 21}},
    },
    {
        "name": "live game uncertainty",
        "game": {
            "home_team": "Home",
            "away_team": "Away",
            "num_books": 6,
            "bookmakers": [
                {"markets": {"spreads": [{"name": "Home", "point": -2.5, "price": -115}, {"name": "Away", "point": 2.5, "price": -105}], "totals": [{"name": "Over", "point": 215.5, "price": -110}, {"name": "Under", "point": 215.5, "price": -110}]}}
            ],
        },
        "signals": [
            {"type": "market", "severity": "medium", "summary": "Market prices changed since the previous snapshot", "direction": "uncertain", "sourceCategory": "market"},
            {"type": "news", "severity": "low", "summary": "Game is live and intelligence context is updating", "direction": "uncertain", "sourceCategory": "ai"},
        ],
        "confidence": {"pct": 61},
        "snapshot": {"changed": True},
        "scoreboard": {"state": "in"},
        "weather_resp": {"weather": {}},
    },
]

async def main():
    for sample in SAMPLES:
        print(f"\n=== {sample['name']} ===")
        out = _market_confidence_from_context(
            sample['game'],
            sample['signals'],
            sample['confidence'],
            sample['snapshot'],
            sample['scoreboard'],
            sample['weather_resp'],
        )
        print(out)

if __name__ == '__main__':
    asyncio.run(main())
