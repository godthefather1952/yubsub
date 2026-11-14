YUBSUB BY 2.WAV — ONE-CLICK MAC INSTALLER
=========================================

HOW TO INSTALL
1. Unzip this entire archive. Keep the files in the same folder.
2. Double-click "Install YUBSUB.command".
   macOS may require you to right-click > Open the first time.
3. Follow any macOS permission prompts. Installation needs internet access.
   It may request an administrator password to install Homebrew,
   Python or FFmpeg if those dependencies are not already installed.
4. The installer downloads the latest YUBSUB source from the public repo,
   installs dependencies, puts a launcher on your Desktop, and opens the app.

AFTER INSTALLATION
- Double-click "Launch YUBSUB.command" on your Desktop when you want to use it.
- Web page: http://127.0.0.1:8000
- Keep its Terminal window running while converting playlists.
- Press Control+C in that window to shut down the server.
- Max 200 tracks and 1200 MB total archive size per job.
- Requires macOS with Python 3.11+ support, and internet access.
- The app runs only on your own Mac, not on an internet-facing port.

WHERE FILES GO
- Application: ~/Applications/YUBSUB
- Launcher: ~/Desktop/Launch YUBSUB.command
- Temporary downloads are managed by YUBSUB and removed automatically.

WHAT THIS INSTALLS
- Python 3.11+ (only when needed; via Homebrew)
- FFmpeg (only when needed; via Homebrew)
- Deno JavaScript runtime (only when needed; from official Deno installer)
- Python packages from requirements.txt, plus the yt-dlp nightly channel
- YUBSUB source from https://github.com/godthefather1952/yubsub

HOMEBREW NOTE
If Homebrew is not installed, its official installer runs and may request
Apple Command Line Tools or a password. On unsupported older macOS versions,
Homebrew may fail; this is an OS tooling limitation, not a YUBSUB failure.

PRIVACY AND SECURITY
- No YouTube credentials or cookies are requested by this package.
- Never put authentication cookies in shared ZIPs or GitHub.
- This package downloads installation tools from their official websites.
- Only download audio you own or have permission to save.
- No service is configured to start automatically at login.

SUPPORT
https://github.com/godthefather1952/yubsub
