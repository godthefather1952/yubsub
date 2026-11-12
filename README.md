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
