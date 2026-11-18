"""Offline regression tests for YUBSUB's macOS native clipboard bridge."""
import sys
import types
from pathlib import Path

from mac_app import DesktopUpdatesAPI


class FakePasteboard:
    def __init__(self, value=None, failure=False):
        self.value = value
        self.failure = failure
        self.reads = 0
        self.pasteboard_type = None

    def stringForType_(self, kind):
        self.reads += 1
        self.pasteboard_type = kind
        if self.failure:
            raise RuntimeError("Pasteboard denied")
        return self.value


def install_appkit(monkeypatch, pasteboard):
    fake_appkit = types.ModuleType("AppKit")
    class NSPasteboard:
        @staticmethod
        def generalPasteboard():
            return pasteboard

    fake_appkit.NSPasteboard = NSPasteboard
    fake_appkit.NSPasteboardTypeString = "public.utf8-plain-text"
    monkeypatch.setitem(sys.modules, "AppKit", fake_appkit)


def test_native_clipboard_returns_plain_text_only_when_called(monkeypatch):
    panel = FakePasteboard("  https://youtu.be/abcdefghijk\n")
    install_appkit(monkeypatch, panel)
    bridge = DesktopUpdatesAPI()
    assert panel.reads == 0  # no automatic clipboard reads on creation
    result = bridge.read_clipboard()
    assert result == {"ok": True, "text": "https://youtu.be/abcdefghijk"}
    assert panel.reads == 1
    assert panel.pasteboard_type == "public.utf8-plain-text"


def test_native_clipboard_reports_empty_or_non_text(monkeypatch):
    for value in ("", "  ", None):
        panel = FakePasteboard(value)
        install_appkit(monkeypatch, panel)
        result = DesktopUpdatesAPI().read_clipboard()
        assert result["ok"] is False
        assert "Copy a YouTube link" in result["error"]


def test_native_clipboard_handles_cocoa_failure(monkeypatch):
    panel = FakePasteboard(failure=True)
    install_appkit(monkeypatch, panel)
    result = DesktopUpdatesAPI().read_clipboard()
    assert result["ok"] is False
    assert "Command+V" in result["error"]


def test_native_clipboard_rejects_large_text(monkeypatch):
    panel = FakePasteboard("x" * 8193)
    install_appkit(monkeypatch, panel)
    result = DesktopUpdatesAPI().read_clipboard()
    assert result["ok"] is False
    assert "too long" in result["error"]


def test_frontends_use_native_paste_then_web_fallback():
    root = Path(__file__).resolve().parents[1]
    mac_ui = (root / "static/index.html").read_text()
    browser_ui = (root / "index.html").read_text()
    assert mac_ui == browser_ui
    assert 'nativeApi.read_clipboard()' in mac_ui
    assert 'navigator.clipboard.readText()' in mac_ui
    assert mac_ui.index('nativeApi.read_clipboard()') < mac_ui.index('navigator.clipboard.readText()')
    assert 'field.dispatchEvent(new Event("input",{bubbles:true}))' in mac_ui
    assert "Clipboard has no text" in mac_ui
