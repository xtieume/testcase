#!/usr/bin/env bash
# Launch a browser the skill owns, in its own profile, with CDP enabled.
# Nothing is copied and the user's everyday browser is never touched: you log in
# once in the window this opens, and that profile keeps the session afterwards.
# Runs headless once the profile holds a session; the window only appears for
# the first login, or when --headed is asked for to refresh an expired one.
#
# The browser is installed by this script into a directory the skill owns, never
# the shared Playwright cache (other tools and cache cleanups wipe that one), and
# its version is pinned: a different Chromium can fail to read the cookies the
# old one wrote, so an upgrade happens only on --upgrade.
# usage: ./agent-browser.sh [port] | --headed | --upgrade | --stop | --reset
set -uo pipefail

HOME_DIR="${PLAYWRIGHT_CDP_HOME:-$HOME/.cache/playwright-cdp}"
BROWSERS="$HOME_DIR/browsers"
PIN_FILE="$HOME_DIR/playwright-version"
RECORD="$HOME_DIR/browser"   # "<playwright version>\t<binary>" of the installed pin
SHARED_CACHE="${PLAYWRIGHT_SHARED_CACHE:-$HOME/Library/Caches/ms-playwright}"
# Playwright 1.65.1 ships Chrome for Testing 159.0.8154.6 (chromium-1255)
DEFAULT_PIN="1.65.1"

# The profile predates the skill-owned directory: keep using it where it is, it
# holds the logins. A fresh machine gets one next to the browser.
LEGACY_PROFILE="$HOME/.cache/playwright-cdp-profile"
if [ -n "${CDP_PROFILE_DIR:-}" ]; then
  PROFILE="$CDP_PROFILE_DIR"
elif [ -d "$LEGACY_PROFILE" ]; then
  PROFILE="$LEGACY_PROFILE"
else
  PROFILE="$HOME_DIR/profile"
fi
PORT="9222"
HEADED="${NOTION_HEADED:-0}"
UPGRADE=0

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
  --upgrade) UPGRADE=1 ;;
  "") ;;
  *) PORT="$1" ;;
esac

# Chrome for Testing is built for automation, so it takes CDP on a custom
# profile dir without the refusals a branded build makes.
browser_in() {
  find "$1" -maxdepth 5 -type f \( -path "*Chrome for Testing.app/Contents/MacOS/*" \
       -o -path "*/chrome-linux*/chrome" \) 2>/dev/null | head -1
}

# The chromium-<revision> directory a Playwright version installs into: the pin
# names exactly one, so a leftover revision beside it is never picked by accident.
revision_dir() {
  PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" npx -y "playwright@$1" install --dry-run --no-shell chromium 2>/dev/null |
    sed -n 's/^ *Install location: *\(.*\/chromium-[0-9][0-9]*\)$/\1/p' | head -1
}

# Make the Chromium of playwright@$1 present, pin it, and record its binary in BIN.
# The shared cache is only read, as a way to skip the download when it holds the
# same revision; the copy lives here, out of reach of whatever empties that cache.
ensure_browser() {
  command -v npx >/dev/null 2>&1 || { echo "npx not found: install Node.js, or point CDP_BROWSER_BIN at a Chromium-family binary." >&2; exit 1; }
  DIR=$(revision_dir "$1")
  [ -n "$DIR" ] || { echo "cannot resolve playwright@$1 (offline, or no such version)." >&2; exit 1; }
  if [ ! -f "$DIR/INSTALLATION_COMPLETE" ]; then
    SEED="$SHARED_CACHE/$(basename "$DIR")"
    mkdir -p "$BROWSERS"
    if [ -f "$SEED/INSTALLATION_COMPLETE" ]; then
      echo "copying $(basename "$DIR") from $SHARED_CACHE into $BROWSERS ..."
      rm -rf "$DIR" && cp -Rp "$SEED" "$DIR"
    else
      echo "installing Chrome for Testing (playwright@$1) into $BROWSERS ..."
      # npx prints a "project dependencies" warning here; it does not apply to this install
      PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" npx -y "playwright@$1" install --no-shell chromium >&2 || {
        echo "browser install failed; see the output above." >&2; exit 1; }
    fi
  fi
  BIN=$(browser_in "$DIR")
  [ -x "$BIN" ] || { echo "no browser binary under $DIR; remove that directory and re-run." >&2; exit 1; }
  echo "$1" > "$PIN_FILE"
  printf '%s\t%s\n' "$1" "$BIN" > "$RECORD"
}

running() { curl -s --max-time 3 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; }

mkdir -p "$HOME_DIR"
PIN=$(cat "$PIN_FILE" 2>/dev/null || echo "$DEFAULT_PIN")
REC_PIN="" REC_BIN=""
[ -f "$RECORD" ] && IFS=$'\t' read -r REC_PIN REC_BIN < "$RECORD"

