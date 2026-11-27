"""Offline ChromeOS launcher, packaging and signed-update tests."""
import base64
import hashlib
import io
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chromeos-app"))
import linux_updater as updates
import chromeos_app as desktop


def test_update_architecture(monkeypatch):
    for machine, expected in (("x86_64", "amd64"), ("aarch64", "arm64")):
        monkeypatch.setattr(updates.platform, "machine", lambda: machine)
        assert updates.architecture() == expected
    monkeypatch.setattr(updates.platform, "machine", lambda: "armv7l")
    with pytest.raises(ValueError, match="Unsupported"):
        updates.architecture()


def test_only_official_github_release_assets():
    tag = "chromeos-v0.5.1"
    name = "yubsub_0.5.1_amd64.deb"
    url = "https://github.com/godthefather1952/yubsub/releases/download/" + tag + "/" + name
    assert updates._asset_url(url, tag, name)
    for unsafe in (
        "http://github.com/godthefather1952/yubsub/releases/download/" + tag + "/" + name,
        "https://github.com.evil.test/godthefather1952/yubsub/releases/download/" + tag + "/" + name,
        "https://127.0.0.1/" + name,
        "https://github.com/elsewhere/repo/releases/download/" + tag + "/" + name,
    ):
        assert not updates._asset_url(unsafe, tag, name)


def test_signed_release_and_verified_package(monkeypatch, tmp_path):
    crypto = pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    appdir = tmp_path / "chromeos-app"
    appdir.mkdir()
    (appdir / "VERSION").write_text("0.5.0\n", encoding="utf-8")
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    (tmp_path / "update-public-key.txt").write_text(
        base64.b64encode(public).decode(), encoding="ascii")
    monkeypatch.setattr(updates, "resources_dir", lambda: tmp_path)
    monkeypatch.setattr(updates.platform, "machine", lambda: "x86_64")
    assert updates.updater_available()
    payload = b"fake-deb-payload-for-offline-tests"
    name = "yubsub_0.5.1_amd64.deb"
    manifest = {
        "version": "0.5.1",
        "packages": {
            "amd64": {"name": name, "size": len(payload),
                      "sha256": hashlib.sha256(payload).hexdigest()}
        },
    }
    raw = json.dumps(manifest, separators=(",", ":")).encode()
    signature = base64.b64encode(private.sign(updates.CONTEXT + raw))
    tag = "chromeos-v0.5.1"
    prefix = "https://github.com/godthefather1952/yubsub/releases/download/" + tag + "/"
    assets = {
        "chromeos-update.json": prefix + "chromeos-update.json",
        "chromeos-update.sig": prefix + "chromeos-update.sig",
        name: prefix + name,
    }
    monkeypatch.setattr(updates, "_find_release", lambda: ((0, 5, 1), tag, assets))
    source = {assets["chromeos-update.json"]: raw, assets["chromeos-update.sig"]: signature}
    monkeypatch.setattr(updates, "_read_small", lambda url, _: source[url])
    verified, url = updates.check_for_update()
    assert verified["version"] == "0.5.1"
    assert url == assets[name]

    class FakeResponse(io.BytesIO):
        def geturl(self):
            return assets[name]

    monkeypatch.setattr(updates, "_open", lambda url: FakeResponse(payload))
    saved = updates.prepare_update(verified, url)
    try:
        assert saved.read_bytes() == payload
    finally:
        saved.unlink()
        saved.parent.rmdir()

    monkeypatch.setattr(updates, "_open", lambda url: FakeResponse(b"tampered"))
    with pytest.raises(ValueError, match="checksum|size"):
        updates.prepare_update(verified, url)

    monkeypatch.setattr(updates, "_read_small", lambda url, _: b"{}" if url.endswith(".json") else signature)
    with pytest.raises(Exception):
        updates.check_for_update()


def test_chromeos_version_api_without_mutating_other_platforms(monkeypatch):
    from flask import Flask
    lock = threading.RLock()
    isolated = SimpleNamespace(app=Flask("yubsub-chromeos-test"), LOCK=lock,
                               JOBS={}, FINAL={"complete", "cancelled", "error"})
    monkeypatch.setattr(desktop, "_backend", lambda: isolated)
    monkeypatch.setattr(updates, "updater_available", lambda: False)
    desktop.register_routes()
    response = isolated.app.test_client().get("/api/chromeos/version")
    assert response.status_code == 200
    assert response.json["platform"] == "chromeos-linux"
    assert response.json["version"] == "0.5.1"
    assert response.json["updates"] is False
    assert isolated.app.test_client().get("/api/chromeos/update/check").status_code == 503


def test_checkout_contains_desktop_shortcut_and_build_workflow():
    launcher = (ROOT / "chromeos-app" / "yubsub.desktop").read_text()
    workflow = (ROOT / ".github" / "workflows" / "chromeos-app.yml").read_text()
    script = (ROOT / "chromeos-app" / "build_linux.sh").read_text()
    assert "Exec=/opt/yubsub/yubsub" in launcher
    assert "ubuntu-22.04-arm" in workflow
    assert "dpkg-deb --build" in script
    assert "yt_dlp_ejs" in script
    assert "sha256sum -c -" in script
