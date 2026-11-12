# yubsub — YouTube playlist to MP3 ZIP

A responsive single webpage with a tiny Flask backend. No accounts, database, build pipeline, third-party UI framework, bucket, or CORS required.

## What it does

Paste a YouTube or YouTube Music playlist URL containing a list= identifier, choose MP3 quality, and get one ZIP with numbered MP3 files. The page displays the playlist title, track-by-track progress, download progress, cancellation, skipped tracks, and a ZIP link. If any tracks fail, the ZIP includes a skipped-tracks.txt explanation. Jobs expire and files are removed after 30 minutes.

## Local installation

Install Python 3.10+, FFmpeg (including ffprobe) and **Deno 2.3+** (recommended; Node 22+ also works). A JavaScript runtime is required by recent yt-dlp for YouTube.

    python -m pip install -r requirements.txt
    python app.py

Open http://localhost:5000 in a browser.

### Docker

Docker installs Python, FFmpeg and Deno automatically:

    docker build -t yubsub .
    docker run --rm -p 5000:5000 yubsub

### Render (one public URL)

At https://dashboard.render.com/blueprints, create a Blueprint from this GitHub repository. render.yaml specifies a single Docker web service. Open its Render URL; the page and its API run together. You do not need GitHub Pages.

**Cloud reliability warning:** YouTube routinely challenges or blocks datacenter IPs, including Render and GitHub Codespaces. Updating the site cannot guarantee YouTube extraction will work on a remote server. If you encounter bot verification, run locally from your own connection. Do not publish cookies or session credentials. Use only content you own or are authorized to download.

## Optional local cookies

For your own authorized YouTube session, place Netscape-format cookies.txt in the repository directory, or set YT_COOKIES to an absolute local path. Cookies are optional and both .gitignore and .dockerignore exclude the default file. Never commit cookies or paste them into issues.

## Configuration

- PORT: web port (5000)
- MAX_TRACKS: tracks per job (50; hard maximum 200)
- MAX_ACTIVE_JOBS: concurrent conversions per process (2; Render: 1)
- MAX_ARCHIVE_MB: combined MP3 payload limit (400 MB)
- MAX_TRACK_MB: per-track source file limit (60 MB)
- YT_COOKIES: private local cookies file path (optional)

This deliberately has one Gunicorn process with background threads and temporary local storage. It is not designed for heavy public traffic or horizontally scaled hosting.

## Testing

    python -m pip install -r requirements.txt pytest
    pytest -q

Automated tests mock yt-dlp and verify URL restrictions, API validation, and ZIP contents. Real YouTube playback/extraction depends on external access and must be tested with a public playlist you have rights to.

**Important:** A browser-only YouTube audio downloader is not viable due to browser CORS restrictions and audio extraction requirements. The backend exists only to run yt-dlp + FFmpeg and deliver the archive.