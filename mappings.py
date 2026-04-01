from __future__ import annotations

from typing import Any, Dict, Optional

# Canonical mapping layer for Push 7.
# This is intentionally explicit: ACE team name -> ESPN team id / weather anchor metadata.
# We prefer partial-but-safe mappings over guessed production logic.

ESPN_TEAM_MAPPINGS: Dict[str, Dict[str, Dict[str, str]]] = {
    "americanfootball_nfl": {
        "Arizona Cardinals": {"espn_id": "22", "abbr": "ARI"},
        "Atlanta Falcons": {"espn_id": "1", "abbr": "ATL"},
        "Baltimore Ravens": {"espn_id": "33", "abbr": "BAL"},
        "Buffalo Bills": {"espn_id": "2", "abbr": "BUF"},
        "Carolina Panthers": {"espn_id": "29", "abbr": "CAR"},
        "Chicago Bears": {"espn_id": "3", "abbr": "CHI"},
        "Cincinnati Bengals": {"espn_id": "4", "abbr": "CIN"},
        "Cleveland Browns": {"espn_id": "5", "abbr": "CLE"},
        "Dallas Cowboys": {"espn_id": "6", "abbr": "DAL"},
        "Denver Broncos": {"espn_id": "7", "abbr": "DEN"},
        "Detroit Lions": {"espn_id": "8", "abbr": "DET"},
        "Green Bay Packers": {"espn_id": "9", "abbr": "GB"},
        "Houston Texans": {"espn_id": "34", "abbr": "HOU"},
        "Indianapolis Colts": {"espn_id": "11", "abbr": "IND"},
        "Jacksonville Jaguars": {"espn_id": "30", "abbr": "JAX"},
        "Kansas City Chiefs": {"espn_id": "12", "abbr": "KC"},
        "Las Vegas Raiders": {"espn_id": "13", "abbr": "LV"},
        "Los Angeles Chargers": {"espn_id": "24", "abbr": "LAC"},
        "Los Angeles Rams": {"espn_id": "14", "abbr": "LAR"},
        "Miami Dolphins": {"espn_id": "15", "abbr": "MIA"},
        "Minnesota Vikings": {"espn_id": "16", "abbr": "MIN"},
        "New England Patriots": {"espn_id": "17", "abbr": "NE"},
        "New Orleans Saints": {"espn_id": "18", "abbr": "NO"},
        "New York Giants": {"espn_id": "19", "abbr": "NYG"},
        "New York Jets": {"espn_id": "20", "abbr": "NYJ"},
        "Philadelphia Eagles": {"espn_id": "21", "abbr": "PHI"},
        "Pittsburgh Steelers": {"espn_id": "23", "abbr": "PIT"},
        "San Francisco 49ers": {"espn_id": "25", "abbr": "SF"},
        "Seattle Seahawks": {"espn_id": "26", "abbr": "SEA"},
        "Tampa Bay Buccaneers": {"espn_id": "27", "abbr": "TB"},
        "Tennessee Titans": {"espn_id": "10", "abbr": "TEN"},
        "Washington Commanders": {"espn_id": "28", "abbr": "WSH"},
    },
    "basketball_nba": {
        "Atlanta Hawks": {"espn_id": "1", "abbr": "ATL"},
        "Boston Celtics": {"espn_id": "2", "abbr": "BOS"},
        "Brooklyn Nets": {"espn_id": "17", "abbr": "BKN"},
        "Charlotte Hornets": {"espn_id": "30", "abbr": "CHA"},
        "Chicago Bulls": {"espn_id": "4", "abbr": "CHI"},
        "Cleveland Cavaliers": {"espn_id": "5", "abbr": "CLE"},
        "Dallas Mavericks": {"espn_id": "6", "abbr": "DAL"},
        "Denver Nuggets": {"espn_id": "7", "abbr": "DEN"},
        "Detroit Pistons": {"espn_id": "8", "abbr": "DET"},
        "Golden State Warriors": {"espn_id": "9", "abbr": "GS"},
        "Houston Rockets": {"espn_id": "10", "abbr": "HOU"},
        "Indiana Pacers": {"espn_id": "11", "abbr": "IND"},
        "LA Clippers": {"espn_id": "12", "abbr": "LAC"},
        "Los Angeles Lakers": {"espn_id": "13", "abbr": "LAL"},
        "Memphis Grizzlies": {"espn_id": "29", "abbr": "MEM"},
        "Miami Heat": {"espn_id": "14", "abbr": "MIA"},
        "Milwaukee Bucks": {"espn_id": "15", "abbr": "MIL"},
        "Minnesota Timberwolves": {"espn_id": "16", "abbr": "MIN"},
        "New Orleans Pelicans": {"espn_id": "3", "abbr": "NO"},
        "New York Knicks": {"espn_id": "18", "abbr": "NY"},
        "Oklahoma City Thunder": {"espn_id": "25", "abbr": "OKC"},
        "Orlando Magic": {"espn_id": "19", "abbr": "ORL"},
        "Philadelphia 76ers": {"espn_id": "20", "abbr": "PHI"},
        "Phoenix Suns": {"espn_id": "21", "abbr": "PHX"},
        "Portland Trail Blazers": {"espn_id": "22", "abbr": "POR"},
        "Sacramento Kings": {"espn_id": "23", "abbr": "SAC"},
        "San Antonio Spurs": {"espn_id": "24", "abbr": "SA"},
        "Toronto Raptors": {"espn_id": "28", "abbr": "TOR"},
        "Utah Jazz": {"espn_id": "26", "abbr": "UTAH"},
        "Washington Wizards": {"espn_id": "27", "abbr": "WSH"},
    },
    "baseball_mlb": {
        "Arizona Diamondbacks": {"espn_id": "29", "abbr": "ARI"},
        "Athletics": {"espn_id": "11", "abbr": "ATH"},
        "Atlanta Braves": {"espn_id": "15", "abbr": "ATL"},
        "Baltimore Orioles": {"espn_id": "1", "abbr": "BAL"},
        "Boston Red Sox": {"espn_id": "2", "abbr": "BOS"},
        "Chicago Cubs": {"espn_id": "16", "abbr": "CHC"},
        "Chicago White Sox": {"espn_id": "4", "abbr": "CHW"},
        "Cincinnati Reds": {"espn_id": "17", "abbr": "CIN"},
        "Cleveland Guardians": {"espn_id": "5", "abbr": "CLE"},
        "Colorado Rockies": {"espn_id": "27", "abbr": "COL"},
        "Detroit Tigers": {"espn_id": "6", "abbr": "DET"},
        "Houston Astros": {"espn_id": "18", "abbr": "HOU"},
        "Kansas City Royals": {"espn_id": "7", "abbr": "KC"},
        "Los Angeles Angels": {"espn_id": "3", "abbr": "LAA"},
        "Los Angeles Dodgers": {"espn_id": "19", "abbr": "LAD"},
        "Miami Marlins": {"espn_id": "28", "abbr": "MIA"},
        "Milwaukee Brewers": {"espn_id": "8", "abbr": "MIL"},
        "Minnesota Twins": {"espn_id": "9", "abbr": "MIN"},
        "New York Mets": {"espn_id": "21", "abbr": "NYM"},
        "New York Yankees": {"espn_id": "10", "abbr": "NYY"},
        "Philadelphia Phillies": {"espn_id": "22", "abbr": "PHI"},
        "Pittsburgh Pirates": {"espn_id": "23", "abbr": "PIT"},
        "San Diego Padres": {"espn_id": "25", "abbr": "SD"},
        "San Francisco Giants": {"espn_id": "26", "abbr": "SF"},
        "Seattle Mariners": {"espn_id": "12", "abbr": "SEA"},
        "St. Louis Cardinals": {"espn_id": "24", "abbr": "STL"},
        "Tampa Bay Rays": {"espn_id": "30", "abbr": "TB"},
        "Texas Rangers": {"espn_id": "13", "abbr": "TEX"},
        "Toronto Blue Jays": {"espn_id": "14", "abbr": "TOR"},
        "Washington Nationals": {"espn_id": "20", "abbr": "WSH"},
    },
    "icehockey_nhl": {
        "Anaheim Ducks": {"espn_id": "25", "abbr": "ANA"},
        "Boston Bruins": {"espn_id": "1", "abbr": "BOS"},
        "Buffalo Sabres": {"espn_id": "2", "abbr": "BUF"},
        "Calgary Flames": {"espn_id": "3", "abbr": "CGY"},
        "Carolina Hurricanes": {"espn_id": "7", "abbr": "CAR"},
        "Chicago Blackhawks": {"espn_id": "4", "abbr": "CHI"},
        "Colorado Avalanche": {"espn_id": "17", "abbr": "COL"},
        "Columbus Blue Jackets": {"espn_id": "29", "abbr": "CBJ"},
        "Dallas Stars": {"espn_id": "9", "abbr": "DAL"},
        "Detroit Red Wings": {"espn_id": "5", "abbr": "DET"},
        "Edmonton Oilers": {"espn_id": "6", "abbr": "EDM"},
        "Florida Panthers": {"espn_id": "26", "abbr": "FLA"},
        "Los Angeles Kings": {"espn_id": "8", "abbr": "LA"},
        "Minnesota Wild": {"espn_id": "30", "abbr": "MIN"},
        "Montreal Canadiens": {"espn_id": "10", "abbr": "MTL"},
        "Nashville Predators": {"espn_id": "27", "abbr": "NSH"},
        "New Jersey Devils": {"espn_id": "11", "abbr": "NJ"},
        "New York Islanders": {"espn_id": "12", "abbr": "NYI"},
        "New York Rangers": {"espn_id": "13", "abbr": "NYR"},
        "Ottawa Senators": {"espn_id": "14", "abbr": "OTT"},
        "Philadelphia Flyers": {"espn_id": "15", "abbr": "PHI"},
        "Pittsburgh Penguins": {"espn_id": "16", "abbr": "PIT"},
        "San Jose Sharks": {"espn_id": "18", "abbr": "SJ"},
        "Seattle Kraken": {"espn_id": "124292", "abbr": "SEA"},
        "St. Louis Blues": {"espn_id": "19", "abbr": "STL"},
        "Tampa Bay Lightning": {"espn_id": "20", "abbr": "TB"},
        "Toronto Maple Leafs": {"espn_id": "21", "abbr": "TOR"},
        "Utah Mammoth": {"espn_id": "129764", "abbr": "UTAH"},
        "Vancouver Canucks": {"espn_id": "22", "abbr": "VAN"},
        "Vegas Golden Knights": {"espn_id": "37", "abbr": "VGK"},
        "Washington Capitals": {"espn_id": "23", "abbr": "WSH"},
        "Winnipeg Jets": {"espn_id": "28", "abbr": "WPG"},
    },
}

