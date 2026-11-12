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

### Connect the actual conversion backend

A Pages-only website **cannot** download arbitrary YouTube media, run FFmpeg, or create a ZIP. The frontend intentionally reports **API NOT CONNECTED** until a working backend is configured, rather than pretending a download succeeded.

**Option A — public website that converts from your phone:**

1. Deploy this same repository as a Docker web service on Render (or another Docker host), using `Dockerfile` and the included `render.yaml`. GitHub Pages and the Docker backend are **separate services**. Render is hosting only the backend; it is **not** replacing GitHub Pages.
2. Verify the backend's `https://<your-service>.onrender.com/api/health` endpoint returns `"ok": true`.
3. Go to **[Repository Settings → Secrets and variables → Actions](https://github.com/godthefather1952/yubsub/settings/variables/actions)**, choose **Variables** → **New repository variable**, set:
   - **Name:** `YUBSUB_API_BASE_URL`
   - **Value:** your public backend HTTPS origin, e.g., `https://<your-service>.onrender.com` (no `/api` suffix).
4. With GitHub Pages configured to build via **GitHub Actions**, run **Publish YUBSUB to GitHub Pages** again. It embeds the configured public API origin into the static page.

If you use branch-based Pages publishing instead, edit `static/config.js` and set `window.YUBSUB_API_BASE_URL` to your backend's HTTPS origin.

Backend CORS explicitly allows the origins `https://yubsub.godthefather1952.com` and `https://godthefather1952.github.io` (GitHub Pages default host). If you move the frontend, update `FRONTEND_ORIGINS` in `app.py`.

**Important:** YouTube frequently challenges or blocks cloud datacenter IPs. Neither Render nor any cloud host is guaranteed to support every playlist. Also, free hosts can sleep/restart and lose temporary jobs. Never publish session cookies.

**Option B — use the GitHub Pages design with a local converter:**

Start the Flask app with Docker or Python (instructions below). The local Flask application serves the same YUBSUB page at `http://localhost:5000` and converts on your own computer. This is generally more reliable than using cloud datacenter IPs. The publicly hosted GitHub Pages version still needs a configured backend.

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
