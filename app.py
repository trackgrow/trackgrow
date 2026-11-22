import os, secrets, sqlite3, json
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
*{box-sizing:border-box}
body{
 margin:0;
 background:#080d19;
 color:#edf2ff;
 font:15px Inter,Arial,sans-serif;
}
a{color:#8bafff;text-decoration:none}
a:hover{color:#fff}
.wrap{max-width:1180px;margin:auto;padding:28px 22px}
nav{
 display:flex;justify-content:space-between;align-items:center;
 padding:18px 5%;border-bottom:1px solid #202b40;
 background:#0b1220;
}
.logo{font-size:25px;font-weight:900;color:#fff;letter-spacing:-1px}
.muted{color:#9aa9c2}
.card{
 background:linear-gradient(145deg,#121d31,#0e1728);
 border:1px solid #263650;border-radius:18px;
 padding:24px;margin:16px 0;
 box-shadow:0 12px 35px #0003;
}
input,textarea,select{
 width:100%;padding:14px;margin:8px 0 16px;
 border-radius:10px;border:1px solid #34445f;
 background:#0b1425;color:#fff;font-size:15px;
}
input:focus,textarea:focus{
 outline:2px solid #527cf5;border-color:#527cf5;
}
button,.btn{
 display:inline-block;background:linear-gradient(120deg,#5578ff,#7657e9);
 color:white;border:0;padding:13px 21px;border-radius:10px;
 font-weight:750;cursor:pointer;transition:.2s;
}
button:hover,.btn:hover{transform:translateY(-2px);filter:brightness(1.12)}
.btn2{background:#202e47}
.grid{
 display:grid;
 grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
 gap:18px;
}
h1{font-size:38px;line-height:1.15;letter-spacing:-1.4px}
h2{margin-top:0;font-size:24px}
h3{font-size:19px}
p{line-height:1.7}
.stat{font-size:32px;font-weight:900;color:#8ba7ff}
.flash{
 background:#49351b;border:1px solid #80602b;
 padding:13px;border-radius:10px;
}
label{color:#b9c7df;font-size:13px;font-weight:700}
.hero{
 max-width:850px;margin:75px auto;text-align:center;padding:40px 20px;
}
.hero h1{font-size:58px;letter-spacing:-2px}
.hero p{font-size:18px;line-height:1.8;color:#bdc9df}
small{color:#9aa8c2}
@media(max-width:600px){
 .wrap{padding:18px 14px}
 nav{padding:15px}
 .hero{margin:35px auto;padding:20px 5px}
 .hero h1{font-size:38px}
 h1{font-size:30px}
 .card{padding:18px}
}
</style>
"""

def page(body, title="TrackGrow"):
    return render_template_string("""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}}</title>""" + STYLE + """</head><body><nav><a class="logo" href="/">TrackGrow</a><span>{% if email %}{{email}} · <a href="/logout">Logout</a>{% else %}<a href="/login">Login</a>{% endif %}</span></nav><main class="wrap">""" + body + """</main></body></html>""",
        title=title, email=session.get("email"))

@app.route("/")
def home():
    return page("""
    <section class="hero">
        <div style="display:inline-block;background:#17264a;color:#9db5ff;padding:9px 16px;border-radius:30px;font-size:13px;font-weight:bold;">
            ✦ ALL-IN-ONE LANDING PAGE PLATFORM
        </div>

        <h1>Build Landing Pages.<br>
        <span style="color:#829aff;">Grow Your Business.</span></h1>

        <p>Create professional landing pages for your products, services,
        courses and campaigns — all from one simple platform.</p>

        <a class="btn" href="/register">Start Building Free →</a>
        <a class="btn btn2" href="/login">Login</a>

        <p><small>No coding required · Simple page management</small></p>
    </section>

    <section style="text-align:center;margin:65px 0 35px;">
        <h2>Everything You Need to Build Pages</h2>
        <p class="muted">One platform to create, manage and grow your online presence.</p>
    </section>

    <div class="grid">
        <div class="card">
            <div style="font-size:32px;">🎨</div>
            <h3>Professional Templates</h3>
            <p class="muted">Choose from landing page designs for different business needs.</p>
        </div>

        <div class="card">
            <div style="font-size:32px;">⚡</div>
            <h3>Easy Page Creation</h3>
            <p class="muted">Create and manage your landing pages from one dashboard.</p>
        </div>

        <div class="card">
            <div style="font-size:32px;">📊</div>
            <h3>Campaign Tracking</h3>
            <p class="muted">Track campaign clicks and understand your traffic.</p>
        </div>

        <div class="card">
            <div style="font-size:32px;">📱</div>
            <h3>Mobile Friendly</h3>
            <p class="muted">Build pages designed to look good on mobile and desktop.</p>
        </div>
    </div>

    <section style="text-align:center;margin:75px 0 30px;">
        <h2>Explore Landing Page Categories</h2>
        <p class="muted">Choose a design that matches your business.</p>
    </section>

    <div class="grid">
        <div class="card">
            <div style="font-size:38px;">🛍️</div>
            <h3>Digital Products</h3>
            <p class="muted">For eBooks, downloads and online products.</p>
        </div>

        <div class="card">
            <div style="font-size:38px;">🎓</div>
            <h3>Course & Coaching</h3>
            <p class="muted">For online courses, mentors and educators.</p>
        </div>

        <div class="card">
            <div style="font-size:38px;">💼</div>
            <h3>Agency & Services</h3>
            <p class="muted">For agencies, freelancers and service providers.</p>
        </div>

        <div class="card">
            <div style="font-size:38px;">🚀</div>
            <h3>Telegram Promotion</h3>
            <p class="muted">For Telegram channels and campaign promotions.</p>
        </div>
    </div>

    <section class="card" style="text-align:center;margin:75px 0;padding:45px 20px;">
        <h2>Ready to Build Your First Landing Page?</h2>
        <p class="muted">Join TrackGrow and start creating your online pages.</p>
        <a class="btn" href="/register">Get Started Now →</a>
    </section>

    <footer style="text-align:center;padding:25px;border-top:1px solid #263650;">
        <strong>TrackGrow</strong>
        <p class="muted">Build. Publish. Grow.</p>
        <small>© 2026 TrackGrow. All rights reserved.</small>
    </footer>
    """, "TrackGrow — Landing Page Builder")
    return page("""<section class="hero"><div class="muted">SMART TELEGRAM GROWTH TRACKING</div><h1>Track Every Click.<br>Measure Every Join.</h1><p>Create campaign landing pages, share unique tracking links and understand which campaigns bring visitors to your Telegram channel.</p><a class="btn" href="/register">Create free account</a> <a class="btn btn2" href="/login">Client login</a><p><small>Early MVP · Telegram membership verification will be connected in a later setup step.</small></p></section>""", "TrackGrow — Smart Tracking")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or len(password) < 8:
            flash("Enter a valid email and password with at least 8 characters.")
        else:
            with db() as con:
                existing = con.execute(
                    "SELECT id FROM users WHERE email=?",
                    (email,)
                ).fetchone()

                if existing:
                    flash("Email already registered. Please login.")
                else:
                    con.execute(
                        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                        (email, generate_password_hash(password))
                    )
                    flash("Account created successfully. Please login.")
                    return redirect(url_for("login"))

    return page("""
    <h1>Create Account</h1>
    <form method="post">
        <label>Email</label>
        <input type="email" name="email" required>
        <label>Password (minimum 8 characters)</label>
        <input type="password" name="password" required minlength="8">
        <button type="submit">Register</button>
    </form>
    <p><a href="/login">Already have an account? Login</a></p>
    """, "Register")

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        campaigns = con.execute(
            "SELECT * FROM campaigns WHERE user_id=? ORDER BY id DESC",
            (session["user_id"],)
        ).fetchall()

        pages = con.execute(
            "SELECT * FROM pages WHERE user_id=? ORDER BY id DESC",
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

    campaign_rows = "".join(
        f"""<div class="card">
        <h3>{c['name']}</h3>
        <p class="muted">{c['clicks']} tracked clicks · Telegram: {c['channel_url']}</p>
        <p><a href="/c/{c['slug']}" target="_blank">Open landing page</a> ·
        <a href="/t/{c['slug']}" target="_blank">Tracking link</a></p>
        </div>"""
        for c in campaigns
    )

    page_rows = "".join(
        f"""<div class="card">
        <h3>{p['title']}</h3>
        <p class="muted">Template: {p['template_id']} · Status: {p['status']}</p>
                <p><a href="/editor/{p['slug']}">Edit Landing Page</a></p>
        </div>"""
        for p in pages
    )

    return page(f"""
    <h1>Client Dashboard</h1>
    <p class="muted">Your TrackGrow workspace</p>

    <div class="grid">
        <div class="card">
            <div class="muted">Tracked clicks</div>
            <div class="stat">{totals}</div>
        </div>
        <div class="card">
            <div class="muted">Campaigns</div>
            <div class="stat">{len(campaigns)}</div>
        </div>
        <div class="card">
            <div class="muted">Verified Telegram joins</div>
            <div class="stat">{joins}</div>
        </div>
        <div class="card">
            <div class="muted">Landing Pages</div>
            <div class="stat">{len(pages)}</div>
        </div>
    </div>

    <div class="card">
        <h2>My Landing Pages</h2>
        <p>Create and manage professional landing pages.</p>
        <a href="/pages/new"><button type="button">Create Landing Page</button></a>
        {page_rows or '<p class="muted">No landing pages created yet.</p>'}
    </div>

    <div class="card">
        <h2>Create a landing page & campaign</h2>
        <form method="post" action="/campaigns/new">
            <label>Campaign name</label>
            <input name="name" required placeholder="Example: Instagram November Campaign">

            <label>Telegram channel invite URL</label>
            <input name="channel_url" type="url" required placeholder="https://t.me/+...">

            <label>Landing page headline</label>
            <input name="headline" required value="Join our Telegram community">

            <label>Description</label>
            <textarea name="description" rows="3">Get updates and community announcements on Telegram.</textarea>

            <label>Button text</label>
            <input name="button_text" value="Join on Telegram">

            <button>Create campaign</button>
        </form>
    </div>

    <h2>Your campaigns</h2>
    {campaign_rows or '<p class="muted">No campaigns yet.</p>'}
    """, "Dashboard")
            
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



@app.route("/pages/new", methods=["GET", "POST"])
@login_required
def new_page():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        template_id = request.form.get("template_id", "basic")

        if not title:
            flash("Please enter a page title.")
            return redirect(url_for("new_page"))

        slug = secrets.token_hex(4)

        with db() as con:
            con.execute("""
                INSERT INTO pages
                (user_id, title, slug, template_id, page_data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                title,
                slug,
                template_id,
                "{}"
            ))

        flash("Landing page created successfully!")
        return redirect(url_for("dashboard"))

    return page("""
<style>
.gallery-head{text-align:center;margin:35px 0}
.gallery-head h1{font-size:36px}
.template-card{background:#111d32;border:1px solid #293b5a;border-radius:18px;overflow:hidden}
.template-preview{height:180px;padding:20px;display:flex;flex-direction:column;justify-content:center;text-align:center}
.preview-digital{background:linear-gradient(135deg,#293e77,#7657e9)}
.preview-course{background:linear-gradient(135deg,#075b58,#16a37a)}
.preview-agency{background:linear-gradient(135deg,#44265f,#a34e9c)}
.preview-telegram{background:linear-gradient(135deg,#14518b,#2698d6)}
.preview-title{font-size:22px;font-weight:900;color:white}
.preview-line{height:7px;background:#ffffff80;border-radius:8px;margin:8px auto;width:65%}
.template-info{padding:20px}
.template-info p{color:#9aa9c2;min-height:48px}
.template-tag{font-size:11px;color:#9db5ff;background:#1b2c4d;padding:6px 10px;border-radius:20px}
</style>

<div class="gallery-head">
    <div class="muted">TRACKGROW TEMPLATE LIBRARY</div>
    <h1>Choose Your Perfect Template</h1>
    <p class="muted">Select a design and start building your landing page.</p>
</div>

<div class="grid">

    <div class="template-card">
        <div class="template-preview preview-digital">
            <div class="preview-title">Your Digital Product</div>
            <div class="preview-line"></div>
            <div class="preview-line" style="width:40%"></div>
            <div>🛍️</div>
        </div>
        <div class="template-info">
            <span class="template-tag">DIGITAL PRODUCTS</span>
            <h2>Digital Product</h2>
            <p>Perfect for ebooks, PDFs and digital downloads.</p>
            <form method="post">
                <input name="title" placeholder="Enter page title" required>
                <input type="hidden" name="template_id" value="digital">
                <button type="submit">Use This Template →</button>
            </form>
        </div>
    </div>

    <div class="template-card">
        <div class="template-preview preview-course">
            <div class="preview-title">Learn Something New</div>
            <div class="preview-line"></div>
            <div class="preview-line" style="width:40%"></div>
            <div>🎓</div>
        </div>
        <div class="template-info">
            <span class="template-tag">EDUCATION</span>
            <h2>Course & Coaching</h2>
            <p>For online courses, mentors and coaching businesses.</p>
            <form method="post">
                <input name="title" placeholder="Enter page title" required>
                <input type="hidden" name="template_id" value="course">
                <button type="submit">Use This Template →</button>
            </form>
        </div>
    </div>

    <div class="template-card">
        <div class="template-preview preview-agency">
            <div class="preview-title">Grow Your Business</div>
            <div class="preview-line"></div>
            <div class="preview-line" style="width:40%"></div>
            <div>💼</div>
        </div>
        <div class="template-info">
            <span class="template-tag">BUSINESS</span>
            <h2>Agency & Services</h2>
            <p>For agencies, freelancers and service providers.</p>
            <form method="post">
                <input name="title" placeholder="Enter page title" required>
                <input type="hidden" name="template_id" value="agency">
                <button type="submit">Use This Template →</button>
            </form>
        </div>
    </div>

    <div class="template-card">
        <div class="template-preview preview-telegram">
            <div class="preview-title">Join Our Community</div>
            <div class="preview-line"></div>
            <div class="preview-line" style="width:40%"></div>
            <div>📢</div>
        </div>
        <div class="template-info">
            <span class="template-tag">TELEGRAM</span>
            <h2>Telegram Promotion</h2>
            <p>For Telegram channels and community promotions.</p>
            <form method="post">
                <input name="title" placeholder="Enter page title" required>
                <input type="hidden" name="template_id" value="telegram">
                <button type="submit">Use This Template →</button>
            </form>
        </div>
    </div>

</div>
""", "Template Gallery")


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

@app.route("/editor/<slug>", methods=["GET", "POST"])
@login_required
def edit_page(slug):
    with db() as con:
        p = con.execute(
            "SELECT * FROM pages WHERE slug=? AND user_id=?",
            (slug, session["user_id"])
        ).fetchone()

        if not p:
            abort(404)

        data = json.loads(p["page_data"] or "{}")

        if request.method == "POST":
            title = request.form.get("title", "").strip()

                        data = {
                "headline": request.form.get("headline", ""),
                "description": request.form.get("description", ""),
                "button_text": request.form.get("button_text", ""),
                "button_url": request.form.get("button_url", ""),
                "bg_color": request.form.get("bg_color", "#101b32"),
                "custom_html": request.form.get("custom_html", ""),
                "custom_css": request.form.get("custom_css", ""),
                "custom_js": request.form.get("custom_js", "")
            }

            if title:
                con.execute(
                    "UPDATE pages SET title=?, page_data=? WHERE id=?",
                    (title, json.dumps(data), p["id"])
                )
                flash("Your design has been saved!")
                return redirect(url_for("edit_page", slug=slug))

    return page("""
    <style>
    .editor-top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:20px}
    .editor-layout{display:grid;grid-template-columns:260px minmax(0,1fr) 260px;gap:16px;align-items:start}
    .editor-panel{background:#111d32;border:1px solid #293b55;border-radius:15px;padding:18px}
    .editor-panel h3{margin-top:0}
    .editor-canvas{background:#dce3ef;border-radius:15px;padding:20px;min-height:550px}
    .canvas-page{min-height:500px;border-radius:10px;padding:45px 20px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center}
    .canvas-page h1{font-size:36px;max-width:600px}
    .canvas-page p{max-width:520px;line-height:1.8}
    .canvas-button{display:inline-block;background:#5878f5;color:white;padding:13px 25px;border-radius:9px;font-weight:bold}
    .editor-label{display:block;color:#aebed7;font-size:12px;font-weight:bold;margin:15px 0 5px}
    .editor-panel input,.editor-panel textarea{margin:5px 0 12px}
    .tool-item{background:#1a2a44;border:1px solid #344967;border-radius:10px;padding:13px;margin:9px 0;color:#dce7ff}
    .editor-actions{display:flex;gap:8px;flex-wrap:wrap}
    .editor-actions button{font-size:13px}
    @media(max-width:850px){
      .editor-layout{grid-template-columns:1fr}
      .editor-canvas{min-height:380px;padding:10px}
      .canvas-page{min-height:350px;padding:25px 12px}
      .canvas-page h1{font-size:27px}
      .editor-panel{padding:15px}
    }
    </style>

    <div class="editor-top">
        <div>
            <div class="muted">TRACKGROW WEBSITE BUILDER</div>
            <h1 style="margin:8px 0;">Page Editor</h1>
            <small>Design and customize your landing page.</small>
        </div>
        <div class="editor-actions">
            <a class="btn btn2" href="/dashboard">Dashboard</a>
            <button type="submit" form="page-editor">Save Design</button>
        </div>
    </div>

    <form method="post" id="page-editor">
    <div class="editor-layout">

        <div class="editor-panel">
            <h3>Content Editor</h3>
            <p class="muted">Edit your page content.</p>

            <label class="editor-label">Page Name</label>
            <input name="title" value="{{title}}" required>

            <label class="editor-label">Main Headline</label>
            <input id="headline-input" name="headline" value="{{headline}}" required>

            <label class="editor-label">Description</label>
            <textarea id="description-input" name="description" rows="5" required>{{description}}</textarea>

            <label class="editor-label">Button Text</label>
            <input id="button-input" name="button_text" value="{{button_text}}" required>

            <label class="editor-label">Button Link</label>
            <input name="button_url" value="{{button_url}}" placeholder="https://example.com">

            <div class="tool-item">✦ Headline Section</div>
            <div class="tool-item">▤ Description Section</div>
            <div class="tool-item">▣ Call To Action Button</div>
            
<hr style="border-color:#293b55;margin:20px 0;">

<h3>Developer Code Mode</h3>
<p class="muted">Customize your landing page with your own code.</p>

<label class="editor-label">Custom HTML</label>
<textarea name="custom_html" rows="6" placeholder="Write your HTML here">{{custom_html}}</textarea>

<label class="editor-label">Custom CSS</label>
<textarea name="custom_css" rows="6" placeholder="Write your CSS here">{{custom_css}}</textarea>

<label class="editor-label">Custom JavaScript</label>
<textarea name="custom_js" rows="6" placeholder="Write your JavaScript here">{{custom_js}}</textarea>

        </div>

        <div>
            <div class="editor-panel editor-top">
                <strong>Page Canvas</strong>
                <span class="template-tag">LIVE PREVIEW</span>
            </div>

            <div class="editor-canvas">
                <div class="canvas-page" id="preview-page"
                     style="background:{{bg_color}};color:white;">
                    <h1 id="preview-headline">{{headline}}</h1>
                    <p id="preview-description">{{description}}</p>
                    <span class="canvas-button" id="preview-button">{{button_text}}</span>
                </div>
            </div>

            <div class="editor-panel" style="margin-top:15px;">
                <strong>Responsive Design</strong>
                <p class="muted">Your landing page is designed to adapt to desktop and mobile screens.</p>
            </div>
        </div>

        <div class="editor-panel">
            <h3>Design Settings</h3>
            <p class="muted">Customize your page appearance.</p>

            <label class="editor-label">Background Color</label>
            <input type="color" id="bg-input" name="bg_color" value="{{bg_color}}">

            <div class="tool-item">🎨 Background Style</div>
            <div class="tool-item">🔤 Typography</div>
            <div class="tool-item">📱 Responsive Layout</div>

            <hr style="border-color:#293b55;margin:20px 0;">

            <h3>Publishing</h3>
            <p class="muted">Save your design before publishing.</p>

            <button type="submit" form="page-editor">Save Design</button>
        </div>

    </div>
    </form>

    <script>
    const headlineInput = document.getElementById("headline-input");
    const descriptionInput = document.getElementById("description-input");
    const buttonInput = document.getElementById("button-input");
    const bgInput = document.getElementById("bg-input");

    headlineInput.addEventListener("input", function(){
        document.getElementById("preview-headline").textContent = this.value;
    });

    descriptionInput.addEventListener("input", function(){
        document.getElementById("preview-description").textContent = this.value;
    });

    buttonInput.addEventListener("input", function(){
        document.getElementById("preview-button").textContent = this.value;
    });

    bgInput.addEventListener("input", function(){
        document.getElementById("preview-page").style.background = this.value;
    });
    </script>

    <div class="editor-panel" style="margin-top:20px;">
        <h3>🚀 Publish Your Landing Page</h3>
        <p class="muted">Make your saved landing page available through a public link.</p>
        <form method="post" action="/publish/{{slug}}">
            <button type="submit" style="background:#16a37a;">Publish Landing Page</button>
        </form>
        <p><small>Public URL: /p/{{slug}}</small></p>
    </div>
    """.replace("{{title}}", p["title"])
       .replace("{{headline}}", data.get("headline", p["title"]))
       .replace("{{description}}", data.get("description", "Describe your offer here."))
       .replace("{{button_text}}", data.get("button_text", "Get Started"))
       .replace("{{button_url}}", data.get("button_url", ""))
       .replace("{{bg_color}}", data.get("bg_color", "#101b32"))
       .replace("{{slug}}", slug),
       "TrackGrow Visual Editor")      
@app.route("/publish/<slug>", methods=["POST"])
@login_required
def publish_page(slug):
    with db() as con:
        p = con.execute(
            "SELECT * FROM pages WHERE slug=? AND user_id=?",
            (slug, session["user_id"])
        ).fetchone()

        if not p:
            abort(404)

        con.execute("""
            UPDATE pages
            SET status='published', published_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (p["id"],))

    flash("Your landing page is now published!")
    return redirect(url_for("edit_page", slug=slug))


@app.route("/p/<slug>")
def public_page(slug):
    from markupsafe import escape

    with db() as con:
        p = con.execute(
            "SELECT * FROM pages WHERE slug=? AND status='published'",
            (slug,)
        ).fetchone()

    if not p:
        abort(404)

    data = json.loads(p["page_data"] or "{}")

    headline = escape(data.get("headline", p["title"]))
    description = escape(data.get("description", ""))
    button_text = escape(data.get("button_text", "Get Started"))

    button_url = data.get("button_url", "")
    if not button_url.startswith(("https://", "http://")):
        button_url = "#"

    return page(f"""
    <section class="hero">
        <h1>{headline}</h1>
        <p>{description}</p>
        <a class="btn" href="{escape(button_url)}">{button_text}</a>
    </section>
    """, escape(p["title"]))
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
