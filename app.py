"""yubsub: YouTube playlist -> MP3 zip downloader.

Run:  python app.py   (needs ffmpeg on PATH)
Only download content you have the right to download.
"""
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
import zipfile

from flask import Flask, jsonify, request, send_file, send_from_directory
import yt_dlp

app = Flask(__name__, static_folder="static")

MAX_TRACKS = int(os.environ.get("MAX_TRACKS", "100"))
JOB_TTL = 60 * 60  # seconds before finished jobs are deleted
JOBS = {}
LOCK = threading.Lock()


def safe_name(s, fallback="track"):
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", s or "").strip(" .")
    return (s or fallback)[:120]


def update(job, **kw):
    with LOCK:
        job.update(kw)


def run_job(job):
    work = job["dir"]
    try:
        base = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}
        with yt_dlp.YoutubeDL(base) as ydl:
            info = ydl.extract_info(job["url"], download=False)
        entries = [e for e in (info.get("entries") or [info]) if e]
        entries = entries[:MAX_TRACKS]
        title = safe_name(info.get("title"), "playlist")
        update(job, total=len(entries), title=title, status="downloading")

        files = []
        for i, e in enumerate(entries, 1):
            if job.get("cancel"):
                raise RuntimeError("cancelled")
            vid = e.get("url") or e.get("id")
            if vid and not vid.startswith("http"):
                vid = f"https://www.youtube.com/watch?v={vid}"
            name = f"{i:03d} - {safe_name(e.get('title'), e.get('id'))}"
            update(job, current=e.get("title") or name, done=i - 1)
            opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "format": "bestaudio/best",
                "outtmpl": os.path.join(work, name + ".%(ext)s"),
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": job["quality"]},
                    {"key": "FFmpegMetadata"},
                ],
            }
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([vid])
                path = os.path.join(work, name + ".mp3")
                if os.path.exists(path):
                    files.append(path)
                else:
                    job["failed"].append(name)
            except Exception as ex:  # skip private/deleted videos
                job["failed"].append(f"{name} ({str(ex)[:80]})")
            update(job, done=i)

        if not files:
            raise RuntimeError("No tracks could be downloaded.")
        update(job, status="zipping")
        zpath = os.path.join(work, title + ".zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
            for f in files:
                z.write(f, os.path.basename(f))
        update(job, status="done", zip=zpath, zipname=title + ".zip", finished=time.time())
    except Exception as ex:
        update(job, status="error", error=str(ex)[:300], finished=time.time())


def reaper():
    while True:
        time.sleep(300)
        now = time.time()
        with LOCK:
            old = [k for k, j in JOBS.items() if j.get("finished") and now - j["finished"] > JOB_TTL]
            for k in old:
                shutil.rmtree(JOBS[k]["dir"], ignore_errors=True)
                del JOBS[k]


threading.Thread(target=reaper, daemon=True).start()


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.post("/api/start")
def start():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not re.match(r"^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", url):
        return jsonify(error="Please enter a valid YouTube playlist URL."), 400
    quality = str(data.get("quality", "192"))
    if quality not in {"128", "192", "256", "320"}:
        quality = "192"
    jid = uuid.uuid4().hex
    job = {"id": jid, "url": url, "quality": quality, "status": "starting", "total": 0, "done": 0,
           "current": "", "failed": [], "dir": tempfile.mkdtemp(prefix="yubsub_")}
    with LOCK:
        JOBS[jid] = job
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
    return jsonify(id=jid)


@app.get("/api/status/<jid>")
def status(jid):
    job = JOBS.get(jid)
    if not job:
        return jsonify(error="Unknown job"), 404
    keys = ("status", "total", "done", "current", "failed", "error", "title")
    return jsonify({k: job.get(k) for k in keys})


@app.get("/api/zip/<jid>")
def get_zip(jid):
    job = JOBS.get(jid)
    if not job or job.get("status") != "done":
        return jsonify(error="Not ready"), 404
    return send_file(job["zip"], as_attachment=True, download_name=job["zipname"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
