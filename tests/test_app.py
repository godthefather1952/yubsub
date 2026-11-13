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
