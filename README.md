# YUBSUB — Playlist in. MP3s out.

**YUBSUB by 2.wav** is a black-and-yellow branded YouTube / YouTube Music playlist-to-MP3 ZIP tool.

## Website: GitHub Pages at yubsub.godthefather1952.com

The **webpage lives on GitHub Pages**. Python, yt-dlp, Deno, and FFmpeg still run in a small separate server because GitHub Pages only hosts static files.

This repository supports **both** GitHub Pages publishing options:
- **Deploy from a branch:** the default branch (`claude/dreamy-keller-yy8w56`), directory `/(root)`. The root `index.html` and `CNAME` are included for this path.
- **GitHub Actions (preferred):** use the committed `.github/workflows/pages.yml`. It publishes `static/index.html`, generates the API configuration, and deploys the page after changes to the default branch.

### Restore GitHub Pages

1. Go to **[Repository Settings → Pages](https://github.com/godthefather1952/yubsub/settings/pages)**.
2. Under **Build and deployment**, choose **GitHub Actions**. If you prefer the old branch method, choose **Deploy from a branch**, `claude/dreamy-keller-yy8w56`, `/(root)`, and save.
3. Under **Custom domain**, enter `yubsub.godthefather1952.com`, save, and enable **Enforce HTTPS** after your certificate becomes available.
4. At your domain DNS host, set a **CNAME** record with **Name/Host** `yubsub` and **Target/Value** `godthefather1952.github.io` (not `godthefather1952.github.io/yubsub`). Do not replace records for your main domain.
5. Check **[GitHub Actions](https://github.com/godthefather1952/yubsub/actions)** for the **Publish YUBSUB to GitHub Pages** workflow. You can trigger it manually under **Run workflow** if necessary.

The root `CNAME` contains the intended hostname. GitHub Pages **still requires configuring the custom domain in repository Settings**; a CNAME file alone does not change the repository's Pages settings.

### Conversion engine — already connected to Render

The converter already exists in your **My Workspace** as the Render web service **yubsub**:

- API base: **https://yubsub.onrender.com**
- Health endpoint: `https://yubsub.onrender.com/api/health`
- Render dashboard: https://dashboard.render.com/web/srv-dbqi1ptbedkc73dm9v5g
- Source branch: `claude/dreamy-keller-yy8w56`
- Runtime: Docker (Python + yt-dlp + FFmpeg + Deno)

The GitHub Pages frontend now points at this **existing backend** automatically:
- **GitHub Actions deployment:** `.github/workflows/pages.yml` defaults `YUBSUB_API_BASE_URL` to `https://yubsub.onrender.com`, and also allows an optional repository variable of the same name to override it.
- **Branch-based Pages deployment:** `static/config.js` already contains `https://yubsub.onrender.com` and the root `index.html` loads it.

You **do not need to create another Render service** or set an Actions variable for the current deployment.

GitHub Pages remains the public website at `https://yubsub.godthefather1952.com`; Render is only the conversion API. CORS on the backend allows the custom domain and the default `godthefather1952.github.io` origin.

**Important:** The Render free service may take time to wake up after inactivity, and YouTube may challenge or block cloud datacenter IPs. Neither a successful deployment nor a passing mocked test guarantees actual playlist extraction; do an end-to-end test with a small playlist you have permission to download. Restarting/free-host sleep can erase temporary in-progress ZIP jobs. Never publish YouTube session cookies.

**Local alternative:** Run the Docker service locally (below). The Flask app serves the same one-page interface at `http://localhost:5000` and processes audio through your own internet connection.

## Run locally — Docker

```sh
docker build -t yubsub .
docker run --rm -p 5000:5000 yubsub
```

Open **http://localhost:5000**.

## Run locally without Docker

Install Python 3.11+, FFmpeg including ffprobe, and Deno 2.3+ (recommended; Node 22+ also works).

```sh
python -m pip install -r requirements.txt
python app.py
```

On a Mac:

```sh
brew install ffmpeg deno python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## How it works

- Supports public YouTube and YouTube Music URLs containing `list=`.
- Provides 128 / 192 / 256 / 320 kbps MP3 conversion. Re-encoding does **not** increase the quality of the original audio.
- Shows per-track status, ZIP packaging progress, cancellation and skip reasons.
- Produces one ZIP with numbered MP3 files plus `skipped-tracks.txt` if necessary.
- Keeps temporary files for 30 minutes.
- Refreshing the same browser tab can reattach to an existing job while it is still active.

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `PORT` | 5000 | Flask / Gunicorn server port |
| `MAX_TRACKS` | 50 | Max playlist items (hard limit 200) |
| `MAX_ACTIVE_JOBS` | 2 | In-process concurrent conversions (Render: 1) |
| `MAX_ARCHIVE_MB` | 400 | Combined audio payload cap |
| `MAX_TRACK_MB` | 60 | Per-track max source/output limit |
| `YT_COOKIES` | ./cookies.txt | Optional **private local** session cookies |

The backend is a single-process Flask + yt-dlp + FFmpeg app with threads and temporary local files; it is not intended for high-traffic public conversion without authentication, rate limits and durable job storage.

## Testing

```sh
python -m pip install -r requirements.txt pytest
python -m pytest -q
```

Existing tests mock download/conversion and verify ZIP contents. CI also tests Pages CORS and frontend JavaScript syntax. **A live, authorized YouTube playlist test is still required** for the actual deployed backend and internet connection.

## Usage rights

Download only content you own, public-domain media or content you're authorized to save, and comply with applicable law and platform terms. YUBSUB is not affiliated with YouTube.
