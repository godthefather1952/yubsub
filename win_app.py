"""YUBSUB for Windows: self-contained WebView2 desktop shell and local converter.

All conversion requests are served exclusively over a random loopback port.
The installed app does not connect to the public Render conversion API.
"""
import ctypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


def resources_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def configure_runtime():
    binaries = resources_dir() / "bin"
    if binaries.is_dir():
        os.environ["PATH"] = str(binaries) + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("MAX_TRACKS", "200")
    os.environ.setdefault("MAX_ARCHIVE_MB", "1200")
    os.environ.setdefault("MAX_ACTIVE_JOBS", "1")


def smoke_test():
    """Works on Windows CI without opening a graphical window."""
    import json
    import webview
    import app as backend
    del webview
    assert os.name == "nt", "Windows executable must be built on Windows"
    found = {}
    for name in ("deno", "ffmpeg", "ffprobe"):
        binary = shutil.which(name)
        assert binary and Path(binary).is_file(), f"Bundled {name}.exe missing"
        args = [binary, "--version" if name == "deno" else "-version"]
        process = subprocess.run(args, capture_output=True, text=True, timeout=25, check=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        found[name] = process.stdout.splitlines()[0] if process.stdout else name
        assert str((resources_dir() / "bin").resolve()).lower() in str(Path(binary).resolve()).lower(), name
    client = backend.app.test_client()
    assert client.get("/").status_code == 200
    assert b"YUBSUB" in client.get("/").data
    assert client.get("/static/config.js").status_code == 200
    assert client.get("/api/health").json["ok"] is True
    from win_updater import installed_version
    print(json.dumps({"ok": True, "version": installed_version(),
                      "health": client.get("/api/health").json, "tools": found}, indent=2))


def _clipboard_text():
    """Read CF_UNICODETEXT only following explicit user paste interaction."""
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


class DesktopAPI:
    def read_clipboard(self):
        try:
            value = _clipboard_text()
        except (OSError, ValueError):
            value = None
        if not isinstance(value, str) or not value.strip():
            return {"ok": False, "error": "Clipboard has no text. Copy a YouTube link first."}
        if len(value) > 8192:
            return {"ok": False, "error": "Clipboard text is too long."}
        return {"ok": True, "text": value.strip()}

    def save_mp3(self, job_id):
        return self.save_audio(job_id)

    def save_audio(self, job_id):
        """Only copy a completed local job, never a web-supplied source filename."""
        import webview
        import app as backend

        if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
            return {"ok": False, "error": "Invalid download request."}
        with backend.LOCK:
            job = backend.JOBS.get(job_id)
            if not job or job["status"] != "complete" or job.get("mode") != "single":
                return {"ok": False, "error": "Audio is not ready or has expired."}
            source = Path(job["archive"])
            folder = Path(job["directory"])
            audio_format = job.get("format", "mp3")
            if audio_format not in backend.AUDIO_FORMATS:
                return {"ok": False, "error": "Unsupported audio format."}
            extension = "." + audio_format
            filename = backend.safe_name(job["title"], "YouTube video") + extension
        if not source.is_file() or source.suffix.lower() != extension or not source.resolve().is_relative_to(folder.resolve()):
            return {"ok": False, "error": "Audio is unavailable or has expired."}
        try:
            choice = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG, save_filename=filename,
                file_types=(audio_format.upper() + " audio (*" + extension + ")",),
            )
            if not choice:
                return {"ok": False, "cancelled": True}
            path = Path(choice if isinstance(choice, str) else choice[0])
            if path.suffix.lower() != extension:
                path = path.with_suffix(extension)
            if not path.parent.is_dir():
                return {"ok": False, "error": "The selected destination folder no longer exists."}
            temporary = None
            try:
                fd, tmpname = tempfile.mkstemp(prefix=".yubsub-", suffix=".part", dir=path.parent)
                temporary = Path(tmpname)
                with os.fdopen(fd, "wb") as writer, source.open("rb") as reader:
                    shutil.copyfileobj(reader, writer)
                os.replace(temporary, path)
                temporary = None
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
            return {"ok": True, "path": str(path)}
        except (OSError, IndexError, ValueError):
            backend.app.logger.exception("Unable to save audio through native dialog")
            return {"ok": False, "error": "Unable to save audio. Check destination permissions and free space."}

    def available(self):
        from win_updater import updater_available
        return updater_available()

    def check(self):
        import app as backend
        with backend.LOCK:
            if any(job["status"] not in backend.FINAL for job in backend.JOBS.values()):
                return {"ok": False, "error": "Finish or cancel your conversion before updating."}
        from win_updater import check_for_updates
        return check_for_updates(interactive=True)


def launch():
    import app as backend
    import webview
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="yubsub-local")
    thread.start()
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        webview.create_window(
            "YUBSUB by 2.wav", f"http://127.0.0.1:{server.server_port}",
            width=1120, height=820, min_size=(600, 480),
            background_color="#121212", js_api=DesktopAPI(),
        )
        # A passive daily check mirrors the Mac updater. It prompts before
        # downloading or launching an installer and skips active conversions.
        def after_window_starts():
            import time
            time.sleep(12)
            with backend.LOCK:
                busy = any(j["status"] not in backend.FINAL for j in backend.JOBS.values())
            if not busy:
                from win_updater import maybe_check_daily
                maybe_check_daily()

        # Native Edge WebView2 (Chromium), using per-user application storage.
        webview.start(after_window_starts, gui="edgechromium", debug=False)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    configure_runtime()
    if "--smoke-test" in sys.argv:
        smoke_test()
    else:
        launch()
