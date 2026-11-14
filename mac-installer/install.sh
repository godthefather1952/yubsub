#!/bin/bash
# YUBSUB Mac first-time installer — downloads the public YUBSUB source and
# installs local runtime dependencies. Everything stays on this Mac.
set -Eeuo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
APP_DIR="$HOME/Applications/YUBSUB"
APP_URL="https://github.com/godthefather1952/yubsub/archive/refs/heads/main.zip"
export PATH="$HOME/.deno/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
step() { printf '\n[%s] %s\n' 'YUBSUB' "$*"; }

on_error() {
  echo ''
  echo "YUBSUB installation stopped (near line $1)." >&2
  echo 'Read the error above. No other applications were removed.' >&2
  echo 'If needed, rerun Install YUBSUB.command after fixing the issue.' >&2
  echo ''
  if [[ -t 0 ]]; then read -r -p 'Press Return to close this window...' _ || true; fi
}
trap 'on_error "$LINENO"' ERR

[[ "$(uname -s)" == "Darwin" ]] || fail 'This installer is for macOS only.'
[[ -f "$PACKAGE_DIR/requirements.txt" ]] || fail 'requirements.txt is missing. Unzip the entire package first.'
[[ -f "$PACKAGE_DIR/Launch YUBSUB.command" ]] || fail 'Launch YUBSUB.command is missing. Unzip the entire package first.'
command -v curl >/dev/null 2>&1 || fail 'curl is required.'
command -v ditto >/dev/null 2>&1 || fail 'macOS ditto is required.'

step 'Installing YUBSUB locally (no GitHub account or Docker required)'
step 'You may be asked for your Mac password if Homebrew must install system tools.'

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/yubsub-install.XXXXXX")"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

ensure_brew() {
  if command -v brew >/dev/null 2>&1; then return 0; fi
  step 'Homebrew is missing. Installing it using the official Homebrew installer...'
  curl --fail --location --silent --show-error --retry 3 \
    'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh' \
    --output "$WORK_DIR/homebrew-install.sh"
  /bin/bash "$WORK_DIR/homebrew-install.sh"
  export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  command -v brew >/dev/null 2>&1 || fail 'Homebrew installation did not complete.'
}

choose_python() {
  local p
  for p in python3.12 python3.13 python3.14 python3.11 python3; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c \
      'import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] <= (3, 14)))' \
      >/dev/null 2>&1; then
      command -v "$p"
      return 0
    fi
  done
  return 1
}

step 'Checking Python 3.11+...'
PYTHON_BIN="$(choose_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  ensure_brew
  step 'Installing Python 3.12...'
  brew install python@3.12
  PYTHON_BIN="$(choose_python || true)"
  [[ -n "$PYTHON_BIN" ]] || fail 'Could not find Python 3.11+ after installation.'
fi
"$PYTHON_BIN" --version

step 'Checking FFmpeg...'
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  ensure_brew
  brew install ffmpeg
fi
command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1 \
  || fail 'FFmpeg or ffprobe is still missing.'
ffmpeg -version | sed -n '1p'

step 'Checking Deno...'
if ! command -v deno >/dev/null 2>&1; then
  step 'Installing Deno from the official installer...'
  curl --fail --location --silent --show-error --retry 3 \
    'https://deno.land/install.sh' --output "$WORK_DIR/deno-install.sh"
  /bin/sh "$WORK_DIR/deno-install.sh"
  export PATH="$HOME/.deno/bin:$PATH"
fi
command -v deno >/dev/null 2>&1 || fail 'Deno installation did not complete.'
deno --version | sed -n '1p'

step 'Downloading the latest YUBSUB application from the project GitHub repository...'
curl --fail --location --silent --show-error --retry 3 \
  --connect-timeout 15 --max-time 180 "$APP_URL" --output "$WORK_DIR/yubsub.zip"
mkdir -p "$WORK_DIR/source"
ditto -x -k "$WORK_DIR/yubsub.zip" "$WORK_DIR/source"
SOURCE_DIR="$WORK_DIR/source/yubsub-main"
[[ -f "$SOURCE_DIR/app.py" && -f "$SOURCE_DIR/static/index.html" ]] \
  || fail 'Downloaded YUBSUB source is incomplete. No files were installed.'

step "Installing application into $APP_DIR..."
mkdir -p "$APP_DIR/static"
cp "$SOURCE_DIR/app.py" "$APP_DIR/app.py"
cp "$SOURCE_DIR/static/index.html" "$APP_DIR/static/index.html"
# This config is only used by GitHub Pages. Localhost always uses the local API.
if [[ -f "$SOURCE_DIR/static/config.js" ]]; then
  cp "$SOURCE_DIR/static/config.js" "$APP_DIR/static/config.js"
fi
cp "$PACKAGE_DIR/requirements.txt" "$APP_DIR/requirements.txt"
cp "$PACKAGE_DIR/Launch YUBSUB.command" "$APP_DIR/Launch YUBSUB.command"
chmod +x "$APP_DIR/Launch YUBSUB.command"

step 'Setting up isolated Python dependencies...'
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade --pre 'yt-dlp[default]'

step 'Verifying the installed app...'
"$APP_DIR/.venv/bin/python" -m py_compile "$APP_DIR/app.py"
"$APP_DIR/.venv/bin/python" -m yt_dlp --version

step 'Creating a one-click Desktop launcher...'
DESKTOP_DIR="$HOME/Desktop"
mkdir -p "$DESKTOP_DIR"
cp "$APP_DIR/Launch YUBSUB.command" "$DESKTOP_DIR/Launch YUBSUB.command"
chmod +x "$DESKTOP_DIR/Launch YUBSUB.command"

printf '\n====================================================\n'
printf '   YUBSUB installation complete!\n'
printf '   Installed to: %s\n' "$APP_DIR"
printf '   Desktop shortcut: Launch YUBSUB.command\n'
printf '   Local website: http://127.0.0.1:8000\n'
printf '====================================================\n\n'

step 'Launching YUBSUB now...'
/bin/bash "$APP_DIR/Launch YUBSUB.command"
