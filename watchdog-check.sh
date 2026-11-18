#!/usr/bin/env bash
# Watchdog for the Dialectica Expert serve.
# Run it on a schedule (cron every 5 minutes works). If a `trued serve`
# process is already running, it does nothing. Otherwise it removes a stale
# lock file (its PID is dead) and starts the serve detached in the
# background, so the calling job exits promptly. The serve retries its own
# connection failures; this script only makes sure a serve process exists.
# Needs trued.py next to this script (or TRUED_PY set) and GROQ_API_KEY.
set -u
if pgrep -f "trued.py serve" >/dev/null 2>&1; then
  exit 0
fi
LOCK="$HOME/.dialectica/serve.lock"
if [ -f "$LOCK" ]; then
  PID="$(tr -d ' \n' < "$LOCK" 2>/dev/null)"
  if [ -n "$PID" ] && ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$LOCK"
  fi
fi
cd "$(dirname "$0")" || exit 1
: "${GROQ_API_KEY:?GROQ_API_KEY is not set}"
TRUED_PY="${TRUED_PY:-$(pwd)/trued.py}"
setsid nohup env DIALECTICA_PROVIDER_CMD="python3 $(pwd)/provider.py" python3 "$TRUED_PY" serve --context-window 131072 --every 10m >> "$HOME/.dialectica/serve.log" 2>&1 < /dev/null &
