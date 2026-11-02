#!/usr/bin/env bash
# NoteVault before/after demo driver (local containers only).
#   bash docs/demo.sh setup     start the baseline app (:8081), fixed app (:8080) and test image
#   bash docs/demo.sh F-01      walk through one finding, pausing for Enter between steps
#   bash docs/demo.sh list      list findings
#   bash docs/demo.sh stop      stop everything
cd "$(dirname "$0")/.." || exit 1
docker() { MSYS_NO_PATHCONV=1 command docker "$@"; }   # keep Git Bash from rewriting container paths
BASELINE=8725faa
COMPOSE="docker compose -f starter-app/docker-compose.yml"
Y=$'\e[1;33m' B=$'\e[1;36m' G=$'\e[1;32m' R=$'\e[1;31m' N=$'\e[0m'

step()  { echo; echo "${Y}━━━━ $* ━━━━${N}"; }
pause() { read -rp "${G}▶ press Enter: $*${N}" _; }
run()   { echo "${B}\$ $*${N}"; eval "$*"; echo; }
code()  { echo "${B}$1 (baseline $BASELINE), lines $2-$3:${N}"
          git show "$BASELINE:$1" | awk -v a="$2" -v b="$3" 'NR>=a && NR<=b {printf "%4d  %s\n", NR, $0}'; echo; }
wait_up() { for _ in $(seq 1 40); do curl -s -o /dev/null "localhost:$1/" && return; sleep 1; done; }
login() { curl -s -o /dev/null -c "/tmp/jar$1" -d "username=$2&password=$3" "localhost:$1/login" -w "login $2 on :$1 -> HTTP %{http_code}\n"; }
logs()  { if [ "$1" = 8081 ]; then docker logs nvbase 2>&1; else $COMPOSE logs --no-log-prefix notevault 2>&1; fi; }
inapp() { local p=$1; shift; if [ "$p" = 8081 ]; then docker exec nvbase "$@"; else $COMPOSE exec -T notevault "$@"; fi; }
label() { if [ "$1" = 8081 ]; then echo "${R}BEFORE — baseline app on :8081${N}"; else echo "${G}AFTER — fixed app on :8080${N}"; fi; }
reset() { docker restart -t 1 nvbase >/dev/null; $COMPOSE restart -t 1 >/dev/null 2>&1; wait_up 8081; wait_up 8080; rm -f /tmp/jar808*; }
unit()  { run "docker run --rm -v \"$(pwd -W)/starter-app:/src:ro\" -w /src notevault-tools python -m pytest -p no:cacheprovider -q -v tests -k '$1' 2>&1 | grep -E 'PASSED|FAILED|passed|failed'"; }

setup() {
  docker info >/dev/null 2>&1 || { echo "Start Docker Desktop first."; exit 1; }
  step "fixed app (current main) -> http://localhost:8080"
  $COMPOSE up -d --build
  step "baseline app (commit $BASELINE) -> http://localhost:8081"
  docker image inspect notevault-baseline >/dev/null 2>&1 || {
    rm -rf /tmp/nv-baseline && mkdir -p /tmp/nv-baseline
    git archive "$BASELINE" starter-app | tar -x -C /tmp/nv-baseline
    docker build -q -t notevault-baseline "$(cygpath -w /tmp/nv-baseline/starter-app)"; }
  docker rm -f nvbase >/dev/null 2>&1
  docker run -d --name nvbase -p 8081:8080 -e TEAM_ID="Let me eat" notevault-baseline >/dev/null
  step "test/audit image"
  printf 'FROM python:3.12-slim\nCOPY requirements.txt .\nRUN pip install -q -r requirements.txt pytest pip-audit\n' |
    docker build -q -t notevault-tools -f - starter-app
  wait_up 8080; wait_up 8081
  echo "${G}Ready: baseline :8081, fixed :8080. Next: bash docs/demo.sh F-01${N}"
}

