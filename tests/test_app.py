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
