import os
import subprocess
import signal
import sys
import json
import secrets
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
import psutil
from functools import wraps
from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    Response,
    session,
    redirect,
    url_for,
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))

# Configuration
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
# Security: Require environment variables for credentials.
# If not set, generate a random password and print it to the console.
USERNAME = os.getenv("WEB_USER", "admin")
PASSWORD = os.getenv("WEB_PASS")

if not PASSWORD:
    generated_pass = secrets.token_urlsafe(12)
    print("=" * 60)
    print(f"WARNING: WEB_PASS environment variable not set.")
    print(f"Generated temporary password for user '{USERNAME}': {generated_pass}")
    print("=" * 60)
    PASSWORD = generated_pass

# Path to the main script (assuming web folder is inside the project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "daly_bms_bt.py")
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "daly_bms.log")


def find_bms_process():
    """Find the running BMS process using psutil."""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            # Check if cmdline exists and contains our script name
            if proc.info["cmdline"]:
                # Look for daly_bms_bt.py in the arguments
                for arg in proc.info["cmdline"]:
                    if "daly_bms_bt.py" in arg:
                        return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None


# Database Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "power_monitor"),
    "user": os.getenv("DB_USER", "master"),
    "password": os.getenv("DB_PASSWORD", "password"),
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"mac_address": "C6:6C:09:03:0A:13"}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if (
            request.form["username"] == USERNAME
            and request.form["password"] == PASSWORD
        ):
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            error = "Invalid Credentials. Please try again."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    config = load_config()
    return render_template("index.html", mac_address=config.get("mac_address", ""))


@app.route("/status")
@login_required
def status():
    proc = find_bms_process()
    is_running = proc is not None and proc.is_running()
    return jsonify({"running": is_running})


@app.route("/start", methods=["POST"])
@login_required
def start():
    if find_bms_process():
        return jsonify({"success": False, "message": "Already running"})

    data = request.get_json()
    mac_address = data.get("mac_address", "C6:6C:09:03:0A:13")
    enable_history = data.get("enable_history", True)

    # Save config
    save_config({"mac_address": mac_address})

    # Command to run the script
    # Using sys.executable to ensure we use the same python interpreter
    cmd = [sys.executable, SCRIPT_PATH, "--bt", mac_address, "--loop", "5", "--keep"]

    if not enable_history:
        cmd.append("--no-db")

    try:
        # Start the process
        subprocess.Popen(cmd, cwd=PROJECT_ROOT)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/stop", methods=["POST"])
@login_required
def stop():
    proc = find_bms_process()
    if proc:
        try:
            # Send SIGTERM to the process
            proc.terminate()
            # Wait a bit for it to close gracefully
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()  # Force kill if it doesn't stop

            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    return jsonify({"success": True, "message": "Not running"})


@app.route("/logs")
@login_required
def get_logs():
    # Read the last N lines of the log file
    if os.path.exists(LOG_FILE):
        try:
            # Simple implementation: read whole file and take last 100 lines
            # For very large logs, seek() would be better
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                return "".join(lines[-50:])  # Return last 50 lines
        except Exception as e:
            return f"Error reading logs: {e}"
    return "No logs found yet."


@app.route("/api/history")
@login_required
def history():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Get last 100 records
        cur.execute(
            "SELECT create_date, total_voltage, current, soc_percent FROM bms_data ORDER BY create_date DESC LIMIT 100"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Convert datetime objects to string and reverse list to have oldest first (for chart)
        formatted_rows = []
        for row in rows:
            if isinstance(row["create_date"], datetime.datetime):
                row["create_date"] = row["create_date"].strftime("%Y-%m-%d %H:%M:%S")
            formatted_rows.append(row)

        return jsonify(formatted_rows[::-1])  # Reverse so chart draws left-to-right
    except Exception as e:
        # If DB is not reachable, return empty list or error
        print(f"DB Error: {e}")
        return jsonify([])


if __name__ == "__main__":
    # Host 0.0.0.0 allows access from other devices on the network
    app.run(host="0.0.0.0", port=5000, debug=True)
