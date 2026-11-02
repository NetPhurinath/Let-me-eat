# NoteVault — Security Assessment Report

> **Team:** `<your-team-name>` &nbsp;·&nbsp; **TEAM_ID:** `<same value you pass to the build>`
> **Members:** `<name (student id)>, <name (student id)>, …`
> **Course / Term:** `<course code — term>`
> **Date:** `<YYYY-MM-DD>`
> **Target:** NoteVault starter app (`starter-app/`), commit `<git short SHA you assessed>`

<!--
HOW TO USE THIS FILE
- Fill every `<placeholder>`. Delete instructional comments like this one before you submit.
- One row per finding in the summary table; one full section per finding in §2.
- Capture evidence (screenshots + raw request/response) WHILE the app is running, then paste here.
- Your TEAM_ID marker appears in the seeded data (e.g. the admin "build-tag" note) — include it in
  at least one screenshot per major finding so the evidence is provably yours.
-->

---

## 0. Executive Summary

`<3–6 sentences for a non-expert reader: what NoteVault is, how many issues you found,
the worst one, and the overall risk verdict. Write this LAST, after everything else.>`

| Severity | Count |
|----------|-------|
| Critical | `<n>` |
| High     | `<n>` |
| Medium   | `<n>` |
| Low      | `<n>` |

---

## 1. Threat Model  *(Rubric item 1 — Week 1)*

### 1.1 System overview
`<1 short paragraph: the app's purpose, users, and the data it holds (accounts, password
hashes, private notes).>`

### 1.2 Data flow diagram (DFD)
`<Embed your DFD image or describe it. Show: browser → Flask app → SQLite DB, plus the
session cookie and the /export subprocess. Mark trust boundaries.>`

![DFD](evidence/dfd.png)

### 1.3 Trust boundaries & assets
- **Assets:** `<e.g. user credentials, password hashes, private notes, admin role, host OS>`
- **Trust boundaries:** `<e.g. network → Flask; Flask → shell (subprocess); Flask → SQLite>`

### 1.4 STRIDE analysis

| Category | Threat in NoteVault | Relevant finding(s) |
|----------|---------------------|---------------------|
| **S**poofing | `<e.g. forge session token>` | `<F-0x>` |
| **T**ampering | `<…>` | |
| **R**epudiation | `<…>` | |
| **I**nformation disclosure | `<…>` | |
| **D**enial of service | `<…>` | |
| **E**levation of privilege | `<…>` | |

### 1.5 Top risks
`<Rank the 3–5 highest risks and justify the ranking in 1–2 sentences each.>`

---

## 2. Vulnerability Findings  *(Rubric item 2 — Weeks 3–6, 10, 12–13)*

### 2.0 Findings summary

| ID | Title | Location | CWE | OWASP 2021 | Severity | Status |
|----|-------|----------|-----|------------|----------|--------|
| F-01 | `<e.g. SQL Injection in /login>` | `app.py:<line>` | CWE-`<n>` | A`<nn>` | `<Critical/High/…>` | `<Fixed/Open>` |
| F-02 | | | | | | |
| F-03 | | | | | | |
| F-04 | | | | | | |

> Copy the block below once per finding. Keep IDs stable (F-01, F-02 …); the remediation
> section and git commits reference them.

---

### F-01 — `<Finding title>`

**Location:** `starter-app/app.py:<line>` (function `<name>`)
**CWE:** CWE-`<number>` — `<title>`
**OWASP Top 10 (2021):** A`<nn>` — `<category>`
**Severity:** `<Critical / High / Medium / Low>`  &nbsp;·&nbsp; **CVSS (optional):** `<vector / score>`

**Description & root cause**
`<2–4 sentences. What is the flaw and WHY does it exist in the code? Quote the offending
line. Example root cause: "user input is concatenated into a SQL string instead of being
passed as a bound parameter, so input is interpreted as code.">`

