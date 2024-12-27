from flask import Flask, render_template, request
import backend.functions as functions
import requests

app = Flask(__name__, template_folder = 'frontend/templates')

@app.route('/', methods=['GET','POST'])
def home():
    
    functions.fetch_and_store_live_data()

    conn = functions.get_database()
    cursor = conn.cursor()

    cursor.execute('SELECT game_id, name, status, clock, period, week, down, detailed_text, date FROM games')
    games = cursor.fetchall()

    filtered_games = [game for game in games if all(game)]

    cursor.execute('SELECT game_id, team_id, team_name, score, abbreviation, logo FROM teams')
    teams = cursor.fetchall()
    
    teams_by_game = {}
    for team in teams:
        game_id = team[0]
        if game_id not in teams_by_game:
            teams_by_game[game_id] = []
        teams_by_game[game_id].append(team)

    combined_games = []
    for game in filtered_games:
        game_id, name, status, clock, period, week, down, detailed_text, date = game
        if game_id in teams_by_game and len(teams_by_game[game_id]) == 2:
            team1, team2 = teams_by_game[game_id]
            combined_games.append(
                (game_id, name, status, clock, team1[1], team1[2], team1[3], team1[4], team1[5], team2[1], team2[2], team2[3], team2[4], team2[5], period, week, down, detailed_text, date)
            )

    conn.close()


    return render_template(
        'home.html',
        games=combined_games,
        teams=teams,
    )

@app.route('/game/<game_id>', methods=['GET', 'POST'])
def display_game_info(game_id):
    print(f"Received game_id: {game_id}")

    team_id = request.args.get('team_id')  # Get team filter from query param
    print(f"Filtering by team_id: {team_id}")

    boxscore_url = f'https://cdn.espn.com/core/nfl/boxscore?xhr=1&gameId={game_id}'

    functions.fetch_and_store_live_data()
    functions.fetch_and_store_boxscore(boxscore_url)
    
    if not game_id:
        return "Game not found", 404

    conn = functions.get_database()
    cursor = conn.cursor()

    cursor.execute('SELECT game_id, name, status, clock, down, detailed_text FROM games WHERE game_id = ?', (game_id,))
    game = cursor.fetchone()

    if not game:
        print("Game not found in DB.")
        return "Game not found", 404

    cursor.execute('SELECT team_name, score, abbreviation, logo, team_id FROM teams WHERE game_id = ?', (game_id,))
    teams = cursor.fetchall()

    if not team_id and teams:
        team_id = teams[0][4]
        print(f"Defaulting to first team_id: {team_id}")

    cursor.execute('''
        SELECT p.full_name, ps.category, ps.stat_key, ps.stat_value, t.team_name
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        JOIN teams t ON ps.team_id = t.team_id
        WHERE ps.game_id = ? AND t.team_id = ?
        ORDER BY t.team_name, ps.category, p.full_name
    ''', (game_id, team_id))

    player_stats = cursor.fetchall()

    stats_by_team = {}
    for player, category, stat_key, stat_value, team in player_stats:
        if team not in stats_by_team:
            stats_by_team[team] = {}
        if category not in stats_by_team[team]:
            stats_by_team[team][category] = {}
        if player not in stats_by_team[team][category]:
            stats_by_team[team][category][player] = {}
        stats_by_team[team][category][player][stat_key] = stat_value

    conn.close()

    return render_template(
        'game.html',
        game=game,
        teams=teams,
        stats_by_team=stats_by_team,
        selected_team_id=team_id
    )



@app.route('/game/teams/<team_id>')
def display_team_info(team_id):

    schedule_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/schedule"
    record_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2024/types/2/teams/{team_id}/record"
    functions.fetch_and_store_competition_results(schedule_url)
    functions.fetch_and_store_team_records(record_url, team_id)

    conn = functions.get_database()
    cursor = conn.cursor()

    cursor.execute('SELECT team_id, team_name, abbreviation, logo FROM teams WHERE team_id = ?', (team_id,))
    teams = cursor.fetchone()

    print(teams)

    cursor.execute('SELECT * FROM records WHERE team_id = ?',(team_id,))
    record = cursor.fetchall()

    cursor.execute('SELECT logo FROM teams WHERE team_id = ?', (team_id,))
    logo = cursor.fetchone()

    print(logo)

    cursor.execute('''
        SELECT 
            g.name, g.week, g.date, g.status,
            t1.abbreviation AS team1_abbr, t1.score AS team1_score, 
            t2.abbreviation AS team2_abbr, t2.score AS team2_score,
            COALESCE(r1.outcome, 'Unknown') AS team1_outcome, t1.logo AS team1_logo, t2.logo AS team2_logo,
            t1.team_id AS team1_id, t2.team_id AS team2_id
        FROM games g
        LEFT JOIN teams t1 ON g.game_id = t1.game_id
        LEFT JOIN competition_results r1 ON r1.team_id = t1.team_id AND r1.game_id = g.game_id
        LEFT JOIN teams t2 ON g.game_id = t2.game_id AND t1.team_id != t2.team_id
        WHERE t1.team_id = ?
        GROUP BY g.game_id
        ORDER BY g.date ASC
    ''', (team_id,))
    schedule = cursor.fetchall()

    conn.close()

    if not teams:
        return "Team not found", 404

    return render_template(
        'team_info.html',
        teams=teams,
        schedule = schedule,
        record=record,
        logo = logo
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=60000)