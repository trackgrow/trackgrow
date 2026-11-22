import os, secrets, sqlite3
from functools import wraps
from urllib.parse import urlencode
from flask import Flask, request, redirect, url_for, render_template_string, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "trackgrow.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-deploying")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            channel_url TEXT NOT NULL,
            headline TEXT NOT NULL,
            description TEXT NOT NULL,
            button_text TEXT NOT NULL,
            clicks INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
        );
        """)

        try:
            con.execute(
                "ALTER TABLE campaigns ADD COLUMN telegram_invite_link TEXT"
            )
        except sqlite3.OperationalError:
            pass

        con.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                template_id TEXT NOT NULL,
                page_data TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                published_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        
init_db()
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

STYLE = """
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1020;color:#eaf0ff;font:15px Arial,sans-serif}
a{color:#7dd3fc;text-decoration:none}.wrap{max-width:1000px;margin:auto;padding:22px}
nav{display:flex;justify-content:space-between;align-items:center;padding:16px 22px;border-bottom:1px solid #27324a}
.logo{font-size:22px;font-weight:800;color:#fff}.muted{color:#9aa8c2}
.card{background:#121b30;border:1px solid #263653;border-radius:16px;padding:20px;margin:14px 0}
input,textarea{width:100%;padding:12px;margin:7px 0 14px;border-radius:9px;border:1px solid #344563;background:#0c1426;color:#fff}
button,.btn{display:inline-block;background:#16a37a;color:white;border:0;padding:12px 17px;border-radius:9px;font-weight:700;cursor:pointer}
.btn2{background:#263653}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
h1{font-size:34px;margin:12px 0}h2{margin-top:0}.stat{font-size:28px;font-weight:800}.flash{background:#49351b;padding:10px;border-radius:8px}
label{color:#b9c7df;font-size:13px}.hero{max-width:720px;margin:70px auto;text-align:center;padding:30px}
.hero h1{font-size:42px}.hero p{font-size:18px;line-height:1.6;color:#bdc9df}
small{color:#9aa8c2}
</style>
"""
def page(body, title="TrackGrow"):
    return render_template_string("""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}}</title>""" + STYLE + """</head><body><nav><a class="logo" href="/">TrackGrow</a><span>{% if email %}{{email}} · <a href="/logout">Logout</a>{% else %}<a href="/login">Login</a>{% endif %}</span></nav><main class="wrap">""" + body + """</main></body></html>""",
        title=title, email=session.get("email"))

@app.route("/")
def home():
    return page("""<section class="hero"><div class="muted">SMART TELEGRAM GROWTH TRACKING</div><h1>Track Every Click.<br>Measure Every Join.</h1><p>Create campaign landing pages, share unique tracking links and understand which campaigns bring visitors to your Telegram channel.</p><a class="btn" href="/register">Create free account</a> <a class="btn btn2" href="/login">Client login</a><p><small>Early MVP · Telegram membership verification will be connected in a later setup step.</small></p></section>""", "TrackGrow — Smart Tracking")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not email or len(password)<8:
            flash("Enter a valid email and password with at least 8 characters.")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(email,password_hash) VALUES(?,?)",(email,generate_password_hash(password)))
                flash("Account created. Please log in.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.")
    return page("""<div class="card"><h2>Create client account</h2>{% for m in get_flashed_messages() %}<p class="flash">{{m}}</p>{% endfor %}<form method="post"><label>Email</label><input name="email" type="email" required><label>Password (minimum 8 characters)</label><input name="password" type="password" minlength="8" required><button>Create account</button></form></div>""","Register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        with db() as con: user=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if user and check_password_hash(user["password_hash"],request.form.get("password","")):
            session["user_id"]=user["id"]; session["email"]=user["email"]
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.")
    return page("""<div class="card"><h2>Client login</h2>{% for m in get_flashed_messages() %}<p class="flash">{{m}}</p>{% endfor %}<form method="post"><label>Email</label><input name="email" type="email" required><label>Password</label><input name="password" type="password" required><button>Login</button></form><p><a href="/register">Create an account</a></p></div>""","Login")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        campaigns = con.execute(
            "SELECT * FROM campaigns WHERE user_id=? ORDER BY id DESC",
            (session["user_id"],)
        ).fetchall()

        totals = con.execute(
            """SELECT COUNT(*) n FROM events e
            JOIN campaigns c ON c.id=e.campaign_id
            WHERE c.user_id=? AND e.event_type='click'""",
            (session["user_id"],)
        ).fetchone()["n"]

        con.execute("""
            CREATE TABLE IF NOT EXISTS telegram_members (
                chat_id TEXT NOT NULL,
                telegram_user_id INTEGER NOT NULL,
                username TEXT,
                status TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, telegram_user_id)
            )
        """)

        joins = con.execute("""
            SELECT COUNT(*) FROM telegram_members
            WHERE chat_id='-1004489288080'
            AND status IN ('member','administrator','creator')
        """).fetchone()[0]

    rows = "".join(
        f"""<div class="card"><h3>{c['name']}</h3>
        <p class="muted">{c['clicks']} tracked clicks · Telegram: {c['channel_url']}</p>
        <p><a href="/c/{c['slug']}" target="_blank">Open landing page</a> ·
        <a href="/t/{c['slug']}" target="_blank">Tracking link</a></p></div>"""
        for c in campaigns
    )

    return page(f"""<h1>Client Dashboard</h1>
    <p class="muted">Your campaign workspace</p>
    <div class="grid">
    <div class="card"><div class="muted">Tracked clicks</div><div class="stat">{totals}</div></div>
    <div class="card"><div class="muted">Campaigns</div><div class="stat">{len(campaigns)}</div></div>
    <div class="card"><div class="muted">Verified Telegram joins</div><div class="stat">{joins}</div></div>
    </div>
    <div class="card"><h2>Create a landing page & campaign</h2>
    <form method="post" action="/campaigns/new">
    <label>Campaign name</label><input name="name" required placeholder="Example: Instagram November Campaign">
    <label>Telegram channel invite URL</label><input name="channel_url" type="url" required placeholder="https://t.me/+...">
    <label>Landing page headline</label><input name="headline" required value="Join our Telegram community">
    <label>Description</label><textarea name="description" rows="3">Get updates and community announcements on Telegram.</textarea>
    <label>Button text</label><input name="button_text" value="Join on Telegram">
    <button>Create campaign</button></form></div>
    <h2>Your campaigns</h2>
    {rows or '<p class="muted">No campaigns yet. Create your first one above.</p>'}
    """, "Dashboard")

@app.route("/campaigns/new", methods=["POST"])
@login_required
def new_campaign():
    name=request.form.get("name","").strip()
    channel=request.form.get("channel_url","").strip()
    if not channel.startswith("https://t.me/"):
        flash("Please enter a valid https://t.me/ Telegram invite or channel URL.")
        return redirect(url_for("dashboard"))
    slug=secrets.token_urlsafe(7).replace("-","").replace("_","")[:10]
    with db() as con:
        con.execute("""INSERT INTO campaigns(user_id,name,slug,channel_url,headline,description,button_text)
        VALUES(?,?,?,?,?,?,?)""",(session["user_id"],name,slug,channel,request.form.get("headline","Join our Telegram community"),request.form.get("description",""),request.form.get("button_text","Join on Telegram")))
    return redirect(url_for("dashboard"))

@app.route("/c/<slug>")
def landing(slug):
    with db() as con: c=con.execute("SELECT * FROM campaigns WHERE slug=?",(slug,)).fetchone()
    if not c: abort(404)
    return page(f"""<section class="hero"><div class="muted">WELCOME</div><h1>{c['headline']}</h1><p>{c['description']}</p><a class="btn" href="/t/{slug}">{c['button_text']}</a></section>""",c["name"])

@app.route("/t/<slug>")
def track(slug):
    with db() as con:
        c=con.execute("SELECT * FROM campaigns WHERE slug=?",(slug,)).fetchone()
        if not c: abort(404)
        source=request.args.get("utm_source") or request.args.get("src") or "direct"
        con.execute("UPDATE campaigns SET clicks=clicks+1 WHERE id=?",(c["id"],))
        con.execute("INSERT INTO events(campaign_id,event_type,source) VALUES(?,?,?)",(c["id"],"click",source))
    return redirect(c["channel_url"])

@app.route("/health")
def health():
    return {"status":"ok","app":"TrackGrow","note":"MVP running; Telegram verified-join webhook is not configured yet."}

@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

    if not secret:
        abort(503)

    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
        abort(403)

    update = request.get_json(silent=True) or {}
    member = update.get("chat_member")

    if member:
        chat = member.get("chat", {})
        new_member = member.get("new_chat_member", {})
        user = new_member.get("user", {})
        status = new_member.get("status", "left")

        if chat.get("id") and user.get("id"):
            with db() as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS telegram_members (
                        chat_id TEXT NOT NULL,
                        telegram_user_id INTEGER NOT NULL,
                        username TEXT,
                        status TEXT NOT NULL,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(chat_id, telegram_user_id)
                    )
                """)

                con.execute("""
                    INSERT INTO telegram_members
                    (chat_id, telegram_user_id, username, status)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(chat_id, telegram_user_id)
                    DO UPDATE SET
                    username=excluded.username,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """, (
                    str(chat["id"]),
                    user["id"],
                    user.get("username"),
                    status
                ))

    return {"ok": True}

    
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
