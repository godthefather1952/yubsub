"""Regression checks for the GitHub Pages / Render deployment split."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pages_custom_domain_and_api_origin():
    assert (ROOT / "CNAME").read_text().strip() == "yubsub.godthefather1952.com"
    config = (ROOT / "static" / "config.js").read_text()
    assert 'window.YUBSUB_API_BASE_URL = "https://yubsub.onrender.com"' in config
    frontend = (ROOT / "index.html").read_text()
    assert '<script src="static/config.js"></script>' in frontend
    assert "apiUrl(" in frontend


def test_pages_workflow_uses_existing_render_backend():
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    assert "https://yubsub.onrender.com" in workflow
    assert "actions/deploy-pages" in workflow
    assert "API_BASE_URL" in workflow
