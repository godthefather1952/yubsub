#!/bin/bash
set -euo pipefail
export PATH="$HOME/.deno/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
APP_DIR="$HOME/Applications/YUBSUB"
cd "$APP_DIR" || exit 1

if [[ ! -x "$APP_DIR/.venv/bin/gunicorn" ]]; then
  echo 'YUBSUB is not installed yet. Run Install YUBSUB.command first.'
  read -r -p 'Press Return to close this window...' _ || true
  exit 1
fi

# Avoid starting multiple servers or interfering with other apps on this port.
if curl --fail --silent --show-error --max-time 2 \
  http://127.0.0.1:8000/api/health 2>/dev/null | grep -q '"ok":true'; then
  echo 'YUBSUB is already running. Opening your browser...'
  open 'http://127.0.0.1:8000'
  exit 0
fi
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo 'Port 8000 is occupied by another application. Please close it first.'
  read -r -p 'Press Return to close this window...' _ || true
  exit 1
fi

# Launch the browser once the Python server is actually responding.
(
  for ((attempt=0;attempt<45;attempt++)); do
    if curl --fail --silent --show-error --max-time 2 \
      http://127.0.0.1:8000/api/health 2>/dev/null | grep -q '"ok":true'; then
      open 'http://127.0.0.1:8000'
      exit 0
    fi
    sleep 1
  done
  echo 'YUBSUB did not become healthy; check the Terminal output above.'
) &

printf '\n============================================\n'
printf '            YUBSUB BY 2.WAV\n'
printf '============================================\n'
printf 'Website: http://127.0.0.1:8000\n'
printf 'Maximum playlist size: 200 tracks\n'
printf 'Maximum ZIP size: 1200 MB\n'
printf 'Press Control+C to stop the server.\n\n'

MAX_TRACKS=200 MAX_ARCHIVE_MB=1200 \
  "$APP_DIR/.venv/bin/gunicorn" \
  --bind 127.0.0.1:8000 \
  --workers 1 \
  --threads 8 \
  --timeout 0 \
  app:app
