import os
import re
import json
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, render_template_string,
    session, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import escape

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "trackgrow-change-this-secret-key")

DB_PATH = os.environ.get("DB_PATH", "trackgrow.db")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").lower().strip()


# -------------------- DATABASE --------------------

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                plan TEXT NOT NULL DEFAULT 'free',
                plan_status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'My Landing Page',
                slug TEXT UNIQUE NOT NULL,
                template_id TEXT DEFAULT 'business',
                page_data TEXT DEFAULT '{}',
                status TEXT DEFAULT 'draft',
                page_views INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                published_at TEXT
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS plan_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                amount TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id INTEGER,
                event_type TEXT,
                source TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Existing database compatibility
        migrations = {
            "users": {
                "name": "TEXT DEFAULT ''",
                "role": "TEXT DEFAULT 'user'",
                "plan": "TEXT DEFAULT 'free'",
                "plan_status": "TEXT DEFAULT 'active'",
                "created_at": "TEXT"
            },
            "pages": {
                "template_id": "TEXT DEFAULT 'business'",
                "page_data": "TEXT DEFAULT '{}'",
                "status": "TEXT DEFAULT 'draft'",
                "page_views": "INTEGER DEFAULT 0",
                "created_at": "TEXT",
                "published_at": "TEXT"
            }
        }

        for table, columns in migrations.items():
            existing = {
                row["name"]
                for row in con.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for column, definition in columns.items():
                if column not in existing:
                    con.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )

        if ADMIN_EMAIL:
            con.execute(
                "UPDATE users SET role='admin' WHERE lower(email)=?",
                (ADMIN_EMAIL,)
            )


init_db()


# -------------------- DESIGN --------------------

STYLE = """
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b1020;color:#edf2ff;font-family:Arial,sans-serif}
a{color:#8ab4ff;text-decoration:none}
button,.btn{border:0;border-radius:10px;padding:12px 18px;
background:#6d5dfc;color:white;font-weight:700;cursor:pointer;display:inline-block}
button:hover,.btn:hover{opacity:.88}
input,textarea,select{width:100%;padding:12px;margin:7px 0 15px;
border:1px solid #303b56;border-radius:9px;background:#111a30;color:white}
textarea{min-height:110px}
label{font-size:14px;color:#c7d2e8}
nav{display:flex;justify-content:space-between;align-items:center;
padding:18px 5%;border-bottom:1px solid #26314a;gap:15px;flex-wrap:wrap}
.logo{font-size:22px;font-weight:900;color:white}
nav span{color:#c7d2e8}
.container{width:min(1100px,92%);margin:35px auto}
.hero{padding:65px 25px;text-align:center;background:linear-gradient(135deg,#17264b,#281c55);
border:1px solid #35436a;border-radius:22px}
.hero h1{font-size:clamp(32px,6vw,58px);margin:10px 0}
.muted{color:#9eabc5;line-height:1.6}
.card{background:#121c32;border:1px solid #283651;border-radius:16px;padding:22px;margin:15px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.stat{font-size:30px;font-weight:900;margin-top:8px}
input[type=checkbox]{width:auto}
hr{border:0;border-top:1px solid #2b3853;margin:22px 0}
small{color:#aab6ce}
h1,h2,h3{line-height:1.25}
table{width:100%;border-collapse:collapse}
td,th{text-align:left;padding:12px;border-bottom:1px solid #2b3853}
.preview{background:white;color:#172033;border-radius:14px;overflow:hidden}
.editor-grid{display:grid;grid-template-columns: minmax(260px,360px) 1fr;gap:20px}
@media(max-width:750px){.editor-grid{grid-template-columns:1fr}.hero{padding:45px 18px}}
</style>
"""


def page(body, title="TrackGrow", **context):
    return render_template_string("""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>{{ title }}</title>
    """ + STYLE + """
    </head>
    <body>
        <nav>
            <a class="logo" href="/">TrackGrow</a>
            <span>
            {% if email %}
                {{ email }} ·
                <a href="/dashboard">Dashboard</a> ·
                <a href="/logout">Logout</a>
            {% else %}
                <a href="/login">Login</a> ·
                <a href="/register">Create account</a>
            {% endif %}
            </span>
        </nav>
        <main class="container">
            {{ body|safe }}
        </main>
    </body>
    </html>
    """, title=title, body=body,
    email=session.get("email"), **context)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please login first.")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        with db() as con:
            user = con.execute(
                "SELECT role FROM users WHERE id=?",
                (session["user_id"],)
            ).fetchone()
        if not user or user["role"] != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


