import os
import subprocess
import sqlite3
import sys
from backend import functions, config


try:
    import flask
    import flask_caching
    import requests
    import asyncio
    import aiohttp
except ImportError as e:
    package_name = str(e).split("'")[1]
    print(f'Package {package_name} is not installed.')

install = input("Would you like to install all required packages? (y/n): ").strip().lower()
if install == 'y':
    subprocess.run(['pip', 'install', '--upgrade', 'pip'])
    subprocess.run(['pip', 'install', 'flask', 'flask-caching', 'requests', 'asyncio', 'aiohttp'])
else:
    print("Please install the required packages manually and run program again! GoodBye!")
    sys.exit(1)

DB_FILE = config.DATABASE

if not os.path.exists(DB_FILE):
    print("Database file not found. Please ensure db_fantasy.db is in the backend folder.")
else:
    print("Database found. Proceeding with initialization.")

functions.fetch_and_store_live_data()

subprocess.run(['flask', 'run', '--host=0.0.0.0', '--port=60000'])