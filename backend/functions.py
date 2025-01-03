from flask import Flask, render_template, request
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
import requests
import json
import backend.config as config
import asyncio
import aiohttp

def get_database():
    return sqlite3.connect(config.DATABASE)


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

        cursor.execute("SELECT * FROM team_odds WHERE game_id = ?", (game_id,))
        stored_team_odds = cursor.fetchall()

        conn.commit()
        conn.close()
    else:
        print("Failed to fetch odds from API.")

def fetch_and_store_live_data():
    response = requests.get(config.API_URL_ESPN)
    if response.status_code == 200:
        espn_data = response.json()
        events = espn_data.get('events', [])
        leagues = espn_data.get('leagues', [])
        
        conn = get_database()
        cursor = conn.cursor()

        for league in leagues :
            league_id = league['id']
            league_year = league['season']['year']
            start_date = league['season']['startDate']
            end_date = league['season']['endDate']
            league_type = league['season']['type']['type']
            league_name = league['season']['type']['name']

            cursor.execute("""
                INSERT OR REPLACE INTO leagueInfo (id, year, startdate, enddate, type, name)
                           VALUES(?,?,?,?,?,?)
            """, (league_id, league_year, start_date, end_date, league_type, league_name))
        
        for event in events:
            game_id = event['id']
            year = event['season']['year']
            season_id = event['season']['type']
            name = event['name']
            date = event['date']
            date = date.replace('Z', '+0000')
            date = datetime.strptime(date, '%Y-%m-%dT%H:%M%z').astimezone(ZoneInfo('America/New_York')).strftime('%m/%d/%Y @ %I:%M %p')
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
                INSERT OR REPLACE INTO games (game_id, name, date, week, venue_id, status, clock, period, down, detailed_text, year, season_id)
                VALUES (?, ?, ?, ?, ?, ?, ?,?,?,?,?,?)
            ''', (game_id, name, date, week, venue_id, status, clock, period, down, detailed_text, year, season_id))

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

def fetch_and_store_data_for_depthChart(url, team_id):
    response = requests.get(url)
    if response.status_code == 200:
        espn_data = response.json()
        items = espn_data.get('items', [])
        data_to_insert = []

        with get_database() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM depthChart WHERE team_id = ?", (team_id,))
            
            for item in items:
                position_category = item['name']
                positions = item.get('positions', {})

                for value in positions.values():
                    abbreviation = value['position']['abbreviation']
                    athletes_info = value.get('athletes', [])

                    for athlete in athletes_info:
                        slot = athlete['slot']
                        rank = athlete['rank']
                        athlete_url = athlete.get('athlete', {}).get('$ref', None)
                        athlete_url = athlete_url.rstrip('/') if athlete_url else None
                        
                        data_to_insert.append((team_id, position_category, abbreviation, slot, rank, athlete_url))

            cursor.executemany("""
                INSERT INTO depthChart (team_id, position_category, position_abbreviation, slot, rank, athlete_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, data_to_insert)
            conn.commit()


async def fetch_player_data(session, url):
    async with session.get(url) as response:
        return await response.json(), url


async def fetch_and_store_player_data_async(urls, team_id):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_player_data(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

        with get_database() as conn:
            cursor = conn.cursor()
            for espn_data, url in results:
                if espn_data:
                    player_full_name = espn_data['fullName']
                    shortName = espn_data.get('shortName', player_full_name)
                    weight = espn_data.get('displayWeight', 'N/A')
                    height = espn_data.get('displayHeight', 'N/A')
                    age = espn_data.get('age', None)
                    dob = espn_data.get('dateOfBirth', None)

                    if dob:
                        dob = dob.replace('Z', '+0000')
                        try:
                            dob = datetime.strptime(dob, '%Y-%m-%dT%H:%M%z')
                        except ValueError:
                            dob = None 
                    else:
                        dob = None

                    slug = espn_data.get('slug', 'N/A')
                    headshot = espn_data.get('headshot', {}).get('href', None)
                    jersey = espn_data.get('jersey', "N/A")
                    position = espn_data.get('position', {})
                    position_name = position.get('displayName', 'N/A')
                    position_abv = position.get('abbreviation', 'N/A')
                    statistics_url = espn_data.get('statistics', {}).get('$ref', None)
                    projections_url = espn_data.get('projections', {}).get('$ref', None)
                    player_status = espn_data.get('status', {}).get('type', {})
                    athlete_url = url
                    athlete_id = espn_data.get('id', 'N/A')

                    cursor.execute("""
                        INSERT OR REPLACE INTO athletes (
                            team_id, player_name, shortName, weight, height, age, dob, slug, headshot, jersey,
                            position_name, position_abv, athlete_url, statistics_url, projections_url, player_status, athlete_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (team_id, player_full_name, shortName, weight, height, age, dob, slug, headshot, jersey,
                          position_name, position_abv, athlete_url, statistics_url, projections_url, player_status, athlete_id))
            conn.commit()

def fetch_and_store_athlete(url):
    response = requests.get(url)
    if response.status_code == 200:
        espn_data = response.json()

        split_labels = espn_data.get('labels', [])
        split_categories = espn_data.get('splitCategories', [])

        player_splits = {}

        for category in split_categories:
            category_name = category.get('displayName')
            for split in category.get('splits', []):
                stat = split.get('abbreviation')
                stats = split.get('stats', [])

                if category_name not in player_splits:
                    player_splits[category_name] = {}

                if stat not in player_splits[category_name]:
                    player_splits[category_name][stat] = {}

                stat_type = "Rec" if split_labels[0].startswith("CAR") else "Rush"

                seen_labels = {}
                for idx, (label, value) in enumerate(zip(split_labels, stats)):
                    if label in seen_labels:
                        seen_labels[label] += 1
                        unique_label = f"{stat_type} {label}"
                    else:
                        seen_labels[label] = 1
                        unique_label = label
                    
                    player_splits[category_name][stat][unique_label] = value

        return player_splits

    return {}

def fetch_and_store_athlete_projections(url):
    response = requests.get(url)
    if response.status_code == 200:
        espn_data = response.json()
        splits = espn_data.get('splits', {})
        categories = splits.get('categories', [])

        projection_splits = {}

        for category in categories:
            displayName = category.get('displayName')
            abbreviation = category.get('abbreviation')
            stat_projections = category.get('stats', [])
            
            if displayName not in projection_splits:
                projection_splits[displayName] = {}

            for stats in stat_projections:
                projection_name = stats.get('displayName')
                short_name = stats.get('shortDisplayName')
                projection_abv = stats.get('abbreviation')
                projection_desc = stats.get('description')
                value = stats.get('value')
                rank_display = stats.get('rankDisplayValue')

                if rank_display is None or rank_display == '':
                    continue

                if value is None or value == 0.0:
                    continue

                if short_name not in projection_splits[displayName]:
                    projection_splits[displayName][short_name] = {}

                    projection_splits[displayName][short_name][projection_desc] = {
                        projection_abv: {
                            "value": value,
                            "rank_display": rank_display
                        }
                    }
        return projection_splits
    return {}



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
            
            if team1_score == 0 and team2_score == 0:
                team1_outcome = 'Pending'
                team2_outcome = 'Pending'
            else:
                team1_outcome = 'W' if team1_score > team2_score else 'L'
                team2_outcome = 'W' if team2_score > team1_score else 'L'

            cursor.execute('''
                INSERT OR REPLACE INTO games (
                    game_id, name, date, week, status
                ) VALUES (?, ?, ?, ?, ?)
            ''', (game_id, name, date, week, "Scheduled"))

            cursor.execute('''
                INSERT OR REPLACE INTO teams (
                    team_id, game_id, team_name, score, abbreviation, logo
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (team1_id, game_id, team1_name, team1_score, team1['team']['abbreviation'], team1_logo))

            cursor.execute('''
                INSERT OR REPLACE INTO teams (
                    team_id, game_id, team_name, score, abbreviation, logo
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (team2_id, game_id, team2_name, team2_score, team2['team']['abbreviation'], team2_logo))

            cursor.execute('''
                INSERT OR REPLACE INTO competition_results (
                    game_id, week, competition_date, team_id, team_name, team_logo,
                    opponent_id, opponent_name, opponent_logo, team_score, opponent_score, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (game_id, week, date, team1_id, team1_name, team1_logo,
                  team2_id, team2_name, team2_logo, team1_score, team2_score, team1_outcome))

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
        
        total_record = next((item for item in items if item['type'] == 'total'), None)
        if total_record:
            summary = total_record.get('summary')
            stats = {stat['name']: stat['value'] for stat in total_record.get('stats', [])}
            
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

        boxscore = espn_data.get('gamepackageJSON', {})
        boxscore = boxscore.get('boxscore', [])
        teams = boxscore.get('teams', [])
        players = boxscore.get('players', [])
        game_data = espn_data.get('gamepackageJSON', {}).get('game', {})
        boxscore_id = game_data.get('id', None)

        if boxscore_id is None:
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(url)
            boxscore_id = parse_qs(parsed_url.query).get('gameId', [None])[0]

        conn = get_database()
        cursor = conn.cursor()

        for team in teams:
            team_id = team['team']['id']

            for player_group in players:
                if player_group['team']['id'] == team_id:
                    for category in player_group['statistics']:
                        category_name = category['name']
                        keys = category['labels']

                        for athlete in category['athletes']:
                            player = athlete['athlete']
                            player_name = player['displayName']
                            player_id = player['id']
                            stats = athlete['stats']
                            jersey = player.get('jersey', "")

                            cursor.execute("""
                                INSERT OR IGNORE INTO players (player_id, full_name, first_name, last_name, jersey, team_id)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (player_id, player_name, player['firstName'], player['lastName'], jersey, team_id))

                            for key, value in zip(keys, stats):
                                cursor.execute("""
                                    INSERT INTO player_stats (player_id, game_id, team_id, category, stat_key, stat_value, jersey)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    ON CONFLICT(stat_id) DO UPDATE SET stat_value = excluded.stat_value
                                """, (player_id, boxscore_id, team_id, category_name, key, value, jersey))

        conn.commit()
        conn.close()

        #test