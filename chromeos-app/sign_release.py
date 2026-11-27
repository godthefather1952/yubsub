"""Sign ChromeOS YUBSUB .deb packages for safe update checks.

The private Ed25519 key is provided only to the GitHub release job.
No package contains the private key. Signatures are domain-separated from
macOS Sparkle and Windows update signatures.
"""
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CONTEXT = b"YUBSUB-CHROMEOS-UPDATE-V1\n"
ARCHES = ("amd64", "arm64")


def signing_key(private_b64, public_b64):
    private = base64.b64decode(private_b64.strip(), validate=True)
    public = base64.b64decode(public_b64.strip(), validate=True)
    if len(private) != 32 or len(public) != 32:
        raise ValueError("Owner keypair must contain 32-byte Ed25519 keys")
    key = Ed25519PrivateKey.from_private_bytes(private)
    actual = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    if actual != public:
        raise ValueError("Owner private/public update-signing key mismatch")
    return key


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sign_release(folder, version, private_b64, public_b64):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Expected semver major.minor.patch")
    key = signing_key(private_b64, public_b64)
    folder = Path(folder)
    packages = {}
    checksums = []
    for arch in ARCHES:
        name = f"yubsub_{version}_{arch}.deb"
        file = folder / name
        if not file.is_file() or file.stat().st_size < 10000:
            raise FileNotFoundError("Missing compiled ChromeOS package: " + name)
        sha = digest_file(file)
        packages[arch] = {"name": name, "size": file.stat().st_size, "sha256": sha}
        checksums.append(f"{sha}  {name}")
    manifest = {"version": version, "packages": packages}
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = key.sign(CONTEXT + payload)
    key.public_key().verify(signature, CONTEXT + payload)
    (folder / "chromeos-update.json").write_bytes(payload)
    (folder / "chromeos-update.sig").write_text(
        base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii")
    (folder / "SHA256SUMS-chromeos.txt").write_text(
        "\n".join(checksums) + "\n", encoding="ascii")
    return manifest


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python chromeos-app/sign_release.py <packages folder> <version>")
    sign_release(sys.argv[1], sys.argv[2],
                 os.environ.get("SPARKLE_PRIVATE_KEY", ""),
                 os.environ.get("SPARKLE_PUBLIC_ED_KEY", ""))
    print("ChromeOS amd64 and arm64 updates signed successfully.")
