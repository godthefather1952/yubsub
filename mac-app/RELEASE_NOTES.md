# YUBSUB Desktop v0.4.1 — Native macOS MP3 Save As fix

## Fixed in v0.4.1

**Single Video → Download Your MP3** now opens a native macOS **Save As** dialog. Choose the destination folder and filename; the completed MP3 is written directly to disk instead of opening as playable audio inside the app.

- Native Save dialog for individual MP3 downloads on macOS.
- Keep the converted MP3 available to save again without re-converting.
- Safe, atomic writing to the selected location; cancelling the dialog leaves the source untouched.
- **Playlist mode** still downloads numbered MP3 files as a ZIP, unchanged.
- GitHub Pages/browser visitors continue using the standard HTTP attachment endpoint.
- Includes Sparkle automatic update support from v0.4.0; Intel and Apple silicon release packages are Ed25519-signed for update verification.

## Download

- **Intel Macs:** `YUBSUB-macOS-Intel.zip`
- **Apple silicon Macs:** `YUBSUB-macOS-Apple-Silicon.zip`

If you already have v0.4.0 installed, click **Check for Updates** to try the new secure updater. If the update prompt does not work, install v0.4.1 manually by replacing YUBSUB.app in Applications.

## How YUBSUB works

YUBSUB is a standalone local macOS application. Python, yt-dlp, Deno, FFmpeg and FFprobe are bundled. It offers **Playlist mode** (default, ZIP of numbered MP3s) and **Single Video mode** (one MP3), selectable audio quality and conversion progress. No Terminal, Homebrew, pip or subscriptions required.

## Compatibility and important limitations

- **Apple Gatekeeper:** This software is not Developer ID signed/notarized. macOS may ask you to approve it at first launch. Update archives are separately Ed25519-signed for Sparkle; that does not replace Apple's Gatekeeper checks.
- **Older Macs:** Built on macOS 15 GitHub runners; test older macOS versions on an actual device.
- **Update installation:** A real device upgrade from v0.4.0 to v0.4.1 still needs to be verified.
- **Rights:** Download only content you own or have permission to use.
- **Local:** The Mac must be running YUBSUB to process downloads.

## Third-party components

The included FFmpeg/FFprobe static distributions use [eugeneware/ffmpeg-static b6.1.1](https://github.com/eugeneware/ffmpeg-static/releases/tag/b6.1.1) with their license and README bundled in the app. [Deno v2.9.7](https://github.com/denoland/deno/releases/tag/v2.9.7) and [Sparkle v2.10.1](https://github.com/sparkle-project/Sparkle/releases/tag/2.10.1) are included in the build. Review these projects' licenses before commercial distribution.
