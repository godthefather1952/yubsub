"""WAV regression tests for the shared web/macOS/Windows/ChromeOS engine."""
import io
import tempfile
import threading
import wave
import zipfile
from pathlib import Path

import app as backend
import music_metadata as metadata


def pcm_wav():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(44100)
        writer.writeframes(b"\x00" * (44100 * 4 // 10))
    return stream.getvalue()


def test_wav_single_and_playlist(monkeypatch):
    source = pcm_wav()
    class FakeYDL:
        def __init__(self, options):
            self.options = options
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download=False):
            if self.options.get("noplaylist"):
                return {"id": "abcdefghijk", "title": "PCM Song"}
            return {"title": "PCM Playlist", "entries": [
                {"id": "abcdefghijk", "title": "First"},
                {"id": "lmnopqrstuv", "title": "Second"},
            ]}
        def download(self, urls):
            processor = self.options["postprocessors"][0]
            assert processor == {"key": "FFmpegExtractAudio", "preferredcodec": "wav"}
            assert self.options["max_filesize"] == backend.MAX_WAV_TRACK
            path = self.options["outtmpl"].replace("%%", "%").replace("%(ext)s", "wav")
            Path(path).write_bytes(source)
            return 0

    monkeypatch.setattr(backend.shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(backend.yt_dlp, "YoutubeDL", FakeYDL)
    client = backend.app.test_client()
    with tempfile.TemporaryDirectory() as directory:
        for mode in ("single", "playlist"):
            folder = Path(directory) / mode
            folder.mkdir()
            jid = "wav-test-" + mode
            job = dict(id=jid, mode=mode, format="wav", metadata=False,
                       url=("https://youtube.com/watch?v=abcdefghijk" if mode == "single"
                            else "https://youtube.com/playlist?list=PL1234567890123"),
                       directory=str(folder), stop=threading.Event(),
                       quality="192", status="queued", title="", current="",
                       total=0, done=0, succeeded=0, track_percent=0,
                       failed=[], error=None, archive=None, finished=None)
            backend.run_job(job)
            assert job["status"] == "complete", job["error"]
            assert job["succeeded"] == (1 if mode == "single" else 2)
            with backend.LOCK:
                backend.JOBS[jid] = job
            response = None
            try:
                response = client.get("/api/jobs/" + jid + "/download")
                assert response.status_code == 200
                if mode == "single":
                    assert response.mimetype == "audio/wav"
                    assert response.data == source
                    assert response.headers["Content-Disposition"].endswith("PCM Song.wav")
                else:
                    assert response.mimetype == "application/zip"
                    with zipfile.ZipFile(job["archive"]) as archive:
                        assert archive.namelist() == [
                            "001 - First.wav", "002 - Second.wav"]
                        for name in archive.namelist():
                            with wave.open(io.BytesIO(archive.read(name)), "rb") as audio:
                                assert audio.getsampwidth() == 2
                                assert audio.getframerate() == 44100
            finally:
                if response is not None:
                    response.close()
                with backend.LOCK:
                    backend.JOBS.pop(jid, None)


def test_wav_metadata_without_reencoding(monkeypatch, tmp_path):
    from mutagen.wave import WAVE

    target = tmp_path / "Example.wav"
    original = pcm_wav()
    target.write_bytes(original)
    monkeypatch.setattr(metadata, "_musicbrainz_match", lambda *args: {
        "title": "Example", "artist": "Example Artist",
        "album": "Example Album", "year": "2023", "release_ids": ["id"],
    })
    monkeypatch.setattr(metadata, "_cover_art", lambda ids: (
        ("image/jpeg", b"\xff\xd8\xff" + b"cover-test"), "coverartarchive",
    ))
    result = metadata.tag_audio(
        target, "wav", {"title": "Example Artist - Example"}, {})
    assert result["art_source"] == "coverartarchive"
    tags = WAVE(target).tags
    assert tags is not None
    assert str(tags["TIT2"]) == "Example"
    assert str(tags["TPE1"]) == "Example Artist"
    assert str(tags["TALB"]) == "Example Album"
    assert str(tags["TDRC"]) == "2023"
    assert tags.getall("APIC")
    with wave.open(str(target), "rb") as reader:
        assert reader.getframerate() == 44100
        assert reader.getsampwidth() == 2
        assert reader.getnframes() == 4410
    assert target.stat().st_size > len(original)
