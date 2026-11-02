"""
Security regression tests for NoteVault.

Each test uses a harmless probe and asserts the SAFE behaviour, so against the
baseline app the security tests fail (evidence the weakness exists) and after
remediation they pass. Run from starter-app/:  python -m pytest -q tests
"""
import base64
import hashlib
import inspect
import json
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as nv  # noqa: E402


@pytest.fixture
def client():
    nv.app.testing = True
    nv.seed()
    if hasattr(nv, "FAILED_LOGINS"):
        nv.FAILED_LOGINS.clear()
    with nv.app.test_client() as c:
        yield c


def login(c, username, password):
    return c.post("/login", data={"username": username, "password": password})


def note_id(owner, title):
    con = nv.db()
    row = con.execute("SELECT id FROM notes WHERE owner = ? AND title = ?", (owner, title)).fetchone()
    con.close()
    return row["id"]


def unsigned_token(sub):
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return "%s.%s." % (b64({"alg": "none", "typ": "JWT"}), b64({"sub": sub}))


def set_session(c, token):
    if "server_name" in inspect.signature(c.set_cookie).parameters:
        c.set_cookie("localhost", "session", token)     # Werkzeug < 2.3
    else:
        c.set_cookie("session", token)


# ---------------------------------------------------------------- findings

def test_f01_login_sql_injection(client):
    r = login(client, "admin' --", "wrong")
    assert r.status_code in (400, 401)


def test_f02_search_sql_injection(client):
    login(client, "alice", "alicepw")
    r = client.get("/search", query_string={"q": "zzz' OR '1'='1' --"})
    assert b"hunter2" not in r.data


def test_f03_template_injection(client):
    login(client, "alice", "alicepw")
    client.post("/notes", data={"title": "t", "body": "calc {{ 7*7 }}"})
    r = client.get("/search", query_string={"q": "calc"})
    assert b"calc 49" not in r.data
    assert b"{{ 7*7 }}" in r.data


def test_f04_export_command_injection(client):
    login(client, "alice", "alicepw")
    r = client.get("/export", query_string={"fmt": "txt; echo INJECTED-MARKER"})
    assert b"INJECTED-MARKER" not in r.data or b"exporting" not in r.data
    assert r.status_code == 400


def test_f05_unsigned_jwt_rejected(client):
    set_session(client, unsigned_token("admin"))
    assert client.get("/admin").status_code in (401, 403)


def test_f06_default_secret_rejected(client):
    import jwt
    tok = jwt.encode({"sub": "admin"}, "notevault-dev-secret", algorithm="HS256")
    tok = tok.decode() if isinstance(tok, bytes) else tok
    set_session(client, tok)
    assert client.get("/admin").status_code in (401, 403)


def test_f07_register_cannot_choose_role(client):
    client.post("/register", data={"username": "mallory", "password": "pw-123456", "role": "admin"})
    login(client, "mallory", "pw-123456")
    assert client.get("/admin").status_code == 403


def test_f08_duplicate_username_rejected(client):
    r = client.post("/register", data={"username": "alice", "password": "other-pw-1"})
    assert r.status_code in (400, 409)
    assert login(client, "alice", "other-pw-1").status_code == 401


def test_f09_cannot_read_other_users_note(client):
    login(client, "alice", "alicepw")
    r = client.get("/api/notes/%d" % note_id("admin", "infra"))
    assert r.status_code == 404


def test_f10_stored_xss_escaped(client):
    login(client, "alice", "alicepw")
    client.post("/notes", data={"title": "<script>probe()</script>", "body": "b"})
    r = client.get("/")
    assert b"<script>probe()</script>" not in r.data
    assert b"&lt;script&gt;" in r.data


def test_f11_passwords_not_md5(client):
    con = nv.db()
    stored = con.execute("SELECT password FROM users WHERE username = 'alice'").fetchone()["password"]
    con.close()
    assert stored != hashlib.md5(b"alicepw").hexdigest()


def test_f12_debug_off_by_default():
    assert getattr(nv, "DEBUG", True) is False


def test_f13_session_cookie_flags(client):
    r = login(client, "alice", "alicepw")
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_f13_logout_requires_post(client):
    login(client, "alice", "alicepw")
    assert client.get("/logout").status_code == 405


def test_f14_admin_does_not_expose_hashes(client):
    login(client, "admin", "admin123")
    users = client.get("/admin").get_json()
    assert users and all("password" not in u for u in users)


def test_f15_login_rate_limited(client):
    for _ in range(5):
        login(client, "alice", "wrong")
    assert login(client, "alice", "alicepw").status_code == 429


def test_f18_register_missing_password_is_400(client):
    r = client.post("/register", data={"username": "nopw"})
    assert r.status_code == 400


def test_f19_failed_login_logged(client, caplog):
    with caplog.at_level(logging.WARNING):
        login(client, "alice", "wrong")
    assert any("login failed" in m for m in caplog.messages)


# ------------------------------------------------- normal behaviour still works

def test_regression_user_flow(client):
    assert client.post("/register", data={"username": "bob", "password": "bob-pw-123"}).status_code == 302
    assert login(client, "bob", "bob-pw-123").status_code == 302
    client.post("/notes", data={"title": "todo", "body": "buy bread"})
    home = client.get("/")
    assert b"todo" in home.data and b"buy bread" in home.data
    assert b"buy bread" in client.get("/search", query_string={"q": "bread"}).data
    own = client.get("/api/notes/%d" % note_id("bob", "todo")).get_json()
    assert own["body"] == "buy bread" and own["owner"] == "bob"
    for fmt in ("txt", "csv", "json"):
        r = client.get("/export", query_string={"fmt": fmt})
        assert r.status_code == 200 and b"buy bread" in r.data
    assert client.post("/logout").status_code == 302
    assert client.get("/api/notes/1").status_code == 401


def test_regression_admin_panel(client):
    login(client, "admin", "admin123")
    names = [u["username"] for u in client.get("/admin").get_json()]
    assert "alice" in names and "admin" in names
    login(client, "alice", "alicepw")
    assert client.get("/admin").status_code == 403


def test_regression_team_marker_seeded(client):
    con = nv.db()
    body = con.execute("SELECT body FROM notes WHERE title = 'build-tag'").fetchone()["body"]
    con.close()
    assert nv.team_marker() in body
