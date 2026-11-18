# YUBSUB Desktop v0.4.3 — Reliable macOS Paste button

## Fixed in v0.4.3

The **PASTE** button in YUBSUB Desktop now reads text directly from the **macOS clipboard** when clicked. Previously, WebKit's browser clipboard API could deny access and show "Clipboard access is unavailable here" even when a YouTube link was copied.

- Native `NSPasteboard` integration avoids embedded WebKit clipboard-permission failures.
- The Paste button works for both **Single Video** and **Playlist** modes.
- The regular browser version still uses the web clipboard API.
- Empty clipboards and permission failures show actionable messages.
- No clipboard content is read at startup, saved or logged by YUBSUB; reading occurs when you click Paste.

All features from v0.4.2 are preserved, including MP3 or FLAC conversion, playlist ZIPs, the Mac Save As dialog, progress reporting and signed Sparkle automatic updates.

## Install or update

Open YUBSUB and click **Check for Updates**. The release contains both Intel and Apple silicon versions, with the same signature key as earlier updates.

Downloadable packages:
- `YUBSUB-macOS-Intel.zip`
- `YUBSUB-macOS-Apple-Silicon.zip`

If the update prompt fails, download and replace your installed `YUBSUB.app` with the correct version from the GitHub release.

## Compatibility notes

- Signed Sparkle updates are separate from Apple Developer ID signing/notarization; the unsigned Mac app may still show a first-launch Gatekeeper warning.
- PyInstaller packages all local Python, yt-dlp, Deno and FFmpeg dependencies.
- Only download content you own or have permission to download.
- Test the PASTE button on a real Mac after updating to confirm local clipboard permissions and the full GUI flow.
