from flask import Flask, render_template, request
import sqlite3
import requests
import json
import backend.config as config

def get_database():
    return sqlite3.connect(config.DATABASE)

def fetch_and_store_data_for_week():
    response = requests.get(config.API_URL_WEEK)
    if response.status_code == 200:
        week_data = response.json()
        conn = get_database()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO nflWeek (
                    week,
                    season_type,
                    season_start_date,
                    season,
                    display_week 
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            week_data.get('week'),
            week_data.get('season_type'),
            week_data.get('season_start_date'),
            week_data.get('season'),
            week_data.get('display_week')
        ))


        conn.commit()
        conn.close()

def fetch_and_store_odds(url):
    response = requests.get(url)
    
    if response.status_code == 200:
        odds_data = response.json()

        if 'items' not in odds_data or not odds_data['items']:
            print("No odds data found in API response.")
            return
        
        conn = get_database()
        cursor = conn.cursor()

        for item in odds_data['items']:
            game_id = item['$ref'].split('/')[-3]
            provider_id = item['provider']['id']
            provider_name = item['provider']['name']
            details = item.get('details', 'N/A')
            over_under = item.get('overUnder', None)
            spread = item.get('spread', None)
            over_odds = item.get('overOdds', None)
            under_odds = item.get('underOdds', None)
            moneyline_winner = item.get('moneylineWinner', False)
            spread_winner = item.get('spreadWinner', False)

            cursor.execute('''
                INSERT OR IGNORE INTO odds_provider (provider_id, name, priority)
                VALUES (?, ?, ?)
            ''', (provider_id, provider_name, 1))

            cursor.execute('''
                INSERT OR REPLACE INTO odds (
                    game_id,
                    provider_id,
                    details,
                    over_under,
                    spread,
                    over_odds,
                    under_odds,
                    moneyline_winner,
                    spread_winner
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                game_id,
                provider_id,
                details,
                over_under,
                spread,
                over_odds,
                under_odds,
                moneyline_winner,
                spread_winner
            ))

            odds_id = cursor.lastrowid

            home_team = item['homeTeamOdds']
            away_team = item['awayTeamOdds']

            for team_odds in [home_team, away_team]:
                team_id = team_odds['team']['$ref'].split('/')[-1]
                favorite = team_odds.get('favorite', False)
                underdog = team_odds.get('underdog', False)
                moneyline = team_odds.get('moneyLine', None)
                spread_odds = team_odds.get('spreadOdds', None)
                point_spread = (
                    team_odds.get('current', {})
                    .get('pointSpread', {})
                    .get('alternateDisplayValue', None)
                )
                
                cursor.execute('SELECT team_id FROM teams WHERE team_id = ?', (team_id,))
                matching_team = cursor.fetchone()

                if not matching_team:
                    abbreviation = team_odds['team'].get('abbreviation', None)
                    cursor.execute('SELECT team_id FROM teams WHERE abbreviation = ?', (abbreviation,))
                    matching_team = cursor.fetchone()

                    if matching_team:
                        team_id = matching_team[0]
                    else:
                        print(f"No match for team {team_id} or {abbreviation} in teams table.")

                cursor.execute('''
                    INSERT OR REPLACE INTO team_odds (
                        odds_id,
                        team_id,
                        game_id,
                        favorite,
                        underdog,
                        moneyline,
                        spread_odds,
                        point_spread
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    odds_id,
                    team_id,
                    game_id,
                    favorite,
                    underdog,
                    moneyline,
                    spread_odds,
                    point_spread
                ))

        conn.commit()

        cursor.execute("SELECT * FROM team_odds WHERE game_id = ?", (game_id,))
        stored_team_odds = cursor.fetchall()

        conn.close()
    else:
        print("Failed to fetch odds from API.")

