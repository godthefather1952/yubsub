"""Feature parity contract for WAV and the per-platform signed update channels."""
from pathlib import Path

import app as backend

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_wav_api_is_enabled_for_every_desktop():
    assert backend.AUDIO_FORMATS == {"mp3", "flac", "wav"}
    assert backend.MAX_WAV_TRACK >= backend.MAX_FLAC_TRACK
    ui = read("static/index.html")
    assert ui == read("index.html")
    assert 'name="format" value="wav"' in ui
    assert '"wav"].includes(s.format)' in ui
    assert 'el("quality-section").hidden = fmt!=="MP3"' in ui
    assert "metadata:el(\"metadata\").checked" in ui


def test_macos_and_windows_save_as_reuse_all_audio_formats():
    mac = read("mac_app.py")
    windows = read("win_app.py")
    assert "audio_format not in backend.AUDIO_FORMATS" in mac
    assert "audio_format not in backend.AUDIO_FORMATS" in windows
    assert 'extension = "." + audio_format' in mac
    assert 'extension = "." + audio_format' in windows


def test_chromeos_shows_daily_signed_updates_but_does_not_install():
    source = read("static/index.html")
    linux = read("chromeos-app/linux_updater.py")
    assert "checkChromeOSDaily()" in source
    assert '"/api/chromeos/update/check"' in source
    assert "24*60*60*1000" in source
    assert "chromeosUpdateVersion" in source
    assert "CONTEXT = b\"YUBSUB-CHROMEOS-UPDATE-V1" in linux
    assert "check_for_update" in linux
    assert "prepare_update" in linux


def test_desktop_release_versions_are_synced_for_wav():
    versions = [
        read("mac-app/VERSION").strip(),
        read("windows-app/VERSION").strip(),
        read("chromeos-app/VERSION").strip(),
    ]
    assert versions == ["0.5.1", "0.5.1", "0.5.1"]


def test_releases_publish_to_distinct_signed_channels():
    mac = read(".github/workflows/mac-app.yml")
    windows = read(".github/workflows/windows-app.yml")
    chrome = read(".github/workflows/chromeos-app.yml")
    assert "SPARKLE_PRIVATE_KEY" in mac
    assert "appcast-Intel.xml" in mac
    assert "SPARKLE_PRIVATE_KEY" in windows
    assert "windows-update.sig" in windows
    assert "SPARKLE_PRIVATE_KEY" in chrome
    assert "chromeos-update.sig" in chrome
    assert "music_metadata.py" in mac
