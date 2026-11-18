# YUBSUB Desktop v0.4.2 — MP3 and FLAC output formats

## New in v0.4.2

- **Audio Format** selector: choose MP3 or FLAC. **MP3 is the default.**
- **Single Video:** convert one video to a direct `.mp3` or `.flac` file using the native macOS Save As dialog.
- **Playlist:** convert multiple videos to numbered MP3 or FLAC files inside a ZIP archive.
- MP3 bitrate options remain available (128, 192, 256, 320 kbps); they hide when FLAC is selected because FLAC has no MP3 bitrate setting.
- FLAC files are usually larger. Since YouTube audio is typically already lossy-compressed, FLAC conversion does **not** restore lost source fidelity.
- The current progress display, cancellation, signed Sparkle updates, and local-only processing remain in place.

## Install or update

Download **YUBSUB.app** for your Mac:
- **Intel:** `YUBSUB-macOS-Intel.zip`
- **Apple Silicon:** `YUBSUB-macOS-Apple-Silicon.zip`

Existing users on v0.4.0 or v0.4.1 can open YUBSUB and try **Check for Updates**. If in-app updating fails, replace the installed app manually with the appropriate downloaded version.

No Terminal, Python, Homebrew or additional FFmpeg installation is necessary. Both architectures ship with the audio conversion dependencies included.

## Compatibility, security, rights

- ZIP downloads and MP3 remain backwards-compatible; omitting the new `format` API field defaults to MP3.
- Official release ZIPs and the two architecture-specific Sparkle appcasts are signed with the existing Ed25519 signing key; keys never ship in source.
- The app is not yet Apple Developer ID signed/notarized, so macOS Gatekeeper may still show first-launch warnings.
- Built with GitHub macOS 15 runners; test on your supported Mac devices.
- Download audio only when you own or have permission to use it.
- FLAC output may consume much more storage, and existing file-size / archive-size safeguards still apply.

## Included third-party components

This release bundles Python dependencies, yt-dlp, Deno, FFmpeg, FFprobe, and Sparkle. FFmpeg/FFprobe static distribution credits and licenses are packaged inside the app. Review redistribution obligations before selling.
