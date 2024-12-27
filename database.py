import sqlite3

DATABASE = 'database/db_fantasy.db'

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

# Existing Tables
cursor.execute("""
    CREATE TABLE IF NOT EXISTS nflWeek (
        week INTEGER PRIMARY KEY,
        season_type TEXT,
        season_start_date TEXT,
        season INTEGER,
        display_week TEXT
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        game_id TEXT PRIMARY KEY,
        name TEXT,
        date TEXT,
        week INTEGER,
        venue_id TEXT,
        status TEXT,
        clock TEXT,
        period TEXT,
        down TEXT,
        detailed_text TEXT
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        team_id TEXT,
        game_id TEXT,
        team_name TEXT,
        score INTEGER,
        home_away TEXT,
        abbreviation TEXT,
        logo TEXT,
        record TEXT,
        PRIMARY KEY (team_id, game_id),
        FOREIGN KEY (game_id) REFERENCES games (game_id)
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        team_id INTEGER PRIMARY KEY,
        record TEXT,
        win_percentage REAL,
        avg_points_for REAL,
        avg_points_against REAL,
        points_for REAL,
        points_against REAL,
        point_differential REAL,
        division_record TEXT,
        division_win_percentage REAL,
        games_played INTEGER,
        playoff_seed INTEGER,
        streak TEXT
    );

""")


cursor.execute("""
    CREATE TABLE IF NOT EXISTS venues (
        venue_id TEXT PRIMARY KEY,
        full_name TEXT,
        city TEXT,
        state TEXT,
        indoor BOOLEAN
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS broadcasts (
        game_id TEXT,
        market TEXT,
        channel TEXT,
        FOREIGN KEY (game_id) REFERENCES games (game_id)
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS competition_results (
        result_id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT,
        name TEXT,
        week INTEGER,
        competition_date TEXT,
        team_id TEXT,
        team_name TEXT,
        team_logo TEXT,
        opponent_id TEXT,
        opponent_name TEXT,
        opponent_logo TEXT,
        team_score INTEGER,
        opponent_score INTEGER,
        outcome TEXT,
        FOREIGN KEY (game_id) REFERENCES games (game_id),
        FOREIGN KEY (team_id) REFERENCES teams (team_id),
        FOREIGN KEY (opponent_id) REFERENCES teams (team_id)
    );

""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        player_id TEXT PRIMARY KEY,
        full_name TEXT,
        first_name TEXT,
        last_name TEXT,
        jersey TEXT,
        team_id TEXT,
        FOREIGN KEY (team_id) REFERENCES teams (team_id)
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_stats (
        stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT,
        game_id TEXT,
        team_id TEXT,
        category TEXT,
        stat_key TEXT,
        stat_value TEXT,
        jersey TEXT,
        FOREIGN KEY (player_id) REFERENCES players (player_id),
        FOREIGN KEY (game_id) REFERENCES games (game_id),
        FOREIGN KEY (team_id) REFERENCES teams (team_id)
    );
""")


# New Odds Tables

# 1. Odds Table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS odds (
        odds_id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT,
        provider_id TEXT,
        details TEXT,
        over_under REAL,
        spread REAL,
        over_odds INTEGER,
        under_odds INTEGER,
        moneyline_winner BOOLEAN,
        spread_winner BOOLEAN,
        FOREIGN KEY (game_id) REFERENCES games (game_id)
    );
""")

cursor.execute("""
        CREATE TABLE IF NOT EXISTS boxscore_data (
            team_id TEXT,
            team_name TEXT,
            abbreviation TEXT,
            home_away TEXT,
            player_id TEXT,
            full_name TEXT,
            position TEXT,
            stat_category TEXT,
            stat_value TEXT,
            PRIMARY KEY (team_id, player_id, stat_category)
            );
""")

# 2. Odds Provider Table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS odds_provider (
        provider_id TEXT PRIMARY KEY,
        name TEXT,
        priority INTEGER
    );
""")

# 3. Team Odds Table (Home/Away Specific Odds)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS team_odds (
        team_odds_id INTEGER PRIMARY KEY AUTOINCREMENT,
        odds_id INTEGER,
        team_id TEXT,
        game_id TEXT,
        favorite BOOLEAN,
        underdog BOOLEAN,
        moneyline INTEGER,
        spread_odds INTEGER,
        point_spread TEXT,
        FOREIGN KEY (team_id) REFERENCES teams (team_id),
        FOREIGN KEY (game_id) REFERENCES games (game_id),
        FOREIGN KEY (odds_id) REFERENCES odds (odds_id)
    );
""")

# 4. Odds Details Table (Over/Under/Total)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS odds_details (
        odds_detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
        odds_id INTEGER,
        type TEXT,
        value REAL,
        display_value TEXT,
        alternate_display_value TEXT,
        decimal REAL,
        fraction TEXT,
        american TEXT,
        outcome_type TEXT,
        FOREIGN KEY (odds_id) REFERENCES odds (odds_id)
    );
""")

# 5. Odds Links Table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS odds_links (
        link_id INTEGER PRIMARY KEY AUTOINCREMENT,
        odds_id INTEGER,
        rel TEXT,
        href TEXT,
        text TEXT,
        short_text TEXT,
        is_external BOOLEAN,
        is_premium BOOLEAN,
        FOREIGN KEY (odds_id) REFERENCES odds (odds_id)
    );
""")

conn.commit()
conn.close()
