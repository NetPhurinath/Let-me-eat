"""
NoteVault — a small team note-sharing web app + JSON API (term-project starter).

This is your TERM-PROJECT TARGET. It is a normal-looking app that contains several
realistic security weaknesses. Your job (see project/README.md): threat-model it,
find and document the vulnerabilities, fix them, and harden the build/release.

We do NOT list the vulnerabilities here — finding them is the assignment.

Run:  docker compose up   (then http://localhost:8080)
"""
import csv
import datetime
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3

import jwt  # PyJWT
from flask import Flask, request, jsonify, render_template_string, redirect, make_response
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
DB = "/tmp/notevault.db"
# Key used to sign session tokens. Supplied at runtime (APP_SECRET); without it a random
# per-process key is used, so sessions simply don't survive a restart.
SECRET = os.environ.get("APP_SECRET") or secrets.token_hex(32)
SESSION_TTL = datetime.timedelta(hours=1)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE") == "1"  # set to 1 when served over HTTPS

USERNAME_RE = re.compile(r"[A-Za-z0-9._-]{1,32}")
MIN_PASSWORD = 8
DUMMY_HASH = generate_password_hash(secrets.token_hex(16))

# Anti-copying: every team's build is seeded with a marker derived from their own TEAM_ID, so
# any evidence a team submits (SQLi dump, IDOR response, admin-panel screenshot) that shows the
# admin's notes carries a value traceable to exactly one team — see instructor/anti-cheating.md.
TEAM_ID = os.environ.get("TEAM_ID", "unassigned")
TEAM_SALT = os.environ.get("TEAM_SALT", "notevault-anti-copy-dev-salt")


def team_marker():
    return hmac.new(TEAM_SALT.encode(), TEAM_ID.encode(), hashlib.sha256).hexdigest()[:12]


PAGE = """
<!doctype html><title>NoteVault</title>
<h1>NoteVault</h1>
{% if user %}<p>Signed in as <b>{{ user }}</b>
  {% if is_admin %}· <a href="/admin">admin</a>{% endif %}</p>
<form method=post action="/logout"><button>Logout</button></form>
<form method=post action="/notes"><input name=title placeholder=title>
  <input name=body placeholder=note><button>Add note</button></form>
<h3>Your notes</h3>
{% for n in notes %}<li>#{{ n.id }} <b>{{ n.title }}</b>: {{ n.body }}</li>{% endfor %}
<form action="/search"><input name=q placeholder="search notes"><button>Search</button></form>
{% else %}
<form method=post action="/login">user <input name=username> pass <input name=password type=password>
  <button>Login</button></form>
<form method=post action="/register">new: <input name=username> <input name=password type=password>
  <button>Register</button></form>
{% endif %}
"""

SEARCH_PAGE = """
<a href=/>back</a><ul>{% for r in rows %}<li>{{ r.title }}: {{ r.body }}</li>{% endfor %}</ul>
"""


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def seed():
    con = db()
    con.executescript(
        "DROP TABLE IF EXISTS users; DROP TABLE IF EXISTS notes;"
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT, role TEXT);"
        "CREATE TABLE notes (id INTEGER PRIMARY KEY, owner TEXT, title TEXT, body TEXT);"
    )
    con.executemany("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                    [("alice", generate_password_hash("alicepw"), "user"),
                     ("admin", generate_password_hash("admin123"), "admin")])
    con.executemany("INSERT INTO notes (owner, title, body) VALUES (?,?,?)",
                    [("alice", "groceries", "milk, eggs"),
                     ("admin", "infra", "prod db password is hunter2"),
                     ("admin", "build-tag", "team=%s marker=%s" % (TEAM_ID, team_marker()))])
    con.commit()
    con.close()


def current_user():
    tok = request.cookies.get("session", "")
    if not tok:
        return None
    try:
        data = jwt.decode(tok, SECRET, algorithms=["HS256"])
        return data.get("sub")
    except Exception:
        return None


def role_of(username):
    con = db()
    r = con.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    con.close()
    return r["role"] if r else None


@app.route("/")
def home():
    user = current_user()
    notes = []
    if user:
        con = db()
        notes = con.execute("SELECT id,title,body FROM notes WHERE owner = ?", (user,)).fetchall()
        con.close()
    return render_template_string(PAGE, user=user, is_admin=(user and role_of(user) == "admin"),
                                  notes=notes)