if [ "$UPGRADE" = 1 ]; then
  [ -z "${CDP_BROWSER_BIN:-}" ] || {
    echo "CDP_BROWSER_BIN is set, so there is no owned browser to upgrade; unset it first." >&2; exit 1; }
  pgrep -f -- "--user-data-dir=$PROFILE" >/dev/null && { echo "stop the running browser first: $0 --stop" >&2; exit 1; }
  LATEST=$(npm view playwright@latest version --fetch-timeout=20000 --fetch-retries=1 2>/dev/null)
  [ -n "$LATEST" ] || { echo "cannot read the latest Playwright version from npm." >&2; exit 1; }
  if [ "$LATEST" = "$PIN" ] && [ "$REC_PIN" = "$PIN" ] && [ -x "$REC_BIN" ]; then
    echo "already at playwright@$PIN"; exit 0
  fi
  echo "upgrading playwright@$PIN -> playwright@$LATEST"
  ensure_browser "$LATEST"
  # keep only the revision the pin now names
  for old in "$BROWSERS"/chromium-* "$BROWSERS"/chromium_headless_shell-*; do
    [ -e "$old" ] && [ "$old" != "$DIR" ] && rm -rf "$old"
  done
  echo "upgraded to playwright@$LATEST. The new browser may not read the old cookies:"
  echo "if an extract lands on a login screen, run $0 --headed and sign in again."
  exit 0
fi

BIN="${CDP_BROWSER_BIN:-}"
if [ -z "$BIN" ]; then
  if [ "$REC_PIN" = "$PIN" ] && [ -x "$REC_BIN" ]; then
    BIN="$REC_BIN"
  else
    echo "no automation browser for playwright@$PIN in $BROWSERS yet."
    ensure_browser "$PIN"
  fi
fi
[ -x "$BIN" ] || { echo "CDP_BROWSER_BIN is not an executable: $BIN" >&2; exit 1; }

if running; then
  echo "CDP already listening on $PORT"
  exit 0
fi

# No profile yet means nobody has logged in, so the window has to be visible.
FIRST_RUN=0
[ -d "$PROFILE" ] || { FIRST_RUN=1; HEADED=1; }
mkdir -p "$PROFILE"

# A profile last opened by another browser version may have lost its session.
LAST=$(cat "$PROFILE/Last Version" 2>/dev/null)
NOW=$("$BIN" --version 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+){3}')
VERSION_CHANGED=0
[ -n "$LAST" ] && [ -n "$NOW" ] && [ "$LAST" != "$NOW" ] && VERSION_CHANGED=1
# An older browser on a newer profile is a downgrade, which loses the session or
# fails to start: refuse instead of finding out from a login screen.
NEWEST=$(printf '%s\n%s\n' "$LAST" "$NOW" | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n | tail -1)
if [ "$VERSION_CHANGED" = 1 ] && [ "$NEWEST" = "$LAST" ]; then
  echo "profile $PROFILE was last opened by Chromium $LAST, newer than this browser ($NOW)." >&2
  echo "opening it with an older one loses the logins: run $0 --upgrade, or set CDP_BROWSER_BIN to a browser at least that new." >&2
  exit 1
fi

# a plain string, not an array: bash 3.2 (the macOS default) errors on an
# empty array expansion under `set -u`
MODE="--headless=new"
[ "$HEADED" = 1 ] && MODE=""

LOG="$HOME_DIR/browser.log"
nohup "$BIN" --remote-debugging-port="$PORT" --user-data-dir="$PROFILE" \
  $MODE --no-first-run --no-default-browser-check \
  >"$LOG" 2>&1 &
disown

for i in $(seq 1 20); do
  if running; then
    echo "CDP ready on $PORT  (browser: ${NOW:-unknown}, profile: $PROFILE, $([ "$HEADED" = 1 ] && echo windowed || echo headless))"
    [ "$VERSION_CHANGED" = 1 ] && echo "profile was last opened by $LAST; this is $NOW, so the logins may be gone. If an extract reports the login screen, run $0 --headed and sign in again."
    [ "$FIRST_RUN" = 1 ] && echo "FIRST RUN: log in to Notion (and Slack/GitHub as needed) in the window that just opened, then re-run the extract."
    [ "$FIRST_RUN" = 1 ] || [ "$HEADED" = 1 ] || echo "running hidden; if an extract reports the login screen, the session expired: re-run with --headed and sign in again."
    exit 0
  fi
  sleep 1
done

echo "CDP did not come up on $PORT. Log tail ($LOG):" >&2
tail -5 "$LOG" >&2
exit 1
