# YUBSUB V4 — Secure automatic updates (owner setup)

Version **0.4.0** introduces Sparkle 2 update support to the self-contained macOS app.
Sparkle provides the native **Update Now / Later** dialog, download, install,
relaunch and recovery behavior. YUBSUB does **not** run a custom privileged
installer or trust arbitrary GitHub download links.

**Important:** The updater is available only after a real Ed25519 verification
key has been installed in the app. The GitHub workflow refuses to publish a
release until a matching private signing key is configured. No key is present
in this repository.

## One-time owner setup — before merging / releasing v0.4.0

Run on **your own Mac**, from a checkout of this project:

```bash
bash mac-app/create_update_key.sh
```

The script writes a private 32-byte Ed25519 seed (base64 encoded) and public key to:

`~/Library/Application Support/YUBSUB/Signing/`

Private file permissions are restricted to your user (`0600`). **Never share
the private key in ChatGPT, a commit, a screenshot, or with customers.** Back it
up securely/offline. The only supported update trust root is that owner key.

1. Open [repository Actions settings](https://github.com/godthefather1952/yubsub/settings/secrets/actions).
2. Under **Variables**, add:
   - **Name:** `SPARKLE_PUBLIC_ED_KEY`
   - **Value:** The public base64 string printed by the setup script, also in `sparkle-public-key.txt`.
3. Under **Secrets**, add:
   - **Name:** `SPARKLE_PRIVATE_KEY`
   - **Value:** The contents of your private `sparkle-private-key.txt` file. Use GitHub's secret-entry UI on your own Mac; do not send it through chat.
4. Trigger the PR build again; both Intel and Apple silicon GitHub Actions
   runners should package **Sparkle.framework** and pass the smoke test.
5. Merge the PR after all checks pass. GitHub Actions will create official
   `mac-app-v0.4.0`, with two signed update feeds and the ZIP files.

To trigger a fresh Actions run after adding the variable, you can use
**Actions → Build standalone YUBSUB for macOS → Run workflow**, selecting
the `feature/secure-auto-updates-v04` branch, or push a small follow-up commit.

## How updates work

- YUBSUB checks GitHub's latest stable release **once per day** while running.
- The native Sparkle dialog offers users **Update Now / Later**.
- A **Check for Updates** control is also shown inside the Mac app.
- Each architecture has its own update feed, hosted as GitHub Release assets:
  - `https://github.com/godthefather1952/yubsub/releases/latest/download/appcast-Intel.xml`
  - `https://github.com/godthefather1952/yubsub/releases/latest/download/appcast-Apple-Silicon.xml`
- Release ZIPs are signed with the owner's Ed25519 private key in the GitHub
  Actions release job. The app trusts the pinned **public** key, and refuses
  updates that fail verification **before extraction**.
- Mac builds do not bundle the private key or download arbitrary executables.
- Sparkle controls installation, replacement/relaunch and error recovery.
- The "Check for Updates" action is blocked while a conversion job is active.
  Automatic checks **never silently install** updates; users must choose.
- This is separate from Apple Developer ID signing/notarization. Until those
  are enabled, a first-launch Gatekeeper warning may still occur.

## Migration and future releases

**Existing v0.3.0 users need one manual update:** download and replace their
existing app with v0.4.0, since v0.3.0 did not ship an updater. Updates after
0.4.0 can use Sparkle.

For every future version:
1. Increase `mac-app/VERSION` (e.g. `0.4.1`).
2. Build Intel and Apple silicon ZIPs on GitHub Actions.
3. The release job verifies that private/public keys match, signs both ZIPs,
   and publishes their Sparkle appcasts alongside the downloads.
4. Test an upgrade from the **previous** version on a real Mac (including
   downloading MP3s and restarting the app).

**Never rotate the Ed25519 key without an explicit migration plan.** With
unsigned Developer ID code-signing, replacing the pinned public key can break
the installed base's ability to trust future updates. Store offline backups
of the private key.

## Security and QA limitations

- The signature authenticates ZIP bytes and mitigates compromised release
  hosting. The feed itself is served over HTTPS; it is **not separately signed**.
  Sparkle verifies archive signatures before extraction.
- End-to-end install/relaunch behavior requires testing in a real `/Applications`
  install, not only an automated runner smoke test.
- The app cannot auto-update itself while running from an unwritable location.
- App bundling is performed on macOS 15 runners. Older macOS compatibility
  should be verified on physical hardware.
- Official downloads are **blocked** if signing credentials are missing.
