#!/usr/bin/env bash
# Launch a Chromium-family browser with CDP enabled, reusing the real logged-in profile.
# usage: ./start-browser.sh [brave|chrome|edge] [port]
set -uo pipefail

BROWSER="${1:-brave}"
PORT="${2:-9222}"

case "$BROWSER" in
  brave)
    BIN="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    DATA="$HOME/Library/Application Support/BraveSoftware/Brave-Browser"
    PROC="Brave Browser"
    ;;
  chrome)
    BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    DATA="$HOME/Library/Application Support/Google/Chrome"
    PROC="Google Chrome"
    ;;
  edge)
    BIN="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    DATA="$HOME/Library/Application Support/Microsoft Edge"
    PROC="Microsoft Edge"
    ;;
  *) echo "unknown browser: $BROWSER (use brave|chrome|edge)" >&2; exit 1 ;;
esac

[ -x "$BIN" ] || { echo "browser binary not found: $BIN" >&2; exit 1; }

# Already listening? nothing to do.
if curl -s --max-time 3 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
  echo "CDP already listening on $PORT"
  exit 0
fi

# List profiles so the caller knows which one holds the Notion session.
echo "profiles under $DATA:"
for d in "$DATA"/Default "$DATA"/Profile*; do
  [ -f "$d/Preferences" ] || continue
  name=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('profile',{}).get('name','(unnamed)'))" "$d/Preferences" 2>/dev/null)
  echo "  $(basename "$d")  ($name)  $(du -sh "$d" 2>/dev/null | cut -f1)"
done

# A running instance holds the profile lock and blocks the debug port. Must close it first.
if pgrep -f "$PROC" >/dev/null 2>&1; then
  echo "closing running $PROC (its profile lock blocks the debug port)..."
  pkill -f "$PROC" 2>/dev/null || true
  sleep 3
  pkill -9 -f "$PROC" 2>/dev/null || true
  sleep 2
fi
rm -f "$DATA/SingletonLock" "$DATA/SingletonSocket" "$DATA/SingletonCookie" 2>/dev/null || true

# Launch detached. NOTE: `open -a ... --args` silently drops these flags — must exec the binary.
nohup "$BIN" --remote-debugging-port="$PORT" --user-data-dir="$DATA" \
  >"/tmp/${BROWSER}-cdp.log" 2>&1 &
disown

for i in $(seq 1 20); do
  if curl -s --max-time 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
    echo "CDP ready on $PORT"
    curl -s "http://127.0.0.1:$PORT/json/version" | head -3
    exit 0
  fi
  sleep 1
done

echo "CDP did not come up on $PORT. Log tail:" >&2
tail -5 "/tmp/${BROWSER}-cdp.log" >&2
echo "If it says 'remote debugging requires a non-default data directory', this browser build refuses CDP on its default profile dir — try another browser (Brave usually works where Chrome does not)." >&2
exit 1