# ---- per finding: CODE (what to show), FIX commit, attack PORT, works PORT, TEST filter
f01_code() { code starter-app/app.py 123 137; }
f01() { run "curl -si -d \"username=admin' --&password=anything\" localhost:$1/login | grep -iE '^(HTTP|set-cookie)'"; }
f01_ok() { run "login $1 alice alicepw"; }

f02_code() { code starter-app/app.py 171 182; }
f02() { run "login $1 alice alicepw"
        run "curl -s -b /tmp/jar$1 --get --data-urlencode \"q=zzz' OR '1'='1' --\" localhost:$1/search"; }
f02_ok() { run "curl -s -b /tmp/jar$1 --get --data-urlencode 'q=milk' localhost:$1/search"; }

f03_code() { code starter-app/app.py 171 182; }
f03() { run "login $1 alice alicepw"
        run "curl -s -o /dev/null -b /tmp/jar$1 --data-urlencode 'title=t' --data-urlencode 'body=calc {{ 7*7 }}' localhost:$1/notes"
        run "curl -s -b /tmp/jar$1 --get --data-urlencode 'q=calc' localhost:$1/search"; }
f03_ok() { run "curl -s -b /tmp/jar$1 localhost:$1/ | grep -o '<li>.*</li>'"; }

f04_code() { code starter-app/app.py 196 204; }
f04() { run "login $1 alice alicepw"
        run "curl -s -b /tmp/jar$1 --get --data-urlencode 'fmt=txt; echo INJECTED-MARKER' localhost:$1/export -w '\nHTTP %{http_code}\n'"; }
f04_ok() { run "curl -s -b /tmp/jar$1 'localhost:$1/export?fmt=csv'"
           run "curl -s -b /tmp/jar$1 'localhost:$1/export?fmt=json'; echo"; }

f05_code() { code starter-app/app.py 78 86; }
f05() { run "T=\$(printf '{\"alg\":\"none\",\"typ\":\"JWT\"}' | base64 -w0 | tr -d '=' | tr '/+' '_-').\$(printf '{\"sub\":\"admin\"}' | base64 -w0 | tr -d '=' | tr '/+' '_-')."
        run "echo \"unsigned token: \$T\""
        run "curl -s -b \"session=\$T\" localhost:$1/admin -w '\nHTTP %{http_code}\n'"
        [ "$1" = 8081 ] && echo "${Y}Rejected even on the baseline: PyJWT 1.7.1 refuses alg=none when a key is passed -> Low, defence in depth.${N}"; }
f05_ok() { run "login $1 admin admin123"; run "curl -s -o /dev/null -b /tmp/jar$1 localhost:$1/admin -w 'admin panel HTTP %{http_code}\n'"; }

f06_code() { code starter-app/app.py 21 24; code starter-app/Dockerfile 1 10; }
f06() { run "T=\$($COMPOSE exec -T notevault python -W ignore -c \"import jwt;print(jwt.encode({'sub':'admin'},'notevault-dev-secret',algorithm='HS256'))\")"
        run "echo \"token signed with the published key: \$T\""
        run "curl -s -b \"session=\$T\" localhost:$1/admin -w '\nHTTP %{http_code}\n'"; }
f06_ok() { f05_ok "$1"; }

f07_code() { code starter-app/app.py 110 120; }
f07() { run "curl -s -o /dev/null -w 'register -> HTTP %{http_code}\n' -d 'username=mallory&password=pw-123456&role=admin' localhost:$1/register"
        run "login $1 mallory pw-123456"
        run "curl -s -b /tmp/jar$1 localhost:$1/admin -w '\nHTTP %{http_code}\n'"; }
f07_ok() { run "curl -s -o /dev/null -w 'register bob -> HTTP %{http_code}\n' -d 'username=bob&password=bob-pw-123' localhost:$1/register"; run "login $1 bob bob-pw-123"; }

