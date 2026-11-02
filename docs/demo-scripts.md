# NoteVault — demo recording scripts (before / after)

Recordings for report §4/§5. Record each one with **Win + Shift + R** (Snipping Tool) or OBS, with your own
voice. Every video follows the same shape, about 2–3 minutes:

1. **Code** — open the baseline line(s) from §4 and say what's wrong (root cause, CWE/OWASP).
2. **Before** — run the probe against the **baseline** container on port **8081** and show the result.
3. **Fix** — show the commit diff (`git show <hash>`) and explain why it fixes the root cause.
4. **After** — run the *same* probe against the **fixed** container on port **8080** and show it fail safely.
5. **Still works** — show the normal feature still working.

All targets are local containers on your own machine (course ethics policy: never against anything else).

## One-time setup (Git Bash, repo root)

```bash
# fixed version (current main) on :8080
cd starter-app && docker compose up -d --build && cd ..
```

```bash
# baseline (commit 8725faa, before any fixes) on :8081
docker build -t notevault-baseline "https://github.com/NetPhurinath/Let-me-eat.git#8725faa:starter-app"
docker run -d --rm --name nvbase -p 8081:8080 -e TEAM_ID="Let me eat" notevault-baseline
```

Helper used below: log in and keep the cookie in a jar per port.

```bash
login() { curl -s -o /dev/null -c "/tmp/jar$1" -d "username=$2&password=$3" "localhost:$1/login" -w "login $2 on :$1 -> %{http_code}\n"; }
```

Automated evidence for every video (show at the end of each "after" section):

```bash
cd starter-app && docker run --rm -v "$(pwd -W):/src:ro" -w /src python:3.12-slim sh -c "pip install -q -r requirements.txt pytest && python -m pytest -v tests" ; cd ..
```

---

## V01 — F-01 SQL injection in login · commit `98587c7`
- **Code:** `app.py:128-130` (baseline) — `%`-formatted SQL.
- **Before:** `curl -i -d "username=admin' --&password=anything" localhost:8081/login` → `302` + `Set-Cookie` (logged in as admin).
- **After:** same against `:8080` → `401 login failed`.
- **Still works:** `login 8080 alice alicepw` → `302`.

## V02 — F-02 SQL injection in search · `98587c7`
- **Code:** `app.py:178-179`.
- **Before:** `login 8081 alice alicepw; curl -s -b /tmp/jar8081 --get --data-urlencode "q=zzz' OR '1'='1' --" localhost:8081/search` → shows admin's `infra … hunter2`.
- **After:** same on `:8080` → empty list.
- **Still works:** `--data-urlencode "q=milk"` → alice's groceries note.

## V03 — F-03 Template injection · `756d587`
- **Code:** `app.py:181-182` — note data concatenated into the template source.
- **Before (browser, :8081):** log in as alice, add a note with body `calc {{ 7*7 }}`, search `calc` → `calc 49`.
- **After (:8080):** same steps → shows `calc {{ 7*7 }}` literally.

## V04 — F-04 Command injection in export · `7e1c09b`
- **Code:** `app.py:202-203` — `subprocess.run(..., shell=True)`.
- **Before:** `login 8081 alice alicepw; curl -s -b /tmp/jar8081 --get --data-urlencode "fmt=txt; echo INJECTED-MARKER" localhost:8081/export` → marker on its own line.
- **After:** same on `:8080` → `400 unsupported format`.
- **Still works:** `fmt=csv` and `fmt=json` on `:8080` → alice's notes.

## V05 — F-05 `alg: none` allowed (latent) · `05f97cf`
- **Code:** `app.py:83` — `algorithms=["HS256", "none"]`.
- Explain: PyJWT 1.7.1 already rejects it because a key is passed, so this is **Low / defence in depth**. Show `test_f05_unsigned_jwt_rejected` passing on both versions and the one-line diff.

## V06 — F-06 Hard-coded JWT secret · `05f97cf`
- **Code:** `app.py:23`, `Dockerfile:5`.
- **Before:** `T=$(python -c "import jwt;print(jwt.encode({'sub':'admin'},'notevault-dev-secret',algorithm='HS256'))"); curl -s -b "session=$T" localhost:8081/admin` → user list. (Needs `pip install pyjwt` locally.)
- **After:** same on `:8080` → `forbidden`.

## V07 — F-07 Choose your own role · `f2f7f44`
- **Code:** `app.py:114-117`.
- **Before:** `curl -s -o /dev/null -d "username=mallory&password=pw-123456&role=admin" localhost:8081/register; login 8081 mallory pw-123456; curl -s -b /tmp/jar8081 localhost:8081/admin` → user list.
- **After:** same on `:8080` → `forbidden`.

