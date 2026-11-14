# YUBSUB for Mac — first-time installer v0.1.0

**One ZIP. One double-click.** No GitHub account or manual Terminal commands required to install.

### Install
1. Download **YUBSUB-Mac-First-Time-Installer.zip** below and unzip it.
2. Double-click **Install YUBSUB.command** (right-click → Open if macOS asks).
3. The installer fetches YUBSUB, sets up Python, yt-dlp, Deno and FFmpeg, and adds **Launch YUBSUB.command** to your Desktop.
4. Use the Desktop launcher whenever you want to run YUBSUB at **http://127.0.0.1:8000**. Keep the Terminal window open during downloads.

**Mac only; Intel and Apple silicon.** No Docker or Git setup required. An internet connection is needed for first-time setup and downloads. macOS may request administrator approval to install dependencies. Some older macOS versions may not support the latest Homebrew packages.

Runs locally on `127.0.0.1`, not as a public server. ZIPs are temporary and expire after 30 minutes. YouTube availability varies; download only media you own or have permission to save.

**Testing:** Shell syntax, packaging and CI checks are automated; clean-machine installation needs real-world macOS testing.

See [Mac setup files](https://github.com/godthefather1952/yubsub/tree/main/mac-installer) for the installer scripts and [README](https://github.com/godthefather1952/yubsub#readme) for backend limitations.