# Explicit weather anchors for outdoor-priority sports.
# Coordinates are intentionally explicit and stored locally so weather enrichment is deterministic.
WEATHER_LOCATION_MAPPINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "americanfootball_nfl": {
        "Arizona Cardinals": {"anchor_name": "State Farm Stadium", "lat": 33.5276, "lon": -112.2626, "indoor": True, "weather_applicable": False},
        "Atlanta Falcons": {"anchor_name": "Mercedes-Benz Stadium", "lat": 33.7554, "lon": -84.4009, "indoor": True, "weather_applicable": False},
        "Baltimore Ravens": {"anchor_name": "M&T Bank Stadium", "lat": 39.2780, "lon": -76.6227, "indoor": False, "weather_applicable": True},
        "Buffalo Bills": {"anchor_name": "Highmark Stadium", "lat": 42.7738, "lon": -78.7870, "indoor": False, "weather_applicable": True},
        "Carolina Panthers": {"anchor_name": "Bank of America Stadium", "lat": 35.2258, "lon": -80.8528, "indoor": False, "weather_applicable": True},
        "Chicago Bears": {"anchor_name": "Soldier Field", "lat": 41.8623, "lon": -87.6167, "indoor": False, "weather_applicable": True},
        "Cincinnati Bengals": {"anchor_name": "Paycor Stadium", "lat": 39.0955, "lon": -84.5160, "indoor": False, "weather_applicable": True},
        "Cleveland Browns": {"anchor_name": "Huntington Bank Field", "lat": 41.5061, "lon": -81.6995, "indoor": False, "weather_applicable": True},
        "Dallas Cowboys": {"anchor_name": "AT&T Stadium", "lat": 32.7473, "lon": -97.0945, "indoor": True, "weather_applicable": False},
        "Denver Broncos": {"anchor_name": "Empower Field at Mile High", "lat": 39.7439, "lon": -105.0201, "indoor": False, "weather_applicable": True},
        "Detroit Lions": {"anchor_name": "Ford Field", "lat": 42.3400, "lon": -83.0456, "indoor": True, "weather_applicable": False},
        "Green Bay Packers": {"anchor_name": "Lambeau Field", "lat": 44.5013, "lon": -88.0622, "indoor": False, "weather_applicable": True},
        "Houston Texans": {"anchor_name": "NRG Stadium", "lat": 29.6847, "lon": -95.4107, "indoor": True, "weather_applicable": False},
        "Indianapolis Colts": {"anchor_name": "Lucas Oil Stadium", "lat": 39.7601, "lon": -86.1639, "indoor": True, "weather_applicable": False},
        "Jacksonville Jaguars": {"anchor_name": "EverBank Stadium", "lat": 30.3239, "lon": -81.6373, "indoor": False, "weather_applicable": True},
        "Kansas City Chiefs": {"anchor_name": "GEHA Field at Arrowhead Stadium", "lat": 39.0489, "lon": -94.4839, "indoor": False, "weather_applicable": True},
        "Las Vegas Raiders": {"anchor_name": "Allegiant Stadium", "lat": 36.0908, "lon": -115.1830, "indoor": True, "weather_applicable": False},
        "Los Angeles Chargers": {"anchor_name": "SoFi Stadium", "lat": 33.9535, "lon": -118.3392, "indoor": True, "weather_applicable": False},
        "Los Angeles Rams": {"anchor_name": "SoFi Stadium", "lat": 33.9535, "lon": -118.3392, "indoor": True, "weather_applicable": False},
        "Miami Dolphins": {"anchor_name": "Hard Rock Stadium", "lat": 25.9580, "lon": -80.2389, "indoor": False, "weather_applicable": True},
        "Minnesota Vikings": {"anchor_name": "U.S. Bank Stadium", "lat": 44.9737, "lon": -93.2575, "indoor": True, "weather_applicable": False},
        "New England Patriots": {"anchor_name": "Gillette Stadium", "lat": 42.0909, "lon": -71.2643, "indoor": False, "weather_applicable": True},
        "New Orleans Saints": {"anchor_name": "Caesars Superdome", "lat": 29.9509, "lon": -90.0812, "indoor": True, "weather_applicable": False},
        "New York Giants": {"anchor_name": "MetLife Stadium", "lat": 40.8135, "lon": -74.0745, "indoor": False, "weather_applicable": True},
        "New York Jets": {"anchor_name": "MetLife Stadium", "lat": 40.8135, "lon": -74.0745, "indoor": False, "weather_applicable": True},
        "Philadelphia Eagles": {"anchor_name": "Lincoln Financial Field", "lat": 39.9008, "lon": -75.1675, "indoor": False, "weather_applicable": True},
        "Pittsburgh Steelers": {"anchor_name": "Acrisure Stadium", "lat": 40.4468, "lon": -80.0158, "indoor": False, "weather_applicable": True},
        "San Francisco 49ers": {"anchor_name": "Levi's Stadium", "lat": 37.4030, "lon": -121.9700, "indoor": False, "weather_applicable": True},
        "Seattle Seahawks": {"anchor_name": "Lumen Field", "lat": 47.5952, "lon": -122.3316, "indoor": False, "weather_applicable": True},
        "Tampa Bay Buccaneers": {"anchor_name": "Raymond James Stadium", "lat": 27.9759, "lon": -82.5033, "indoor": False, "weather_applicable": True},
        "Tennessee Titans": {"anchor_name": "Nissan Stadium", "lat": 36.1665, "lon": -86.7713, "indoor": False, "weather_applicable": True},
        "Washington Commanders": {"anchor_name": "Northwest Stadium", "lat": 38.9078, "lon": -76.8644, "indoor": False, "weather_applicable": True},
    },
    "baseball_mlb": {
        "Arizona Diamondbacks": {"anchor_name": "Chase Field", "lat": 33.4455, "lon": -112.0667, "indoor": True, "weather_applicable": False},
        "Athletics": {"anchor_name": "Sutter Health Park", "lat": 38.5806, "lon": -121.5139, "indoor": False, "weather_applicable": True},
        "Atlanta Braves": {"anchor_name": "Truist Park", "lat": 33.8907, "lon": -84.4677, "indoor": False, "weather_applicable": True},
        "Baltimore Orioles": {"anchor_name": "Oriole Park at Camden Yards", "lat": 39.2841, "lon": -76.6215, "indoor": False, "weather_applicable": True},
        "Boston Red Sox": {"anchor_name": "Fenway Park", "lat": 42.3467, "lon": -71.0972, "indoor": False, "weather_applicable": True},
        "Chicago Cubs": {"anchor_name": "Wrigley Field", "lat": 41.9484, "lon": -87.6553, "indoor": False, "weather_applicable": True},
        "Chicago White Sox": {"anchor_name": "Rate Field", "lat": 41.8300, "lon": -87.6338, "indoor": False, "weather_applicable": True},
        "Cincinnati Reds": {"anchor_name": "Great American Ball Park", "lat": 39.0979, "lon": -84.5081, "indoor": False, "weather_applicable": True},
        "Cleveland Guardians": {"anchor_name": "Progressive Field", "lat": 41.4962, "lon": -81.6852, "indoor": False, "weather_applicable": True},
        "Colorado Rockies": {"anchor_name": "Coors Field", "lat": 39.7561, "lon": -104.9942, "indoor": False, "weather_applicable": True},
        "Detroit Tigers": {"anchor_name": "Comerica Park", "lat": 42.3390, "lon": -83.0485, "indoor": False, "weather_applicable": True},
        "Houston Astros": {"anchor_name": "Daikin Park", "lat": 29.7572, "lon": -95.3552, "indoor": True, "weather_applicable": False},
        "Kansas City Royals": {"anchor_name": "Kauffman Stadium", "lat": 39.0517, "lon": -94.4803, "indoor": False, "weather_applicable": True},
        "Los Angeles Angels": {"anchor_name": "Angel Stadium", "lat": 33.8003, "lon": -117.8827, "indoor": False, "weather_applicable": True},
        "Los Angeles Dodgers": {"anchor_name": "Dodger Stadium", "lat": 34.0739, "lon": -118.2400, "indoor": False, "weather_applicable": True},
        "Miami Marlins": {"anchor_name": "loanDepot park", "lat": 25.7781, "lon": -80.2197, "indoor": True, "weather_applicable": False},
        "Milwaukee Brewers": {"anchor_name": "American Family Field", "lat": 43.0280, "lon": -87.9712, "indoor": True, "weather_applicable": False},
        "Minnesota Twins": {"anchor_name": "Target Field", "lat": 44.9817, "lon": -93.2776, "indoor": False, "weather_applicable": True},
        "New York Mets": {"anchor_name": "Citi Field", "lat": 40.7571, "lon": -73.8458, "indoor": False, "weather_applicable": True},
        "New York Yankees": {"anchor_name": "Yankee Stadium", "lat": 40.8296, "lon": -73.9262, "indoor": False, "weather_applicable": True},
        "Philadelphia Phillies": {"anchor_name": "Citizens Bank Park", "lat": 39.9061, "lon": -75.1665, "indoor": False, "weather_applicable": True},
        "Pittsburgh Pirates": {"anchor_name": "PNC Park", "lat": 40.4469, "lon": -80.0057, "indoor": False, "weather_applicable": True},
        "San Diego Padres": {"anchor_name": "Petco Park", "lat": 32.7073, "lon": -117.1573, "indoor": False, "weather_applicable": True},
        "San Francisco Giants": {"anchor_name": "Oracle Park", "lat": 37.7786, "lon": -122.3893, "indoor": False, "weather_applicable": True},
        "Seattle Mariners": {"anchor_name": "T-Mobile Park", "lat": 47.5914, "lon": -122.3325, "indoor": True, "weather_applicable": False},
        "St. Louis Cardinals": {"anchor_name": "Busch Stadium", "lat": 38.6226, "lon": -90.1928, "indoor": False, "weather_applicable": True},
        "Tampa Bay Rays": {"anchor_name": "George M. Steinbrenner Field", "lat": 27.9803, "lon": -82.5062, "indoor": False, "weather_applicable": True},
        "Texas Rangers": {"anchor_name": "Globe Life Field", "lat": 32.7473, "lon": -97.0825, "indoor": True, "weather_applicable": False},
        "Toronto Blue Jays": {"anchor_name": "Rogers Centre", "lat": 43.6414, "lon": -79.3894, "indoor": True, "weather_applicable": False},
        "Washington Nationals": {"anchor_name": "Nationals Park", "lat": 38.8730, "lon": -77.0074, "indoor": False, "weather_applicable": True},
    },
}


def get_espn_team_mapping(sport_key: str, team_name: str) -> Optional[Dict[str, str]]:
    return ESPN_TEAM_MAPPINGS.get(sport_key, {}).get(team_name)



def get_weather_mapping(sport_key: str, team_name: str) -> Optional[Dict[str, Any]]:
    return WEATHER_LOCATION_MAPPINGS.get(sport_key, {}).get(team_name)



def get_injury_coverage(sport_key: str, home_team: str, away_team: str) -> str:
    teams = ESPN_TEAM_MAPPINGS.get(sport_key, {})
    have = sum(1 for t in (home_team, away_team) if t in teams)
    if have == 2:
        return "full"
    if have == 1:
        return "partial"
    return "none"



def get_weather_coverage(sport_key: str, home_team: str) -> str:
    if sport_key not in {"americanfootball_nfl", "americanfootball_ncaaf", "baseball_mlb"}:
        return "not_applicable"
    mapping = get_weather_mapping(sport_key, home_team)
    if not mapping:
        return "none"
    return "full" if mapping.get("weather_applicable", False) or mapping.get("indoor") is not None else "partial"