```python
# vulnerable code (app.py:<line>)
<paste the exact lines>
```

**Reproduction steps**
1. `<precondition — e.g. app running at http://localhost:8080, logged out>`
2. `<exact action — form input, URL, or curl command>`
3. `<observed result>`

```bash
# Proof-of-concept request (make it copy-pasteable)
<curl ... >
```

**Impact**
`<What does an attacker gain and why does it matter for THIS app? Chain it: e.g. "auth
bypass → admin panel → dump all password hashes including admin.">`

**Evidence**
`<Paste screenshot(s) showing the attack and result. Include the TEAM_ID marker where
possible. Also paste the raw request/response text, not just an image.>`

![F-01 evidence](evidence/f01-<short-name>.png)

```
<raw request / response capture>
```

**Remediation** *(see also §3)*
`<State the fix in one line, then show corrected code and explain why it closes the hole.
Tip: this codebase often does the right thing elsewhere — cite the correct sibling line.>`

```python
# fixed code
<paste your fix>
```

---

<!-- Duplicate the F-01 block above for F-02, F-03, … -->

---

## 3. Remediation  *(Rubric item 3 — all term)*

Each fix lives in its own branch/commit referencing the finding ID.

| Finding | Fix summary | Branch / Commit | Verified (how) |
|---------|-------------|-----------------|----------------|
| F-01 | `<e.g. parameterized the login query>` | `fix/F-01-sqli` / `<SHA>` | `<re-ran PoC → blocked>` |
| F-02 | | | |

**Regression / verification notes:** `<How you confirmed each fix works AND didn't break
normal login/notes behavior.>`

---

## 4. Supply-Chain Hardening  *(Rubric item 4 — Week 12)*

- **SBOM (CycloneDX):** `<tool + command used, e.g. `syft`/`cyclonedx-py`; attach the SBOM file>`
  - File: `evidence/sbom.cdx.json`
- **Dependency risks found:** `<from requirements.txt — list outdated/vulnerable packages + CVEs>`
- **Image signing (Cosign):** `<key generation, `cosign sign`, and `cosign verify` output>`

```
<cosign verify output>
```

---

## 5. Build & CI Hardening  *(Rubric item 5 — Weeks 13, 15)*

### 5.1 Dockerfile hardening
| Issue in original `Dockerfile` | Fix |
|--------------------------------|-----|
| `<e.g. runs as root>` | `<add non-root USER>` |
| `<…>` | |

### 5.2 Security CI pipeline
`<Describe the pipeline. It must run SAST + SCA + secret scanning and FAIL on HIGH/CRITICAL.>`

| Stage | Tool | Fails build on |
|-------|------|----------------|
| SAST | `<Semgrep / Bandit>` | `<HIGH/CRITICAL>` |
| SCA | `<Trivy>` | `<HIGH/CRITICAL>` |
| Secret scan | `<Gitleaks>` | `<any secret>` |

- Pipeline config: `<path, e.g. .github/workflows/security.yml>`
- Evidence of a failing-then-passing run: `evidence/ci-run.png`

---

## 6. Demo Notes  *(Rubric item 6 — Week 19)*

For the live demo, prepare one end-to-end story per headline finding:

| Finding | Attack (show it break) | Root cause (1 line) | Fix (show it blocked) |
|---------|------------------------|---------------------|-----------------------|
| F-01 | | | |

---

## Appendix A — Environment & Reproducibility

- **How to build/run:** `<the exact commands, incl. setting TEAM_ID>`
- **Seeded logins:** `alice / alicepw`, `admin / admin123`
- **Tools used:** `<Burp, sqlmap, Trivy, Semgrep, Gitleaks, Cosign, …>`
- **Assessed commit:** `<git short SHA>`

## Appendix B — Changelog
| Date | Author | Change |
|------|--------|--------|
| `<YYYY-MM-DD>` | `<name>` | `<e.g. added F-01, F-02>` |
