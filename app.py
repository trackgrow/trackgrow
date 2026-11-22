import os
import json
import sqlite3
import secrets
from functools import wraps
from flask import Flask, request, redirect, url_for, render_template_string, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import escape

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB_PATH = os.environ.get("DATABASE_PATH", "trackgrow.db")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").lower().strip()

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'client'
        );
        CREATE TABLE IF NOT EXISTS pages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            template_id TEXT DEFAULT 'blank',
            page_data TEXT DEFAULT '{}',
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS page_views(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS plans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER DEFAULT 0,
            page_limit INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS subscriptions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_id INTEGER,
            status TEXT DEFAULT 'pending'
        );
        """)
        for table, column, definition in [
            ("users", "role", "TEXT DEFAULT 'client'"),
            ("pages", "template_id", "TEXT DEFAULT 'blank'"),
            ("pages", "page_data", "TEXT DEFAULT '{}'"),
            ("pages", "status", "TEXT DEFAULT 'draft'")
        ]:
            try:
                con.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )
            except sqlite3.OperationalError:
                pass

        con.execute("INSERT OR IGNORE INTO plans(name,price,page_limit) VALUES('Free',0,1)")
        con.execute("INSERT OR IGNORE INTO plans(name,price,page_limit) VALUES('Starter',299,5)")
        con.execute("INSERT OR IGNORE INTO plans(name,price,page_limit) VALUES('Pro',799,25)")

        if ADMIN_EMAIL:
            con.execute(
                "UPDATE users SET role='admin' WHERE lower(email)=?",
                (ADMIN_EMAIL,)
            )

init_db()

STYLE = """
<style>
*{box-sizing:border-box}
body{margin:0;background:#0a1020;color:#eef4ff;font-family:Arial}
a{color:#a9bdff;text-decoration:none}
nav{padding:18px 5%;background:#101b31;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:24px;font-weight:bold;color:white}
main{max-width:1150px;margin:30px auto;padding:0 16px}
.hero{padding:65px 25px;text-align:center;background:linear-gradient(135deg,#1b3154,#11182d);border-radius:20px}
h1{font-size:clamp(30px,5vw,50px)}
.panel,.template{background:#111b31;border:1px solid #263957;border-radius:15px;padding:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:15px}
.btn,button{display:inline-block;background:#6d8cff;color:white;padding:12px 18px;border:0;border-radius:9px;font-weight:bold;cursor:pointer}
.secondary{background:#263957}
input,textarea{width:100%;padding:12px;background:#0b1426;color:white;border:1px solid #263957;border-radius:8px;margin:7px 0 15px}
label{font-weight:bold;font-size:13px}
.muted{color:#9aabc5}
.stat{font-size:30px;font-weight:bold}
.preview-tile{height:120px;background:linear-gradient(135deg,#294b7d,#18233b);display:grid;place-items:center;border-radius:10px;font-weight:bold}
footer{text-align:center;padding:30px;color:#9aabc5}
@media(max-width:600px){main{margin:18px auto}nav{padding:15px}}
</style>
"""

def page(body, title="TrackGrow", **context):
    email = session.get("email")
    links = (
        f'<span>{escape(email)}</span> <a href="/dashboard">Dashboard</a> <a href="/logout">Logout</a>'
        if email else
        '<a href="/login">Login</a> <a href="/register">Register</a>'
    )
    return render_template_string("""
    <!doctype html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{{title}}</title>
    """ + STYLE + """
    </head>
    <body>
    <nav>
      <a class="logo" href="/">TrackGrow</a>
      <div>""" + links + """</div>
    </nav>
    <main>
    {% with messages=get_flashed_messages() %}
      {% for message in messages %}
        <p class="muted">{{message}}</p>
      {% endfor %}
    {% endwith %}
    """ + body + """
    </main>
    <footer>TrackGrow · Track Every Click. Measure Every Join.</footer>
    </body>
    </html>
    """, title=title, **context)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login")
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login")
        with db() as con:
            user = con.execute(
                "SELECT role FROM users WHERE id=?",
                (session["user_id"],)
            ).fetchone()
        if not user or user["role"] != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

TEMPLATES = {
    "digital": {
        "name":"Digital Product",
        "headline":"Launch Your Digital Product",
        "description":"Showcase your ebook or digital download.",
        "button_text":"Get It Now",
        "bg_color":"#101b32"
    },
    "course": {
        "name":"Course & Coaching",
        "headline":"Learn A New Skill",
        "description":"Present your course and coaching program.",
        "button_text":"Join Now",
        "bg_color":"#18243e"
    },
    "agency": {
        "name":"Agency & Services",
        "headline":"Grow Your Business",
        "description":"Showcase your professional services.",
        "button_text":"Book A Call",
        "bg_color":"#111827"
    },
    "telegram": {
        "name":"Telegram Promotion",
        "headline":"Join Our Telegram Community",
        "description":"Join our community today.",
        "button_text":"Join Telegram",
        "bg_color":"#10263b"
    },
    "blank": {
        "name":"Blank Page",
        "headline":"Your Headline Here",
        "description":"Write your description here.",
        "button_text":"Get Started",
        "bg_color":"#101b32"
    }
}

@app.route("/")
def home():
    return page("""
    <section class="hero">
      <p>LANDING PAGE BUILDER</p>
      <h1>Build Pages. Track Growth.</h1>
      <p class="muted">Create professional landing pages and publish them online.</p>
      <a class="btn" href="/register">Start Building Free</a>
      <a class="btn secondary" href="/pricing">View Plans</a>
    </section>
    <h2>Everything you need</h2>
    <div class="grid">
      <div class="panel"><h3>Visual Builder</h3><p class="muted">Customize your pages.</p></div>
      <div class="panel"><h3>Code Mode</h3><p class="muted">Edit HTML, CSS and JS.</p></div>
      <div class="panel"><h3>Analytics</h3><p class="muted">Track your page views.</p></div>
    </div>
    """)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").lower().strip()
        password = request.form.get("password","")
        if len(password) < 8:
            flash("Password must have at least 8 characters.")
        else:
            try:
                role = "admin" if ADMIN_EMAIL and email == ADMIN_EMAIL else "client"
                with db() as con:
                    con.execute(
                        "INSERT INTO users(email,password_hash,role) VALUES(?,?,?)",
                        (email,generate_password_hash(password),role)
                    )
                flash("Account created. Please login.")
                return redirect("/login")
            except sqlite3.IntegrityError:
                flash("Email already registered.")

    return page("""
    <div class="panel" style="max-width:480px;margin:auto">
    <h2>Create Account</h2>
    <form method="post">
    <label>Email</label>
    <input name="email" type="email" required>
    <label>Password</label>
    <input name="password" type="password" minlength="8" required>
    <button>Create Account</button>
    </form>
    </div>
    """)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").lower().strip()
        with db() as con:
            user = con.execute(
                "SELECT * FROM users WHERE lower(email)=?",
                (email,)
            ).fetchone()

        if user and check_password_hash(
            user["password_hash"],request.form.get("password","")
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            return redirect("/dashboard")
        flash("Invalid email or password.")

    return page("""
    <div class="panel" style="max-width:480px;margin:auto">
    <h2>Client Login</h2>
    <form method="post">
    <label>Email</label>
    <input name="email" type="email" required>
    <label>Password</label>
    <input name="password" type="password" required>
    <button>Login</button>
    </form>
    </div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        pages = con.execute("""
        SELECT p.*,
        (SELECT COUNT(*) FROM page_views v WHERE v.page_id=p.id) AS views
        FROM pages p WHERE p.user_id=? ORDER BY p.id DESC
        """,(session["user_id"],)).fetchall()

        plan = con.execute("""
        SELECT pl.name,pl.page_limit
        FROM subscriptions s JOIN plans pl ON pl.id=s.plan_id
        WHERE s.user_id=? AND s.status='active'
        ORDER BY s.id DESC LIMIT 1
        """,(session["user_id"],)).fetchone()

        if not plan:
            plan = con.execute(
                "SELECT name,page_limit FROM plans WHERE name='Free'"
            ).fetchone()

    cards = ""
    for p in pages:
        cards += f"""
        <div class="panel">
        <h3>{escape(p['title'])}</h3>
        <p class="muted">{escape(p['status'])} · {p['views']} views</p>
        <a class="btn" href="/editor/{escape(p['slug'])}">Edit</a>
        <a class="btn secondary" href="/p/{escape(p['slug'])}">Open</a>
        </div>
        """

    if not cards:
        cards = '<div class="panel">No pages created yet.</div>'

    return page(f"""
    <h1>Your Dashboard</h1>
    <div class="grid">
      <div class="panel"><p class="muted">Landing Pages</p><div class="stat">{len(pages)}</div></div>
      <div class="panel"><p class="muted">Current Plan</p><div class="stat">{escape(plan['name'])}</div></div>
      <div class="panel"><p class="muted">Page Limit</p><div class="stat">{plan['page_limit']}</div></div>
    </div>
    <p><a class="btn" href="/templates">+ Create Landing Page</a></p>
    <h2>Your Pages</h2>
    <div class="grid">{cards}</div>
    <p><a href="/pricing">Upgrade Plan</a></p>
    """)

@app.route("/templates")
@login_required
def templates():
    cards = ""
    for key,t in TEMPLATES.items():
        cards += f"""
        <div class="template">
        <div class="preview-tile">{escape(t['name'])}</div>
        <h3>{escape(t['name'])}</h3>
        <a class="btn" href="/create/{key}">Use Template</a>
        </div>
        """
    return page("<h1>Choose Template</h1><div class='grid'>"+cards+"</div>")

@app.route("/create/<template_id>",methods=["GET","POST"])
@login_required
def create_page(template_id):
    if template_id not in TEMPLATES:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title","").strip()[:100]
        if not title:
            flash("Enter a page name.")
        else:
            with db() as con:
                active = con.execute("""
                SELECT pl.page_limit FROM subscriptions s
                JOIN plans pl ON pl.id=s.plan_id
                WHERE s.user_id=? AND s.status='active'
                ORDER BY s.id DESC LIMIT 1
                """,(session["user_id"],)).fetchone()
                limit = active["page_limit"] if active else 1
                count = con.execute(
                    "SELECT COUNT(*) n FROM pages WHERE user_id=?",
                    (session["user_id"],)
                ).fetchone()["n"]

                if count >= limit:
                    flash("Page limit reached. Please upgrade.")
                    return redirect("/pricing")

                slug = secrets.token_urlsafe(7).replace("-","").replace("_","")[:10]
                data = dict(TEMPLATES[template_id])
                data.update({
                    "custom_html":"",
                    "custom_css":"",
                    "custom_js":"",
                    "sections":[]
                })
                con.execute("""
                INSERT INTO pages(user_id,title,slug,template_id,page_data,status)
                VALUES(?,?,?,?,?,'draft')
                """,(session["user_id"],title,slug,template_id,json.dumps(data)))

            return redirect(url_for("edit_page",slug=slug))

    return page(f"""
    <div class="panel" style="max-width:550px;margin:auto">
    <h2>Create {escape(TEMPLATES[template_id]['name'])} Page</h2>
    <form method="post">
    <label>Page Name</label>
    <input name="title" required>
    <button>Create & Edit</button>
    </form>
    </div>
    """)
@app.route("/editor/<slug>", methods=["GET","POST"])
@login_required
def edit_page(slug):
    with db() as con:
        p = con.execute(
            "SELECT * FROM pages WHERE slug=? AND user_id=?",
            (slug,session["user_id"])
        ).fetchone()

        if not p:
            abort(404)

        data = json.loads(p["page_data"] or "{}")

        if request.method == "POST":
            data.update({
                "headline":request.form.get("headline","")[:200],
                "description":request.form.get("description","")[:2000],
                "button_text":request.form.get("button_text","")[:80],
                "button_url":request.form.get("button_url","")[:1000],
                "bg_color":request.form.get("bg_color","#101b32"),
                "custom_html":request.form.get("custom_html","")[:50000],
                "custom_css":request.form.get("custom_css","")[:30000],
                "custom_js":request.form.get("custom_js","")[:30000],
            })
            con.execute(
                "UPDATE pages SET page_data=? WHERE slug=? AND user_id=?",
                (json.dumps(data),slug,session["user_id"])
            )
            flash("Page saved successfully.")
            return redirect("/editor/"+slug)

    preview = json.dumps(data).replace("</","<\\/")

    body = """
    <h1>Page Editor</h1>
    <p class="muted">Customize your landing page and publish it.</p>
    <div class="grid">
      <div class="panel">
        <h2>Visual Editor</h2>
        <form method="post">
          <label>Headline</label>
          <input name="headline" value="{{data.get('headline','')}}" required>
          <label>Description</label>
          <textarea name="description" rows="4">{{data.get('description','')}}</textarea>
          <label>Button Text</label>
          <input name="button_text" value="{{data.get('button_text','')}}">
          <label>Button URL</label>
          <input name="button_url" value="{{data.get('button_url','')}}" placeholder="https://example.com">
          <label>Background Color</label>
          <input name="bg_color" type="color" value="{{data.get('bg_color','#101b32')}}">
          <button type="submit">Save Visual Changes</button>
        </form>
      </div>
      <div class="panel">
        <h2>Live Preview</h2>
        <iframe id="visualPreview" sandbox="allow-scripts"
          style="width:100%;height:420px;background:white;border:0;border-radius:10px"></iframe>
      </div>
    </div>

    <div class="panel" style="margin-top:20px">
      <h2>HTML / CSS / JavaScript Code Mode</h2>
      <form method="post">
        <label>HTML Code</label>
        <textarea name="custom_html" rows="8">{{data.get('custom_html','')}}</textarea>
        <label>CSS Code</label>
        <textarea name="custom_css" rows="8">{{data.get('custom_css','')}}</textarea>
        <label>JavaScript Code</label>
        <textarea name="custom_js" rows="8">{{data.get('custom_js','')}}</textarea>
        <button type="submit">Save Code</button>
      </form>
      <p class="muted">Custom code runs inside a sandboxed preview on your published page.</p>
    </div>

    <div class="panel" style="margin-top:20px">
      <h2>Publish Your Landing Page</h2>
      <p class="muted">Make your saved landing page available through a public link.</p>
      <form method="post" action="/publish/{{slug}}">
        <button type="submit">Publish Page</button>
      </form>
      <p><a href="/p/{{slug}}" target="_blank">Open Public Page</a></p>
      <p><a href="/dashboard">Back to Dashboard</a></p>
    </div>

    <script>
    const pageData = {{preview|safe}};
    const frame = document.getElementById("visualPreview");

    function renderPreview(){
      const esc = s => String(s || "").replace(/[&<>"']/g, c =>
        ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])
      );
      const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width">
      <style>
      body{font-family:Arial;margin:0;padding:35px;text-align:center;color:white}
      h1{font-size:32px}p{line-height:1.6}
      a{display:inline-block;background:#6d8cff;color:white;padding:12px 20px;border-radius:8px;text-decoration:none}
      </style></head><body style="background:${esc(pageData.bg_color || '#101b32')}">
      <h1>${esc(pageData.headline || '')}</h1>
      <p>${esc(pageData.description || '')}</p>
      <a>${esc(pageData.button_text || 'Get Started')}</a>
      </body></html>`;
      frame.srcdoc = html;
    }
    renderPreview();
    </script>
    """

    return render_template_string(
        page(body),
        data=data,
        slug=slug,
        preview=preview
    )

@app.route("/publish/<slug>", methods=["POST"])
@login_required
def publish_page(slug):
    with db() as con:
        p = con.execute(
            "SELECT id FROM pages WHERE slug=? AND user_id=?",
            (slug,session["user_id"])
        ).fetchone()
        if not p:
            abort(404)
        con.execute(
            "UPDATE pages SET status='published' WHERE slug=? AND user_id=?",
            (slug,session["user_id"])
        )
    flash("Your page is now published.")
    return redirect("/editor/"+slug)

@app.route("/p/<slug>")
def public_page(slug):
    with db() as con:
        p = con.execute(
            "SELECT * FROM pages WHERE slug=? AND status='published'",
            (slug,)
        ).fetchone()
        if not p:
            abort(404)
        con.execute(
            "INSERT INTO page_views(page_id) VALUES(?)",
            (p["id"],)
        )

    data = json.loads(p["page_data"] or "{}")

    custom_html = data.get("custom_html","")
    custom_css = data.get("custom_css","")
    custom_js = data.get("custom_js","")

    if custom_html or custom_css or custom_js:
        custom_document = """<!doctype html>
        <html><head><meta name="viewport" content="width=device-width">
        <style>""" + custom_css + """</style></head>
        <body>""" + custom_html + """
        <script>""" + custom_js + """</script>
        </body></html>"""

        return render_template_string("""
        <!doctype html><html><head>
        <meta name="viewport" content="width=device-width">
        <title>{{title}}</title></head>
        <body style="margin:0">
        <iframe sandbox="allow-scripts"
        style="width:100%;height:100vh;border:0"
        srcdoc="{{document|e}}"></iframe>
        </body></html>
        """,title=p["title"],document=custom_document)

    return render_template_string("""
    <!doctype html><html><head>
    <meta name="viewport" content="width=device-width">
    <title>{{title}}</title>
    <style>
    body{margin:0;font-family:Arial;color:white;text-align:center;
    padding:90px 20px;background:{{bg}}}
    h1{font-size:40px}
    p{line-height:1.7;max-width:650px;margin:20px auto}
    a{display:inline-block;background:#6d8cff;color:white;
    padding:14px 25px;border-radius:8px;text-decoration:none}
    </style></head><body>
    <h1>{{headline}}</h1>
    <p>{{description}}</p>
    <a href="{{button_url}}">{{button_text}}</a>
    </body></html>
    """,
    title=p["title"],
    headline=data.get("headline",""),
    description=data.get("description",""),
    bg=data.get("bg_color","#101b32"),
    button_text=data.get("button_text","Get Started"),
    button_url=data.get("button_url") or "#"
    )

@app.route("/pricing")
def pricing():
    with db() as con:
        plans = con.execute("SELECT * FROM plans ORDER BY price").fetchall()

    cards = ""
    for plan in plans:
        cards += f"""
        <div class="panel">
          <h2>{escape(plan['name'])}</h2>
          <div class="stat">₹{plan['price']}</div>
          <p>{plan['page_limit']} landing pages</p>
          <p class="muted">Plan activation is currently manual.</p>
          <a class="btn" href="/request-plan/{plan['id']}">Choose Plan</a>
        </div>
        """
    return page("<h1>Plans & Pricing</h1><div class='grid'>"+cards+"</div>")

@app.route("/request-plan/<int:plan_id>")
@login_required
def request_plan(plan_id):
    with db() as con:
        plan = con.execute(
            "SELECT * FROM plans WHERE id=?",
            (plan_id,)
        ).fetchone()
        if not plan:
            abort(404)
        con.execute(
            "INSERT INTO subscriptions(user_id,plan_id,status) VALUES(?,?,?)",
            (session["user_id"],plan_id,"pending")
        )
    flash("Plan request submitted. Admin approval is required.")
    return redirect("/dashboard")

@app.route("/admin")
@admin_required
def admin():
    with db() as con:
        users = con.execute(
            "SELECT id,email,role FROM users ORDER BY id DESC"
        ).fetchall()
        requests = con.execute("""
        SELECT s.id,u.email,pl.name,pl.price
        FROM subscriptions s
        JOIN users u ON u.id=s.user_id
        JOIN plans pl ON pl.id=s.plan_id
        WHERE s.status='pending'
        ORDER BY s.id DESC
        """).fetchall()

    user_rows = "".join(
        f"<tr><td>{u['id']}</td><td>{escape(u['email'])}</td><td>{escape(u['role'])}</td></tr>"
        for u in users
    )
    request_rows = "".join(
        f"""<tr><td>{escape(r['email'])}</td>
        <td>{escape(r['name'])}</td><td>₹{r['price']}</td>
        <td><form method="post" action="/admin/approve/{r['id']}">
        <button>Approve</button></form></td></tr>"""
        for r in requests
    )

    return page(f"""
    <h1>Admin Dashboard</h1>
    <div class="panel"><h2>Clients</h2>
    <table width="100%"><tr><th>ID</th><th>Email</th><th>Role</th></tr>
    {user_rows}</table></div>
    <div class="panel" style="margin-top:20px">
    <h2>Pending Plan Requests</h2>
    <table width="100%"><tr><th>Email</th><th>Plan</th><th>Price</th><th>Action</th></tr>
    {request_rows}</table></div>
    """)

@app.route("/admin/approve/<int:request_id>",methods=["POST"])
@admin_required
def approve_plan(request_id):
    with db() as con:
        req = con.execute(
            "SELECT * FROM subscriptions WHERE id=? AND status='pending'",
            (request_id,)
        ).fetchone()
        if not req:
            abort(404)
        con.execute(
            "UPDATE subscriptions SET status='cancelled' WHERE user_id=? AND status='active'",
            (req["user_id"],)
        )
        con.execute(
            "UPDATE subscriptions SET status='active' WHERE id=?",
            (request_id,)
        )
    flash("Plan activated.")
    return redirect("/admin")

@app.errorhandler(403)
def forbidden(error):
    return page("<h1>403 - Access denied</h1>"),403

@app.errorhandler(404)
def not_found(error):
    return page("<h1>404 - Page not found</h1>"),404

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
        
