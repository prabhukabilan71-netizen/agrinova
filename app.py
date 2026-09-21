import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    render_template,
    flash
)

from werkzeug.security import generate_password_hash, check_password_hash

try:
    from google import genai
except ImportError:
    genai = None


# =========================================================
# AGRI NOVA
# =========================================================

app = Flask(
    __name__,
    template_folder="."
)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "agrinova-development-secret-change-this"
)


# =========================================================
# SETTINGS
# =========================================================

DATABASE = os.environ.get(
    "DATABASE_PATH",
    "agrinova.db"
)

ESP_TOKEN = os.environ.get(
    "ESP_TOKEN",
    "CHANGE_THIS_ESP_TOKEN"
)

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
)

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():

    folder = os.path.dirname(
        os.path.abspath(DATABASE)
    )

    if folder:
        os.makedirs(folder, exist_ok=True)

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            location TEXT,
            state TEXT,
            farm_size REAL,
            crop TEXT,
            profile_done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            lux REAL,
            temperature REAL,
            moisture REAL,
            ph REAL,
            acidity REAL,
            alkalinity REAL,
            updated_at TEXT
        )
    """)

    existing = db.execute(
        "SELECT id FROM sensor_data WHERE id = 1"
    ).fetchone()

    if existing is None:

        db.execute("""
            INSERT INTO sensor_data
            (
                id,
                lux,
                temperature,
                moisture,
                ph,
                acidity,
                alkalinity,
                updated_at
            )
            VALUES
            (
                1,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL
            )
        """)

    db.commit()
    db.close()


# =========================================================
# FARMER FUNCTIONS
# =========================================================

def get_current_farmer():

    if "farmer_id" not in session:
        return None

    db = get_db()

    farmer = db.execute(
        "SELECT * FROM farmers WHERE id = ?",
        (session["farmer_id"],)
    ).fetchone()

    db.close()

    return farmer


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "farmer_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# =========================================================
# SENSOR DATA
# =========================================================

def get_sensor_data():

    db = get_db()

    data = db.execute(
        "SELECT * FROM sensor_data WHERE id = 1"
    ).fetchone()

    db.close()

    if data is None:

        return {
            "lux": None,
            "temperature": None,
            "moisture": None,
            "ph": None,
            "acidity": None,
            "alkalinity": None,
            "updated_at": None
        }

    return dict(data)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    if "farmer_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            flash(
                "Please enter username and password."
            )

            return redirect(
                url_for("login")
            )

        db = get_db()

        farmer = db.execute(
            """
            SELECT *
            FROM farmers
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        db.close()

        if farmer and check_password_hash(
            farmer["password_hash"],
            password
        ):

            session["farmer_id"] = farmer["id"]
            session["username"] = farmer["username"]

            if farmer["profile_done"]:

                return redirect(
                    url_for("dashboard")
                )

            return redirect(
                url_for("profile")
            )

        flash(
            "Invalid username or password."
        )

    return render_template("login.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            flash(
                "Username and password are required."
            )

            return redirect(
                url_for("register")
            )

        db = get_db()

        existing = db.execute(
            """
            SELECT id
            FROM farmers
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if existing:

            db.close()

            flash(
                "Username already exists."
            )

            return redirect(
                url_for("register")
            )

        password_hash = generate_password_hash(
            password
        )

        cursor = db.execute(
            """
            INSERT INTO farmers
            (
                username,
                password_hash,
                name,
                age,
                location,
                state,
                farm_size,
                crop,
                profile_done,
                created_at
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                "",
                None,
                "",
                "",
                None,
                "",
                0,
                datetime.utcnow().isoformat()
            )
        )

        farmer_id = cursor.lastrowid

        db.commit()
        db.close()

        session["farmer_id"] = farmer_id
        session["username"] = username

        return redirect(
            url_for("profile")
        )

    return render_template("register.html")


