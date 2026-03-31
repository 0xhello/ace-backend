# ACE Backend

Sports odds and game data API for the ACE frontend.

## Setup

```bash
# 1. Copy env and add your API key
cp .env.example .env
# edit .env and set ODDS_API_KEY=your_key_from_the-odds-api.com

# 2. Install deps
pip install -r requirements.txt

# 3. Run
uvicorn main:app --reload --port 8000
```

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Status + API key check |
| `GET /sports` | All active in-season sports |
| `GET /games` | All games (NBA/NFL/MLB/NHL/NCAAB/NCAAF) with odds |
| `GET /games/{sport}` | Games for one sport key |
| `GET /odds/{sport}` | Raw odds from The Odds API |

## Sport Keys

- `basketball_nba`
- `americanfootball_nfl`
- `baseball_mlb`
- `icehockey_nhl`
- `basketball_ncaab`
- `americanfootball_ncaaf`

## Docs

FastAPI auto-docs at: http://localhost:8000/docs
