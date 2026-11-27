"""Signature-checked ChromeOS .deb updates; installations are user-controlled.

Only official GitHub releases with an Ed25519-signed manifest are considered.
The updater verifies full .deb SHA-256 before handing it to Chrome's downloads.
It never executes a package or requests sudo itself.
"""
import base64
import hashlib
import json
import os
import platform
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REPO = "godthefather1952/yubsub"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
CONTEXT = b"YUBSUB-CHROMEOS-UPDATE-V1\n"
MAX_DEB_SIZE = 500 * 1024 * 1024
TAG = re.compile(r"^chromeos-v(\d+\.\d+\.\d+)$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
CACHE_SECONDS = 300
_cache_at = 0.0
_cached_release = None


def resources_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def current_version():
    version = (resources_dir() / "chromeos-app" / "VERSION").read_text(
        encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid bundled ChromeOS version")
    return version


def architecture():
    value = platform.machine().lower()
    if value in ("x86_64", "amd64"):
        return "amd64"
    if value in ("aarch64", "arm64"):
        return "arm64"
    raise ValueError("Unsupported ChromeOS Linux architecture: " + value)


def updater_available():
    try:
        value = (resources_dir() / "update-public-key.txt").read_text(
            encoding="ascii").strip()
        return len(base64.b64decode(value, validate=True)) == 32
    except (OSError, ValueError):
        return False


def _version_tuple(value):
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(value)):
        raise ValueError("Invalid update version")
    return tuple(int(number) for number in value.split("."))


def _asset_url(url, tag, name):
    if not isinstance(url, str) or not isinstance(name, str):
        return False
    try:
        part = urlsplit(url)
        return (
            part.scheme == "https" and part.hostname == "github.com"
            and part.username is None and part.password is None
            and part.port in (None, 443)
            and part.query == "" and part.fragment == ""
            and part.path == f"/{REPO}/releases/download/{tag}/{name}"
        )
    except ValueError:
        return False


def _open(url):
    request = Request(url, headers={
        "User-Agent": f"YUBSUB-ChromeOS/{current_version()} (+https://github.com/{REPO})",
        "Accept": "application/octet-stream,application/json",
    })
    return urlopen(request, timeout=30)


def _read_small(url, limit):
    with _open(url) as response:
        if urlsplit(response.geturl()).scheme != "https":
            raise ValueError("Update source must use HTTPS")
        payload = response.read(limit + 1)
        if len(payload) > limit:
            raise ValueError("Update manifest/signature too large")
        return payload


def _find_release():
    global _cache_at, _cached_release
    if time.monotonic() - _cache_at < CACHE_SECONDS:
        return _cached_release
    listings = json.loads(_read_small(RELEASES_API, 1 * 1024 * 1024))
    if not isinstance(listings, list):
        raise ValueError("Invalid GitHub releases listing")
    candidates = []
    for release in listings:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name", "")
        match = TAG.fullmatch(str(tag))
        if not match:
            continue
        assets = {}
        for item in release.get("assets", []):
            if not isinstance(item, dict):
                continue
            name, url = item.get("name"), item.get("browser_download_url")
            if isinstance(name, str) and _asset_url(url, tag, name):
                assets[name] = url
        if "chromeos-update.json" in assets and "chromeos-update.sig" in assets:
            candidates.append((_version_tuple(match.group(1)), tag, assets))
    _cached_release = max(candidates, default=None, key=lambda row: row[0])
    _cache_at = time.monotonic()
    return _cached_release


def check_for_update():
    """Return (validated manifest, official .deb URL) or None."""
    if not updater_available():
        raise ValueError("Update verification key is not configured")
    result = _find_release()
    if not result or result[0] <= _version_tuple(current_version()):
        return None
    _, tag, assets = result
    manifest_raw = _read_small(assets["chromeos-update.json"], 8192)
    signature_raw = _read_small(assets["chromeos-update.sig"], 512)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    public_b64 = (resources_dir() / "update-public-key.txt").read_text(
        encoding="ascii").strip()
    public_key = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(public_b64, validate=True))
    signature = base64.b64decode(signature_raw.strip(), validate=True)
    public_key.verify(signature, CONTEXT + manifest_raw)
    manifest = json.loads(manifest_raw)
    version = tag[len("chromeos-v"):]
    if manifest.get("version") != version:
        raise ValueError("Signed ChromeOS version mismatch")
    arch = architecture()
    expected_name = f"yubsub_{version}_{arch}.deb"
    package = (manifest.get("packages") or {}).get(arch)
    if not isinstance(package, dict) or package.get("name") != expected_name:
        raise ValueError("Signed update does not support this architecture")
    if expected_name not in assets:
        raise ValueError("Official ChromeOS .deb missing from release")
    if type(package.get("size")) is not int or not 0 < package["size"] <= MAX_DEB_SIZE:
        raise ValueError("Invalid signed update size")
    if not isinstance(package.get("sha256"), str) or not DIGEST.fullmatch(package["sha256"]):
        raise ValueError("Invalid signed update SHA-256")
    return dict(version=version, package=package), assets[expected_name]


def prepare_update(manifest, url):
    """Download package and verify the signed bytes before exposing a local file."""
    package = manifest["package"]
    arch = architecture()
    filename = f'yubsub_{manifest["version"]}_{arch}.deb'
    if package["name"] != filename:
        raise ValueError("Update filename mismatch")
    tag = "chromeos-v" + manifest["version"]
    if not _asset_url(url, tag, filename):
        raise ValueError("Untrusted ChromeOS package URL")
    directory = Path(tempfile.mkdtemp(prefix="yubsub-update-"))
    destination = directory / filename
    checksum = hashlib.sha256()
    total = 0
    try:
        with _open(url) as response, destination.open("wb") as output:
            if urlsplit(response.geturl()).scheme != "https":
                raise ValueError("Package download was redirected off HTTPS")
            for piece in iter(lambda: response.read(1024 * 1024), b""):
                total += len(piece)
                if total > package["size"]:
                    raise ValueError("Package exceeded signed size")
                output.write(piece)
                checksum.update(piece)
        if total != package["size"] or checksum.hexdigest() != package["sha256"]:
            raise ValueError("ChromeOS package checksum mismatch")
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        directory.rmdir()
        raise
