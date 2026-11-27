"""Sign a Windows installer manifest with YUBSUB's existing owner Ed25519 key.

Private signing key never enters the Windows application or repository.
Manifest signature is domain-separated from macOS Sparkle archive signatures.
"""
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mac-app"))
from sign_release import load_signing_key  # noqa: E402

CONTEXT = b"YUBSUB-WINDOWS-UPDATE-V1\n"


def sign_windows_release(directory, version, private_key, public_key):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid release version")
    destination = Path(directory)
    installer_name = f"YUBSUB-Setup-v{version}.exe"
    portable_name = f"YUBSUB-Windows-x64-Portable-v{version}.zip"
    setup = destination / installer_name
    portable = destination / portable_name
    if not setup.is_file() or not portable.is_file():
        raise FileNotFoundError("Expected Windows installer and portable ZIP")
    if setup.stat().st_size < 10000 or portable.stat().st_size < 10000:
        raise ValueError("Installer or portable ZIP is unexpectedly small")
    signer = load_signing_key(private_key, public_key)
    manifest = {
        "version": version,
        "installer": installer_name,
        "sha256": hashlib.sha256(setup.read_bytes()).hexdigest(),
        "size": setup.stat().st_size,
    }
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = signer.sign(CONTEXT + raw)
    signer.public_key().verify(signature, CONTEXT + raw)
    (destination / "windows-update.json").write_bytes(raw)
    (destination / "windows-update.sig").write_text(
        base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii")
    checksums = []
    for file in (setup, portable):
        checksums.append(hashlib.sha256(file.read_bytes()).hexdigest() + "  " + file.name)
    (destination / "SHA256SUMS-windows.txt").write_text(
        "\n".join(checksums) + "\n", encoding="ascii")
    return manifest


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: sign_release.py <release asset dir> <version>")
    sign_windows_release(
        sys.argv[1], sys.argv[2],
        os.environ.get("SPARKLE_PRIVATE_KEY", ""),
        os.environ.get("SPARKLE_PUBLIC_ED_KEY", ""),
    )
    print("Windows installer manifest signed and verified.")
