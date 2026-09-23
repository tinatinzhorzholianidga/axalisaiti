"""IO, the welcome host, on the eLearning home page (templates/main/home.html)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services import feature_flags

ATTR = re.compile(r"data-([a-z-]+)=([\"'])(.*?)\2")
DOOR = re.compile(r'<a class="btn[^"]*" href="([^"]+)" data-io-path="(basic|kids)"')


def _root_attrs(html: str) -> dict[str, str]:
    root = html.split('id="io-host-root"', 1)[1].split(">", 1)[0]
    return {name: value for name, _quote, value in ATTR.findall(root)}


def _doors(html: str) -> dict[str, str]:
    """The buttons IO reacts to ("doors"), by kind -> href."""
    return {kind: href for href, kind in DOOR.findall(html)}


@pytest.fixture
def built(app, tmp_path):  # type: ignore[no-untyped-def]
    """Point the bundle lookup at a fake Vite manifest with both entries."""
    static = Path(tmp_path) / "cyberhero"
    (static / ".vite").mkdir(parents=True)
    manifest = {
        "src/main.jsx": {
            "file": "assets/main-abc.js",
            "css": ["assets/main-abc.css"],
            "isEntry": True,
        },
        "src/io-host.jsx": {
            "file": "assets/io-host-def.js",
            "css": ["assets/io-host-def.css"],
            "imports": ["_three-vendor-xyz.js"],
            "isEntry": True,
        },
        "_three-vendor-xyz.js": {"file": "assets/three-vendor-xyz.js"},
    }
    (static / ".vite" / "manifest.json").write_text(json.dumps(manifest))
    app.config["CYBERHERO_STATIC_DIR"] = str(static)
    return static


def test_home_mounts_io_with_runtime_attributes(client, built):  # type: ignore[no-untyped-def]
    html = client.get("/?lang=en").get_data(as_text=True)
    attrs = _root_attrs(html)
    assert attrs["locale"] == "en"
    assert attrs["skin"] == "classic"
    assert attrs["doors"] == "basic,kids"
    assert attrs["label"].startswith("IO, the cybersecurity guide robot")
    assert attrs["label-close"] == "Hide IO" and attrs["label-open"] == "Show IO"
    # only the host entry (and its shared three.js chunk) is loaded, not the CyberHero app
    assert 'src="/static/cyberhero/assets/io-host-def.js"' in html
    assert 'href="/static/cyberhero/assets/io-host-def.css"' in html
    assert 'rel="modulepreload" href="/static/cyberhero/assets/three-vendor-xyz.js"' in html
    assert "assets/main-abc.js" not in html
    # his two doors are the page's own buttons: the catalogue and CyberHero
    assert _doors(html) == {"basic": "/courses/", "kids": "/cyberhero/"}
    # the hero itself is the original one
    assert "A secure" in html and "digital future" in html and 'class="hero-art"' in html
    assert _root_attrs(client.get("/?lang=ka").get_data(as_text=True))["locale"] == "ka"
    assert 'data-label-close="იოს დამალვა"' in client.get("/?lang=ka").get_data(as_text=True)


def test_kids_door_follows_the_cyberhero_flag(client, built):  # type: ignore[no-untyped-def]
    feature_flags.set_flag("CYBERHERO_ENABLED", False)
    feature_flags.invalidate()
    html = client.get("/").get_data(as_text=True)
    assert _root_attrs(html)["doors"] == "basic"
    assert _doors(html) == {"basic": "/courses/"}


def test_unbuilt_bundle_renders_the_page_without_io(client):  # type: ignore[no-untyped-def]
    client.application.config["CYBERHERO_STATIC_DIR"] = "/nonexistent/path"
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="io-host-root"' not in html and "/static/cyberhero/" not in html
    assert 'class="hero-art"' in html


def test_home_keeps_the_strict_policy(client, built):  # type: ignore[no-untyped-def]
    response = client.get("/")
    html = response.get_data(as_text=True)
    assert "<script>" not in html and "onclick=" not in html and " style=" not in html
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe" not in csp and "wasm" not in csp
