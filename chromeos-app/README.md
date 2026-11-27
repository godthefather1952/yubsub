# YUBSUB for ChromeOS Linux (.deb)

This is the local ChromeOS/Crostini Linux edition, not a web-only PWA or
Chrome extension. The same Flask, yt-dlp, FFmpeg and shared interface run
locally on the Chromebook. Downloads are processed on-device without
depending on YUBSUB's Render converter.

## Installer packages

The GitHub Actions workflow produces two installer files:

- yubsub_0.5.1_amd64.deb — 64-bit Intel/AMD Chromebooks
- yubsub_0.5.1_arm64.deb — 64-bit ARM Chromebooks

They install YUBSUB under /opt/yubsub and add a YUBSUB launcher to the
ChromeOS Linux apps menu. They include the frozen Python engine and
checksum-verified Deno; the Debian package manager automatically installs
FFmpeg, xdg-utils and CA certificates. No manual pip/Python installation
is needed on an end-user Chromebook.

## Install

1. In ChromeOS Settings > About ChromeOS > Developers, turn on the Linux
   development environment if your Chromebook supports it.
2. In Linux Terminal, run: uname -m
   x86_64 means choose amd64; aarch64 means choose arm64.
3. Download the corresponding official YUBSUB .deb package.
4. In ChromeOS Files, select Install with Linux, or copy the .deb to Linux
   files and use: sudo apt install ./yubsub_0.5.1_amd64.deb
   Substitute the correct architecture filename.
5. Open YUBSUB from Linux apps. The launcher runs the local audio engine and
   opens Chrome on http://localhost:8765. If necessary open this address
   manually while YUBSUB is running.
6. ChromeOS browser downloads use the normal ChromeOS download location.
   Set Chrome to ask where to save files if desired.

ChromeOS Developer Mode is not necessary. The device must support Linux
applications and its Linux installation must be Debian 12+ (glibc 2.35+).
Old Linux environments and Chromebooks without Linux support cannot use
these packages. Linux Files and ChromeOS shared folders are integrated into
the ChromeOS Files application.

## Features carried forward

- Single-video downloads to MP3/FLAC/WAV, playlists to numbered ZIP files
- MP3 quality selector (128/192/256/320 kbps), FLAC and WAV options; WAV is uncompressed PCM and can be substantially larger
- Clipboard Paste, normal ChromeOS browser saving and download prompts
- Progress, cancellation, skipped-track reporting and temporary files
- Optional artist/title/album/year and embedded album-art tagging
- Local conversion without reliance on public Render service
- Daily automatic Linux update checks with signed .deb downloads offered for explicit user approval

The existing owner Ed25519 public key authenticates signed chromeos-v*
release manifests. The Linux updater checks for signed updates when the browser opens (at most daily) and verifies the full downloaded .deb
against its signed size and SHA256 before Chrome is allowed to download it.
An updater without an owner public key is disabled, including unsigned
development builds. The user installs a verified package explicitly via
Files; YUBSUB never requests sudo or silently installs updates.

The Linux app binds only to 127.0.0.1:8765. ChromeOS forwards localhost
requests to its Linux environment. To avoid keeping the Linux environment
awake indefinitely, the local YUBSUB server exits after 45 minutes with
no page activity or active conversions.

## Build and quality assurance

The workflow in .github/workflows/chromeos-app.yml builds native amd64 and
arm64 Linux versions using Ubuntu 22.04 runners, installs Python dependencies
and Deno, packages a self-contained PyInstaller executable, creates each
.deb with dpkg-deb, verifies the architecture, and smoke-tests the executable
and extracted installation. Development PR builds offer separate GitHub
Actions artifact downloads for both architectures. Once integrated in main
and signed using the owner's private key, official ChromeOS releases use
chromeos-vX.Y.Z tags, separate from Mac and Windows.

Local build command on a Linux machine with apt FFmpeg, xdg-utils, curl,
unzip, dpkg-deb and Python 3.12:

    bash chromeos-app/build_linux.sh

Output files are placed under dist/chromeos/.

Real Chromebook testing remains necessary: verify launching Chrome,
clipboard paste, single MP3, single FLAC, playlist ZIP, cover tags,
conversion cancellation, signed updates, and install/uninstall on both
processor architectures. Automated CI on ordinary Linux does not prove
ChromeOS host-browser integration. Some managed devices block Linux.

Only download content you own or have permission to save.
