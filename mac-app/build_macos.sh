#!/usr/bin/env bash
# Build a self-contained unsigned YUBSUB.app on a GitHub macOS Actions runner.
# Both CPU architectures are built separately to avoid mixed-architecture binaries.
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)
    DENO_ARCH="x86_64"
    FFMPEG_ARCH="x64"
    FFMPEG_SHA="ebdddc936f61e14049a2d4b549a412b8a40deeff6540e58a9f2a2da9e6b18894"
    FFPROBE_SHA="fa3add0ce901f7241abe0dfc0155d958fc834aca3f8ce61f87cc712ae669c1e0"
    ;;
  arm64)
    DENO_ARCH="aarch64"
    FFMPEG_ARCH="arm64"
    FFMPEG_SHA="a90e3db6a3fd35f6074b013f948b1aa45b31c6375489d39e572bea3f18336584"
    FFPROBE_SHA="bb2db6f5d8cef919da12fbf592119a987202a8c060a886f3cab091f9cab90b64"
    ;;
  *) echo "Unsupported macOS architecture: $ARCH" >&2; exit 1 ;;
esac

mkdir -p build/bin build/licenses
echo "Building YUBSUB.app for $ARCH"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install --upgrade --pre 'yt-dlp[default]'
python -m pip install 'pyinstaller>=6.16,<7' 'pywebview>=5.4,<7' 'Pillow>=11,<13'

# Fetch and validate an official pinned Deno runtime binary.
DENO_VERSION="2.9.7"
DENO_NAME="deno-${DENO_ARCH}-apple-darwin.zip"
DENO_URL="https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/${DENO_NAME}"
curl -fL --retry 3 "$DENO_URL" -o "build/${DENO_NAME}"
curl -fL --retry 3 "${DENO_URL}.sha256sum" -o "build/${DENO_NAME}.sha256sum"
(
  cd build
  expected="$(awk '{print $1}' "${DENO_NAME}.sha256sum" | head -n 1)"
  printf '%s  %s\n' "$expected" "$DENO_NAME" | shasum -a 256 -c -
)
unzip -q -o "build/${DENO_NAME}" -d build/bin
chmod +x build/bin/deno

# Self-contained FFmpeg and FFprobe (with their upstream license text).
FFMPEG_BASE="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"
curl -fL --retry 3 "${FFMPEG_BASE}/ffmpeg-darwin-${FFMPEG_ARCH}" -o build/bin/ffmpeg
curl -fL --retry 3 "${FFMPEG_BASE}/ffprobe-darwin-${FFMPEG_ARCH}" -o build/bin/ffprobe
printf '%s  %s\n' "$FFMPEG_SHA" 'build/bin/ffmpeg' | shasum -a 256 -c -
printf '%s  %s\n' "$FFPROBE_SHA" 'build/bin/ffprobe' | shasum -a 256 -c -
chmod +x build/bin/ffmpeg build/bin/ffprobe
curl -fL --retry 3 "${FFMPEG_BASE}/darwin-${FFMPEG_ARCH}.LICENSE" -o 'build/licenses/FFmpeg-FFprobe-LICENSE.txt'
curl -fL --retry 3 "${FFMPEG_BASE}/darwin-${FFMPEG_ARCH}.README" -o 'build/licenses/FFmpeg-FFprobe-README.txt'

build/bin/deno --version
build/bin/ffmpeg -version | head -n 1
build/bin/ffprobe -version | head -n 1

python mac-app/make_icon.py

# NOTE: PyInstaller's --onedir --windowed generates the macOS .app bundle.
# Bundled runtime assets live in sys._MEIPASS, with their own PATH prefix.
python -m PyInstaller --clean --noconfirm \
  --name YUBSUB \
  --windowed \
  --onedir \
  --osx-bundle-identifier com.twowav.yubsub \
  --icon build/YUBSUB.icns \
  --add-data 'static:static' \
  --add-data 'build/licenses:licenses' \
  --add-binary 'build/bin/deno:bin' \
  --add-binary 'build/bin/ffmpeg:bin' \
  --add-binary 'build/bin/ffprobe:bin' \
  --collect-all yt_dlp \
  --collect-all yt_dlp_ejs \
  --collect-all webview \
  --hidden-import webview.platforms.cocoa \
  mac_app.py

test -d dist/YUBSUB.app
test -x dist/YUBSUB.app/Contents/MacOS/YUBSUB

# Local HTTP communication with our embedded Flask server.
PLIST="dist/YUBSUB.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :NSAppTransportSecurity dict" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSAppTransportSecurity:NSAllowsLocalNetworking bool true" "$PLIST"

# An ad-hoc signature supports Apple Silicon; it is NOT a Developer ID signature
# and does NOT bypass the macOS downloaded-app warning.
codesign --force --deep --sign - dist/YUBSUB.app
codesign --verify --deep --strict dist/YUBSUB.app

echo 'Running frozen executable smoke test...'
dist/YUBSUB.app/Contents/MacOS/YUBSUB --smoke-test
echo 'Standalone Mac application smoke test passed.'