def credentials():
    """Username/password from a form or JSON body, as strings ('' if missing)."""
    body = request.get_json(silent=True) or {}
    username = request.form.get("username") or body.get("username") or ""
    password = request.form.get("password") or body.get("password") or ""
    return (username if isinstance(username, str) else "",
            password if isinstance(password, str) else "")


@app.route("/register", methods=["POST"])
def register():
    username, password = credentials()
    if not USERNAME_RE.fullmatch(username):
        return "username must be 1-32 letters, digits, '.', '_' or '-'", 400
    if not MIN_PASSWORD <= len(password) <= 128:
        return "password must be %d-128 characters" % MIN_PASSWORD, 400
    con = db()
    try:
        # role is always "user"; admins are provisioned server-side, never by the client
        con.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                    (username, generate_password_hash(password), "user"))
        con.commit()
    except sqlite3.IntegrityError:
        return "username already taken", 409
    finally:
        con.close()
    return redirect("/")


@app.route("/login", methods=["POST"])
def login():
    username, password = credentials()
    con = db()
    row = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    con.close()
    # check a dummy hash for unknown users so response time doesn't reveal which names exist
    if not check_password_hash(row["password"] if row else DUMMY_HASH, password) or not row:
        return "login failed", 401
    tok = jwt.encode({"sub": username, "exp": datetime.datetime.now(datetime.timezone.utc) + SESSION_TTL},
                     SECRET, algorithm="HS256")
    resp = make_response(redirect("/"))
    resp.set_cookie("session", tok, max_age=int(SESSION_TTL.total_seconds()),
                    httponly=True, samesite="Lax", secure=COOKIE_SECURE)
    return resp


@app.route("/logout", methods=["POST"])
def logout():
    resp = make_response(redirect("/"))
    resp.delete_cookie("session")
    return resp


@app.route("/notes", methods=["POST"])
def add_note():
    user = current_user()
    if not user:
        return "auth required", 401
    title = request.form.get("title", "")
    body = request.form.get("body", "")
    con = db()
    con.execute("INSERT INTO notes (owner,title,body) VALUES (?,?,?)", (user, title, body))
    con.commit()
    con.close()
    return redirect("/")


@app.route("/api/notes/<int:nid>")
def api_note(nid):
    if not current_user():
        return jsonify(error="auth required"), 401
    con = db()
    r = con.execute("SELECT id,owner,title,body FROM notes WHERE id = ?", (nid,)).fetchone()
    con.close()
    return (jsonify(dict(r)) if r else (jsonify(error="not found"), 404))


@app.route("/search")
def search():
    user = current_user()
    if not user:
        return "auth required", 401
    term = request.args.get("q", "")
    con = db()
    rows = con.execute("SELECT id,title,body FROM notes WHERE owner = ? AND body LIKE ?",
                       (user, "%" + term + "%")).fetchall()
    con.close()
    return render_template_string(SEARCH_PAGE, rows=rows)


@app.route("/admin")
def admin():
    user = current_user()
    if not user or role_of(user) != "admin":
        return "forbidden", 403
    con = db()
    rows = con.execute("SELECT id,username,password,role FROM users").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])


EXPORT_TYPES = {"txt": "text/plain", "csv": "text/csv", "json": "application/json"}


@app.route("/export")
def export():
    user = current_user()
    if not user:
        return "auth required", 401
    fmt = request.args.get("fmt", "txt")
    if fmt not in EXPORT_TYPES:
        return "unsupported format (use txt, csv or json)", 400
    # convenience "export" feature — built in Python, no shell involved
    con = db()
    rows = [dict(r) for r in con.execute(
        "SELECT id,title,body FROM notes WHERE owner = ?", (user,)).fetchall()]
    con.close()
    if fmt == "json":
        out = json.dumps(rows)
    elif fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["id", "title", "body"])
        w.writeheader()
        w.writerows(rows)
        out = buf.getvalue()
    else:
        out = "".join("#%d %s: %s\n" % (r["id"], r["title"], r["body"]) for r in rows)
    resp = make_response(out)
    resp.headers["Content-Type"] = EXPORT_TYPES[fmt] + "; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=notes.%s" % fmt
    return resp


if __name__ == "__main__":
    seed()
    app.run(host="0.0.0.0", port=8080, debug=True)
