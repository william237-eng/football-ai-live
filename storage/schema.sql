-- Schéma SQL pour matches, live_snapshots, market_lines, executed_positions
-- Conçu pour SQLite/Postgres (types génériques)

CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    start_time TIMESTAMP,
    status TEXT,
    meta JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_start_time ON matches(start_time);

CREATE TABLE IF NOT EXISTS live_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    pressure_index REAL,
    xg_home REAL,
    xg_away REAL,
    poss_home REAL,
    raw JSON,
    FOREIGN KEY(match_id) REFERENCES matches(match_id)
);
CREATE INDEX IF NOT EXISTS idx_live_snapshots_mid_ts ON live_snapshots(match_id, timestamp);

CREATE TABLE IF NOT EXISTS market_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    market_type TEXT NOT NULL,
    selection TEXT,
    odds REAL NOT NULL,
    line_value REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta JSON
);
CREATE INDEX IF NOT EXISTS idx_market_lines_match_provider ON market_lines(match_id, provider);

CREATE TABLE IF NOT EXISTS executed_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    side TEXT NOT NULL,
    stake REAL NOT NULL,
    odds REAL NOT NULL,
    prob_model REAL NOT NULL,
    clv REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta JSON
);
CREATE INDEX IF NOT EXISTS idx_executed_positions_match ON executed_positions(match_id);

-- Table to replace the JSON-based registries (predictions per market)
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id TEXT,
    market TEXT,
    probability REAL,
    probability_pct REAL,
    confidence TEXT,
    status TEXT,
    result TEXT,
    total_cards_final INTEGER,
    timestamp_prediction TEXT,
    timestamp_validated TEXT,
    raw JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_predictions_fixture ON predictions(fixture_id);
CREATE INDEX IF NOT EXISTS idx_predictions_market ON predictions(market);

