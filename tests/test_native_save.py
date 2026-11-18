"""Regression tests for native macOS MP3 saving (no GUI or YouTube needed)."""
import sys
import tempfile
import types
from pathlib import Path

import app as backend
from mac_app import DesktopUpdatesAPI


class SavePanel:
    def __init__(self, selection):
        self.selection = selection
        self.calls = []

    def create_file_dialog(self, mode, **kwargs):
        self.calls.append((mode, kwargs))
        return self.selection


def fixture_job(tmp_path, mode="single"):
    job_id = "c" * 32
    folder = tmp_path / "conversion"
    folder.mkdir()
    source = folder / "Track.mp3"
    source.write_bytes(b"ID3 audio test content")
    with backend.LOCK:
        backend.JOBS[job_id] = {
            "id": job_id, "status": "complete", "mode": mode,
            "directory": str(folder), "archive": str(source),
            "title": "Track / Title?",
        }
    return job_id, source


def clear_job(job_id):
    with backend.LOCK:
        backend.JOBS.pop(job_id, None)


def test_mp3_native_save_dialog_writes_file_and_keeps_source(tmp_path, monkeypatch):
    jid, source = fixture_job(tmp_path)
    destination = tmp_path / "Selected Folder"
    destination.mkdir()
    requested = destination / "My favorite song"  # simulate filename without extension
    panel = SavePanel((str(requested),))
    monkeypatch.setitem(sys.modules, "webview",
                        types.SimpleNamespace(SAVE_DIALOG=30, windows=[panel]))
    try:
        result = DesktopUpdatesAPI().save_mp3(jid)
        assert result["ok"] is True
        saved = destination / "My favorite.mp3" if False else destination / "My favorite song.mp3"
        assert result["path"] == str(saved)
        assert saved.read_bytes() == b"ID3 audio test content"
        assert source.read_bytes() == b"ID3 audio test content"
        assert panel.calls == [(30, {
            "save_filename": "Track _ Title_.mp3",
            "file_types": ("MP3 audio (*.mp3)",),
        })]
        assert not list(destination.glob(".yubsub-*.part"))
    finally:
        clear_job(jid)


def test_native_dialog_cancel_does_not_write_anything(tmp_path, monkeypatch):
    jid, source = fixture_job(tmp_path)
    panel = SavePanel(None)
    monkeypatch.setitem(sys.modules, "webview",
                        types.SimpleNamespace(SAVE_DIALOG=30, windows=[panel]))
    try:
        result = DesktopUpdatesAPI().save_mp3(jid)
        assert result == {"ok": False, "cancelled": True}
        assert list(tmp_path.glob("*.mp3")) == []
        assert source.is_file()
    finally:
        clear_job(jid)


def test_native_save_never_reads_arbitrary_sources_or_playlist_jobs(tmp_path, monkeypatch):
    jid, source = fixture_job(tmp_path)
    panel = SavePanel((str(tmp_path / "output.mp3"),))
    monkeypatch.setitem(sys.modules, "webview",
                        types.SimpleNamespace(SAVE_DIALOG=30, windows=[panel]))
    try:
        bridge = DesktopUpdatesAPI()
        assert bridge.save_mp3("not-a-job")["ok"] is False
        assert bridge.save_mp3("a" * 32)["ok"] is False
        assert panel.calls == []
        with backend.LOCK:
            backend.JOBS[jid]["mode"] = "playlist"
        assert bridge.save_mp3(jid)["ok"] is False
        with backend.LOCK:
            backend.JOBS[jid]["mode"] = "single"
            backend.JOBS[jid]["archive"] = str(tmp_path / "other.mp3")
        (tmp_path / "other.mp3").write_bytes(b"wrong source")
        assert bridge.save_mp3(jid)["ok"] is False
        assert panel.calls == []
        assert source.exists()
    finally:
        clear_job(jid)


def test_frontend_uses_native_save_without_audio_navigation():
    root = Path(__file__).resolve().parents[1]
    mac_ui = (root / "static/index.html").read_text()
    pages_ui = (root / "index.html").read_text()
    assert mac_ui == pages_ui
    assert 'if(jobMode!=="single"||!window.pywebview)return;' in mac_ui
    assert "event.preventDefault();" in mac_ui
    assert "await apiBridge.save_mp3(jobId)" in mac_ui
    assert "MP3 saved successfully" in mac_ui
