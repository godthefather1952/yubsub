"""Offline tests — no network requests or real YouTube extraction."""
import tempfile
import threading
import zipfile
from pathlib import Path
import app as mod


def test_url():
    assert mod.playlist_url("https://youtube.com/playlist?list=PL1234567890123")
    assert mod.playlist_url("https://music.youtube.com/watch?v=foo&list=PL1234567890123")
    for url in ("https://evil.test/?list=PL1234567890123",
                "https://youtube.com.evil.test/?list=PL1234567890123",
                "http://youtube.com/playlist?list=PL1234567890123",
                "https://youtube.com/watch?v=abcd",
                "https://youtube.com:8080/playlist?list=PL1234567890123"):
        assert mod.playlist_url(url) is None


def test_api_validation():
    client = mod.app.test_client()
    assert b"Convert" in client.get("/").data
    assert client.post("/api/jobs", json={"url": "not a url"}).status_code == 400
    assert client.post("/api/jobs", json={"url": "https://youtube.com/playlist?list=PL1234567890123", "quality": "400"}).status_code == 400
    assert client.get("/api/jobs/nope").status_code == 404


def test_fake_conversion(monkeypatch):
    class FakeYDL:
        def __init__(self, opts): self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, *args, **kwargs):
            return {"title": "A Playlist", "entries": [
                {"id": "abcdefghijk", "title": "First"}, {"id": "lmnopqrstuv", "title": "Second"}]}
        def download(self, urls):
            path = self.opts["outtmpl"].replace("%%", "%").replace("%(ext)s", "mp3")
            Path(path).write_bytes(b"ID3 placeholder")
            return 0

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", FakeYDL)
    with tempfile.TemporaryDirectory() as directory:
        Path(directory, "job").mkdir()
        job = dict(id="test", url="https://youtube.com/playlist?list=PL1234567890123",
                   directory=str(Path(directory, "job")), stop=threading.Event(),
                   quality="192", status="queued", title="", current="",
                   total=0, done=0, succeeded=0, track_percent=0, failed=[],
                   error=None, archive=None, finished=None)
        mod.run_job(job)
        assert job["status"] == "complete", job["error"]
        assert job["succeeded"] == 2
        with zipfile.ZipFile(job["archive"]) as z:
            assert z.namelist() == ["001 - First.mp3", "002 - Second.mp3"]


def test_github_pages_cors():
    client = mod.app.test_client()
    preflight = client.options(
        "/api/jobs",
        headers={
            "Origin": "https://yubsub.godthefather1952.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == "https://yubsub.godthefather1952.com"
    assert "POST" in preflight.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in preflight.headers["Access-Control-Allow-Headers"]
    blocked = client.get("/api/health", headers={"Origin": "https://untrusted.invalid"})
    assert "Access-Control-Allow-Origin" not in blocked.headers


def test_extractor_runtime_options(monkeypatch):
    monkeypatch.setattr(mod.shutil, "which", lambda program: "/usr/bin/fake")
    opts = mod.yt_options()
    assert opts["remote_components"] == ["ejs:github"]
    assert "deno" in opts["js_runtimes"]
    assert mod.player_response_error("Failed to extract any player response")
    assert not mod.player_response_error("FFmpeg is missing")


def test_error_logging_keeps_youtube_failure(monkeypatch):
    class FakeYDL:
        def __init__(self, opts): self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def download(self, urls):
            self.opts["logger"].error("ERROR: [youtube] failed to extract any player response")
            return 1

    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", FakeYDL)
    import pytest
    with pytest.raises(RuntimeError, match="failed to extract any player response"):
        mod.download_video("abcdefghijk", {})


def test_player_response_fallback_and_stop(monkeypatch):
    attempts = []
    class FakeYDL:
        def __init__(self, opts): self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, *args, **kwargs):
            return {"title": "Blocked", "entries": [
                {"id": "abcdefghijk", "title": "First"},
                {"id": "lmnopqrstuv", "title": "Second"},
                {"id": "abcdefghijZ", "title": "Third"}]}
        def download(self, urls):
            attempts.append(self.opts.get("extractor_args"))
            self.opts["logger"].error(
                "ERROR: [youtube] Failed to extract any player response")
            return 1

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", FakeYDL)
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory, "job")
        folder.mkdir()
        job = dict(id="blocked", url="https://youtube.com/playlist?list=PL1234567890123",
                   directory=str(folder), stop=threading.Event(),
                   quality="192", status="queued", title="", current="",
                   total=0, done=0, succeeded=0, track_percent=0, failed=[],
                   error=None, archive=None, finished=None)
        mod.run_job(job)
        assert job["status"] == "error"
        assert len(job["failed"]) == 2
        assert job["done"] == 2
        assert len(attempts) == 4  # original + alternate client for two tracks
        assert attempts[1] == {"youtube": {"player_client": ["web", "mweb", "tv"]}}
        assert "YouTube is not providing playable video data" in job["error"]


