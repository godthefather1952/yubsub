"""yubsub: one-page playlist to MP3 ZIP. Download authorized content only."""
import itertools
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yt_dlp
from flask import Flask, jsonify, request, send_file

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

# The UI is hosted on GitHub Pages, while this Python app runs separately.
# Browser clients require explicit, narrow cross-origin access to the API.
FRONTEND_ORIGINS = {
    "https://yubsub.godthefather1952.com",
    "https://godthefather1952.github.io",
}


@app.after_request
def allow_pages_origin(response):
    origin = request.headers.get("Origin")
    if origin in FRONTEND_ORIGINS and request.path.startswith("/api/"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers.add("Vary", "Origin")
    return response
MAX_TRACKS = max(1, min(200, int(os.getenv("MAX_TRACKS", "50"))))
MAX_ACTIVE = max(1, int(os.getenv("MAX_ACTIVE_JOBS", "2")))
MAX_TOTAL = max(10, int(os.getenv("MAX_ARCHIVE_MB", "400"))) * 1024**2
MAX_TRACK = max(5, int(os.getenv("MAX_TRACK_MB", "60"))) * 1024**2
# FLAC encodes uncompressed PCM losslessly and is much larger than MP3.
MAX_FLAC_TRACK = max(5, int(os.getenv("MAX_FLAC_TRACK_MB", "250"))) * 1024**2
AUDIO_FORMATS = {"mp3", "flac"}
COOKIE_FILE = Path(os.getenv("YT_COOKIES", str(ROOT / "cookies.txt")))
JOBS = {}
LOCK = threading.RLock()
FINAL = {"complete", "error", "cancelled"}


def playlist_url(raw):
    """Accept only YouTube playlist identifiers, never arbitrary destination hosts."""
    try:
        u = urlsplit(raw.strip())
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
            return None
        if u.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com",
                              "music.youtube.com", "youtu.be", "www.youtu.be"):
            return None
        playlist_id = (parse_qs(u.query).get("list") or [""])[0]
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,128}", playlist_id):
            return None
        return "https://www.youtube.com/playlist?list=" + playlist_id
    except (ValueError, AttributeError):
        return None


def video_url(raw):
    """Accept a single YouTube video link and return a canonical watch URL."""
    try:
        u = urlsplit(raw.strip())
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
            return None
        if u.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com",
                              "music.youtube.com", "youtu.be", "www.youtu.be"):
            return None
        if u.hostname in ("youtu.be", "www.youtu.be"):
            match = re.fullmatch(r"/([A-Za-z0-9_-]{11})/?", u.path)
            video_id = match.group(1) if match else ""
        elif u.path == "/watch":
            video_id = (parse_qs(u.query).get("v") or [""])[0]
        else:
            match = re.fullmatch(r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})/?", u.path)
            video_id = match.group(1) if match else ""
        return ("https://www.youtube.com/watch?v=" + video_id
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) else None)
    except (ValueError, AttributeError):
        return None


def safe_name(value, fallback="playlist"):
    value = re.sub(r'[\x00-\x1f\\/:*?"<>|]', "_", str(value or ""))
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:115] or fallback


def update(job, **kwargs):
    with LOCK:
        job.update(kwargs)


class ExtractorLogger:
    """Keep yt-dlp's original extraction error so we can retry intelligently."""
    def __init__(self):
        self.errors = []

    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        self.errors.append(str(message))


def player_response_error(reason):
    value = str(reason).lower()
    return ("failed to extract any player response" in value
            or "all player responses are invalid" in value)


def download_video(video_id, options):
    """Download one video, preserving the error that yt-dlp normally only logs."""
    logger = ExtractorLogger()
    options = dict(options, ignoreerrors=False, logger=logger)
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.download(["https://www.youtube.com/watch?v=" + video_id])
        if result:
            raise RuntimeError(logger.errors[-1] if logger.errors
                               else "yt-dlp could not download this track.")
        return result
    except InterruptedError:
        raise
    except Exception as exc:
        if logger.errors:
            raise RuntimeError(logger.errors[-1]) from exc
        raise