f08_code() { code starter-app/app.py 62 66; code starter-app/app.py 110 120; }
f08() { run "curl -s -w '\nregister second alice -> HTTP %{http_code}\n' -d 'username=alice&password=newpass1' localhost:$1/register | grep -v '<'"
        run "login $1 alice newpass1"
        run "curl -s -b /tmp/jar$1 localhost:$1/ | grep -o '<li>.*</li>'"; }
f08_ok() { run "login $1 alice alicepw"; }

f09_code() { code starter-app/app.py 161 168; }
f09() { run "login $1 alice alicepw"
        run "curl -s -b /tmp/jar$1 localhost:$1/api/notes/2 -w 'HTTP %{http_code}\n'"; }
f09_ok() { run "curl -s -b /tmp/jar$1 localhost:$1/api/notes/1 -w 'HTTP %{http_code}\n'"; }

f10_code() { code starter-app/app.py 36 51; code starter-app/app.py 96 107; }
f10() { run "login $1 alice alicepw"
        run "curl -s -o /dev/null -b /tmp/jar$1 --data-urlencode 'title=<img src=x onerror=alert(document.domain)>' --data-urlencode 'body=b' localhost:$1/notes"
        run "curl -s -b /tmp/jar$1 localhost:$1/ | grep -oE '<li>#[0-9]+ <b>[^:]*onerror[^:]*'"
        echo "${Y}(optional) open http://localhost:$1 in a browser, log in as alice / alicepw to see it live${N}"; }
f10_ok() { run "curl -s -b /tmp/jar$1 localhost:$1/ | grep -o '<li>.*</li>'"; }

f11_code() { code starter-app/app.py 60 73; }
f11() { run "inapp $1 python -c \"import sqlite3;[print(r) for r in sqlite3.connect('/tmp/notevault.db').execute('select username,password from users')]\""
        [ "$1" = 8081 ] && run "printf admin123 | md5sum"; }
f11_ok() { run "login $1 admin admin123"; }

f12_code() { code starter-app/app.py 205 209; }
f12() { run "logs $1 | grep -iE 'debug' | tail -3"
        run "curl -s -d 'username=x' localhost:$1/register -w '\nHTTP %{http_code}\n' | grep -oE 'Werkzeug Debugger|password must be[^<]*|HTTP [0-9]+' | sort -u"; }
f12_ok() { run "login $1 alice alicepw"; }

f13_code() { code starter-app/app.py 132 144; }
f13() { run "curl -si -d 'username=alice&password=alicepw' localhost:$1/login | grep -i '^set-cookie'"
        run "curl -s -o /dev/null -w 'GET /logout -> HTTP %{http_code}\n' localhost:$1/logout"; }
f13_ok() { run "login $1 alice alicepw"; run "curl -s -o /dev/null -b /tmp/jar$1 -X POST -w 'POST /logout (the Logout button) -> HTTP %{http_code}\n' localhost:$1/logout"; }

f14_code() { code starter-app/app.py 185 193; }
f14() { run "login $1 admin admin123"; run "curl -s -b /tmp/jar$1 localhost:$1/admin"; }

f15_code() { code starter-app/app.py 123 137; }
f15() { run "for i in 1 2 3 4 5 6; do login $1 alice wrong\$i; done"
        run "login $1 alice alicepw"; }
f15_ok() { run "login $1 admin admin123"; }

f16_code() { echo "${B}starter-app/requirements.txt (baseline):${N}"; git show "$BASELINE:starter-app/requirements.txt"; echo; }
f16() { if [ "$1" = 8081 ]; then
          run "git show $BASELINE:starter-app/requirements.txt > /tmp/req-old.txt"
          run "docker run --rm -v \"$(cygpath -w /tmp):/t\" notevault-tools pip-audit -r /t/req-old.txt --desc off 2>&1 | tail -4"
        else
          run "docker run --rm -v \"$(pwd -W)/starter-app:/s\" notevault-tools pip-audit -r /s/requirements.txt 2>&1 | tail -2"
        fi; }

