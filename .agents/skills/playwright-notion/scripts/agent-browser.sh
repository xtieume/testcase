#!/usr/bin/env bash
# Launch a browser the skill owns, in its own profile, with CDP enabled.
# Nothing is copied and the user's everyday browser is never touched: you log in
# once in the window this opens, and that profile keeps the session afterwards.
# Runs headless once the profile holds a session; the window only appears for
# the first login, or when --headed is asked for to refresh an expired one.
# usage: ./agent-browser.sh [port] | --headed | --stop | --reset
set -uo pipefail

PROFILE="${NOTION_PROFILE_DIR:-$HOME/.cache/playwright-notion-profile}"
PORT="9222"
HEADED="${NOTION_HEADED:-0}"

case "${1:-}" in
  --stop)
    pkill -f -- "--user-data-dir=$PROFILE" 2>/dev/null && echo "stopped" || echo "not running"
    exit 0 ;;
  --reset)
    # only for a session that went bad; it throws away the login
    pkill -f -- "--user-data-dir=$PROFILE" 2>/dev/null; sleep 2
    rm -rf "$PROFILE" && echo "profile cleared: $PROFILE"
    exit 0 ;;
  --headed) HEADED=1 ;;
  "") ;;
  *) PORT="$1" ;;
esac

# Chrome for Testing ships with Playwright and is built for automation, so it
# takes CDP on a custom profile dir without the refusals a branded build makes.
BIN="${NOTION_BROWSER_BIN:-}"
if [ -z "$BIN" ]; then
  BIN=$(find "$HOME/Library/Caches/ms-playwright" -maxdepth 6 -type f \
        -path "*Chrome for Testing.app/Contents/MacOS/*" 2>/dev/null | sort | tail -1)
fi
[ -x "$BIN" ] || {
  echo "no automation browser found. Install one with:" >&2
  echo "  npx playwright install chromium" >&2
  echo "or point NOTION_BROWSER_BIN at a Chromium-family binary." >&2
  exit 1
}

if curl -s --max-time 3 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
  echo "CDP already listening on $PORT"
  exit 0
fi

# No profile yet means nobody has logged in, so the window has to be visible.
FIRST_RUN=0
[ -d "$PROFILE" ] || { FIRST_RUN=1; HEADED=1; }
mkdir -p "$PROFILE"

MODE=(--headless=new)
[ "$HEADED" = 1 ] && MODE=()

nohup "$BIN" --remote-debugging-port="$PORT" --user-data-dir="$PROFILE" \
  "${MODE[@]}" --no-first-run --no-default-browser-check \
  >"/tmp/notion-agent-browser.log" 2>&1 &
disown

for i in $(seq 1 20); do
  if curl -s --max-time 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
    echo "CDP ready on $PORT  (profile: $PROFILE, $([ "$HEADED" = 1 ] && echo windowed || echo headless))"
    [ "$FIRST_RUN" = 1 ] && echo "FIRST RUN: log in to Notion in the window that just opened, then re-run the extract."
    [ "$FIRST_RUN" = 1 ] || [ "$HEADED" = 1 ] || echo "running hidden; if an extract reports the login screen, re-run with --headed and sign in again."
    exit 0
  fi
  sleep 1
done

echo "CDP did not come up on $PORT. Log tail:" >&2
tail -5 /tmp/notion-agent-browser.log >&2
exit 1