## V08 — F-08 Duplicate username takeover · `f2f7f44`
- **Code:** `app.py:64` (no UNIQUE), `:116`.
- **Before:** `curl -s -o /dev/null -w "%{http_code}\n" -d "username=alice&password=newpass1" localhost:8081/register; login 8081 alice newpass1; curl -s -b /tmp/jar8081 localhost:8081/ | grep groceries` → the real alice's note.
- **After:** register on `:8080` → `409 username already taken`; login with `newpass1` → `401`.

## V09 — F-09 IDOR on notes API · `47a4ded`
- **Code:** `app.py:161-168`.
- **Before:** `login 8081 alice alicepw; curl -s -b /tmp/jar8081 localhost:8081/api/notes/2` → admin's `infra` note.
- **After:** same on `:8080` → `{"error":"not found"}` 404; `/api/notes/1` (alice's own) → 200.

## V10 — F-10 Stored XSS · `756d587`
- **Code:** `app.py:43` (`|safe`), `:104-105`.
- **Before (browser, :8081):** add a note titled `<img src=x onerror=alert(document.domain)>` → alert pops on the home page.
- **After (:8080):** same → the text is shown literally (view source: `&lt;img …`).

## V11 — F-11 MD5 passwords · `f2f7f44`
- **Code:** `app.py:68-69`, `:117`, `:129`.
- **Before:** `login 8081 admin admin123; curl -s -b /tmp/jar8081 localhost:8081/admin` → `0192023a7bbd73250516f069df18b500`; search that hash online / in a wordlist → `admin123`.
- **After:** `docker compose -f starter-app/docker-compose.yml exec notevault python -c "import sqlite3;print(sqlite3.connect('/tmp/notevault.db').execute('select password from users').fetchone()[0][:40])"` → `scrypt:…` salted hash.

## V12 — F-12 Debugger enabled · `72fdcf5`
- **Code:** `app.py:209` — `debug=True`.
- **Before:** `docker logs nvbase | head` → `Debugger is active!` + PIN; browser: submit the register form with an empty password on `:8081` → Werkzeug Debugger page with source and console icon.
- **After:** `docker compose -f starter-app/docker-compose.yml logs | head` → `Debug mode: off`; the same form on `:8080` → `400 password must be…`.

## V13 — F-13 Cookie flags, expiry, logout CSRF · `05f97cf`
- **Before:** `curl -si -d "username=alice&password=alicepw" localhost:8081/login | grep -i set-cookie` → only `Path=/`; `curl -s -o /dev/null -w "%{http_code}\n" localhost:8081/logout` → 302 (GET works cross-site).
- **After:** on `:8080` → `Max-Age=3600; HttpOnly; Path=/; SameSite=Lax`; `GET /logout` → 405. Show the Logout button still works in the browser.

## V14 — F-14 Admin exposes hashes · `47a4ded`
- **Before:** `login 8081 admin admin123; curl -s -b /tmp/jar8081 localhost:8081/admin` → includes `password`.
- **After:** same on `:8080` → `id`, `role`, `username` only.

## V15 — F-15 No brute-force limit · `72fdcf5`
- **Before:** `for i in 1 2 3 4 5 6; do login 8081 alice wrong$i; done; login 8081 alice alicepw` → still 302.
- **After:** same on `:8080` → five `401`s, then `429`, and the correct password is also refused (`429`) until the 15-minute window passes. Then show the log (V19).

## V16 — F-16 Vulnerable dependencies · `8bc8591`
- **Before:** `git show 8725faa:starter-app/requirements.txt > /tmp/req-old.txt; docker run --rm -v /tmp:/t python:3.12-slim sh -c "pip install -q pip-audit && pip-audit -r /t/req-old.txt"` → 81 known vulnerabilities.
- **After:** same with `starter-app/requirements.txt` → `No known vulnerabilities found`. Show the 21 tests passing.

## V17 — F-17 Container hardening · `036da1a`, `f2e3807`
- **Before:** `docker exec nvbase id` → `uid=0(root)`; `docker run --rm -v //var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL notevault-baseline | grep Total`.
- **After:** `docker compose -f starter-app/docker-compose.yml exec notevault id` → `uid=10001(notevault)`; Trivy on `starter-app-notevault` → 45 HIGH, 0 CRITICAL (explain these have no upstream fix yet).

## V18 — F-18 Input validation · `f2f7f44`
- **Before:** `curl -s -o /dev/null -w "%{http_code}\n" -d "username=x" localhost:8081/register` → 500.
- **After:** same on `:8080` → 400.

## V19 — F-19 Security logging · `72fdcf5`
- **Before:** fail a login on `:8081`, `docker logs nvbase | tail -3` → only a generic access line.
- **After:** fail a login on `:8080`, `docker compose -f starter-app/docker-compose.yml logs --tail 3` → `WARNING notevault: login failed for 'alice' from …`.

---

## Clean-up

```bash
docker stop nvbase
```

```bash
docker compose -f starter-app/docker-compose.yml down
```
