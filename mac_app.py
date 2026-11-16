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
    """Small, local pywebview bridge; Sparkle performs all privileged operations."""

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
