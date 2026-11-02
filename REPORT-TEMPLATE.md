# Term Project Report — Secure Build

> Fill in every section. Keep the headings. Total **100 pts** (see rubric at the end).
> This is **team work** (2–3). Do not share your report with other teams.

## Cover

| Field | Value |
|---|---|
| Team name | |
| Members (name + ID) | |
| Target application | |
| Repository URL | |
| Date | |

## AI-tool usage disclosure
*Academic integrity: state how you used any AI tools (ChatGPT, Copilot, etc.) — e.g. searching, coding, translating, drafting. "None" is a valid answer.*

| Tool | How it was used |
|---|---|
| | |

---

## 1. Executive Summary
*(½ page) What the app is, how many findings by severity, and the overall risk before vs. after your fixes.*

---

## 2. System Scope & Function

### 2.1 What the application does
**NoteVault** is a small team note-sharing web app with a JSON API, written as a single Flask
file (`starter-app/app.py`). Users register and log in; the app then issues a JWT stored in a
`session` cookie. Logged-in users can create notes, view their own notes on the home page, fetch a
note by ID through the API, and search their notes by keyword. Users with the `admin` role can
open an admin panel that lists all accounts, and there is an "export" convenience endpoint.

It runs as one Docker container on `http://localhost:8080`. Data lives in a SQLite file at
`/tmp/notevault.db`, which is recreated and seeded on every start with two accounts
(`alice` / `user` role and `admin` / `admin` role) and a few notes. One admin note holds the
per-team `TEAM_ID` marker.

We assess the **baseline (pre-remediation) build** at the repository's starting commit.

### 2.2 In-scope components

| Component | Details |
|---|---|
| Client | Web browser or any HTTP/API client (curl, Burp). HTML forms and JSON bodies are both accepted. |
| Web application | `starter-app/app.py` — Flask 2.0.1 on the Werkzeug development server, `debug=True`, bound to `0.0.0.0:8080`. Pages are built with `render_template_string`. |
| Session / authentication | PyJWT 1.7.1. Token `{"sub": <username>}` signed HS256 with the hard-coded `SECRET`; decode accepts algorithms `HS256` and `none`. Sent as the `session` cookie. |
| Database | SQLite file `/tmp/notevault.db`. Tables `users(id, username, password, role)` with MD5 password hashes, and `notes(id, owner, title, body)`. |
| OS shell | `/export` calls `subprocess.run(..., shell=True)`. |
| Configuration & secrets | `SECRET` in `app.py`; `APP_SECRET` in the `Dockerfile`; `TEAM_ID` and `TEAM_SALT` from `docker-compose.yml`. |
| Build & supply chain | `Dockerfile` (`python:3.12` base, runs as root, `COPY . .`), `docker-compose.yml`, and `requirements.txt` (Flask, Werkzeug, Jinja2, PyJWT, requests, urllib3 pinned to older versions). |

**Out of scope:** the host OS and Docker daemon, networks beyond localhost, GitHub and other
third-party services, and denial-of-service testing.

### 2.3 Endpoints

| # | Method | Path | Auth required | Input | Data touched | Purpose |
|---|---|---|---|---|---|---|
| 1 | GET | `/` | Optional | `session` cookie | `notes` (own), `users` (role) | Login/register forms, or the user's notes and the note/search forms |
| 2 | POST | `/register` | No | `username`, `password`, `role` (form or JSON) | Writes `users` | Create an account (`role` defaults to `user`) |
| 3 | POST | `/login` | No | `username`, `password` (form or JSON) | Reads `users` | Check credentials and set the `session` JWT cookie |
| 4 | GET | `/logout` | No | — | — | Delete the `session` cookie |
| 5 | POST | `/notes` | Logged in | `title`, `body` (form) | Writes `notes` | Add a note owned by the caller |
| 6 | GET | `/api/notes/<id>` | Logged in | Note ID in the path | Reads `notes` | Return a note as JSON (`id`, `owner`, `title`, `body`) |
| 7 | GET | `/search` | Logged in | `q` (query string) | Reads `notes` | Keyword search over the caller's note bodies |
| 8 | GET | `/admin` | Logged in, `admin` role | — | Reads `users` | Return every account (ID, username, password hash, role) as JSON |
| 9 | GET | `/export` | Logged in | `fmt` (query string) | OS shell | "Export notes" helper; returns command output |

### 2.4 Data-Flow Diagram

![NoteVault Level-1 DFD](docs/img/dfd-notevault.png)

*Editable source: [`docs/img/dfd-notevault.svg`](docs/img/dfd-notevault.svg).*

**External entities**

| ID | Entity | Description |
|---|---|---|
| E1 | User | Anyone who can reach port 8080: an anonymous visitor or a registered user such as `alice`. |
| E2 | Admin user | A logged-in account with `role = admin`. |
| E3 | Developer / build pipeline | Supplies the image: Docker Hub base image, PyPI packages, compose environment variables. |
| — | OS shell | `/bin/sh`, started by the app; outside the Python process. |