def current_user():
    if not session.get("user_id"):
        return None
    with db() as con:
        return con.execute(
            "SELECT * FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()


def make_slug():
    return secrets.token_hex(12)


def default_page_data():
    return {
        "title": "Grow Your Business With Us",
        "subtitle": "Create a powerful first impression and turn visitors into customers.",
        "button_text": "Join Now",
        "button_url": "https://t.me/",
        "background": "#111827",
        "text_color": "#ffffff",
        "custom_html": "",
        "custom_css": "",
        "custom_js": ""
    }


# -------------------- HOME --------------------

@app.route("/")
def home():
    body = """
    <section class="hero">
        <p>SMART LANDING PAGE & CAMPAIGN TRACKING PLATFORM</p>
        <h1>Track Every Click.<br>Measure Every Join.</h1>
        <p class="muted">
            Build professional landing pages, publish tracking links
            and understand which campaigns bring visitors.
        </p>
        <p>
            <a class="btn" href="/register">Create Free Account</a>
            <a class="btn" href="/login">Client Login</a>
        </p>
    </section>

    <div class="grid">
        <div class="card">
            <h3>Landing Page Builder</h3>
            <p class="muted">Create and customize professional landing pages.</p>
        </div>
        <div class="card">
            <h3>Campaign Tracking</h3>
            <p class="muted">Track page visits and campaign sources.</p>
        </div>
        <div class="card">
            <h3>Analytics Dashboard</h3>
            <p class="muted">Monitor your page performance in one place.</p>
        </div>
    </div>
    """
    return page(body, "TrackGrow - Landing Page Builder")


# -------------------- AUTHENTICATION --------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 6:
            flash("Name, valid email and password (minimum 6 characters) are required.")
        else:
            try:
                with db() as con:
                    role = "admin" if email == ADMIN_EMAIL and ADMIN_EMAIL else "user"
                    con.execute("""
                        INSERT INTO users(name,email,password,role)
                        VALUES(?,?,?,?)
                    """, (
                        name, email, generate_password_hash(password), role
                    ))
                flash("Account created. Please login.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("This email is already registered.")

    body = """
    <div class="card" style="max-width:480px;margin:auto">
        <h2>Create your free account</h2>
        <form method="post">
            <label>Your name</label>
            <input name="name" required>
            <label>Email address</label>
            <input type="email" name="email" required>
            <label>Password</label>
            <input type="password" name="password" minlength="6" required>
            <button type="submit">Create Account</button>
        </form>
        <p class="muted">Already registered? <a href="/login">Login here</a></p>
    </div>
    """
    return page(body, "Create Account")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")

        with db() as con:
            user = con.execute(
                "SELECT * FROM users WHERE lower(email)=?",
                (email,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            return redirect(url_for("dashboard"))

        flash("Incorrect email or password.")

    body = """
    <div class="card" style="max-width:480px;margin:auto">
        <h2>Client Login</h2>
        <form method="post">
            <label>Email address</label>
            <input type="email" name="email" required>
            <label>Password</label>
            <input type="password" name="password" required>
            <button type="submit">Login</button>
        </form>
        <p class="muted">New here? <a href="/register">Create account</a></p>
    </div>
    """
    return page(body, "Login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# -------------------- DASHBOARD --------------------

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        user = con.execute(
            "SELECT * FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()

        pages = con.execute("""
            SELECT * FROM pages
            WHERE user_id=?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

        total_views = con.execute("""
            SELECT COALESCE(SUM(page_views),0) AS total
            FROM pages WHERE user_id=?
        """, (session["user_id"],)).fetchone()["total"]

    rows = ""
    for p in pages:
        status = escape(p["status"] or "draft")
        rows += f"""
        <tr>
            <td>{escape(p["title"])}</td>
            <td>{status}</td>
            <td>{p["page_views"] or 0}</td>
            <td>
                <a href="/editor/{p['slug']}">Edit</a> ·
                <a href="/p/{p['slug']}" target="_blank">View</a>
            </td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="4">No landing pages created yet.</td></tr>'

    body = f"""
    <h1>Dashboard</h1>
    <p class="muted">Welcome back, {escape(user["name"] or user["email"])}.</p>

    <div class="grid">
        <div class="card"><div class="muted">Your Plan</div>
            <div class="stat">{escape(user["plan"].title())}</div>
        </div>
        <div class="card"><div class="muted">Landing Pages</div>
            <div class="stat">{len(pages)}</div>
        </div>
        <div class="card"><div class="muted">Total Page Views</div>
            <div class="stat">{total_views}</div>
        </div>
    </div>

    <p>
        <a class="btn" href="/templates">+ Create Landing Page</a>
        <a class="btn" href="/pricing">View Plans</a>
    </p>

    <div class="card">
        <h2>Your Landing Pages</h2>
        <table>
            <tr><th>Page</th><th>Status</th><th>Views</th><th>Actions</th></tr>
            {rows}
        </table>
    </div>
    """
    return page(body, "Dashboard")


# -------------------- TEMPLATES & CREATE PAGE --------------------

@app.route("/templates")
@login_required
def templates():
    body = """
    <h1>Choose a Landing Page Template</h1>
    <p class="muted">Select a starting design. You can customize it in the editor.</p>
    <div class="grid">
        <div class="card">
            <h2>Business</h2>
            <p class="muted">Professional business landing page.</p>
            <a class="btn" href="/create/business">Use Template</a>
        </div>
        <div class="card">
            <h2>Telegram</h2>
            <p class="muted">Promote your Telegram channel or community.</p>
            <a class="btn" href="/create/telegram">Use Template</a>
        </div>
        <div class="card">
            <h2>Product</h2>
            <p class="muted">Promote a product, service or offer.</p>
            <a class="btn" href="/create/product">Use Template</a>
        </div>
    </div>
    """
    return page(body, "Choose Template")


@app.route("/create/<template_id>")
@login_required
def create_page(template_id):
    allowed = ["business", "telegram", "product"]
    if template_id not in allowed:
        abort(404)

    data = default_page_data()
    if template_id == "telegram":
        data["title"] = "Join Our Telegram Community"
        data["subtitle"] = "Get updates, news and useful information directly on Telegram."
        data["button_text"] = "Join Telegram"
    elif template_id == "product":
        data["title"] = "Discover Our Product"
        data["subtitle"] = "Explore our product and get started today."
        data["button_text"] = "Get Started"

    slug = make_slug()

    with db() as con:
        con.execute("""
            INSERT INTO pages(user_id,title,slug,template_id,page_data,status)
            VALUES(?,?,?,?,?,'draft')
        """, (
            session["user_id"],
            data["title"],
            slug,
            template_id,
            json.dumps(data)
        ))

    return redirect(url_for("edit_page", slug=slug))


# -------------------- PAGE EDITOR --------------------

@app.route("/editor/<slug>", methods=["GET", "POST"])
@login_required
def edit_page(slug):
    with db() as con:
        p = con.execute("""
            SELECT * FROM pages
            WHERE slug=? AND user_id=?
        """, (slug, session["user_id"])).fetchone()

    if not p:
        abort(404)

    try:
        data = json.loads(p["page_data"] or "{}")
    except (TypeError, json.JSONDecodeError):
        data = default_page_data()

    for key, value in default_page_data().items():
        data.setdefault(key, value)

    if request.method == "POST":
        data["title"] = request.form.get("title", data["title"])
        data["subtitle"] = request.form.get("subtitle", data["subtitle"])
        data["button_text"] = request.form.get("button_text", data["button_text"])
        data["button_url"] = request.form.get("button_url", data["button_url"])
        data["background"] = request.form.get("background", data["background"])
        data["text_color"] = request.form.get("text_color", data["text_color"])

        data["custom_html"] = request.form.get("custom_html", data["custom_html"])
        data["custom_css"] = request.form.get("custom_css", data["custom_css"])
        data["custom_js"] = request.form.get("custom_js", data["custom_js"])

        with db() as con:
            con.execute("""
                UPDATE pages
                SET title=?,page_data=?
                WHERE slug=? AND user_id=?
            """, (
                data["title"], json.dumps(data),
                slug, session["user_id"]
            ))

        flash("Your changes have been saved.")

    preview = json.dumps(data).replace("</", "<\\/")

    body = """
    <h1>Landing Page Editor</h1>
    <p class="muted">Customize your page, save your changes and publish it when ready.</p>

    <div class="editor-grid">
        <div class="card">
            <form method="post">
                <h3>Page Content</h3>
                <label>Headline</label>
                <input name="title" id="titleInput" value="{{ data.title }}">
                <label>Description</label>
                <textarea name="subtitle" id="subtitleInput">{{ data.subtitle }}</textarea>
                <label>Button Text</label>
                <input name="button_text" id="buttonInput" value="{{ data.button_text }}">
                <label>Button Link</label>
                <input name="button_url" value="{{ data.button_url }}">
                <label>Background Color</label>
                <input type="color" name="background" id="bgInput" value="{{ data.background }}">
                <label>Text Color</label>
                <input type="color" name="text_color" value="{{ data.text_color }}">

                <hr>
                <h3>Custom HTML</h3>
                <textarea name="custom_html" rows="5">{{ data.custom_html }}</textarea>
                <h3>Custom CSS</h3>
                <textarea name="custom_css" rows="5">{{ data.custom_css }}</textarea>
                <h3>Custom JavaScript</h3>
                <textarea name="custom_js" rows="5">{{ data.custom_js }}</textarea>

                <button type="submit">Save Changes</button>
            </form>

            <hr>
            <form method="post" action="/publish/{{ slug }}">
                <button type="submit">Publish Landing Page</button>
            </form>
            <p><a href="/dashboard">← Back to Dashboard</a></p>
        </div>

        <div>
            <div class="card">
                <h3>Live Preview</h3>
                <div class="preview" id="preview-page">
                    <div style="padding:55px 20px;text-align:center" id="preview-content">
                        <h1 i
                        # -------------------- PUBLISH PAGE --------------------

@app.route("/publish/<slug>", methods=["POST"])
@login_required
def publish_page(slug):
    with db() as con:
        p = con.execute("""
            SELECT * FROM pages
            WHERE slug=? AND user_id=?
        """, (slug, session["user_id"])).fetchone()

        if not p:
            abort(404)

        con.execute("""
            UPDATE pages
            SET status='published', published_at=CURRENT_TIMESTAMP
            WHERE slug=? AND user_id=?
        """, (slug, session["user_id"]))

    flash("Your landing page is now published.")
    return redirect(url_for("edit_page", slug=slug))


# -------------------- PUBLIC LANDING PAGE --------------------

@app.route("/p/<slug>")
def public_page(slug):
    with db() as con:
        p = con.execute("""
            SELECT * FROM pages
            WHERE slug=? AND status='published'
        """, (slug,)).fetchone()

        if not p:
            abort(404)

        con.execute("""
            UPDATE pages SET page_views=COALESCE(page_views,0)+1
            WHERE id=?
        """, (p["id"],))

        source = request.args.get("utm_source", "")[:150]
        con.execute("""
            INSERT INTO events(page_id,event_type,source)
            VALUES(?,?,?)
        """, (p["id"], "page_view", source))

    try:
        data = json.loads(p["page_data"] or "{}")
    except (TypeError, json.JSONDecodeError):
        data = default_page_data()

    for key, value in default_page_data().items():
        data.setdefault(key, value)

    title = escape(data.get("title", "Welcome"))
    subtitle = escape(data.get("subtitle", ""))
    button_text = escape(data.get("button_text", "Join Now"))
    button_url = escape(data.get("button_url", "#"))
    background = escape(data.get("background", "#111827"))
    text_color = escape(data.get("text_color", "#ffffff"))

    custom_html = data.get("custom_html", "")
    custom_css = data.get("custom_css", "")
    custom_js = data.get("custom_js", "")

    # Custom code is displayed inside a sandboxed iframe.
    custom_document = """
    <!doctype html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body{margin:0;font-family:Arial,sans-serif}
    """ + custom_css + """
    </style>
    </head>
    <body>
    """ + custom_html + """
    <script>
    """ + custom_js + """
    </script>
    </body>
    </html>
    """

    iframe_document = escape(custom_document)

    body = f"""
    <div style="min-height:75vh;background:{background};color:{text_color};
    border-radius:18px;padding:65px 20px;text-align:center">

        <div style="max-width:850px;margin:auto">
            <h1 style="font-size:clamp(32px,6vw,58px);margin:15px 0">
                {title}
            </h1>

            <p style="font-size:18px;line-height:1.7;opacity:.85">
                {subtitle}
            </p>

            <a href="{button_url}" target="_blank" rel="noopener noreferrer"
            style="display:inline-block;margin-top:20px;padding:15px 28px;
            background:#6d5dfc;color:white;border-radius:10px;
            text-decoration:none;font-weight:bold">
                {button_text}
            </a>
        </div>
    </div>
    """

    if custom_html or custom_css or custom_js:
        body += f"""
        <div style="margin-top:25px;background:white;border-radius:14px;overflow:hidden">
            <iframe
                title="Custom landing page content"
                sandbox="allow-scripts"
                referrerpolicy="no-referrer"
                srcdoc="{iframe_document}"
                style="width:100%;min-height:450px;border:0">
            </iframe>
        </div>
        """

    body += """
    <p style="text-align:center;color:#9eabc5;margin-top:25px">
        Powered by TrackGrow
    </p>
    """

    return page(body, p["title"])


# -------------------- PRICING --------------------

@app.route("/pricing")
@login_required
def pricing():
    body = """
    <h1>Choose Your Plan</h1>
    <p class="muted">Select a plan according to your business needs.</p>

    <div class="grid">
        <div class="card">
            <h2>Free</h2>
            <div class="stat">₹0</div>
            <p class="muted">For getting started.</p>
            <ul>
                <li>Landing page builder</li>
                <li>Basic page analytics</li>
                <li>Publish landing pages</li>
            </ul>
            <a class="btn" href="/dashboard">Current Free Access</a>
        </div>

        <div class="card">
            <h2>Starter</h2>
            <div class="stat">₹499</div>
            <p class="muted">For growing campaigns.</p>
            <ul>
                <li>Landing page builder</li>
                <li>Campaign tracking</li>
                <li>Page analytics</li>
            </ul>
            <form method="post" action="/request-plan">
                <input type="hidden" name="plan" value="starter">
                <input type="hidden" name="amount" value="499">
                <button type="submit">Request Starter Plan</button>
            </form>
        </div>

        <div class="card">
            <h2>Pro</h2>
            <div class="stat">₹999</div>
            <p class="muted">For advanced users.</p>
            <ul>
                <li>All Starter features</li>
                <li>Advanced campaign tools</li>
                <li>Priority support</li>
            </ul>
            <form method="post" action="/request-plan">
                <input type="hidden" name="plan" value="pro">
                <input type="hidden" name="amount" value="999">
                <button type="submit">Request Pro Plan</button>
            </form>
        </div>
    </div>

    <p class="muted">
        Note: Online payment gateway is not connected yet.
        Plan requests are submitted for manual admin approval.
    </p>
    """
    return page(body, "TrackGrow Pricing")


# -------------------- PLAN REQUEST --------------------

@app.route("/request-plan", methods=["POST"])
@login_required
def request_plan():
    plan = request.form.get("plan", "").lower().strip()
    amount = request.form.get("amount", "").strip()

    allowed_plans = {
        "starter": "499",
        "pro": "999"
    }

    if plan not in allowed_plans or amount != allowed_plans[plan]:
        abort(400)

    with db() as con:
        con.execute("""
            INSERT INTO plan_requests(user_id,plan,amount,status)
            VALUES(?,?,?,'pending')
        """, (session["user_id"], plan, amount))

    flash("Your plan request has been submitted for admin approval.")
    return redirect(url_for("dashboard"))


# -------------------- ADMIN DASHBOARD --------------------

@app.route("/admin")
@login_required
@admin_required
def admin():
    with db() as con:
        users = con.execute("""
            SELECT id,name,email,role,plan,created_at
            FROM users ORDER BY id DESC
        """).fetchall()

        requests = con.execute("""
            SELECT plan_requests.*,users.name,users.email
            FROM plan_requests
            JOIN users ON users.id=plan_requests.user_id
            ORDER BY plan_requests.id DESC
        """).fetchall()

        total_pages = con.execute(
            "SELECT COUNT(*) AS n FROM pages"
        ).fetchone()["n"]

        total_views = con.execute(
            "SELECT COALESCE(SUM(page_views),0) AS n FROM pages"
        ).fetchone()["n"]

    user_rows = ""
    for u in users:
        user_rows += f"""
        <tr>
            <td>{u['id']}</td>
            <td>{escape(u['name'] or '')}</td>
            <td>{escape(u['email'])}</td>
            <td>{escape(u['role'])}</td>
            <td>{escape(u['plan'])}</td>
        </tr>
        """

    request_rows = ""
    for r in requests:
        action = ""
        if r["status"] == "pending":
            action = f"""
            <form method="post" action="/admin/approve/{r['id']}">
                <button type="submit">Approve</button>
            </form>
            """
        request_rows += f"""
        <tr>
            <td>{escape(r['name'] or '')}</td>
            <td>{escape(r['email'])}</td>
            <td>{escape(r['plan'])}</td>
            <td>₹{escape(r['amount'])}</td>
            <td>{escape(r['status'])}</td>
            <td>{action}</td>
        </tr>
        """

    if not user_rows:
        user_rows = "<tr><td colspan='5'>No users found.</td></tr>"

    if not request_rows:
        request_rows = "<tr><td colspan='6'>No plan requests found.</td></tr>"

    body = f"""
    <h1>Admin Dashboard</h1>
    <p class="muted">Manage users and plan requests.</p>

    <div class="grid">
        <div class="card">
            <div class="muted">Total Users</div>
            <div class="stat">{len(users)}</div>
        </div>
        <div class="card">
            <div class="muted">Total Landing Pages</div>
            <div class="stat">{total_pages}</div>
        </div>
        <div class="card">
            <div class="muted">Total Page Views</div>
            <div class="stat">{total_views}</div>
        </div>
    </div>

    <div class="card">
        <h2>Plan Requests</h2>
        <table>
            <tr>
                <th>Name</th><th>Email</th><th>Plan</th>
                <th>Amount</th><th>Status</th><th>Action</th>
            </tr>
            {request_rows}
        </table>
    </div>

    <div class="card">
        <h2>Registered Users</h2>
        <table>
            <tr>
                <th>ID</th><th>Name</th><th>Email</th>
                <th>Role</th><th>Plan</th>
            </tr>
            {user_rows}
        </table>
    </div>
    """
    return page(body, "TrackGrow Admin")


# -------------------- APPROVE PLAN --------------------

@app.route("/admin/approve/<int:request_id>", methods=["POST"])
@login_required
@admin_required
def approve_plan(request_id):
    with db() as con:
        plan_request = con.execute("""
            SELECT * FROM plan_requests WHERE id=?
        """, (request_id,)).fetchone()

        if not plan_request:
            abort(404)

        if plan_request["status"] != "pending":
            flash("This request has already been processed.")
            return redirect(url_for("admin"))

        con.execute("""
            UPDATE users
            SET plan=?,plan_status='active'
            WHERE id=?
        """, (plan_request["plan"], plan_request["user_id"]))

        con.execute("""
            UPDATE plan_requests
            SET status='approved'
            WHERE id=?
        """, (request_id,))

    flash("Plan approved successfully.")
    return redirect(url_for("admin"))


# -------------------- ERROR PAGES --------------------

@app.errorhandler(403)
def forbidden(error):
    return page("""
    <div class="card">
        <h1>403 - Access Denied</h1>
        <p class="muted">You do not have permission to access this page.</p>
        <a class="btn" href="/dashboard">Go to Dashboard</a>
    </div>
    """, "Access Denied"), 403


@app.errorhandler(404)
def not_found(error):
    return page("""
    <div class="card">
        <h1>404 - Page Not Found</h1>
        <p class="muted">The page you are looking for does not exist.</p>
        <a class="btn" href="/">Go Home</a>
    </div>
    """, "Page Not Found"), 404


@app.errorhandler(500)
def server_error(error):
    return page("""
    <div class="card">
        <h1>500 - Server Error</h1>
        <p class="muted">Something went wrong. Please try again later.</p>
        <a class="btn" href="/">Go Home</a>
    </div>
    """, "Server Error"), 500


# -------------------- START APPLICATION --------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    