def readable_error(exc):
    reason = str(exc).strip()
    lower = reason.lower()
    if player_response_error(reason):
        return ("YouTube is not providing playable video data to this server. "
                "This may be a YouTube extractor change or a restriction on Render's IP. "
                "Try again later or use YUBSUB locally. See README.")
    if any(x in lower for x in ("confirm you're not a bot", "sign in to confirm",
                                 "http error 429", "too many requests")):
        return ("YouTube blocked this machine or cloud IP. Try running Yubsub locally "
                "or see README for optional authorized cookies.txt setup.")
    if "ffmpeg" in lower:
        return "FFmpeg is missing. Install FFmpeg and restart."
    return reason[-350:] or "Unknown download error."


def yt_options(**extra):
    opts = dict(quiet=True, no_warnings=True, no_color=True, socket_timeout=25,
                retries=2, fragment_retries=2, extractor_retries=1,
                # Allow yt-dlp to refresh JS solver components when YouTube changes.
                remote_components=["ejs:github"])
    if COOKIE_FILE.is_file():
        opts["cookiefile"] = str(COOKIE_FILE)
    if shutil.which("deno"):
        opts["js_runtimes"] = {"deno": {}}
    elif shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}
    opts.update(extra)
    return opts


def check_cancel(job):
    if job["stop"].is_set():
        raise InterruptedError("cancelled")