# =========================================================
# FARMER PROFILE
# =========================================================

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    farmer = get_current_farmer()

    if farmer is None:

        session.clear()

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        age_text = request.form.get(
            "age",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        state = request.form.get(
            "state",
            ""
        ).strip()

        farm_size_text = request.form.get(
            "farm_size",
            ""
        ).strip()

        crop = request.form.get(
            "crop",
            ""
        ).strip()

        try:

            age = (
                int(age_text)
                if age_text
                else None
            )

        except ValueError:

            age = None

        try:

            farm_size = (
                float(farm_size_text)
                if farm_size_text
                else None
            )

        except ValueError:

            farm_size = None

        if not name:

            flash(
                "Please enter your name."
            )

            return redirect(
                url_for("profile")
            )

        db = get_db()

        db.execute(
            """
            UPDATE farmers

            SET
                name = ?,
                age = ?,
                location = ?,
                state = ?,
                farm_size = ?,
                crop = ?,
                profile_done = 1

            WHERE id = ?
            """,
            (
                name,
                age,
                location,
                state,
                farm_size,
                crop,
                session["farmer_id"]
            )
        )

        db.commit()
        db.close()

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "profile.html",
        farmer=farmer
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    farmer = get_current_farmer()

    if farmer is None:

        session.clear()

        return redirect(
            url_for("login")
        )

    if not farmer["profile_done"]:

        return redirect(
            url_for("profile")
        )

    sensors = get_sensor_data()

    return render_template(
        "dashboard.html",
        farmer=farmer,
        sensors=sensors
    )


# =========================================================
# MY FARM
# =========================================================

@app.route("/myfarm")
@login_required
def myfarm():

    farmer = get_current_farmer()

    sensors = get_sensor_data()

    return render_template(
        "myfarm.html",
        farmer=farmer,
        sensors=sensors
    )


# =========================================================
# SENSOR API
# =========================================================

@app.route("/api/sensors")
def api_sensors():

    sensors = get_sensor_data()

    return jsonify({
        "success": True,
        "sensors": sensors
    })


# =========================================================
# ESP8266 UPDATE
# =========================================================

@app.route(
    "/api/esp/update",
    methods=["POST"]
)
def esp_update():

    supplied_token = request.headers.get(
        "X-ESP-TOKEN",
        ""
    )

    if supplied_token != ESP_TOKEN:

        return jsonify({
            "success": False,
            "error": "Unauthorized ESP8266"
        }), 401

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "success": False,
            "error": "JSON data required"
        }), 400

    def number(name):

        value = data.get(name)

        if value is None or value == "":
            return None

        try:

            return float(value)

        except (
            ValueError,
            TypeError
        ):

            return None

    lux = number("lux")
    temperature = number("temperature")
    moisture = number("moisture")
    ph = number("ph")
    acidity = number("acidity")
    alkalinity = number("alkalinity")

    updated = datetime.utcnow().isoformat()

    db = get_db()

    db.execute(
        """
        UPDATE sensor_data

        SET
            lux = ?,
            temperature = ?,
            moisture = ?,
            ph = ?,
            acidity = ?,
            alkalinity = ?,
            updated_at = ?

        WHERE id = 1
        """,
        (
            lux,
            temperature,
            moisture,
            ph,
            acidity,
            alkalinity,
            updated
        )
    )

    db.commit()
    db.close()

    return jsonify({
        "success": True,
        "message": "ESP8266 sensor data received",
        "updated_at": updated
    })


# =========================================================
# GEMINI AI
# =========================================================

@app.route(
    "/ai",
    methods=["GET", "POST"]
)
@login_required
def ai():

    farmer = get_current_farmer()

    sensors = get_sensor_data()

    answer = None

    question = ""

    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        if not question:

            answer = (
                "Please enter an agriculture question."
            )

        elif not GEMINI_API_KEY:

            answer = (
                "Gemini AI is not configured yet. "
                "Add GEMINI_API_KEY in Render "
                "Environment Variables."
            )

        elif genai is None:

            answer = (
                "The Google Gemini package "
                "is not installed."
            )

        else:

            try:

                client = genai.Client(
                    api_key=GEMINI_API_KEY
                )

                prompt = f"""
You are Agri Nova, an agriculture-focused
AI assistant.

Farmer information:

Name: {farmer["name"]}
Age: {farmer["age"]}
Farm location: {farmer["location"]}
State: {farmer["state"]}
Farm size: {farmer["farm_size"]} acres
Crop: {farmer["crop"]}

Latest ESP8266 readings:

Lux: {sensors["lux"]}
Temperature: {sensors["temperature"]}
Moisture: {sensors["moisture"]}
pH: {sensors["ph"]}
Acidity: {sensors["acidity"]}
Alkalinity: {sensors["alkalinity"]}

Farmer question:

{question}

Give a clear and practical agriculture answer.

Important:

- Do not invent sensor readings.
- If a sensor value is missing,
  say that it is unavailable.
- Treat hobby-grade sensor readings
  as approximate.
- Do not claim a diagnosis from
  sensor data.
- Give safety-conscious farming advice.
"""

                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                )

                answer = response.text

            except Exception as error:

                print(
                    "Gemini error:",
                    error
                )

                answer = (
                    "Gemini could not answer right now. "
                    "Please check the Gemini API "
                    "configuration."
                )

    return render_template(
        "ai.html",
        farmer=farmer,
        sensors=sensors,
        question=question,
        answer=answer
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "application": "Agri Nova",
        "time": datetime.utcnow().isoformat()
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# START DATABASE
# =========================================================

init_database()


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
