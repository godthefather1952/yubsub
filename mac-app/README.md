# Standalone Mac application

This directory contains the build source for **YUBSUB.app**. It is separate from the older `mac-installer/` scripts.

## How `requirements.txt` works

At GitHub build time, `pip install -r requirements.txt` installs Flask, yt-dlp and Gunicorn. The build additionally installs the newer yt-dlp nightly, pywebview (the native Cocoa/WebKit window), PyInstaller, and packages Deno, FFmpeg, and FFprobe. PyInstaller freezes Python and its dependencies into the `.app`.

**At user launch time, nothing is installed.** YUBSUB opens as a normal app; the Python interpreter and packages are already inside. The app processes authorized audio directly on the user's Mac.

There are two separate .app downloads (Intel and Apple silicon). The workflow uses standard macOS GitHub Actions runners and publishes the WAV-enabled v0.5.1 release only after the owner configures matching Ed25519 update-signing keys.

## Build locally on a Mac

With macOS, Python 3.12 and network access:

```bash
bash mac-app/build_macos.sh
open dist/YUBSUB.app
```

The script obtains pinned verified binaries for Deno and FFmpeg from public upstream releases and installs the build tools in your **current Python environment**. For isolated builds, use a virtual environment first.

Sparkle 2 is embedded when `SPARKLE_PUBLIC_ED_KEY` is configured; the signed GitHub update archives and feeds are created in the release job. See [UPDATING.md](UPDATING.md) for key setup and security constraints.

**MP3/FLAC/WAV output:** Audio Format selects MP3 (default), FLAC or WAV. MP3 offers bitrate selection; FLAC uses lossless *encoding* of a compressed YouTube source and does not increase original fidelity. All three formats work for single-video files and playlist ZIPs. WAV uses 16-bit PCM with the source sample rate; conversion does not restore quality lost in YouTube audio. The Mac Save dialog uses the selected extension.

**Single video MP3 saving:** The `DesktopUpdatesAPI.save_mp3` bridge validates an in-process, completed single-video job and uses the native macOS Save As dialog to copy the completed file atomically into the destination chosen by the customer. This avoids WebKit's inline audio playback behavior without changing the playlist ZIP workflow.

Build success is verified with a smoke test that loads the app's Flask routes and detects all three bundled executables. The end-to-end GUI and YouTube download path must also be tested on an actual Intel / Apple silicon device.

## Native Paste button

The embedded macOS WebKit window may deny `navigator.clipboard.readText()`. The Desktop bridge calls `AppKit.NSPasteboard.generalPasteboard()` only when the user clicks **PASTE**, returning plain text to the URL input. GitHub Pages continues using the browser clipboard API.

## Important limitations

- This is an **unsigned** application; Gatekeeper warnings are not eliminated until signing and notarization.
- Because the GitHub builds run on macOS 15, runtime support for the user's older macOS 12 Intel machine has not yet been validated.
- The binary FFmpeg distributions include a GPL license; review their source and distribution terms before commercial release.
- Do not publish private cookies, tokens or credentials inside the binary.
- A standalone app runs locally; it does not convert videos on a server while the Mac is off.