def fetch_and_store_live_data():
    response = requests.get(config.API_URL_ESPN)
    if response.status_code == 200:
        espn_data = response.json()
        events = espn_data.get('events', [])
        
        conn = get_database()
        cursor = conn.cursor()
        
        for event in events:
            game_id = event['id']
            name = event['name']
            date = event['date']
            week = event['week']['number']
            down = event['competitions'][0].get('situation', {}).get('downDistanceText', 'No play')
            detailed_text = event['competitions'][0].get('situation', {}).get('lastPlay', {}).get('text', 'No play description available')
            status = event['status']['type']['description']
            clock = event['status']['displayClock']
            period = event['status']['period']
            venue = event['competitions'][0]['venue']
            venue_id = venue['id']
            venue_name = venue['fullName']
            city = venue['address']['city']
            state = venue['address']['state']
            indoor = venue['indoor']

            cursor.execute('''
                INSERT OR REPLACE INTO games (game_id, name, date, week, venue_id, status, clock, period, down, detailed_text)
                VALUES (?, ?, ?, ?, ?, ?, ?,?,?,?)
            ''', (game_id, name, date, week, venue_id, status, clock, period, down, detailed_text))

            cursor.execute('''
                INSERT OR REPLACE INTO venues (venue_id, full_name, city, state, indoor)
                VALUES (?, ?, ?, ?, ?)
            ''', (venue_id, venue_name, city, state, indoor))

            for competition in event['competitions']:
                for team in competition['competitors']:
                    team_id = team['team']['id']
                    team_name = team['team']['displayName']
                    score = int(team['score']) if 'score' in team else 0
                    home_away = team['homeAway']
                    abbreviation = team['team']['abbreviation']
                    logo = team['team']['logo']

                    cursor.execute('''
                        INSERT OR REPLACE INTO teams (team_id, game_id, team_name, score, home_away, abbreviation, logo)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (team_id, game_id, team_name, score, home_away, abbreviation, logo))

        
        conn.commit()
        conn.close()

def fetch_and_store_data_for_depthChart():
    response = requests.get(config.API_URL_PLAYERS)
    if response.status_code == 200:
        player_data = response.json()

def fetch_and_store_competition_results(url):
    response = requests.get(url)
    if response.status_code == 200:
        espn_data = response.json()
        events = espn_data.get('events', [])
        
        conn = get_database()
        cursor = conn.cursor()
        
        for event in events:
            game_id = event['id']
            date = event['date']
            week = event['week']['number']
            name = event['name']
            competitors = event['competitions'][0]['competitors']

            team1 = competitors[0]
            team2 = competitors[1]
            
            team1_id = team1['team']['id']
            team2_id = team2['team']['id']
            team1_name = team1['team']['displayName']
            team2_name = team2['team']['displayName']
            team1_logo = team1['team']['logos'][0]['href']
            team2_logo = team2['team']['logos'][0]['href']
            
            team1_score = int(team1['score']['value']) if 'score' in team1 and 'value' in team1['score'] else 0
            team2_score = int(team2['score']['value']) if 'score' in team2 and 'value' in team2['score'] else 0
            
            # Infer outcome by comparing scores
            if team1_score == 0 and team2_score == 0:
                team1_outcome = 'Pending'
                team2_outcome = 'Pending'
            else:
                team1_outcome = 'W' if team1_score > team2_score else 'L'
                team2_outcome = 'W' if team2_score > team1_score else 'L'

            # Insert into games table
            cursor.execute('''
                INSERT OR REPLACE INTO games (
                    game_id, name, date, week, status
                ) VALUES (?, ?, ?, ?, ?)
            ''', (game_id, name, date, week, "Scheduled"))

            # Insert for team 1
            cursor.execute('''
                INSERT OR REPLACE INTO teams (
                    team_id, game_id, team_name, score, abbreviation, logo
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (team1_id, game_id, team1_name, team1_score, team1['team']['abbreviation'], team1_logo))

            # Insert for team 2
            cursor.execute('''
                INSERT OR REPLACE INTO teams (
                    team_id, game_id, team_name, score, abbreviation, logo
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (team2_id, game_id, team2_name, team2_score, team2['team']['abbreviation'], team2_logo))

            # Insert into competition_results (Team 1 perspective)
            cursor.execute('''
                INSERT OR REPLACE INTO competition_results (
                    game_id, week, competition_date, team_id, team_name, team_logo,
                    opponent_id, opponent_name, opponent_logo, team_score, opponent_score, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (game_id, week, date, team1_id, team1_name, team1_logo,
                  team2_id, team2_name, team2_logo, team1_score, team2_score, team1_outcome))

            # Insert into competition_results (Team 2 perspective)
            cursor.execute('''
                INSERT OR REPLACE INTO competition_results (
                    game_id, week, competition_date, team_id, team_name, team_logo,
                    opponent_id, opponent_name, opponent_logo, team_score, opponent_score, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (game_id, week, date, team2_id, team2_name, team2_logo,
                  team1_id, team1_name, team1_logo, team2_score, team1_score, team2_outcome))

        conn.commit()
        conn.close()

def fetch_and_store_team_records(url, team_id):
    response = requests.get(url)
    if response.status_code == 200:
        espn_data = response.json()
        items = espn_data.get('items', [])
        
        # Find the "total" record
        total_record = next((item for item in items if item['type'] == 'total'), None)
        if total_record:
            summary = total_record.get('summary')
            stats = {stat['name']: stat['value'] for stat in total_record.get('stats', [])}
            
            # Extract required stats
            overall_record = summary
            win_percentage = stats.get('winPercent')
            avg_points_for = stats.get('avgPointsFor')
            avg_points_against = stats.get('avgPointsAgainst')
            points_for = stats.get('pointsFor')
            points_against = stats.get('pointsAgainst')
            point_differential = stats.get('pointDifferential')
            division_record = stats.get('divisionRecord')
            division_win_percentage = stats.get('divisionWinPercent')
            games_played = stats.get('gamesPlayed')
            playoff_seed = stats.get('playoffSeed')
            streak = stats.get('streak')
            

            # Store data in the database
            conn = get_database()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO records (
                    team_id, record, win_percentage,avg_points_for, avg_points_against, points_for, points_against,
                    point_differential, division_record, division_win_percentage,
                    games_played, playoff_seed, streak
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                team_id, overall_record, win_percentage, avg_points_for, avg_points_against, points_for, points_against,
                point_differential, division_record, division_win_percentage,games_played, playoff_seed, streak
            ))
            conn.commit()
            conn.close()
            print(f"Data for team {team_id} stored successfully.")

def fetch_and_store_boxscore(url):
    response = requests.get(url)
    
    if response.status_code == 200:
        espn_data = response.json()
        boxscore = espn_data.get('boxscore', {})
        teams = boxscore.get('teams', [])
        players = boxscore.get('players', [])

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        for team in teams:
            team_id = team['team']['id']
            team_name = team['team']['displayName']
            abbreviation = team['team']['abbreviation']
            home_away = team['homeAway']

            cursor.execute(
                """
                INSERT OR REPLACE INTO teams (team_id, team_name, abbreviation, home_away)
                VALUES (?, ?, ?, ?)
                """,
                (team_id, team_name, abbreviation, home_away)
            )

            # Extract team statistics
            for stat in team['statistics']:
                stat_name = stat['name']
                stat_value = stat['displayValue']
                cursor.execute(
                    """
                    INSERT INTO records (team_id, record, win_percentage)
                    VALUES (?, ?, ?)
                    ON CONFLICT(team_id) DO UPDATE SET record=excluded.record, win_percentage=excluded.win_percentage
                    """,
                    (team_id, stat_name, stat_value)
                )

        for player_group in players:
            team_id = player_group['team']['id']
            for category in player_group['statistics']:
                for athlete in category['athletes']:
                    player_id = athlete['athlete']['id']
                    full_name = athlete['athlete']['displayName']
                    position = category['name']
                    jersey = athlete['athlete'].get('jersey', "")
                    
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO players (player_id, full_name, position, team_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        (player_id, full_name, position, team_id)
                    )

                    for i, key in enumerate(category['keys']):
                        stat_value = athlete['stats'][i]
                        cursor.execute(
                            """
                            INSERT INTO player_stats (player_id, stat_category, stat_value)
                            VALUES (?, ?, ?)
                            """,
                            (player_id, key, stat_value)
                        )

                        # Insert into boxscore_data table
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO boxscore_data (team_id, team_name, abbreviation, home_away, player_id, full_name, position, stat_category, stat_value)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (team_id, team_name, abbreviation, home_away, player_id, full_name, position, key, stat_value)
                        )
        
        conn.commit()
        conn.close()