f17_code() { code starter-app/Dockerfile 1 11; }
f17() { run "inapp $1 id"; run "inapp $1 ls /app"; }
f17_ok() { run "curl -s -o /dev/null -w 'app on :$1 -> HTTP %{http_code}\n' localhost:$1/"; }

f18_code() { code starter-app/app.py 110 120; }
f18() { run "curl -s -d 'username=x' localhost:$1/register -o /dev/null -w 'register without password -> HTTP %{http_code}\n'"; }
f18_ok() { f07_ok "$1"; }

f19_code() { echo "(no code to point at: there is no security logging anywhere in app.py)"; }
f19() { run "login $1 alice wrong-password"; run "logs $1 | tail -2"; }

declare -A FIX=([01]=98587c7 [02]=98587c7 [03]=756d587 [10]=756d587 [04]=7e1c09b [05]=05f97cf [06]=05f97cf
                [13]=05f97cf [07]=f2f7f44 [08]=f2f7f44 [11]=f2f7f44 [18]=f2f7f44 [09]=47a4ded [14]=47a4ded
                [12]=72fdcf5 [15]=72fdcf5 [19]=72fdcf5 [16]=8bc8591 [17]="036da1a f2e3807")
declare -A TITLE=([01]="SQL injection in login" [02]="SQL injection in search" [03]="Template injection"
  [04]="Command injection in export" [05]="JWT alg none (latent)" [06]="Hard-coded JWT secret"
  [07]="Client chooses own role" [08]="Duplicate username takeover" [09]="IDOR on notes API"
  [10]="Stored XSS" [11]="MD5 password hashes" [12]="Debugger enabled" [13]="Cookie flags / expiry / logout CSRF"
  [14]="Admin exposes hashes" [15]="No brute-force limit" [16]="Vulnerable dependencies"
  [17]="Container runs as root" [18]="Missing input validation" [19]="No security logging")

demo() {
  local n=${1#F-}; n=${n#f-}; n=${n#F}; n=$(printf '%02d' "$((10#$n))")
  [ -n "${TITLE[$n]}" ] || { echo "unknown finding $1"; exit 1; }
  local f="f$n"
  echo "${Y}Resetting both apps to fresh seed data...${N}"; reset; clear
  echo "${Y}F-$n — ${TITLE[$n]}${N}  (see REPORT-TEMPLATE.md §4/§5)"
  step "1. The vulnerable code";            "${f}_code";  pause "run the test against the BASELINE app"
  step "2. $(label 8081)";                  "$f" 8081;    pause "show the fix"
  step "3. The fix — commit ${FIX[$n]}"
  for h in ${FIX[$n]}; do git --no-pager show --color=always --stat --patch "$h" -- starter-app/app.py starter-app/Dockerfile starter-app/requirements.txt starter-app/docker-compose.yml starter-app/.dockerignore | sed -n '1,400p'; done
  pause "run the SAME test against the FIXED app"
  step "4. $(label 8080)";                  "$f" 8080
  if [ "$(type -t "${f}_ok")" = function ]; then
    pause "show normal use still works"; step "5. Normal use still works on :8080"; "${f}_ok" 8080; fi
  if [ "$n" != 16 ] && [ "$n" != 17 ]; then pause "run the automated test"; step "6. Automated regression test"; unit "f$n"; fi
  echo "${G}Done with F-$n — stop the recording.${N}"
}

case "$1" in
  setup) setup ;;
  stop)  docker rm -f nvbase >/dev/null 2>&1; $COMPOSE down ;;
  list|"") for k in $(printf '%s\n' "${!TITLE[@]}" | sort); do echo "F-$k  ${TITLE[$k]}"; done
           echo; echo "usage: bash docs/demo.sh setup | F-01 … F-19 | stop" ;;
  *) demo "$1" ;;
esac
