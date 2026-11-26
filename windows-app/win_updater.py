"""Signed Windows updates. No installer executes without a pinned Ed25519 check.

The signed release manifest binds version, filename, size and SHA-256.
Windows releases are separate from macOS's Sparkle 'latest' feed.
"""
import base64
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

REPO = "godthefather1952/yubsub"
RELEASES_API = "https://api.github.com/repos/" + REPO + "/releases?per_page=50"
CONTEXT = b"YUBSUB-WINDOWS-UPDATE-V1\n"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
MAX_INSTALLER_SIZE = 500 * 1024 * 1024


def resources_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def installed_version():
    path = resources_dir() / "windows-app" / "VERSION"
    version = path.read_text(encoding="utf-8").strip()
    if not VERSION_RE.fullmatch(version):
        raise ValueError("Invalid bundled YUBSUB version")
    return version


def version_tuple(version):
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ValueError("Invalid update version")
    return tuple(int(part) for part in version.split("."))


def updater_available():
    try:
        return len(base64.b64decode(
            (resources_dir() / "update-public-key.txt").read_text(encoding="utf-8").strip(),
            validate=True)) == 32
    except (OSError, ValueError):
        return False


def _open(url, accept="application/json"):
    request = Request(url, headers={
        "User-Agent": "YUBSUB-Windows-Updater/0.5 (+https://github.com/" + REPO + ")",
        "Accept": accept,
    })
    return urlopen(request, timeout=25)


def _asset_url(url, tag, name):
    if not isinstance(url, str):
        return False
    u = urlsplit(url)
    return (u.scheme == "https" and u.hostname == "github.com"
            and u.username is None and u.password is None and u.port in (None, 443)
            and u.path == "/" + REPO + "/releases/download/" + tag + "/" + name)


def _release_assets(release):
    tag = str(release.get("tag_name") or "")
    if not re.fullmatch(r"windows-v\d+\.\d+\.\d+", tag):
        return None
    items = {}
    for asset in release.get("assets") or []:
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if isinstance(name, str) and _asset_url(url, tag, name):
            items[name] = url
    if not all(name in items for name in ("windows-update.json", "windows-update.sig")):
        return None
    return tag, items


def _latest_windows_release():
    # Reading the public GitHub API does not trust release contents; verification
    # always uses the pinned key and the manifest's installer SHA.
    with _open(RELEASES_API) as response:
        releases = json.load(response)
    if not isinstance(releases, list):
        raise ValueError("Invalid release listing")
    choices = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        result = _release_assets(release)
        if result:
            tag, assets = result
            choices.append((version_tuple(tag[len("windows-v"):]), tag, assets))
    return max(choices, default=None, key=lambda row: row[0])


def _verified_release():
    current = version_tuple(installed_version())
    found = _latest_windows_release()
    if not found or found[0] <= current:
        return None
    version, tag, assets = found
    with _open(assets["windows-update.json"]) as response:
        raw = response.read(8192)
    with _open(assets["windows-update.sig"], "text/plain") as response:
        signature_b64 = response.read(512).decode("ascii").strip()
    public_raw = base64.b64decode(
        (resources_dir() / "update-public-key.txt").read_text(encoding="utf-8").strip(),
        validate=True)
    signature = base64.b64decode(signature_b64, validate=True)
    Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, CONTEXT + raw)
    manifest = json.loads(raw)
    expected_name = "YUBSUB-Setup-v" + tag[len("windows-v"):] + ".exe"
    if manifest.get("version") != tag[len("windows-v"):]:
        raise ValueError("Update manifest version mismatch")
    if manifest.get("installer") != expected_name or expected_name not in assets:
        raise ValueError("Installer not found in signed release")
    if not isinstance(manifest.get("size"), int) or not 0 < manifest["size"] < MAX_INSTALLER_SIZE:
        raise ValueError("Invalid signed installer length")
    digest = manifest.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid signed checksum")
    return manifest, assets[expected_name]


def _show(message, title="YUBSUB for Windows", yes_no=False):
    flags = 0x20 | (0x04 if yes_no else 0)  # Question icon and Yes/No if requested.
    return ctypes.windll.user32.MessageBoxW(None, message, title, flags)


def _download_verified(manifest, url):
    folder = Path(tempfile.mkdtemp(prefix="yubsub-update-"))
    path = folder / manifest["installer"]
    actual = hashlib.sha256()
    total = 0
    try:
        with _open(url, "application/octet-stream") as response, path.open("wb") as stream:
            # GitHub may redirect assets to a temporary CDN URL. The signed
            # size+hash check authenticates the final payload before execution.
            if urlsplit(response.geturl()).scheme != "https":
                raise ValueError("Non-HTTPS update response")
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                total += len(chunk)
                if total > manifest["size"]:
                    raise ValueError("Update larger than signed size")
                actual.update(chunk)
                stream.write(chunk)
        if total != manifest["size"] or actual.hexdigest() != manifest["sha256"]:
            raise ValueError("Update signature payload check failed")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        try:
            folder.rmdir()
        except OSError:
            pass
        raise


def check_for_updates(interactive=True):
    """Only install after an explicit user action and a verified download."""
    if not updater_available():
        return {"ok": False, "error": "Secure Windows updates are not configured."}
    try:
        update = _verified_release()
        if not update:
            if interactive:
                _show("YUBSUB " + installed_version() + " is up to date.")
            return {"ok": True, "update_available": False}
        manifest, url = update
        if not interactive:
            return {"ok": True, "update_available": True, "version": manifest["version"]}
        if _show("YUBSUB " + manifest["version"] + " is available.\n\n"
                 "Download the verified installer and update now?", yes_no=True) != 6:
            return {"ok": True, "update_available": True, "declined": True}
        installer = _download_verified(manifest, url)
        subprocess.Popen([str(installer), "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
                         close_fds=True)
        # Installer uses Restart Manager to close/replace this application.
        # Also request the UI close to avoid a locked running executable.
        def close_window():
            time.sleep(1)
            try:
                import webview
                if webview.windows:
                    webview.windows[0].destroy()
            except Exception:
                pass
        threading.Thread(target=close_window, daemon=True).start()
        return {"ok": True, "update_available": True, "installer_started": True}
    except Exception:
        return {"ok": False, "error": "Could not verify a Windows update. Try again later."}
