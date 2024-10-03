import sys
import subprocess
import sqlite3
from datetime import datetime
import threading
import time

# Function to install packages if they are missing
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Ensure necessary packages are installed
try:
    import speedtest
except ImportError:
    install('speedtest-cli')
    import speedtest

try:
    from flask import Flask, jsonify, render_template
except ImportError:
    install('flask')
    from flask import Flask, jsonify, render_template

# Initialize Flask application
app = Flask(__name__)

# Database file (relative path or ensure absolute path)
DB_FILE = 'speedtest_results.db'

# Function to perform the speed test and update the SQLite database
def run_speedtest():
    try:
        # Create a Speedtest object and find the best server
        st = speedtest.Speedtest()
        server = st.get_best_server()
        server_name = server['sponsor']
        server_location = f"{server['name']}, {server['country']}"

        # Perform the speed test
        download_speed = st.download() / 1_000_000  # Convert from bits to Mbps
        upload_speed = st.upload() / 1_000_000  # Convert from bits to Mbps
        ping = st.results.ping

        # Get the current time for the record
        timestamp = datetime.now()

        # Insert results into the SQLite database
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    download REAL,
                    upload REAL,
                    ping REAL,
                    server_name TEXT,
                    server_location TEXT
                )
            ''')
            cursor.execute('''
                INSERT INTO results (timestamp, download, upload, ping, server_name, server_location)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, download_speed, upload_speed, ping, server_name, server_location))
            conn.commit()

        return {
            "timestamp": timestamp,
            "download": download_speed,
            "upload": upload_speed,
            "ping": ping,
            "server_name": server_name,
            "server_location": server_location
        }
    except Exception as e:
        # Log the exception for debugging
        print(f"Error running speed test: {e}")
        return {"error": str(e)}

# Background service to run speed tests periodically
def background_speedtest_service():
    while True:
        start_time = time.time()
        run_speedtest()
        time_elapsed = time.time() - start_time
        sleep_time = max(0, 60 - time_elapsed)  # Ensure 60 seconds between test runs
        time.sleep(sleep_time)

# Flask route to fetch the latest speed test result
@app.route('/speedtest/latest', methods=['GET'])
def get_latest_speedtest():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, download, upload, ping, server_name, server_location
            FROM results
            ORDER BY id DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            return jsonify({
                "timestamp": row[0],
                "download": row[1],
                "upload": row[2],
                "ping": row[3],
                "server_name": row[4],
                "server_location": row[5]
            })
        else:
            return jsonify({"error": "No results found"}), 404

# Flask route to get all speed test results
@app.route('/speedtest/all', methods=['GET'])
def get_all_speedtests():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, download, upload, ping, server_name, server_location
            FROM results
            ORDER BY id DESC
        ''')
        rows = cursor.fetchall()
        results = [{
            "timestamp": row[0],
            "download": row[1],
            "upload": row[2],
            "ping": row[3],
            "server_name": row[4],
            "server_location": row[5]
        } for row in rows]
        return jsonify(results)

# Flask route to trigger a new speed test
@app.route('/speedtest/run', methods=['GET'])
def run_new_speedtest():
    result = run_speedtest()
    if "error" in result:
        return jsonify(result), 500
    else:
        return jsonify(result)

# Flask route to display speed test data on a webpage (table view)
@app.route('/')
def show_speedtest_results():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, download, upload, ping, server_name, server_location
            FROM results
            ORDER BY id DESC
        ''')
        rows = cursor.fetchall()
        results = [{
            "timestamp": row[0],
            "download": row[1],
            "upload": row[2],
            "ping": row[3],
            "server_name": row[4],
            "server_location": row[5]
        } for row in rows]
    return render_template('main.html', results=results)

# Function to run the speedtest in a background thread
def start_background_service():
    thread = threading.Thread(target=background_speedtest_service, daemon=True)
    thread.start()

# Start the Flask app and background service
if __name__ == "__main__":
    # Start the background speed test service
    start_background_service()

    # Run the Flask app
    app.run(host='127.0.0.1', port=5000)
