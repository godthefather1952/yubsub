#!/usr/bin/env bash
# Build a ChromeOS/Crostini-compatible self-contained Debian package.
# Run on a native x86_64 or aarch64 Linux runner with Python 3.12.
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH="$(dpkg --print-architecture)"
case "$ARCH" in
  amd64) DENO_TARGET=x86_64 ;;
  arm64) DENO_TARGET=aarch64 ;;
  *) echo "Unsupported Linux architecture: $ARCH" >&2; exit 1 ;;
esac
VERSION="$(tr -d '[:space:]' < chromeos-app/VERSION)"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid chromeos-app/VERSION"; exit 1; }
printf 'Building YUBSUB for ChromeOS %s (%s)\n' "$VERSION" "$ARCH"

command -v dpkg-deb
command -v ffmpeg
command -v ffprobe
command -v xdg-open
command -v unzip
command -v curl
command -v sha256sum

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install --upgrade --pre 'yt-dlp[default]'
python3 -m pip install 'pyinstaller>=6.16,<7' 'Pillow>=11,<13' 'cryptography>=44,<49'

mkdir -p build/bin build/pkg
DENO_VERSION=2.9.7
DENO_FILE="deno-${DENO_TARGET}-unknown-linux-gnu.zip"
DENO_URL="https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/${DENO_FILE}"
curl -fL --retry 3 "$DENO_URL" -o "build/$DENO_FILE"
curl -fL --retry 3 "${DENO_URL}.sha256sum" -o "build/${DENO_FILE}.sha256sum"
expected="$(awk '{print $1}' "build/${DENO_FILE}.sha256sum" | head -n 1)"
[[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || { echo 'Invalid Deno checksum file' >&2; exit 1; }
printf '%s  %s\n' "$expected" "build/$DENO_FILE" | sha256sum -c -
unzip -q -o "build/$DENO_FILE" -d build/bin
chmod 0755 build/bin/deno
build/bin/deno --version
python3 chromeos-app/make_icon.py

# Use the same release owner public key as Sparkle and Windows, but a distinct
# signature context. No private signing key enters this build.
KEY="${SPARKLE_PUBLIC_ED_KEY:-}"
PUBKEY="$KEY" python3 - <<'PY'
import base64, os
from pathlib import Path
key = os.environ.get("PUBKEY", "").strip()
if key and len(base64.b64decode(key, validate=True)) != 32:
    raise SystemExit("SPARKLE_PUBLIC_ED_KEY is not a valid Ed25519 public key")
Path("build/update-public-key.txt").write_text(key + "\n", encoding="ascii")
PY

python3 -m PyInstaller --clean --noconfirm \
  --name yubsub \
  --onedir \
  --add-data 'static:static' \
  --add-data 'chromeos-app/VERSION:chromeos-app' \
  --add-data 'build/update-public-key.txt:.' \
  --add-binary 'build/bin/deno:bin' \
  --collect-all yt_dlp \
  --collect-all yt_dlp_ejs \
  --hidden-import linux_updater \
  --paths chromeos-app \
  chromeos_app.py

test -x dist/yubsub/yubsub
dist/yubsub/yubsub --smoke-test

STAGE="build/pkg/yubsub_${VERSION}_${ARCH}"
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
  "$STAGE/opt/yubsub" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/256x256/apps"

cp -a dist/yubsub/. "$STAGE/opt/yubsub/"
cp chromeos-app/yubsub.desktop "$STAGE/usr/share/applications/yubsub.desktop"
cp build/yubsub.png "$STAGE/usr/share/icons/hicolor/256x256/apps/yubsub.png"
chmod 0755 "$STAGE/opt/yubsub/yubsub"
chmod 0644 "$STAGE/usr/share/applications/yubsub.desktop"
chmod 0644 "$STAGE/usr/share/icons/hicolor/256x256/apps/yubsub.png"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: yubsub
Version: $VERSION
Section: sound
Priority: optional
Architecture: $ARCH
Maintainer: YUBSUB by 2.wav <noreply@github.com>
Depends: ffmpeg (>= 4.4), xdg-utils, ca-certificates, libc6 (>= 2.35)
Description: YUBSUB local YouTube playlist and audio converter for ChromeOS
 YUBSUB runs locally inside the Chromebook Debian Linux environment.
 Convert authorized single videos and playlists to MP3 and FLAC using a
 bundled Python engine and Deno runtime. No separate Python installation.
EOF

mkdir -p dist/chromeos
DEB="dist/chromeos/yubsub_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB"
dpkg-deb --info "$DEB"
dpkg-deb --contents "$DEB" | grep -F '/opt/yubsub/yubsub'
mkdir -p build/verify-deb
dpkg-deb --extract "$DEB" build/verify-deb
build/verify-deb/opt/yubsub/yubsub --smoke-test
sha256sum "$DEB"
printf 'ChromeOS .deb package verified: %s\n' "$DEB"