def test_single_video_links_and_host_validation():
    canonical = "https://www.youtube.com/watch?v=abcdefghijk"
    assert mod.video_url(canonical) == canonical
    assert mod.video_url("https://youtu.be/abcdefghijk?t=3") == canonical
    assert mod.video_url("https://www.youtube.com/shorts/abcdefghijk") == canonical
    assert mod.video_url("https://youtube.com/live/abcdefghijk") == canonical
    assert mod.video_url("https://music.youtube.com/watch?v=abcdefghijk&list=PL1234567890123") == canonical
    for url in (
        "http://youtube.com/watch?v=abcdefghijk",
        "https://youtube.com:8888/watch?v=abcdefghijk",
        "https://evil.test/watch?v=abcdefghijk",
        "https://youtube.com.evil.test/watch?v=abcdefghijk",
        "https://youtube.com/playlist?list=PL1234567890123",
        "https://youtube.com/watch?v=short",
        "https://youtu.be/abcdefghijkx",
        "https://username:password@youtube.com/watch?v=abcdefghijk",
    ):
        assert mod.video_url(url) is None


def test_job_api_validates_mode_and_keeps_playlist_default(monkeypatch):
    class NoRunThread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass

    monkeypatch.setattr(mod.threading, "Thread", NoRunThread)
    monkeypatch.setattr(mod, "MAX_ACTIVE", 99)
    client = mod.app.test_client()
    assert client.post("/api/jobs", json={"url": "https://youtu.be/abcdefghijk", "mode": "other"}).status_code == 400
    assert client.post("/api/jobs", json={"url": "https://evil.test/watch?v=abcdefghijk", "mode": "single"}).status_code == 400
    assert client.post("/api/jobs", json={"url": "https://youtu.be/abcdefghijk", "mode": "playlist"}).status_code == 400

    created = []
    try:
        for payload, expected in (
            ({"url": "https://youtu.be/abcdefghijk", "mode": "single"}, "single"),
            ({"url": "https://youtube.com/playlist?list=PL1234567890123"}, "playlist"),
        ):
            response = client.post("/api/jobs", json=payload)
            assert response.status_code == 202, response.json
            job_id = response.json["id"]
            created.append(job_id)
            status = client.get("/api/jobs/" + job_id)
            assert status.json["mode"] == expected
            assert mod.JOBS[job_id]["mode"] == expected
    finally:
        with mod.LOCK:
            for job_id in created:
                job = mod.JOBS.pop(job_id, None)
                if job:
                    import shutil
                    shutil.rmtree(job["directory"], ignore_errors=True)


def test_single_video_converts_to_direct_mp3(monkeypatch):
    class FakeYDL:
        def __init__(self, opts): self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, *args, **kwargs):
            assert self.opts["noplaylist"] is True
            return {"id": "abcdefghijk", "title": "Sample Video"}
        def download(self, urls):
            assert urls == ["https://www.youtube.com/watch?v=abcdefghijk"]
            output = self.opts["outtmpl"].replace("%%", "%").replace("%(ext)s", "mp3")
            Path(output).write_bytes(b"ID3 fake mp3")
            return 0

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", FakeYDL)
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory, "single")
        folder.mkdir()
        job = dict(id="single-test", mode="single",
                   url="https://www.youtube.com/watch?v=abcdefghijk",
                   directory=str(folder), stop=threading.Event(),
                   quality="192", status="queued", title="", current="",
                   total=0, done=0, succeeded=0, track_percent=0, failed=[],
                   error=None, archive=None, finished=None)
        mod.run_job(job)
        assert job["status"] == "complete", job["error"]
        assert job["succeeded"] == job["total"] == 1
        assert Path(job["archive"]).name == "Sample Video.mp3"
        assert not list(folder.glob("*.zip"))
        with mod.LOCK:
            mod.JOBS[job["id"]] = job
        response = None
        try:
            response = mod.app.test_client().get("/api/jobs/single-test/download")
            assert response.status_code == 200
            assert response.data == b"ID3 fake mp3"
            assert response.mimetype == "audio/mpeg"
            assert "Sample Video.mp3" in response.headers["Content-Disposition"]
        finally:
            if response is not None:
                response.close()
            with mod.LOCK:
                mod.JOBS.pop(job["id"], None)