**Processes**

| ID | Process | Routes |
|---|---|---|
| P1 | Authentication & session | `/register`, `/login`, `/logout`, plus the JWT check (`current_user`) used by every protected route |
| P2 | Notes | `/`, `/notes`, `/api/notes/<id>` |
| P3 | Search | `/search` |
| P4 | Admin | `/admin` |
| P5 | Export | `/export` |

**Data stores**

| ID | Store | Contents |
|---|---|---|
| D1 | `users` table | Usernames, MD5 password hashes, roles |
| D2 | `notes` table | Owner, title, body for every user's notes (including admin notes and the team marker) |
| D3 | Config & secrets | JWT `SECRET`, `APP_SECRET`, `TEAM_ID`, `TEAM_SALT` |

**Data flows**

| # | From → To | Data |
|---|---|---|
| 1 / 2 | E1 ↔ P1 | Username, password (and optional `role`) → `session` JWT cookie |
| 3 / 4 | E1 ↔ P2 | JWT + note title/body or note ID → notes as HTML or JSON |
| 5 / 6 | E1 ↔ P3 | JWT + search term `q` → results page |
| 7 / 8 | E1 ↔ P5 | JWT + `fmt` → export output |
| 9 / 10 | E2 ↔ P4 | Admin JWT → list of all users |
| 11 | P1 ↔ D1 | Insert user; look up user by username + password hash; role lookup |
| 12 | D3 → P1 | JWT signing / verification key |
| 13 | P2 ↔ D2 | Insert and read notes |
| 14 | P3 ↔ D2 | `LIKE` search query and matching rows |
| 15 / 16 | P5 ↔ OS shell | Command string built from `fmt` → stdout |
| 17 | P4 ↔ D1 | Role check and all user rows |
| 18 | E3 → container | Base image, Python packages, environment variables |

**Trust boundaries**

| ID | Boundary | Flows crossing it | Why it matters |
|---|---|---|---|
| TB1 | Internet / browser ↔ NoteVault container (HTTP :8080) | 1–10 | Everything from E1/E2 — form fields, JSON, query strings, path IDs, the `session` cookie — is attacker-controlled. |
| TB2 | App ↔ OS shell | 15, 16 | Data leaves the Python process and is interpreted by `/bin/sh`. |
| TB3 | App ↔ data at rest (SQLite file) | 11, 13, 14, 17 | Request data is turned into SQL; the file holds every user's credentials and notes. |
| TB4 | Build / supply chain → runtime | 18 | Third-party base image and packages, and secrets set at build time, end up inside the running container. |

These elements and boundary crossings are the rows analysed with STRIDE in §3.

---

## 3. Threat Model — STRIDE  *(20 pts)*

| Element / data flow | S | T | R | I | D | E | Top threat & mitigation |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

*Then rank the top 5 risks by likelihood × impact.*

---

## 4. Vulnerability Findings  *(25 pts)*

One block per finding (copy as needed):

### Finding F-01 — <title>
| Field | Value |
|---|---|
| CWE | CWE-___ |
| OWASP 2025 | A__ / API__ / LLM__ |
| Severity | Critical / High / Medium / Low |
| Location | file:line or endpoint |
| Reproduction | step-by-step (payload/command) |
| Impact | what an attacker gains |
| Evidence | screenshot / request-response |

---

## 5. Remediation  *(25 pts)*

Per finding: the fix, **before/after** code, and the commit that implements it.

### Fix for F-01
```diff
- vulnerable line
+ fixed line
```
- **Why this fixes it:** …
- **Commit:** `<hash>`
- **Proof the exploit now fails:** (screenshot)

---

## 6. Supply-Chain Hardening  *(15 pts)*
- **SBOM** (CycloneDX) generated — attach `sbom.json`, note component count.
- **Artifact signed & verified** with Cosign — paste the `cosign verify` output.
- One-paragraph **SLSA** self-assessment (which level, why).

---

## 7. Security CI Pipeline  *(10 pts)*
- Link to the GitHub Actions workflow (SAST + SCA + secret scanning).
- Screenshot of a build **failing** on a HIGH/CRITICAL finding.
- How the gate is configured (what fails the build).

---

## 8. Conclusion & Reflection  *(5 pts — clarity)*
- Residual risks and what you'd harden next.
- Lessons learned.

---

## Appendix
- Tools used, references (OWASP/CWE links), and the team's task split.

---

## Grading rubric (100)

| Criterion | Pts |
|---|---|
| Threat model quality & completeness (§3) | 20 |
| Vulnerability findings — correctness, CWE/OWASP mapping, depth (§4) | 25 |
| Remediation quality — correct, minimal, well-explained (§5) | 25 |
| Supply-chain hardening — SBOM + signing + provenance (§6) | 15 |
| CI pipeline — works, fails build appropriately (§7) | 10 |
| Presentation & report clarity (§1, §8) | 5 |

*All work stays within the [ethics policy](../ETHICS.md).*
