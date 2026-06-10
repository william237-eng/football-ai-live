/* ═══════════════════════════════════════════════════════════════════════════════
   SCHÉMA SQL — MOTEUR DE TRADING ALGORITHMIQUE
   Base de données : SQLite (pour développement) / PostgreSQL (production)
   Optimisations : INDEX sur clés de recherche fréquentes
   ═══════════════════════════════════════════════════════════════════════════════ */

-- Table 1 : Matches (fixtures)
CREATE TABLE IF NOT EXISTS matches (
    fixture_id INTEGER PRIMARY KEY,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    home_team_name TEXT NOT NULL,
    away_team_name TEXT NOT NULL,
    league_id INTEGER NOT NULL,
    league_name TEXT NOT NULL,
    kickoff_ts BIGINT NOT NULL,
    status TEXT DEFAULT 'NS',  -- NS, 1H, HT, 2H, FT, etc.

    -- Données Elo Dynamique (Pré-Match)
    elo_home REAL DEFAULT 1500.0,
    elo_away REAL DEFAULT 1500.0,

    -- xG Pré-Match (Dixon-Coles Lambda)
    lambda_home_pre REAL DEFAULT 1.5,
    lambda_away_pre REAL DEFAULT 1.5,

    -- Fatigue & Déplacement
    days_rest_home INTEGER DEFAULT 7,
    days_rest_away INTEGER DEFAULT 7,
    distance_km_home REAL DEFAULT 0.0,
    distance_km_away REAL DEFAULT 0.0,
    fatigue_coeff_home REAL DEFAULT 1.0,
    fatigue_coeff_away REAL DEFAULT 1.0,

    -- Climat & Arbitrage
    weather_condition TEXT DEFAULT 'clear',
    precipitation_mm REAL DEFAULT 0.0,
    referee_id INTEGER,
    referee_name TEXT,
    referee_card_ratio REAL DEFAULT 0.0,

    -- Topologie Tactique
    tactical_vulnerability_home REAL DEFAULT 1.0,
    tactical_vulnerability_away REAL DEFAULT 1.0,
    motivation_urgency_home REAL DEFAULT 1.0,  -- Compression variance basée urgence points
    motivation_urgency_away REAL DEFAULT 1.0,

    -- Marqueurs pré-match finalisés
    final_lambda_home REAL,
    final_lambda_away REAL,
    marche_outcome_prob REAL DEFAULT 0.0,  -- P(Home Win) via Dixon-Coles

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_matches_kickoff ON matches(kickoff_ts);
CREATE INDEX idx_matches_league ON matches(league_id);

-- Table 2 : Live Snapshots (Deltas minute par minute)
CREATE TABLE IF NOT EXISTS live_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL REFERENCES matches(fixture_id),
    minute_elapsed INTEGER NOT NULL,
    timestamp BIGINT NOT NULL,

    -- Score & Événements
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,

    -- xG cumulé live
    xg_home_accumulated REAL DEFAULT 0.0,
    xg_away_accumulated REAL DEFAULT 0.0,
    xg_home_live REAL DEFAULT 0.0,
    xg_away_live REAL DEFAULT 0.0,

    -- Pression Live (PPDA, possession, tirs)
    ppda_home REAL DEFAULT 10.0,  -- Passes Per Defensive Action
    ppda_away REAL DEFAULT 10.0,
    possession_pct_home REAL DEFAULT 50.0,
    possession_pct_away REAL DEFAULT 50.0,
    shots_total_home INTEGER DEFAULT 0,
    shots_total_away INTEGER DEFAULT 0,
    shots_on_target_home INTEGER DEFAULT 0,
    shots_on_target_away INTEGER DEFAULT 0,
    corners_home INTEGER DEFAULT 0,
    corners_away INTEGER DEFAULT 0,

    -- Cartons & Exclusions
    yellows_home INTEGER DEFAULT 0,
    yellows_away INTEGER DEFAULT 0,
    reds_home INTEGER DEFAULT 0,
    reds_away INTEGER DEFAULT 0,

    -- Live Pressure Index (brut et lissé via EMA)
    pressure_index_home REAL DEFAULT 50.0,
    pressure_index_away REAL DEFAULT 50.0,
    pressure_index_ema_home REAL DEFAULT 50.0,
    pressure_index_ema_away REAL DEFAULT 50.0,

    -- Lambda recalculé (Bayésien)
    lambda_home_live REAL,
    lambda_away_live REAL,

    -- Détection Carton Rouge / Blessures Fantômes
    red_card_home BOOLEAN DEFAULT FALSE,
    red_card_away BOOLEAN DEFAULT FALSE,
    ghost_injury_detected BOOLEAN DEFAULT FALSE,

    -- Métadonnées
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_snapshots_fixture ON live_snapshots(fixture_id, minute_elapsed);
CREATE INDEX idx_snapshots_timestamp ON live_snapshots(timestamp);

-- Table 3 : Market Lines (suivi des cotes, Asian Handicap, O/U)
CREATE TABLE IF NOT EXISTS market_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL REFERENCES matches(fixture_id),
    timestamp BIGINT NOT NULL,

    -- Bookmaker & API Source
    bookmaker_name TEXT NOT NULL,
    api_source TEXT DEFAULT 'pinnacle',

    -- Over/Under 2.5 Buts
    ou_2_5_over_odds REAL,
    ou_2_5_under_odds REAL,

    -- Asian Handicap (Handicap mains: -0.5, -1.0, -1.5, etc.)
    ah_home_line REAL,  -- ex: -0.5 (Home apeurant devoir gagner de 1+ but net)
    ah_home_odds REAL,
    ah_away_odds REAL,

    -- 1X2 Classique
    odds_1 REAL,  -- Home Win
    odds_x REAL,  -- Draw
    odds_2 REAL,  -- Away Win

    -- Métadonnées pour Veto
    last_line_movement_pct REAL DEFAULT 0.0,  -- Variation % par rapport dernier snapshot
    sharp_money_detected BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_lines_fixture_time ON market_lines(fixture_id, timestamp);

-- Table 4 : Executed Positions (Historique des ordres exécutés)
CREATE TABLE IF NOT EXISTS executed_positions (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL REFERENCES matches(fixture_id),

    -- Type Pari (Market)
    market_type TEXT NOT NULL,  -- 'OU_2_5', 'AH', '1X2', 'OVER_YELLOW', etc.
    side TEXT NOT NULL,  -- 'OVER', 'UNDER', 'HOME', 'AWAY', 'DRAW'

    -- Modèle & Décision
    model_used TEXT NOT NULL,  -- 'DIXON_COLES', 'BAYESIAN_LIVE', 'SKELLAM', etc.
    predicted_probability REAL NOT NULL,
    bookmaker_odds REAL NOT NULL,
    kelly_fraction REAL NOT NULL,  -- Fraction du Kelly plein

    -- Execution
    stake_units REAL NOT NULL,
    max_bet_limit REAL,
    slippage_tolerance_pct REAL DEFAULT 2.0,
    order_placed_at BIGINT NOT NULL,
    odds_at_execution REAL,

    -- Résultat
    status TEXT DEFAULT 'PENDING',  -- PENDING, WON, LOST, VOID, CANCELLED
    final_result TEXT,
    clv_value REAL,  -- Closing Line Value = (odd_executed / odd_closing) - 1
    profit_units REAL,

    metadata_json TEXT,  -- JSON: détails additionnels
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_positions_fixture ON executed_positions(fixture_id);
CREATE INDEX idx_positions_status ON executed_positions(status);
CREATE INDEX idx_positions_model ON executed_positions(model_used);

-- Optimization pour requêtes fréquentes
CREATE INDEX idx_matches_status_kickoff ON matches(status, kickoff_ts);
CREATE INDEX idx_snapshots_live_lambda ON live_snapshots(fixture_id, lambda_home_live, lambda_away_live);

