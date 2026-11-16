# YUBSUB Desktop v0.3.0 — standalone macOS application

**No Terminal, Homebrew, Python or pip required.** The YUBSUB application contains its own Python runtime and libraries, yt-dlp + the matching EJS scripts, Deno, FFmpeg and FFprobe.

## What's new in v0.3.0\n\n- **Playlist / Single Video switch** directly above the link field. **Playlist is selected by default.**\n- Playlist mode continues downloading numbered MP3s inside a ZIP file.\n- Single Video mode accepts individual YouTube URLs and downloads the converted audio as a **single .mp3 file, no ZIP**.\n- Mode-aware link examples, status text, action button and download button.\n- Secure URL allowlist on both modes; no arbitrary website downloads.\n\n## Download
- **Intel Macs:** `YUBSUB-macOS-Intel.zip`
- **Apple Silicon (M1/M2/M3/M4/M5):** `YUBSUB-macOS-Apple-Silicon.zip`

Unzip the appropriate archive, drag **YUBSUB.app** into the **Applications** folder and launch it from Finder. YUBSUB opens as a native Mac window, including Save dialogs for your MP3 ZIP downloads. Quit the window to stop its temporary local server.

The app listens only on a randomly selected `127.0.0.1` port. It never exposes an internet-facing API. Max 200 tracks and 1.2 GB of ZIP output per conversion. All media downloads are processed on your Mac.

## Compatibility and limitations

- **Unsigned/unnotarized:** Apple's Gatekeeper may block the app initially. Use Finder's Open command and macOS Privacy & Security controls if you trust the release. There is no supported way to eliminate the warning for all users without Apple Developer ID signing and notarization. Do **not** disable Gatekeeper globally.
- **macOS compatibility:** Built on GitHub-hosted macOS 15 runners for both CPU architectures. Older systems (including macOS 12) require actual device testing and may not run all packaged components.
- **YouTube:** Availability may change. Use YUBSUB only for content you own or have permission to download.
- **No automatic updates:** A later release must be installed manually.
- **No public cloud hosting:** The standalone app works only when the Mac is powered on and YUBSUB is open.

## Third-party binary licenses
YUBSUB bundles FFmpeg / FFprobe static distributions from [eugeneware/ffmpeg-static b6.1.1](https://github.com/eugeneware/ffmpeg-static/releases/tag/b6.1.1), including the corresponding license/README in the app bundle. The upstream FFmpeg source is available at [ffmpeg.org/download](https://ffmpeg.org/download.html). Deno is downloaded from [denoland/deno v2.9.7](https://github.com/denoland/deno/releases/tag/v2.9.7). The build verifies these downloads before packaging.

The build process is in [mac-app/build_macos.sh](https://github.com/godthefather1952/yubsub/blob/main/mac-app/build_macos.sh).