def test_audio_formats_validate_and_default_to_mp3(monkeypatch):
    class NoRunThread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass

    monkeypatch.setattr(mod.threading, "Thread", NoRunThread)
    monkeypatch.setattr(mod, "MAX_ACTIVE", 99)
    client = mod.app.test_client()
    url = "https://youtu.be/abcdefghijk"
    assert client.post("/api/jobs", json={"url": url, "mode": "single", "format": "wav"}).status_code == 400
    assert client.post("/api/jobs", json={"url": url, "mode": "single", "format": None}).status_code == 400
    assert client.post("/api/jobs", json={"url": url, "mode": "single", "format": "../flac"}).status_code == 400
    assert client.post("/api/jobs", json={"url": url, "mode": "single", "format": "mp3", "quality": "500"}).status_code == 400
    ids = []
    try:
        for payload, expected in (
            ({"url": url, "mode": "single"}, "mp3"),
            ({"url": url, "mode": "single", "format": "flac"}, "flac"),
            ({"url": "https://youtube.com/playlist?list=PL1234567890123",
              "mode": "playlist", "format": "flac"}, "flac"),
        ):
            res = client.post("/api/jobs", json=payload)
            assert res.status_code == 202, res.json
            jid = res.json["id"]
            ids.append(jid)
            assert mod.JOBS[jid]["format"] == expected
            assert client.get("/api/jobs/" + jid).json["format"] == expected
    finally:
        import shutil
        with mod.LOCK:
            for jid in ids:
                job = mod.JOBS.pop(jid, None)
                if job:
                    shutil.rmtree(job["directory"], ignore_errors=True)


def test_flac_single_and_playlist_conversion(monkeypatch):
    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, *args, **kwargs):
            if self.opts.get("noplaylist"):
                return {"title": "My song", "id": "abcdefghijk"}
            return {"title": "FLAC playlist", "entries": [
                {"id": "abcdefghijk", "title": "My song"},
                {"id": "lmnopqrstuv", "title": "Another song"},
            ]}
        def download(self, urls):
            codec = self.opts["postprocessors"][0]
            assert codec["key"] == "FFmpegExtractAudio"
            assert codec["preferredcodec"] == "flac"
            assert "preferredquality" not in codec
            assert self.opts["max_filesize"] == mod.MAX_FLAC_TRACK
            assert self.opts["postprocessors"][1]["key"] == "FFmpegMetadata"
            output = self.opts["outtmpl"].replace("%%", "%").replace("%(ext)s", "flac")
            Path(output).write_bytes(b"fLaC fake audio")
            return 0

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", FakeYDL)
    client = mod.app.test_client()
    with tempfile.TemporaryDirectory() as directory:
        for mode in ("single", "playlist"):
            folder = Path(directory, mode)
            folder.mkdir()
            jid = "flac-" + mode
            job = dict(id=jid, mode=mode, format="flac",
                       url=("https://www.youtube.com/watch?v=abcdefghijk" if mode == "single"
                            else "https://youtube.com/playlist?list=PL1234567890123"),
                       directory=str(folder), stop=threading.Event(), quality="192",
                       status="queued", title="", current="", total=0, done=0,
                       succeeded=0, track_percent=0, failed=[], error=None,
                       archive=None, finished=None)
            mod.run_job(job)
            assert job["status"] == "complete", job["error"]
            with mod.LOCK:
                mod.JOBS[jid] = job
            response = None
            try:
                response = client.get("/api/jobs/" + jid + "/download")
                assert response.status_code == 200
                if mode == "single":
                    assert response.mimetype == "audio/flac"
                    assert response.data == b"fLaC fake audio"
                    assert ".flac" in response.headers["Content-Disposition"]
                    assert Path(job["archive"]).suffix == ".flac"
                else:
                    assert response.mimetype == "application/zip"
                    with zipfile.ZipFile(job["archive"]) as archive:
                        assert archive.namelist() == [
                            "001 - My song.flac", "002 - Another song.flac"]
            finally:
                if response is not None:
                    response.close()
                with mod.LOCK:
                    mod.JOBS.pop(jid, None)


def test_legacy_mp3_postprocessor_still_uses_bitrate(monkeypatch):
    class FakeYDL:
        def __init__(self, opts): self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, *args, **kwargs):
            return {"title": "Test", "id": "abcdefghijk"}
        def download(self, urls):
            assert self.opts["postprocessors"][0] == {
                "key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                "preferredquality": "320"}
            output = self.opts["outtmpl"].replace("%%", "%").replace("%(ext)s", "mp3")
            Path(output).write_bytes(b"ID3")
            return 0

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", FakeYDL)
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory, "single")
        folder.mkdir()
        job = dict(id="legacy-mp3", mode="single", url="https://www.youtube.com/watch?v=abcdefghijk",
                   directory=str(folder), stop=threading.Event(), quality="320",
                   status="queued", title="", current="", total=0, done=0,
                   succeeded=0, track_percent=0, failed=[], error=None,
                   archive=None, finished=None)
        mod.run_job(job)
        assert job["status"] == "complete", job["error"]
        assert Path(job["archive"]).suffix == ".mp3"