def run_job(job):
    folder = Path(job["directory"])
    try:
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            raise RuntimeError("FFmpeg is not installed.")
        if not (shutil.which("deno") or shutil.which("node")):
            raise RuntimeError("Deno 2.3+ (or Node 22+) is required for YouTube.")
        mode = job.get("mode", "playlist")
        audio_format = job.get("format", "mp3")
        if audio_format not in AUDIO_FORMATS:
            raise ValueError("Unsupported audio format.")
        max_track = MAX_FLAC_TRACK if audio_format == "flac" else MAX_TRACK
        update(job, status="reading")
        if mode == "single":
            with yt_dlp.YoutubeDL(yt_options(skip_download=True, noplaylist=True,
                                             ignoreerrors=False)) as ydl:
                info = ydl.extract_info(job["url"], download=False)
            check_cancel(job)
            if not info or info.get("entries"):
                raise RuntimeError("Video is private or unavailable.")
            video_id = str(info.get("id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                raise RuntimeError("Video is unavailable or has no valid ID.")
            title = safe_name(info.get("title"), "YouTube video")
            entries = [{"id": video_id, "title": title}]
        else:
            with yt_dlp.YoutubeDL(yt_options(extract_flat="in_playlist", skip_download=True,
                                             ignoreerrors=True, playlistend=MAX_TRACKS)) as ydl:
                info = ydl.extract_info(job["url"], download=False)
            check_cancel(job)
            if not info or not info.get("entries"):
                raise RuntimeError("Playlist is empty, private or unavailable.")
            entries = list(itertools.islice((e for e in info["entries"] if e), MAX_TRACKS))
            if not entries:
                raise RuntimeError("No accessible tracks found.")
            title = safe_name(info.get("title"), "YouTube playlist")
        update(job, status="downloading", title=title, total=len(entries))
        ready = []
        total_bytes = 0
        consecutive_player_errors = 0
        for index, item in enumerate(entries, 1):
            check_cancel(job)
            track = safe_name(item.get("title"), "Track " + str(index))
            label = track if mode == "single" else "{:03d} - {}".format(index, track)
            update(job, done=index - 1, current=track, track_percent=0)
            video_id = str(item.get("id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                with LOCK:
                    job["failed"].append(label + ": invalid video ID")
                update(job, done=index)
                continue
            prefix = str(folder / label)
            template = prefix.replace("%", "%%") + ".%(ext)s"

            def progress(info):
                check_cancel(job)
                if info.get("status") == "downloading":
                    total = info.get("total_bytes") or info.get("total_bytes_estimate")
                    if total:
                        update(job, track_percent=min(99, int(100 * info.get("downloaded_bytes", 0) / total)))

            codec_options = {"key": "FFmpegExtractAudio", "preferredcodec": audio_format}
            if audio_format == "mp3":
                codec_options["preferredquality"] = job["quality"]
            opts = yt_options(format="bestaudio/best", noplaylist=True,
                              outtmpl=template, max_filesize=max_track,
                              progress_hooks=[progress], postprocessors=[
                                  codec_options,
                                  {"key": "FFmpegMetadata"}])
            try:
                try:
                    result = download_video(video_id, opts)
                except InterruptedError:
                    raise
                except Exception as first_error:
                    if not player_response_error(first_error):
                        raise
                    # A second supported YouTube client set can recover when a
                    # particular player API changes. Do not loop endlessly.
                    check_cancel(job)
                    alternate = dict(opts, extractor_args={
                        "youtube": {"player_client": ["web", "mweb", "tv"]}
                    })
                    app.logger.info("Retrying %s with alternate YouTube clients", video_id)
                    result = download_video(video_id, alternate)
                check_cancel(job)
                audio = Path(prefix + "." + audio_format)
                if result or not audio.is_file():
                    raise RuntimeError("No " + audio_format.upper() + " output was produced.")
                size = audio.stat().st_size
                if not size or size > max_track:
                    audio.unlink(missing_ok=True)
                    raise RuntimeError("Track exceeded size limit.")
                if total_bytes + size > MAX_TOTAL:
                    audio.unlink(missing_ok=True)
                    with LOCK:
                        job["failed"].append(label + ": archive size limit reached")
                    break
                ready.append(audio)
                total_bytes += size
                consecutive_player_errors = 0
                update(job, succeeded=len(ready))
            except InterruptedError:
                raise
            except Exception as exc:
                consecutive_player_errors = (
                    consecutive_player_errors + 1 if player_response_error(exc) else 0
                )
                app.logger.warning("Track %s failed: %s", video_id, exc)
                with LOCK:
                    job["failed"].append(label + ": " + readable_error(exc))
            finally:
                update(job, done=index, track_percent=0)
            if consecutive_player_errors >= 2:
                app.logger.warning("Stopped early: YouTube returned no usable player "
                                   "response for two consecutive tracks")
                break
        check_cancel(job)
        if not ready:
            first = job["failed"][0] if job["failed"] else "Unknown"
            raise RuntimeError("No tracks could be converted. " + first)
        if mode == "single":
            # Direct audio file: one downloadable MP3 or FLAC, no ZIP or numbering.
            update(job, status="complete", archive=str(ready[0]), finished=time.time(),
                   current="", track_percent=100)
            return
        update(job, status="zipping", current="Packaging MP3 files")
        zip_path = folder / (title + ".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED, allowZip64=True) as bundle:
            for file in ready:
                check_cancel(job)
                bundle.write(file, file.name)
            if job["failed"]:
                bundle.writestr("skipped-tracks.txt", "\n".join(job["failed"]) + "\n")
        for file in ready:
            file.unlink(missing_ok=True)
        update(job, status="complete", archive=str(zip_path), finished=time.time(),
               current="", track_percent=100)
    except InterruptedError:
        update(job, status="cancelled", finished=time.time(), current="")
    except Exception as exc:
        app.logger.warning("Conversion failed: %s", exc)
        update(job, status="error", error=readable_error(exc), finished=time.time(), current="")
    finally:
        if job["status"] != "complete":
            shutil.rmtree(folder, ignore_errors=True)


def reaper():
    while True:
        time.sleep(60)
        with LOCK:
            expired = [jid for jid, j in JOBS.items()
                       if j["finished"] and time.time() - j["finished"] > 1800]
            for jid in expired:
                shutil.rmtree(JOBS[jid]["directory"], ignore_errors=True)
                del JOBS[jid]


threading.Thread(target=reaper, daemon=True).start()


@app.get("/")
def home():
    return send_file(ROOT / "static/index.html")


@app.get("/api/health")
def health():
    runtime = "deno" if shutil.which("deno") else ("node" if shutil.which("node") else None)
    return jsonify(ok=bool(runtime and shutil.which("ffmpeg") and shutil.which("ffprobe")),
                   runtime=runtime, ffmpeg=bool(shutil.which("ffmpeg")),
                   yt_dlp_version=yt_dlp.version.__version__)


@app.post("/api/jobs")
def start():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Submit a YouTube URL."), 400
    mode = data.get("mode", "playlist")
    if mode not in ("playlist", "single"):
        return jsonify(error="Choose playlist or single video mode."), 400
    url = (video_url if mode == "single" else playlist_url)(str(data.get("url", "")))
    if not url:
        message = ("Enter a single YouTube video link."
                   if mode == "single"
                   else "Enter a YouTube playlist link containing list=.")
        return jsonify(error=message), 400
    audio_format = data.get("format", "mp3")
    if not isinstance(audio_format, str) or audio_format not in AUDIO_FORMATS:
        return jsonify(error="Choose MP3 or FLAC output format."), 400
    quality = str(data.get("quality", "192"))
    if audio_format == "mp3" and quality not in {"128", "192", "256", "320"}:
        return jsonify(error="Invalid MP3 bitrate."), 400
    with LOCK:
        if sum(j["status"] not in FINAL for j in JOBS.values()) >= MAX_ACTIVE:
            return jsonify(error="Converter is busy. Try again shortly."), 429
        jid = uuid.uuid4().hex
        job = dict(id=jid, mode=mode, format=audio_format, url=url, quality=quality, directory=tempfile.mkdtemp(prefix="yubsub_"),
                   stop=threading.Event(), status="queued", title="", current="",
                   total=0, done=0, succeeded=0, track_percent=0, failed=[],
                   error=None, archive=None, finished=None)
        JOBS[jid] = job
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
    return jsonify(id=jid), 202


@app.get("/api/jobs/<jid>")
def status(jid):
    with LOCK:
        job = JOBS.get(jid)
        if not job:
            return jsonify(error="Job not found or expired."), 404
        fields = ("id", "mode", "status", "title", "current", "total", "done", "succeeded",
                  "track_percent", "failed", "error")
        response = {key: job[key] for key in fields}
        response["format"] = job.get("format", "mp3")
        return jsonify(response)


@app.delete("/api/jobs/<jid>")
def cancel(jid):
    with LOCK:
        job = JOBS.get(jid)
        if not job:
            return jsonify(error="Job not found or expired."), 404
        if job["status"] in FINAL:
            return jsonify(error="Job already finished."), 409
        job["stop"].set()
    return jsonify(message="Cancellation requested."), 202


@app.get("/api/jobs/<jid>/download")
def download(jid):
    with LOCK:
        job = JOBS.get(jid)
        if not job or job["status"] != "complete":
            return jsonify(error="Download is not ready or has expired."), 404
        path, title, mode = job["archive"], job["title"], job.get("mode", "playlist")
        audio_format = job.get("format", "mp3")
    if not Path(path).is_file():
        return jsonify(error="Download expired."), 410
    if audio_format not in AUDIO_FORMATS:
        return jsonify(error="Unsupported audio format."), 400
    extension = ("." + audio_format) if mode == "single" else ".zip"
    mimetype = ({"mp3": "audio/mpeg", "flac": "audio/flac"}[audio_format]
                if mode == "single" else "application/zip")
    return send_file(path, as_attachment=True, download_name=safe_name(title) + extension,
                     mimetype=mimetype, max_age=0)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), threaded=True)
