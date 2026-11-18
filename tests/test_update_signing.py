"""Offline security regression tests for YUBSUB's Sparkle update pipeline."""
import base64
import importlib.util
import pathlib
import zipfile
from xml.etree import ElementTree as ET

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sign_release", ROOT / "mac-app" / "sign_release.py")
signing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signing)
SPARKLE_NS = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"


def sample_keys():
    key = Ed25519PrivateKey.generate()
    secret = key.private_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption())
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return base64.b64encode(secret).decode(), base64.b64encode(public).decode()


def test_key_pair_is_verified_and_mismatch_is_blocked():
    private, public = sample_keys()
    key = signing.load_signing_key(private, public)
    assert key
    _, other_public = sample_keys()
    with pytest.raises(ValueError, match="does not match"):
        signing.load_signing_key(private, other_public)
    with pytest.raises(ValueError):
        signing.load_signing_key("not a key", public)


def test_sparkle_signatures_verify_and_tampering_is_rejected(tmp_path):
    private, public = sample_keys()
    key = signing.load_signing_key(private, public)
    for arch in signing.ARCHES:
        target = tmp_path / f"YUBSUB-macOS-{arch}.zip"
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("YUBSUB.app/test.txt", "version 0.4.0")

    feeds = signing.sign_archives(tmp_path, "0.4.0", key)
    assert len(feeds) == 2
    for arch in signing.ARCHES:
        doc = ET.parse(tmp_path / f"appcast-{arch}.xml")
        enclosure = doc.find("./channel/item/enclosure")
        assert enclosure is not None
        assert doc.findtext(f"./channel/item/{SPARKLE_NS}version") == "400"
        assert doc.findtext(f"./channel/item/{SPARKLE_NS}shortVersionString") == "0.4.0"
        assert f"YUBSUB-macOS-{arch}.zip" in enclosure.attrib["url"]
        original = (tmp_path / f"YUBSUB-macOS-{arch}.zip").read_bytes()
        signed = base64.b64decode(enclosure.attrib[SPARKLE_NS + "edSignature"])
        key.public_key().verify(signed, original)
        with pytest.raises(InvalidSignature):
            key.public_key().verify(signed, original + b"malicious change")

    with pytest.raises(ValueError, match="mismatch"):
        signing.sign_archives(tmp_path, "0.4.0", key, "mac-app-v0.4.1")


def test_macos_build_and_release_require_signed_updates():
    script = (ROOT / "mac-app" / "build_macos.sh").read_text()
    workflow = (ROOT / ".github" / "workflows" / "mac-app.yml").read_text()
    assert "SUVerifyUpdateBeforeExtraction bool true" in script
    assert "SPARKLE_PUBLIC_ED_KEY" in script
    assert "SPARKLE_PRIVATE_KEY" in workflow
    assert "Require trustworthy update-signing keys" in workflow
    assert "sign_release.py" in workflow
    assert "appcast-Intel.xml" in workflow
    assert "appcast-Apple-Silicon.xml" in workflow
    version = (ROOT / "mac-app" / "VERSION").read_text().strip()
    assert version == "0.4.3"
    assert signing.version_build(version) == "403"
