import os
import secrets
import sqlite3
import hashlib
from datetime import datetime, timezone

from flask import (
    Flask,
    request,
    redirect,
    session,
    jsonify,
    render_template_string
)

from google import genai


# =========================================================
# AGRI NOVA AI
# PUBLIC AGRICULTURE + AI PLATFORM
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    secrets.token_hex(32)
)

DATABASE = os.environ.get(
    "DATABASE_PATH",
    "/var/data/agrinova.db"
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
# GEMINI
# =========================================================

gemini_client = None

if GEMINI_API_KEY:

    try:

        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

    except Exception as error:

        print("Gemini initialization error:", error)


# =========================================================
# DATABASE
# =========================================================

def get_db():

    connection = sqlite3.connect(
        DATABASE,
        timeout=20
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    os.makedirs(
        os.path.dirname(DATABASE),
        exist_ok=True
    )

    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS farmers (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            name TEXT DEFAULT '',

            age INTEGER DEFAULT 0,

            location TEXT DEFAULT '',

            state TEXT DEFAULT '',

            farm_size REAL DEFAULT 0,

            crop TEXT DEFAULT '',

            profile_done INTEGER DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (

            id INTEGER PRIMARY KEY,

            lux REAL,

            temperature REAL,

            moisture REAL,

            ph REAL,

            acidity REAL,

            alkalinity REAL,

            updated_at TEXT

        )
    """)

    connection.commit()

    connection.close()


# =========================================================
# PASSWORD
# =========================================================

def hash_password(password):

    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


# =========================================================
# SENSOR DATABASE
# =========================================================

def save_sensor_data(
    lux,
    temperature,
    moisture,
    ph,
    acidity,
    alkalinity
):

    connection = get_db()

    connection.execute(
        """
        INSERT OR REPLACE INTO sensor_data
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
            1,?,?,?,?,?,?,?
        )
        """,
        (
            lux,
            temperature,
            moisture,
            ph,
            acidity,
            alkalinity,
            datetime.now(
                timezone.utc
            ).isoformat()
        )
    )

    connection.commit()

    connection.close()


def read_sensor_data():

    connection = get_db()

    row = connection.execute(
        """
        SELECT *
        FROM sensor_data
        WHERE id=1
        """
    ).fetchone()

    connection.close()

    if not row:

        return {

            "lux": None,
            "temperature": None,
            "moisture": None,
            "ph": None,
            "acidity": None,
            "alkalinity": None,
            "updated_at": None,
            "online": False

        }

    return {

        "lux": row["lux"],
        "temperature": row["temperature"],
        "moisture": row["moisture"],
        "ph": row["ph"],
        "acidity": row["acidity"],
        "alkalinity": row["alkalinity"],
        "updated_at": row["updated_at"],
        "online": True

    }


# =========================================================
# PH INTERPRETATION
# =========================================================

def ph_information(ph):

    if ph is None:

        return (
            "WAITING",
            "Waiting for a calibrated pH sensor reading."
        )

    try:

        value = float(ph)

    except:

        return (
            "UNAVAILABLE",
            "The received pH value is unavailable."
        )

    if value < 7:

        return (
            "ACIDIC",
            "The measured pH is below 7."
        )

    if value > 7:

        return (
            "ALKALINE",
            "The measured pH is above 7."
        )

    return (
        "NEUTRAL",
        "The measured pH is approximately neutral."
    )


# =========================================================
# HTML STYLE
# =========================================================

STYLE = """

<style>

* {
    box-sizing:border-box;
}

:root {

    --bg:#031008;
    --panel:#091a0f;
    --panel2:#0d2415;
    --border:#214b2d;
    --green:#63ed82;
    --green2:#1cab58;
    --text:#f1fff4;
    --muted:#8ba494;
    --blue:#55bdff;
    --orange:#ffbd58;

}

body {

    margin:0;

    color:var(--text);

    font-family:
    Arial,
    Helvetica,
    sans-serif;

    background:

    radial-gradient(
        circle at 15% 10%,
        rgba(75,220,103,.16),
        transparent 28%
    ),

    radial-gradient(
        circle at 90% 20%,
        rgba(28,160,81,.12),
        transparent 30%
    ),

    linear-gradient(
        135deg,
        #020b06,
        #06180c,
        #020b06
    );

    min-height:100vh;

}

nav {

    height:72px;

    display:flex;

    align-items:center;

    justify-content:space-between;

    padding:0 30px;

    position:sticky;

    top:0;

    z-index:20;

    background:
    rgba(3,15,8,.90);

    backdrop-filter:blur(18px);

    border-bottom:
    1px solid rgba(99,237,130,.13);

}

.logo {

    font-size:21px;

    font-weight:800;

}

.logo span {

    color:var(--green);

}

.navlinks {

    display:flex;

    gap:8px;

}

.navlinks a {

    text-decoration:none;

    color:#9eb3a4;

    padding:10px 14px;

    border-radius:10px;

}

.navlinks a:hover {

    color:white;

    background:#10291a;

}

.container {

    width:min(1200px,94%);

    margin:auto;

}

.page {

    padding:35px 0 70px;

}

.hero {

    border:
    1px solid var(--border);

    border-radius:26px;

    padding:45px;

    background:

    radial-gradient(
        circle at 90% 10%,
        rgba(99,237,130,.18),
        transparent 30%
    ),

    linear-gradient(
        135deg,
        #102d19,
        #06150b
    );

}

.hero h1 {

    font-size:44px;

    margin:15px 0 10px;

}

.hero p {

    color:var(--muted);

    line-height:1.7;

}

.card {

    border:
    1px solid var(--border);

    border-radius:20px;

    padding:25px;

    background:
    rgba(8,27,14,.88);

}

.grid {

    display:grid;

    grid-template-columns:
    repeat(4,1fr);

    gap:16px;

}

.sensor {

    min-height:170px;

}

.sensor-icon {

    font-size:27px;

}

.sensor-name {

    color:var(--muted);

    font-size:12px;

    margin-top:16px;

}

.value {

    font-size:34px;

    font-weight:800;

    margin-top:7px;

    color:var(--green);

}

.unit {

    color:#71897a;

}

.two {

    display:grid;

    grid-template-columns:1fr 1fr;

    gap:18px;

    margin-top:18px;

}

.profile {

    display:grid;

    grid-template-columns:1fr 1fr;

    gap:12px;

}

.info {

    padding:15px;

    border-radius:12px;

    background:#0a1d10;

    border:1px solid #193d25;

}

.info small {

    display:block;

    color:#718b79;

    margin-bottom:5px;

}

button {

    border:none;

    border-radius:11px;

    padding:14px 18px;

    cursor:pointer;

    font-weight:800;

}

.primary {

    background:
    linear-gradient(
        135deg,
        #6af087,
        #1cab58
    );

    color:#031008;

}

input,
textarea {

    width:100%;

    padding:14px;

    margin:
    7px 0 17px;

    border-radius:11px;

    border:1px solid #295538;

    background:#07170c;

    color:white;

    outline:none;

}

input:focus,
textarea:focus {

    border-color:var(--green);

}

label {

    color:#9eb5a5;

    font-size:13px;

    font-weight:700;

}

.login {

    min-height:100vh;

    display:flex;

    align-items:center;

    justify-content:center;

    padding:25px;

}

.loginbox {

    width:min(460px,100%);

    padding:38px;

    border-radius:25px;

    border:1px solid var(--border);

    background:#081b0e;

    box-shadow:
    0 30px 90px rgba(0,0,0,.45);

}

.loginbox h1 {

    font-size:36px;

}

.error {

    background:#4c1919;

    color:#ffb0b0;

    border:1px solid #7b3030;

    padding:12px;

    border-radius:10px;

    margin-bottom:15px;

}

.success {

    background:#123b20;

    color:#aaf5b8;

    padding:12px;

    border-radius:10px;

    margin-bottom:15px;

}

.chat {

    min-height:600px;

    display:flex;

    flex-direction:column;

}

.chatbody {

    flex:1;

    padding:20px;

    min-height:400px;

}

.msg {

    max-width:82%;

    padding:16px;

    border-radius:15px;

    line-height:1.65;

    margin-bottom:15px;

}

.ai {

    background:#10291a;

    border:1px solid #214d2e;

}

.user {

    margin-left:auto;

    background:#176136;

}

.chatform {

    display:flex;

    gap:10px;

    padding-top:15px;

    border-top:1px solid var(--border);

}

.chatform textarea {

    margin:0;

}

.status {

    display:inline-flex;

    align-items:center;

    gap:8px;

    color:#aaf5b8;

    background:#0c2915;

    border:1px solid #1e5a2c;

    padding:8px 12px;

    border-radius:100px;

    font-size:12px;

}

.dot {

    width:8px;

    height:8px;

    background:var(--green);

    border-radius:50%;

    box-shadow:
    0 0 12px var(--green);

}

.footer {

    text-align:center;

    color:#637969;

    padding:30px;

}

@media(max-width:850px) {

    .grid {

        grid-template-columns:
        repeat(2,1fr);

    }

    .two {

        grid-template-columns:1fr;

    }

}

@media(max-width:600px) {

    nav {

        padding:0 15px;

    }

    .navlinks {

        display:none;

    }

    .grid {

        grid-template-columns:1fr;

    }

    .profile {

        grid-template-columns:1fr;

    }

    .hero {

        padding:28px;

    }

    .hero h1 {

        font-size:32px;

    }

}

</style>

"""


# =========================================================
# LOGIN
# =========================================================

LOGIN_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
content="width=device-width,initial-scale=1">

<title>AgriNova AI</title>

""" + STYLE + """

</head>

<body>

<div class="login">

<div class="loginbox">

<div class="logo">
🌱 AGRI<span>NOVA</span> AI
</div>

<h1>
Smart Farming.<br>
<span style="color:#63ed82">
Powered by AI.
</span>
</h1>

<p style="color:#8ba494;line-height:1.7">

Connect your farm intelligence,
sensor network and agricultural AI
from anywhere.

</p>

{% if error %}

<div class="error">
{{error}}
</div>

{% endif %}

<form method="POST">

<label>USERNAME</label>

<input
name="username"
required
placeholder="Farmer username"
>

<label>PASSWORD</label>

<input
type="password"
name="password"
required
placeholder="Password"
>

<button class="primary"
style="width:100%">
LOGIN
</button>

</form>

<br>

<a href="/register">

<button
style="width:100%;
background:#122b19;
color:#bdeac7">

CREATE FARMER ACCOUNT

</button>

</a>

</div>

</div>

</body>

</html>

"""


# =========================================================
# REGISTER
# =========================================================

REGISTER_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
content="width=device-width,initial-scale=1">

<title>Create Account</title>

""" + STYLE + """

</head>

<body>

<div class="login">

<div class="loginbox">

<div class="logo">
🌱 AGRI<span>NOVA</span> AI
</div>

<h1>Create Farmer Account</h1>

{% if error %}

<div class="error">
{{error}}
</div>

{% endif %}

<form method="POST">

<label>USERNAME</label>

<input
name="username"
required
>

<label>PASSWORD</label>

<input
type="password"
name="password"
required
>

<label>CONFIRM PASSWORD</label>

<input
type="password"
name="confirm"
required
>

<button
class="primary"
style="width:100%">

CREATE ACCOUNT

</button>

</form>

<br>

<a href="/">

<button
style="width:100%;
background:#122b19;
color:#bdeac7">

BACK TO LOGIN

</button>

</a>

</div>

</div>

</body>

</html>

"""


# =========================================================
# PROFILE
# =========================================================

PROFILE_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
content="width=device-width,initial-scale=1">

<title>Farm Profile</title>

""" + STYLE + """

</head>

<body>

<div class="login">

<div class="loginbox">

<div class="logo">
🌱 AGRI<span>NOVA</span> AI
</div>

<h1>Your Farm</h1>

<p style="color:#8ba494">

Complete your farmer profile once.

</p>

<form method="POST">

<label>NAME</label>

<input name="name" required>

<label>AGE</label>

<input
type="number"
name="age"
required
>

<label>FARM LOCATION</label>

<input
name="location"
required
>

<label>STATE</label>

<input
name="state"
required
>

<label>FARM SIZE — ACRES</label>

<input
type="number"
step="0.01"
name="farm_size"
required
>

<label>CROP PLANTED</label>

<input
name="crop"
required
>

<button
class="primary"
style="width:100%">

SAVE FARM PROFILE

</button>

</form>

</div>

</div>

</body>

</html>

"""


# =========================================================
# DASHBOARD
# =========================================================

DASHBOARD_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
content="width=device-width,initial-scale=1">

<meta http-equiv="refresh"
content="10">

<title>AgriNova Dashboard</title>

""" + STYLE + """

</head>

<body>

<nav>

<div class="logo">
🌱 AGRI<span>NOVA</span> AI
</div>

<div class="navlinks">

<a href="/dashboard">Dashboard</a>

<a href="/myfarm">My Farm</a>

<a href="/ai">AI</a>

<a href="/logout">Logout</a>

</div>

</nav>

<div class="container page">

<div class="hero">

<div class="status">

<div class="dot"></div>

AGRINOVA FARM INTELLIGENCE

</div>

<h1>
Welcome, {{user["name"]}} 👨‍🌾
</h1>

<p>
Your farm intelligence centre is online.
</p>

</div>


<h2 style="margin-top:35px">
Live Farm Conditions
</h2>


<div class="grid">

{% for item in sensors %}

<div class="card sensor">

<div class="sensor-icon">
{{item.icon}}
</div>

<div class="sensor-name">
{{item.name}}
</div>

<div class="value">
{{item.value}}
</div>

<div class="unit">
{{item.unit}}
</div>

</div>

{% endfor %}

</div>


<div class="two">


<div class="card">

<h2>🌾 My Farm</h2>

<div class="profile">

<div class="info">
<small>FARMER</small>
<strong>{{user["name"]}}</strong>
</div>

<div class="info">
<small>AGE</small>
<strong>{{user["age"]}}</strong>
</div>

<div class="info">
<small>LOCATION</small>
<strong>{{user["location"]}}</strong>
</div>

<div class="info">
<small>STATE</small>
<strong>{{user["state"]}}</strong>
</div>

<div class="info">
<small>FARM SIZE</small>
<strong>{{user["farm_size"]}} acres</strong>
</div>

<div class="info">
<small>CROP</small>
<strong>{{user["crop"]}}</strong>
</div>

</div>

</div>


<div class="card">

<h2>🤖 Agriculture AI</h2>

<p style="color:#8ba494;line-height:1.7">

Ask AgriNova AI about crops,
irrigation, soil, pH, pests and
agricultural technology.

</p>

<a href="/ai">

<button class="primary">
OPEN AI ASSISTANT →
</button>

</a>

</div>

</div>

</div>

<div class="footer">
AGRI NOVA AI • SMART AGRICULTURE
</div>

</body>

</html>

"""


# =========================================================
# MY FARM
# =========================================================

MYFARM_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
content="width=device-width,initial-scale=1">

<meta http-equiv="refresh"
content="5">

<title>My Farm</title>

""" + STYLE + """

</head>

<body>

<nav>

<div class="logo">
🌱 AGRI<span>NOVA</span> AI
</div>

<div class="navlinks">

<a href="/dashboard">Dashboard</a>

<a href="/myfarm">My Farm</a>

<a href="/ai">AI</a>

<a href="/logout">Logout</a>

</div>

</nav>

<div class="container page">

<div class="hero">

<div class="status">

<div class="dot"></div>

LIVE FARM MONITORING

</div>

<h1>🌾 My Farm</h1>

<p>
ESP8266 sensor intelligence
received from your farm.
</p>

</div>


<h2 style="margin-top:35px">
📡 Sensor Network
</h2>


<div class="grid">

{% for item in sensors %}

<div class="card sensor">

<div class="sensor-icon">
{{item.icon}}
</div>

<div class="sensor-name">
{{item.name}}
</div>

<div class="value">
{{item.value}}
</div>

<div class="unit">
{{item.unit}}
</div>

</div>

{% endfor %}

</div>


<div class="two">

<div class="card">

<h2>🧪 Soil Condition</h2>

<h1 style="color:#63ed82">
{{ph_status}}
</h1>

<p style="color:#8ba494">
{{ph_message}}
</p>

</div>


<div class="card">

<h2>📡 Connection</h2>

{% if sensor.online %}

<div class="status">
<div class="dot"></div>
ESP8266 DATA RECEIVED
</div>

{% else %}

<p style="color:#ff9c9c">
WAITING FOR ESP8266
</p>

{% endif %}

<p style="color:#708779">

Last update:
{{sensor.updated_at or "No reading yet"}}

</p>

</div>

</div>

</div>

</body>

</html>

"""


# =========================================================
# AI
# =========================================================

AI_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
content="width=device-width,initial-scale=1">

<title>AgriNova AI</title>

""" + STYLE + """

</head>

<body>

<nav>

<div class="logo">
🤖 AGRI<span>NOVA</span> AI
</div>

<div class="navlinks">

<a href="/dashboard">Dashboard</a>

<a href="/myfarm">My Farm</a>

<a href="/ai">AI</a>

<a href="/logout">Logout</a>

</div>

</nav>

<div class="container page">

<div class="card chat">

<h1>
🤖 AgriNova AI
</h1>

<p style="color:#8ba494">

Agriculture Intelligence Assistant

</p>


<div class="chatbody">

<div class="msg ai">

<strong>AgriNova AI</strong>

<br><br>

Hello {{user["name"]}} 👋

<br><br>

Ask me about your crop, soil,
irrigation, pests, pH or farming
technology.

</div>


{% if question %}

<div class="msg user">

{{question}}

</div>

{% endif %}


{% if answer %}

<div class="msg ai">

<strong>AgriNova AI</strong>

<br><br>

{{answer}}

</div>

{% endif %}

</div>


<form
method="POST"
class="chatform">

<textarea
name="question"
rows="2"
placeholder="Ask an agriculture question..."
required></textarea>

<button
class="primary"
type="submit">

ASK AI

</button>

</form>

</div>

</div>

</body>

</html>

"""


# =========================================================
# LOGIN
# =========================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = hash_password(
            request.form["password"]
        )

        connection = get_db()

        user = connection.execute(
            """
            SELECT *
            FROM farmers
            WHERE username=?
            AND password=?
            """,
            (
                username,
                password
            )
        ).fetchone()

        connection.close()

        if user:

            session["farmer_id"] = user["id"]

            if not user["profile_done"]:

                return redirect("/profile")

            return redirect("/dashboard")

        return render_template_string(
            LOGIN_PAGE,
            error="Invalid username or password."
        )

    return render_template_string(
        LOGIN_PAGE,
        error=None
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]

        confirm = request.form[
            "confirm"
        ]

        if password != confirm:

            return render_template_string(
                REGISTER_PAGE,
                error="Passwords do not match."
            )

        connection = get_db()

        existing = connection.execute(
            """
            SELECT id
            FROM farmers
            WHERE username=?
            """,
            (username,)
        ).fetchone()

        if existing:

            connection.close()

            return render_template_string(
                REGISTER_PAGE,
                error=(
                    "USERNAME ALREADY EXISTS. "
                    "Please choose another."
                )
            )

        connection.execute(
            """
            INSERT INTO farmers
            (username,password)
            VALUES (?,?)
            """,
            (
                username,
                hash_password(password)
            )
        )

        connection.commit()

        user = connection.execute(
            """
            SELECT id
            FROM farmers
            WHERE username=?
            """,
            (username,)
        ).fetchone()

        connection.close()

        session["farmer_id"] = user["id"]

        return redirect("/profile")

    return render_template_string(
        REGISTER_PAGE,
        error=None
    )


# =========================================================
# PROFILE
# =========================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    if "farmer_id" not in session:

        return redirect("/")

    if request.method == "POST":

        connection = get_db()

        connection.execute(
            """
            UPDATE farmers

            SET
                name=?,
                age=?,
                location=?,
                state=?,
                farm_size=?,
                crop=?,
                profile_done=1

            WHERE id=?
            """,
            (
                request.form["name"],
                request.form["age"],
                request.form["location"],
                request.form["state"],
                request.form["farm_size"],
                request.form["crop"],
                session["farmer_id"]
            )
        )

        connection.commit()

        connection.close()

        return redirect("/dashboard")

    return render_template_string(
        PROFILE_PAGE
    )


# =========================================================
# CURRENT USER
# =========================================================

def current_user():

    connection = get_db()

    user = connection.execute(
        """
        SELECT *
        FROM farmers
        WHERE id=?
        """,
        (
            session["farmer_id"],
        )
    ).fetchone()

    connection.close()

    return user


# =========================================================
# SENSOR CARDS
# =========================================================

def sensor_cards(sensor):

    return [

        {
            "icon": "☀️",
            "name": "LIGHT",
            "value":
                sensor["lux"]
                if sensor["lux"] is not None
                else "—",
            "unit": "lux"
        },

        {
            "icon": "🌡️",
            "name": "TEMPERATURE",
            "value":
                sensor["temperature"]
                if sensor["temperature"] is not None
                else "—",
            "unit": "°C"
        },

        {
            "icon": "💧",
            "name": "SOIL MOISTURE",
            "value":
                sensor["moisture"]
                if sensor["moisture"] is not None
                else "—",
            "unit": "%"
        },

        {
            "icon": "🧪",
            "name": "SOIL pH",
            "value":
                sensor["ph"]
                if sensor["ph"] is not None
                else "—",
            "unit":
                ph_information(
                    sensor["ph"]
                )[0]
        }

    ]


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "farmer_id" not in session:

        return redirect("/")

    user = current_user()

    if not user["profile_done"]:

        return redirect("/profile")

    sensor = read_sensor_data()

    return render_template_string(

        DASHBOARD_PAGE,

        user=user,

        sensors=sensor_cards(sensor)

    )


# =========================================================
# MY FARM
# =========================================================

@app.route("/myfarm")
def myfarm():

    if "farmer_id" not in session:

        return redirect("/")

    user = current_user()

    sensor = read_sensor_data()

    status, message = ph_information(
        sensor["ph"]
    )

    return render_template_string(

        MYFARM_PAGE,

        user=user,

        sensor=sensor,

        sensors=sensor_cards(sensor),

        ph_status=status,

        ph_message=message

    )


# =========================================================
# PUBLIC SENSOR API
# =========================================================

@app.route("/api/sensors")
def api_sensors():

    return jsonify(
        read_sensor_data()
    )


# =========================================================
# ESP8266 UPLOAD ENDPOINT
# =========================================================

@app.route(
    "/api/esp/update",
    methods=["POST"]
)
def esp_update():

    token = request.headers.get(
        "X-ESP-TOKEN",
        ""
    )

    if not secrets.compare_digest(
        token,
        ESP_TOKEN
    ):

        return jsonify({
            "ok": False,
            "error": "Unauthorized"
        }), 401


    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "ok": False,
            "error": "JSON required"
        }), 400


    try:

        lux = float(
            data["lux"]
        )

        temperature = float(
            data["temperature"]
        )

        moisture = float(
            data["moisture"]
        )

        ph = float(
            data["ph"]
        )

        acidity = float(
            data.get(
                "acidity",
                0
            )
        )

        alkalinity = float(
            data.get(
                "alkalinity",
                0
            )
        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):

        return jsonify({
            "ok": False,
            "error":
                "Invalid sensor values"
        }), 400


    save_sensor_data(
        lux,
        temperature,
        moisture,
        ph,
        acidity,
        alkalinity
    )


    return jsonify({
        "ok": True,
        "message":
            "Sensor data received"
    })


# =========================================================
# AI
# =========================================================

@app.route(
    "/ai",
    methods=["GET", "POST"]
)
def ai():

    if "farmer_id" not in session:

        return redirect("/")

    user = current_user()

    question = None

    answer = None


    if request.method == "POST":

        question = request.form[
            "question"
        ].strip()


        if not GEMINI_API_KEY:

            answer = (
                "Gemini is not configured on "
                "the server yet."
            )

        else:

            try:

                sensor = read_sensor_data()

                prompt = f"""

You are AgriNova AI,
an agriculture-focused AI assistant.

Farmer:
Name: {user["name"]}
Age: {user["age"]}
Location: {user["location"]}
State: {user["state"]}
Farm size: {user["farm_size"]} acres
Crop: {user["crop"]}

Latest sensor information:

Light:
{sensor["lux"]}

Temperature:
{sensor["temperature"]}

Soil moisture:
{sensor["moisture"]}

Soil pH:
{sensor["ph"]}

Answer the following agriculture question:

{question}

Give a clear and useful answer.

Do not invent measurements.

Do not claim that hobby-grade sensors
are laboratory accurate.

If professional agricultural,
laboratory or veterinary advice is needed,
recommend the appropriate professional.
"""


                response = (
                    gemini_client.models.generate_content(

                        model=GEMINI_MODEL,

                        contents=prompt

                    )
                )


                answer = response.text


            except Exception as error:

                answer = (
                    "Gemini error: "
                    + str(error)
                )


    return render_template_string(

        AI_PAGE,

        user=user,

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
        "service": "AgriNova AI"
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================================================
# START
# =========================================================

init_database()


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )