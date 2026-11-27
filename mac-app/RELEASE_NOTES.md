# YUBSUB Desktop v0.5.1 — WAV support across desktop platforms

## New in v0.5.1
- Adds **WAV (16-bit PCM)** export for single YouTube videos and multi-track playlists.
- WAV keeps the source audio's sample rate and uses uncompressed PCM suitable for DAW editing.
- Single WAV files use the existing native Save As dialog. Playlist WAVs are delivered as numbered files in a ZIP.
- The format selector now offers MP3, FLAC and WAV. MP3 keeps its 128–320 kbps controls; WAV and FLAC do not present an MP3 bitrate.
- WAV permits best-effort artist, title, album, release year and RIFF ID3 artwork metadata. Not every WAV player reads embedded artwork; MP3 and FLAC artwork behavior remains intact.
- Raises format-specific WAV track-size limits while retaining archive safety limits.

## Existing features preserved
- Single and playlist modes, MP3 and FLAC conversion and ZIP packaging
- Mac native clipboard Paste, MP3/FLAC/WAV Save As, progress, cancellation and skipped-track reporting
- MusicBrainz identification, official artwork with thumbnail fallback
- Secure Sparkle Ed25519 update verification, Update Now / Later and periodic update checks

## Update
Users on a signed Sparkle-enabled prior release may use **Check for Updates**.
The release contains Intel and Apple Silicon builds and must be signed with
the **existing owner Ed25519 key**. Build and publish only after the cross-
platform CI and on-device checks succeed. This version is not released until
its official `mac-app-v0.5.1` GitHub Release exists.

WAV conversion cannot restore quality already lost by compressed source audio.
WAV files are substantially larger than MP3 and FLAC and can hit playlist
size limits. Only download music or audio you are authorized to save.
