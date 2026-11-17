#!/usr/bin/env bash
# Run ONCE on YOUR Mac. Creates a private Ed25519 signing key locally.
# It never sends your private key to ChatGPT or commits it to your repository.
set -euo pipefail
umask 077

KEY_DIR="$HOME/Library/Application Support/YUBSUB/Signing"
PRIVATE_KEY="$KEY_DIR/sparkle-private-key.txt"
PUBLIC_KEY="$KEY_DIR/sparkle-public-key.txt"
mkdir -p "$KEY_DIR"

if [[ -e "$PRIVATE_KEY" || -e "$PUBLIC_KEY" ]]; then
  echo "Signing key already exists in $KEY_DIR."
  echo "Never replace it once you release an updater-enabled build."
  exit 1
fi

# Reuse your existing YUBSUB Python environment if available; otherwise
# create a small isolated environment for signing-key management.
PYTHON="$HOME/yubsub/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  command -v python3 >/dev/null 2>&1 || {
    echo "Python 3 is required only to create the signing key." >&2
    exit 1
  }
  python3 -m venv "$KEY_DIR/.venv"
  PYTHON="$KEY_DIR/.venv/bin/python"
fi
"$PYTHON" -m pip install --quiet 'cryptography>=44,<49'

"$PYTHON" - "$PRIVATE_KEY" "$PUBLIC_KEY" <<'PY'
import base64, sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
private_path, public_path = map(Path, sys.argv[1:])
key = ed25519.Ed25519PrivateKey.generate()
private_bytes = key.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption())
public_bytes = key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw)
private_path.write_text(base64.b64encode(private_bytes).decode("ascii") + "\n")
public_path.write_text(base64.b64encode(public_bytes).decode("ascii") + "\n")
private_path.chmod(0o600)
public_path.chmod(0o600)
print("\nCreated secure YUBSUB update signing identity.")
print("Public key (safe to use in GitHub Actions variable SPARKLE_PUBLIC_ED_KEY):")
print(base64.b64encode(public_bytes).decode("ascii"))
print("\nPrivate key location (DO NOT POST OR COMMIT):", private_path)
PY

cat <<EOF

NEXT STEPS
1. In GitHub > Settings > Secrets and variables > Actions > Variables:
   New repository variable: SPARKLE_PUBLIC_ED_KEY
   Value: copy the public key printed above (also in sparkle-public-key.txt).

2. In GitHub > Settings > Secrets and variables > Actions > Secrets:
   New repository secret: SPARKLE_PRIVATE_KEY
   Value: the single line inside this PRIVATE file:
   $PRIVATE_KEY

3. Back up that private key OFFLINE. If lost, unsigned YUBSUB builds cannot
   continue the verified update chain.

4. Do NOT share the private key in ChatGPT, screenshots, issues or commits.
EOF
