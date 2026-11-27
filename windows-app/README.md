# YUBSUB for Windows (x64)

This folder builds the Windows counterpart to YUBSUB Desktop for macOS. The
**same `app.py` and `static/index.html`** power the Windows, macOS and web
versions. A platform-specific launcher handles native desktop controls.

## What is included

- One portable `YUBSUB.exe` **inside a ZIP with its `_internal` folder**.
  Do not move only `YUBSUB.exe` out of the extracted folder.
- One `YUBSUB-Setup-v0.5.0.exe` installer. It installs per-user into
  `%LOCALAPPDATA%\Programs\YUBSUB`, creates a Start Menu shortcut,
  offers a Desktop shortcut, and supports uninstalling.
- Native Windows clipboard Paste, native Save As for single MP3/FLAC files,
  one ZIP for playlists, download progress/cancellation and single-video mode.
- MP3 or FLAC conversion; original bitrate options apply to MP3 only.
- Optional embedded artist, track, album, release-year and artwork tagging.
  MusicBrainz and Cover Art Archive are queried when there is a confident
  match. The original YouTube thumbnail may be used as a fallback.
- Bundled Python/yt-dlp/Deno/FFmpeg/FFprobe, so no user-side Python or
  developer toolchain is required.
- User-confirmed Windows updates using signed Ed25519 manifests and verified
  installer SHA-256 hashes. The updater will only operate when the owner
  configured the same Ed25519 key already used for the Mac Sparkle releases.

**Windows 10/11 64-bit only for this build.** Windows 11 typically has Microsoft
Edge WebView2 preinstalled. The installer bundles Microsoft's signed Evergreen
WebView2 bootstrapper and runs it only if necessary; that step may require
internet access. Portable ZIP users need WebView2 installed already.
ARM64 Windows is not built natively in this first release.

## Build from source (Windows)

Use a Windows x64 machine with Python 3.12 and an internet connection:

```powershell
powershell -ExecutionPolicy Bypass -File windows-app/build_windows.ps1
choco install innosetup -y
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "/DAppVersion=0.5.0" windows-app/installer.iss
```

The build script downloads a pinned Deno release and checks its published
SHA-256, bundles an FFmpeg Essentials archive and records its SHA-256, and
includes an official Microsoft-signed WebView2 bootstrapper. It then builds
`dist/YUBSUB/YUBSUB.exe` with PyInstaller and checks the frozen executable.

The GitHub Actions workflow `.github/workflows/windows-app.yml` builds an
installer and portable ZIP on a Windows runner, checks the frozen binary,
and uploads both as workflow artifacts for review. Merging to `main` publishes
a separate `windows-vX.Y.Z` release only if the existing Sparkle Ed25519
public/private signing credentials are configured. The Windows updater
discovers `windows-v*` releases from GitHub rather than relying on
`releases/latest`, preserving the Mac Sparkle update feed.

## Future updates

Increment `windows-app/VERSION` with each new Windows release. A Windows app
with a configured trusted public key can use **Check for Updates**. The app
verifies the signed manifest and the installer payload hash, presents
**Update Now / Later**, then launches the verified Inno Setup installer.
Updates are never silently installed. An unsigned PR build can still run
downloads, but cannot safely self-update.

**Windows code signing is separate from Ed25519 update manifest signing.**
Until an Authenticode certificate and a reputation history are configured,
Windows SmartScreen may warn about a downloaded installer or portable EXE.
Do not claim this is a digitally signed Windows executable. The build will
need physical Windows 10/11 testing for real clipboard dialogs, WebView2,
installed upgrades, FLAC/MP3 playback, and YouTube permission restrictions.

FFmpeg distributions may be GPL-licensed; redistribute the applicable
copyright/license notices and satisfy source-distribution obligations
before selling Windows binaries. Only download media you are authorized to
save.
