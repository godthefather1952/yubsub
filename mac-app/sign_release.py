"""Sign YUBSUB GitHub Releases with the *offline-owner generated* Ed25519 key.

Creates architecture-specific Sparkle appcasts from the FINAL ZIP bytes. Never
signs a release unless the private key matches the public key baked into the
corresponding app. Does not output or persist signing secrets.
"""
import base64
import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SPARKLE = "http://www.andymatuschak.org/xml-namespaces/sparkle"
ET.register_namespace("sparkle", SPARKLE)
REPO = "godthefather1952/yubsub"
ARCHES = ("Intel", "Apple-Silicon")


def load_signing_key(private_key_b64, public_key_b64):
    """Fail closed on invalid key length or a key mismatch."""
    private_raw = base64.b64decode(private_key_b64.strip(), validate=True)
    public_raw = base64.b64decode(public_key_b64.strip(), validate=True)
    if len(private_raw) != 32 or len(public_raw) != 32:
        raise ValueError("Expected base64-encoded 32-byte Ed25519 secret/public keys.")
    key = Ed25519PrivateKey.from_private_bytes(private_raw)
    actual = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    if actual != public_raw:
        raise ValueError("Signing secret does not match SPARKLE_PUBLIC_ED_KEY.")
    return key


def version_build(version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Use numeric major.minor.patch version.")
    major, minor, patch = (int(x) for x in version.split("."))
    if minor >= 100 or patch >= 100:
        raise ValueError("Minor and patch versions must be below 100.")
    return str(major * 10000 + minor * 100 + patch)


def sign_archives(directory, version, key, tag=None):
    """Sign release assets and build simple Sparkle feeds.

    This feed contains no remote release notes, external links or HTML.
    The archive signature must match the exact downloadable ZIP bytes.
    """
    directory = Path(directory)
    tag = tag or f"mac-app-v{version}"
    if not re.fullmatch(r"mac-app-v\d+\.\d+\.\d+", tag):
        raise ValueError("Invalid release tag.")
    if tag != f"mac-app-v{version}":
        raise ValueError("Release version/tag mismatch.")
    build = version_build(version)
    feeds = []
    for arch in ARCHES:
        filename = f"YUBSUB-macOS-{arch}.zip"
        archive = directory / filename
        if not archive.is_file() or archive.stat().st_size < 100:
            raise FileNotFoundError(f"Missing release ZIP {filename}")
        payload = archive.read_bytes()
        signature = key.sign(payload)
        key.public_key().verify(signature, payload)

        rss = ET.Element("rss", {"version": "2.0"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = f"YUBSUB Desktop — macOS {arch}"
        ET.SubElement(channel, "link").text = f"https://github.com/{REPO}/releases"
        ET.SubElement(channel, "description").text = "Signed YUBSUB desktop updates"
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"YUBSUB Desktop {version}"
        ET.SubElement(item, f"{{{SPARKLE}}}version").text = build
        ET.SubElement(item, f"{{{SPARKLE}}}shortVersionString").text = version
        ET.SubElement(item, "enclosure", {
            "url": f"https://github.com/{REPO}/releases/download/{tag}/{filename}",
            "length": str(len(payload)),
            "type": "application/octet-stream",
            f"{{{SPARKLE}}}edSignature": base64.b64encode(signature).decode("ascii"),
        })
        feed = directory / f"appcast-{arch}.xml"
        ET.ElementTree(rss).write(feed, encoding="utf-8", xml_declaration=True)
        feeds.append(feed)
    return feeds


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: sign_release.py <asset directory> <version>")
    key = load_signing_key(
        os.environ.get("SPARKLE_PRIVATE_KEY", ""),
        os.environ.get("SPARKLE_PUBLIC_ED_KEY", ""))
    created = sign_archives(sys.argv[1], sys.argv[2], key)
    for feed in created:
        print(f"Signed update feed created: {feed.name}")
    print("All update archives verified with the public key; no secret was printed.")


if __name__ == "__main__":
    main()
