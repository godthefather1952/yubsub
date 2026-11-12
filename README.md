# YUBSUB — Playlist in. MP3s out.

**YUBSUB by 2.wav** is a branded, mobile-friendly, single-page YouTube / YouTube Music playlist converter. Paste an authorized playlist URL, choose MP3 bitrate and download a ZIP containing individually numbered MP3s.

**One webpage. One small backend. No sign-up, database, JavaScript build step or cloud storage required.**

## What you get

- Responsive black, charcoal, white and yellow 2.wav-inspired design.
- Accepts YouTube or YouTube Music URLs with a `list=` playlist ID.
- 128, 192, 256, or 320 kbps MP3 output (re-encoding does not improve the original source).
- Live playlist scan, song-by-song conversion progress, cancellation, and skipped-track report.
- One numbered MP3 per available track in a ZIP; skipped tracks are noted in `skipped-tracks.txt`.
- Refresh-safe running jobs in the same browser tab (the page reconnects through session storage).
- Temporary jobs and archive files expire after 30 minutes.

## Quick start — Docker (recommended)

Docker installs Python, FFmpeg, Deno, yt-dlp and the required YouTube EJS components.

```sh
docker build -t yubsub .
docker run --rm -p 5000:5000 yubsub
```

Open **http://localhost:5000**.

## Run without Docker

Install Python **3.11+**, [FFmpeg](https://ffmpeg.org/download.html) (including `ffprobe`), and [Deno 2.3+](https://docs.deno.com/runtime/getting_started/installation/) (recommended) or Node.js 22+.

```sh
python -m pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. The `yt-dlp[default]` package installs the YouTube JavaScript challenge components (`yt-dlp-ejs`) alongside the downloader. If YouTube changes its extraction requirements, upgrade the packages:

```sh
python -m pip install -U "yt-dlp[default]"
```

### Mac example

```sh
brew install ffmpeg deno python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Put it online with Render

1. Push or merge this branch into the branch you want to deploy.
2. Open [Render Blueprints](https://dashboard.render.com/blueprints) and connect this GitHub repo.
3. Render reads `render.yaml`, builds `Dockerfile` and hosts the page and backend together at one Render URL. Do **not** use GitHub Pages; static hosting cannot run yt-dlp or FFmpeg.

**Hosting caveats:** Many datacenter IPs (including Render) can be blocked by YouTube or presented with a bot challenge; code cannot guarantee extraction from a hosted IP. Run locally on your own internet connection if the host is blocked. Render Free services spin down when idle; their temporary filesystem also clears on restart/redeploy/spin-down, so an active ZIP job can be lost. For reliability with large playlists, run the Docker app locally or use a more persistent host.

Never upload your YouTube cookies to a public repo, GitHub issue or deployment environment.

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `PORT` | `5000` | App server port |
| `MAX_TRACKS` | `50` | Max tracks per playlist job (hard max 200) |
| `MAX_ACTIVE_JOBS` | `2` | Concurrent jobs per Python process (Render: 1) |
| `MAX_ARCHIVE_MB` | `400` | Max combined ZIP audio payload |
| `MAX_TRACK_MB` | `60` | Max audio file per track |
| `YT_COOKIES` | `./cookies.txt` | Optional private, local Netscape-format session cookies |

The server uses one Gunicorn process with background threads and temporary local files. It is intended for personal/small-scale use, not high-traffic multi-instance production hosting.

## Testing

```sh
python -m pip install -r requirements.txt pytest
python -m pytest -q
```

`.github/workflows/tests.yml` also tests the backend and checks the frontend JavaScript syntax on GitHub.

Automated tests mock YouTube extraction. You need to do one manual end-to-end test with a public playlist of media you own or are authorized to download in order to verify YouTube connectivity and MP3 ZIP output from your own environment.

## Legal and technical note

YUBSUB is not affiliated with YouTube. Use it only for audio you own, public-domain material or downloads you are otherwise authorized to make, and comply with applicable laws and service terms. Some content is private, age-restricted, unavailable in some regions, or blocked to the machine running the converter. There is no reliable *browser-only* way to fetch an arbitrary YouTube playlist, convert all entries to MP3 and package a ZIP due to cross-origin restrictions and the need for FFmpeg.
