# yubsub

Paste a YouTube playlist URL, get a ZIP of MP3s.

## Run
Requires Python 3.9+ and [ffmpeg](https://ffmpeg.org/) on your PATH.

```bash
pip install -r requirements.txt
python app.py   # http://localhost:5000
```

Or with Docker:

```bash
docker build -t yubsub . && docker run -p 5000:5000 yubsub
```

Env: `PORT` (default 5000), `MAX_TRACKS` (default 100). Finished jobs are deleted after 1 hour.
Keep `yt-dlp` updated (`pip install -U yt-dlp`) as YouTube changes often.

Only download content you own or have permission to download.

## Deploy online (one URL, one page)
1. Push this repo to GitHub, then on [Render](https://render.com) choose **New > Blueprint** and select it (`render.yaml` is included). Any Docker host (Fly.io, Railway) works too.
2. Open the URL Render gives you. The same service serves the page and the API.

Optional: host `static/index.html` on GitHub Pages instead, set `window.YUBSUB_API = "https://your-backend"` in it, and set `CORS_ORIGIN=https://you.github.io` on the backend.

Note: YouTube often blocks datacenter IPs. If downloads fail with "Sign in to confirm you're not a bot", run it from a home machine or supply cookies to yt-dlp.

## Windows
Double-click `start.bat` (needs Python and ffmpeg: `winget install ffmpeg`).

## GitHub Codespaces
Open the repo in a Codespace. The `.devcontainer` installs ffmpeg and dependencies and starts the app; open the forwarded port 5000. Or run `python app.py` manually.

## Fixing "Sign in to confirm you're not a bot"
YouTube blocks cloud IPs (Codespaces, Render...) unless requests carry a logged-in session.
1. In Chrome/Firefox, install a "Get cookies.txt LOCALLY" extension.
2. Open youtube.com while logged in, export cookies in Netscape format.
3. Save the file as `cookies.txt` in the project root (in Codespaces, drag it into the file explorer), then restart `python app.py`.

It is auto-detected (or set `YT_COOKIES=/path/to/file`) and is git-ignored. Use a throwaway Google account: heavy automated downloading can get an account flagged. Never commit or share cookies.txt.
