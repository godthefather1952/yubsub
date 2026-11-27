"""Regression checks for the GitHub Pages / Render deployment split."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pages_custom_domain_and_api_origin():
    # GitHub can remove CNAME when the user changes Pages custom-domain settings.
    # Keep Pages validation independent of whether a custom domain is enabled.
    cname = ROOT / "CNAME"
    if cname.exists():
        assert cname.read_text(encoding="utf-8").strip() == "yubsub.godthefather1952.com"
    config = (ROOT / "static" / "config.js").read_text(encoding="utf-8")
    assert 'window.YUBSUB_API_BASE_URL = "https://yubsub.onrender.com"' in config
    frontend = (ROOT / "index.html").read_text(encoding="utf-8")
    assert '<script src="static/config.js"></script>' in frontend
    assert "apiUrl(" in frontend


def test_pages_workflow_uses_existing_render_backend():
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "https://yubsub.onrender.com" in workflow
    assert "actions/deploy-pages" in workflow
    assert "API_BASE_URL" in workflow


def test_playlist_mode_is_default_on_both_frontends():
    root = (ROOT / "index.html").read_text(encoding="utf-8")
    local = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert root == local  # GitHub Pages and the Mac app display the same UI
    assert 'name="mode" value="playlist" checked' in root
    assert 'name="mode" value="single"' in root
    assert "mode:jobMode" in root
    assert 'name="format" value="mp3" checked' in root
    assert 'name="format" value="flac"' in root
    assert 'name="format" value="wav"' in root
    assert "format:jobFormat" in root
    assert 'el("quality-section").hidden = fmt!=="MP3"' in root
    assert '"↓ DOWNLOAD YOUR "+fmt' in root
