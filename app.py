import os
import hashlib, binascii
import secrets, string
import sqlite3
import time

from urllib.parse import urljoin
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, g, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(32)

DATABASE = os.environ.get("DB_PATH", "db.sqlite")
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:808")

WAIT_SEC = float(os.environ.get("BOT_WAIT_SEC", "5.0"))

try:
    FLAG = open("./flag.txt", "r").read().strip()
except:
    FLAG = "[**FLAG**]"

ADMIN_USER = "administrator"
ADMIN_PASS = binascii.hexlify(os.urandom(32)).decode()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

def is_admin_session():
    return session.get("username") == ADMIN_USER

def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "uid" not in session:
            flash("로그인 먼저 해주세요")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view


@app.after_request
def add_header(response):
    csp_policy = [
        "default-src 'none'",
        "script-src 'none'",
        "style-src 'self' 'unsafe-inline'"
    ]
    response.headers['Content-Security-Policy'] = "; ".join(csp_policy)
    return response


@app.route("/")
def index():
    db = get_db()
    reserved = []
    if "uid" in session:
        reserved = [r["seat_code"] for r in db.execute(
            "SELECT seat_code FROM tickets WHERE uid=?",
            (session["uid"],)
        ).fetchall()]
    selected = request.args.get("selected")
    msg = request.args.get("msg")
    return render_template("index.html",
                           reserved=reserved,
                           selected=selected,
                           logged_in=("uid" in session),
                           msg=msg)

@app.route("/buy", methods=["POST"])
@login_required
def buy():
    seat_code = request.form.get("seat_code", "").strip()
    optional = request.form.get("optional", "").strip()
    if not seat_code:
        flash("좌석을 선택하세요.")
        return redirect(url_for("index"))
    db = get_db()
    
    db.execute("INSERT INTO tickets(uid, seat_code, optional) VALUES(?,?,?)",
               (session["uid"], seat_code, optional))
    db.commit()
    flash("좌석 예약 성공!")
    return redirect(url_for("index", selected=seat_code))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        hashed = hashlib.sha256(password.encode()).hexdigest()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND password=?",
                          (username, hashed)).fetchone()
        if user:
            session["uid"] = user["id"]
            session["username"] = user["username"]
            if "staff_code" in user.keys() and user["staff_code"]:
                session["staff_code"] = user["staff_code"]
            return redirect(url_for("index"))
        return render_template("login.html", error="Login failed")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("register.html", error="Both fields required")
        db = get_db()
        try:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            db.execute("INSERT INTO users(username,password) VALUES(?,?)", (username, hashed))
            db.commit()
            flash("Registration successful!")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username already taken")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/mypage")
@login_required
def mypage():
    db = get_db()
    tid = request.args.get("ticket_id", type=int)
    ticket = None
    if tid:
        query = "SELECT id, uid, seat_code, optional FROM tickets WHERE id=?"
        params = (tid,)
        if not is_admin_session():
            query += " AND uid=?"
            params = (tid, session["uid"])
        ticket = db.execute(query, params).fetchone()

    if not ticket:
        ticket = db.execute(
            "SELECT id, uid, seat_code, optional FROM tickets WHERE uid=? ORDER BY id DESC LIMIT 1",
            (session["uid"],)
        ).fetchone()

    staff_code_to_display = None
    if is_admin_session():
        staff_code_to_display = session.get("staff_code")

    return render_template("mypage.html", ticket=ticket, staff_code=staff_code_to_display)

@app.route("/list")
def list_page():
    db = get_db()

    provided_code = request.args.get("code")
    admin = db.execute(
        "SELECT staff_code FROM users WHERE username=?",
        (ADMIN_USER,)
    ).fetchone()

    if not (admin and provided_code == admin["staff_code"]):
        return render_template("403.html"), 403

    custom_notice = request.args.get("motd")
    rendered_notice = None
    if custom_notice:
        try:
            rendered_notice = render_template_string(custom_notice)
        except Exception:
            rendered_notice = "Error: Invalid MOTD format."

    return render_template(
        "list.html",
        custom_notice=rendered_notice,
        reserved=[]  
    )

@app.route("/report", methods=["GET", "POST"])
@login_required
def report():
    if request.method == "POST":
        path = (request.form.get("path") or "").strip()
        #/mypage?
        target_url = urljoin(BASE_URL, path.lstrip("/"))
        verdict = bot_visit(target_url)
        return render_template("report.html", msg=verdict)
    return render_template("report.html")


def bot_visit(url: str):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException, WebDriverException
    import time
    from urllib.parse import urljoin

    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--incognito")
    opts.add_argument("--disable-cache")


    service = ChromeService(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=opts)
    

    d.set_page_load_timeout(7)

    start_time = 0

    try:
        d.get(urljoin(BASE_URL, "/login"))
        d.find_element(By.NAME, "username").send_keys(ADMIN_USER)
        d.find_element(By.NAME, "password").send_keys(ADMIN_PASS)
        d.find_element(By.CSS_SELECTOR, "form button, form input[type=submit]").click()
        time.sleep(0.5)

        start_time = time.time()
        d.get(url)
        duration = time.time() - start_time

        return f"[티켓 신고 시스템] 티켓 검수가 완료되었습니다. (소요 시간: {duration:.2f}초)"
    # HINT: 크래쉬는 타임아웃을 유발할 수 있습니다.
    except (TimeoutException, WebDriverException) as e:

        duration = time.time() - start_time if start_time > 0 else 0
        

        if isinstance(e, TimeoutException):
            return f"[오류 발생] 페이지 로딩 시간이 초과되었습니다. (소요 시간: {duration:.2f}초)"
        else:
            return f"[오류 발생] 브라우저 오류가 발생했습니다. (소요 시간: {duration:.2f}초)"

    finally:
        try:
            d.quit()
        except:
            pass

def init_db():
    db = get_db()
    db.execute("DROP TABLE IF EXISTS users;")
    db.execute("DROP TABLE IF EXISTS tickets;")

    db.execute("""
        CREATE TABLE users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            staff_code TEXT
        );
    """)
    db.execute("""
        CREATE TABLE tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER,
            seat_code TEXT,
            optional TEXT
        );
    """)
    db.commit()

def create_admin_user():
    db = get_db()
    admin_exists = db.execute("SELECT 1 FROM users WHERE username = ?", (ADMIN_USER,)).fetchone()
    if not admin_exists:
        staff_code = ''.join(secrets.choice(string.ascii_letters) for _ in range(16))
        hashed_password = hashlib.sha256(ADMIN_PASS.encode()).hexdigest()
        db.execute(
            "INSERT INTO users (username, password, staff_code) VALUES (?, ?, ?)",
            (ADMIN_USER, hashed_password, staff_code)
        )
        db.commit()

with app.app_context():
    init_db()
    create_admin_user()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=808, debug=False, use_reloader=False)

