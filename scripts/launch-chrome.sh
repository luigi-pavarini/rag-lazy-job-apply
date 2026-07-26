#!/usr/bin/env bash
# Launch Chrome with the DevTools debug port so lazyapply can attach to it.
#
# Uses a dedicated profile dir (~/.lazy-apply-chrome) so it never clashes with
# your everyday Chrome window and so logins to LinkedIn/Indeed/etc. persist.
# Log into each site once here; sessions stick around for next time.
set -euo pipefail

PORT="${LAZYAPPLY_CDP_PORT:-9222}"
PROFILE_DIR="${LAZYAPPLY_CHROME_PROFILE:-$HOME/.lazy-apply-chrome}"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [[ ! -x "$CHROME" ]]; then
  # Fallbacks: Chromium / Brave
  for alt in \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"; do
    [[ -x "$alt" ]] && CHROME="$alt" && break
  done
fi

if [[ ! -x "$CHROME" ]]; then
  echo "Chrome not found. Install Google Chrome or set CHROME manually." >&2
  exit 1
fi

mkdir -p "$PROFILE_DIR"
echo "Launching $(basename "$CHROME") on debug port $PORT"
echo "Profile: $PROFILE_DIR"
exec "$CHROME" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check
