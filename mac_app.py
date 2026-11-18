"""YUBSUB desktop application.

PyInstaller includes the Python interpreter, Flask, yt-dlp/ejs, Deno,
FFmpeg and FFprobe at build time. No pip, Homebrew or runtime setup is needed.
"""
import os
import subprocess
import sys
import threading
from pathlib import Path

# Must be configured *before* importing app.py: it validates bundled tools
# with shutil.which() and builds routes relative to its own resource path.
def configure_runtime():
    resources = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bundled_bin = resources / "bin"
    if bundled_bin.is_dir():
        os.environ["PATH"] = str(bundled_bin) + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("MAX_TRACKS", "200")
    os.environ.setdefault("MAX_ARCHIVE_MB", "1200")
    os.environ.setdefault("MAX_ACTIVE_JOBS", "1")
    return resources


def smoke_test():
    """Test frozen dependencies, Flask routes and bundled binaries without GUI."""
    import json
    import shutil

    import app as backend
    import webview

    del webview  # Verify import of the Cocoa GUI dependencies
    tools = {}
    for name in ("deno", "ffmpeg", "ffprobe"):
        binary = shutil.which(name)
        assert binary, f"{name} not found in bundled PATH"
        result = subprocess.run([binary, "--version" if name == "deno" else "-version"],
                                capture_output=True, text=True, timeout=15, check=True)
        tools[name] = result.stdout.splitlines()[0] if result.stdout else name

    # Validate the native updater bundle when enabled.
    from Foundation import NSBundle
    bundle = NSBundle.mainBundle()
    if bundle.objectForInfoDictionaryKey_("SUPublicEDKey"):
        import objc
        framework = Path(str(bundle.bundlePath())) / "Contents" / "Frameworks" / "Sparkle.framework"
        assert framework.is_dir(), "Sparkle framework missing"
        objc.loadBundle("Sparkle", {}, bundle_path=str(framework))
        assert objc.lookUpClass("SPUStandardUpdaterController")
        assert bundle.objectForInfoDictionaryKey_("SUVerifyUpdateBeforeExtraction")
    client = backend.app.test_client()
    page = client.get("/")
    status = client.get("/api/health")
    assert page.status_code == 200 and b"YUBSUB" in page.data
    assert status.status_code == 200 and status.json["ok"] is True
    assert client.get("/static/config.js").status_code == 200, "missing local static assets"
    print(json.dumps({"ok": True, "health": status.json, "tools": tools}, indent=2))


class DesktopUpdatesAPI:
    """Local desktop bridge for updates, saving and user-initiated pasting."""

    def read_clipboard(self):
        """Read plain text from macOS after the user clicks the PASTE button.

        WebKit's navigator.clipboard.readText() is denied in some embedded
        windows. The macOS pasteboard API does not require web clipboard
        permissions. Never read clipboard content on startup or in background.
        """
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeString
            value = NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString)
        except Exception:
            return {"ok": False, "error": "macOS clipboard access is unavailable. Try Command+V."}
        if not isinstance(value, str) or not value.strip():
            return {"ok": False, "error": "Clipboard has no text. Copy a YouTube link first."}
        if len(value) > 8192:
            return {"ok": False, "error": "Clipboard text is too long for a YouTube link."}
        return {"ok": True, "text": value.strip()}

    def save_mp3(self, job_id):
        """Backward-compatible bridge for clients built before FLAC support."""
        return self.save_audio(job_id)

    def save_audio(self, job_id):
        """Save a completed MP3 or FLAC with a native macOS Save As dialog.

        Never accepts an arbitrary source path from JavaScript. A random job ID
        selects only completed single-video jobs from our in-process backend.
        """
        import re
        import shutil
        import tempfile
        import webview
        import app as backend

        if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
            return {"ok": False, "error": "Invalid download request."}
        with backend.LOCK:
            job = backend.JOBS.get(job_id)
            if not job or job["status"] != "complete" or job.get("mode") != "single":
                return {"ok": False, "error": "Audio is not ready or has expired."}
            source = Path(job["archive"])
            job_dir = Path(job["directory"])
            audio_format = job.get("format", "mp3")
            if audio_format not in backend.AUDIO_FORMATS:
                return {"ok": False, "error": "Unsupported audio format."}
            extension = "." + audio_format
            filename = backend.safe_name(job["title"], "YouTube video") + extension

        # Only save a converted file inside its completed job directory.
        if (source.suffix.lower() != extension
                or not source.is_file()
                or not source.resolve().is_relative_to(job_dir.resolve())):
            return {"ok": False, "error": "Audio has expired or is unavailable."}

        try:
            choices = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=filename,
                file_types=(audio_format.upper() + " audio (*" + extension + ")",),
            )
            if not choices:
                return {"ok": False, "cancelled": True}
            destination = Path(choices if isinstance(choices, str) else choices[0])
            # A user may edit the filename; ensure it matches the file's codec.
            if destination.suffix.lower() != extension:
                destination = destination.with_suffix(extension)
            if not destination.parent.is_dir():
                return {"ok": False, "error": "The selected folder no longer exists."}

            # Copy to a sibling temporary file, then replace atomically so a
            # disk-full or permission error cannot leave a partial MP3 behind.
            temporary = None
            try:
                fd, temp_name = tempfile.mkstemp(
                    prefix=".yubsub-", suffix=".part", dir=str(destination.parent)
                )
                temporary = Path(temp_name)
                with os.fdopen(fd, "wb") as output, source.open("rb") as audio:
                    shutil.copyfileobj(audio, output)
                os.replace(temporary, destination)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return {"ok": True, "path": str(destination)}
        except (OSError, ValueError, IndexError):
            backend.app.logger.exception("Cannot save single-video audio file")
            return {"ok": False, "error": "Could not save the audio file. Check folder permissions and available disk space."}

    def available(self):
        import sparkle_updater
        return sparkle_updater.updater_available()

    def check(self):
        import sparkle_updater
        if not sparkle_updater.updater_available():
            return {"ok": False, "error": "Signed updates are not configured."}
        with __import__("app").LOCK:
            backend = __import__("app")
            if any(j["status"] not in backend.FINAL for j in backend.JOBS.values()):
                return {"ok": False, "error": "Finish or cancel your conversion before updating."}
        return {"ok": sparkle_updater.check_for_updates()}


def launch():
    import webview
    from werkzeug.serving import make_server
    import app as backend
    import sparkle_updater

    # Ephemeral loopback port: no LAN/public exposure, no collisions with 8000.
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True, name="yubsub-local").start()
    address = f"http://127.0.0.1:{server.server_port}"

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        webview.create_window(
            "YUBSUB by 2.wav", address,
            width=1120, height=820,
            min_size=(600, 480),
            background_color="#121212",
            js_api=DesktopUpdatesAPI(),
        )
        # Initialize Sparkle on the main Cocoa thread, not from the Flask
        # worker or the JavaScript bridge. If it cannot load, conversion works
        # normally but updates remain unavailable; never fall back to a custom
        # unsigned updater.
        try:
            from AppKit import NSApplication
            NSApplication.sharedApplication()
            sparkle_updater.start_updater()
        except Exception:
            backend.app.logger.exception("Sparkle updater is unavailable")
        # Native macOS Cocoa/WebKit window; blocks until the user quits the app.
        webview.start(debug=False)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    configure_runtime()
    if "--smoke-test" in sys.argv:
        smoke_test()
    else:
        launch()
