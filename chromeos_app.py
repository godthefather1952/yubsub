"""YUBSUB desktop for ChromeOS's Debian Linux environment (Crostini).

The download engine executes entirely on the Chromebook in a self-contained
PyInstaller bundle. ChromeOS Chrome supplies the browser window and native
file-download controls; no hosted conversion service or extra Linux browser is
required.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from flask import jsonify, request, send_file

PORT = 8765
APP_VERSION_PATH = "chromeos-app/VERSION"
IDLE_SECONDS = 45 * 60
last_activity = time.monotonic()
last_activity_lock = threading.Lock()
prepared_update = None
prepared_lock = threading.Lock()


def resources_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def configure_runtime():
    resources = resources_dir()
    bundled_bin = resources / "bin"
    if bundled_bin.is_dir():
        os.environ["PATH"] = str(bundled_bin) + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("MAX_TRACKS", "200")
    os.environ.setdefault("MAX_ARCHIVE_MB", "1200")
    os.environ.setdefault("MAX_ACTIVE_JOBS", "1")


def _backend():
    import app
    return app


def register_routes():
    """Register ChromeOS endpoints only in this executable, not the website."""
    backend = _backend()
    from linux_updater import current_version, updater_available, check_for_update, prepare_update

    @backend.app.before_request
    def chromeos_activity():
        global last_activity
        with last_activity_lock:
            last_activity = time.monotonic()

    @backend.app.get("/api/chromeos/version")
    def chromeos_version():
        return jsonify(platform="chromeos-linux", app="YUBSUB",
                       version=current_version(), updates=updater_available())

    @backend.app.get("/api/chromeos/update/check")
    def chromeos_update_check():
        if not updater_available():
            return jsonify(ok=False, error="Secure Chromebook updates are not configured."), 503
        try:
            result = check_for_update()
            if not result:
                return jsonify(ok=True, update_available=False, version=current_version())
            manifest, _ = result
            return jsonify(ok=True, update_available=True, version=manifest["version"])
        except Exception:
            backend.app.logger.exception("ChromeOS update check failed")
            return jsonify(ok=False, error="Could not securely check ChromeOS updates."), 503

    @backend.app.post("/api/chromeos/update/prepare")
    def chromeos_update_prepare():
        global prepared_update
        if not updater_available():
            return jsonify(error="Secure Chromebook updates are not configured."), 503
        # Do not let an unrelated website trigger a large local download.
        if request.headers.get("Origin") not in (
            None, "http://localhost:" + str(PORT), "http://127.0.0.1:" + str(PORT),
        ):
            return jsonify(error="Cross-origin update requests are forbidden."), 403
        with backend.LOCK:
            if any(j["status"] not in backend.FINAL for j in backend.JOBS.values()):
                return jsonify(error="Finish or cancel the conversion before updating."), 409
        try:
            result = check_for_update()
            if not result:
                return jsonify(error="YUBSUB is already up to date."), 409
            manifest, url = result
            package = prepare_update(manifest, url)
            with prepared_lock:
                previous = prepared_update
                prepared_update = package
            if previous is not None:
                previous.unlink(missing_ok=True)
            return jsonify(ok=True, filename=package.name,
                           download="/api/chromeos/update/download")
        except Exception:
            backend.app.logger.exception("ChromeOS update verification failed")
            return jsonify(error="Unable to download or verify the signed update."), 503

    @backend.app.get("/api/chromeos/update/download")
    def chromeos_update_download():
        with prepared_lock:
            path = prepared_update
        if not path or not path.is_file():
            return jsonify(error="No verified package is ready."), 404
        response = send_file(path, as_attachment=True,
                             download_name=path.name, mimetype="application/vnd.debian.binary-package")
        response.headers["Cache-Control"] = "no-store"
        return response


def smoke_test():
    """Verify bundled local assets, architecture and web API without downloads."""
    import platform

    import app as backend
    import yt_dlp
    from linux_updater import current_version
    assert sys.platform == "linux"
    tools = {}
    for program in ("deno", "ffmpeg", "ffprobe"):
        executable = shutil.which(program)
        assert executable and Path(executable).is_file(), program
        output = subprocess.run(
            [executable, "--version" if program == "deno" else "-version"],
            capture_output=True, text=True, timeout=20, check=True,
        )
        tools[program] = (output.stdout or output.stderr).splitlines()[0]
    assert str((resources_dir() / "bin").resolve()) in str(Path(tools_dir("deno")).resolve())
    client = backend.app.test_client()
    assert client.get("/").status_code == 200
    assert b"YUBSUB" in client.get("/").data
    assert client.get("/static/config.js").status_code == 200
    assert client.get("/api/health").json["ok"] is True
    info = client.get("/api/chromeos/version")
    assert info.status_code == 200 and info.json["platform"] == "chromeos-linux"
    print(json.dumps({"ok": True, "platform": platform.machine(),
                      "version": current_version(), "tools": tools,
                      "yt_dlp": yt_dlp.version.__version__}, indent=2))


def tools_dir(program):
    return shutil.which(program) or ""


def existing_app_url():
    """Reconnect a launcher click to our own existing loopback server."""
    import socket
    try:
        with urlopen("http://127.0.0.1:" + str(PORT) + "/api/chromeos/version", timeout=1.5) as response:
            data = json.load(response)
        if data.get("app") == "YUBSUB" and data.get("platform") == "chromeos-linux":
            return "http://localhost:" + str(PORT) + "/"
    except (OSError, URLError, ValueError, TimeoutError, socket.timeout):
        pass
    return None


def open_chromeos_browser(url):
    """Crostini xdg-open delegates URLs to the Chromebook host via Garcon."""
    for command in (["xdg-open", url], ["garcon-url-handler", url]):
        if not shutil.which(command[0]):
            continue
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return True
        except OSError:
            continue
    print("Open this address in Chrome on your Chromebook: " + url, flush=True)
    return False


def run():
    from werkzeug.serving import make_server
    backend = _backend()
    existing = existing_app_url()
    if existing:
        open_chromeos_browser(existing)
        return

    try:
        server = make_server("127.0.0.1", PORT, backend.app, threaded=True)
    except OSError:
        raise SystemExit("YUBSUB cannot bind localhost:8765. Close the existing program and retry.")

    # Avoid idle YUBSUB processes keeping Chromebook Linux running forever.
    stop_idle = threading.Event()
    def idle_monitor():
        while not stop_idle.wait(60):
            with backend.LOCK:
                running = any(j["status"] not in backend.FINAL for j in backend.JOBS.values())
            with last_activity_lock:
                idle = time.monotonic() - last_activity
            if not running and idle > IDLE_SECONDS:
                server.shutdown()
                break

    thread = threading.Thread(target=idle_monitor, daemon=True, name="yubsub-idle")
    thread.start()
    url = "http://localhost:" + str(PORT) + "/"
    print("YUBSUB is running at " + url, flush=True)
    try:
        open_chromeos_browser(url)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_idle.set()
        server.server_close()
        with prepared_lock:
            package = prepared_update
        if package is not None:
            folder = package.parent
            try:
                package.unlink(missing_ok=True)
                folder.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    configure_runtime()
    register_routes()
    if "--smoke-test" in sys.argv:
        smoke_test()
    elif "--print-url" in sys.argv:
        print("http://localhost:" + str(PORT) + "/")
    else:
        run()
