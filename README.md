# ACE Backend

Sports odds and intelligence API for the ACE frontend.

## Current backbone

- **Market data:** The Odds API
- **Intelligence adapter groundwork:**
  - ESPN scoreboard (live game state)
  - ESPN injuries (scaffolded, pending explicit team mapping)
  - Open-Meteo weather (scaffolded, pending venue mapping)

## Setup

```bash
cp .env.example .env
# set ODDS_API_KEY=...

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Status + API key check |
| `GET /sports` | All active in-season sports |
| `GET /games` | All games with odds |
| `GET /games/{sport}` | Games for one sport key |
| `GET /odds/{sport}` | Raw odds from The Odds API |
| `GET /sources/status` | External source adapter readiness |
| `GET /intel/game/{game_id}` | Normalized intelligence payload for one game |
| `GET /intel/tracked` | Tracked index scaffold payload |

## Notes

### What is real now
- Odds API market data
- ESPN scoreboard adapter architecture
- Snapshot foundation for internal market movement tracking
- Normalized intelligence payload shape for frontend consumption

### What is intentionally not guessed yet
- ESPN team ID mapping for injury endpoints
- Venue coordinate mapping for weather lookup

Those are blocked on explicit mapping because ACE should not guess unsafe production logic.

## Docs

FastAPI auto-docs at: http://localhost:8000/docs
