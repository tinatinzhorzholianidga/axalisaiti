"""The Flask shell that serves the CyberHero single-page app."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services import feature_flags, settings_service
from tests.conftest import login

ATTR = re.compile(r"data-([a-z-]+)=([\"'])(.*?)\2")


def _attrs(html: str) -> dict[str, str]:
    root = html.split('id="cyberhero-root"', 1)[1].split(">", 1)[0]
    return {name: value for name, _quote, value in ATTR.findall(root)}


@pytest.fixture
def built(app, tmp_path):  # type: ignore[no-untyped-def]
    """Point the shell at a fake Vite manifest."""
    static = Path(tmp_path) / "cyberhero"
    (static / ".vite").mkdir(parents=True)
    (static / "assets").mkdir()
    manifest = {
        "src/main.jsx": {
            "file": "assets/main-abc.js",
            "css": ["assets/main-abc.css"],
            "imports": ["_three-vendor-xyz.js"],
            "isEntry": True,
        },
        "_three-vendor-xyz.js": {"file": "assets/three-vendor-xyz.js"},
    }
    (static / ".vite" / "manifest.json").write_text(json.dumps(manifest))
    app.config["CYBERHERO_STATIC_DIR"] = str(static)
    return static


def test_shell_serves_every_route_with_runtime_attributes(client, built):  # type: ignore[no-untyped-def]
    for path in ("/cyberhero/", "/cyberhero/guardians", "/cyberhero/guardians/mission/g1"):
        response = client.get(path)
        assert response.status_code == 200, path
    html = client.get("/cyberhero/parents?lang=en").get_data(as_text=True)
    assert 'lang="en"' in html
    attrs = _attrs(html)
    assert attrs["basename"] == "/cyberhero"
    assert attrs["locale"] == "en"
    assert attrs["api-base"] == "/api/v1/cyberhero"
    assert attrs["emergency-phone"] == "112"
    assert json.loads(attrs["flags"].replace("&#34;", '"')) == {"CYBERHERO_IO_CHAT_ENABLED": False}
    assert attrs["user-id"] == ""
    assert attrs["lang-switch-ka"].endswith("?lang=ka")
    # hashed bundle files must NOT get the ?v= stamp (chunks import each other by bare path)
    assert 'src="/static/cyberhero/assets/main-abc.js"' in html
    assert 'href="/static/cyberhero/assets/main-abc.css"' in html
    assert 'rel="modulepreload" href="/static/cyberhero/assets/three-vendor-xyz.js"' in html
    # ...while ordinary static files do
    assert 'href="/static/css/cyberhero-host.css?v=' in html
    # strict CSP: no inline scripts / styles on the shell
    assert "<script>" not in html and "onclick=" not in html and "style=" not in html
    csp = client.get("/cyberhero/").headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe" not in csp


def test_shell_passes_user_and_verified_contacts(client, built, student):  # type: ignore[no-untyped-def]
    settings_service.set_value("cyberhero.cybercrime_contact", "+995 32 241 19 19")
    settings_service.set_value("cyberhero.help_line", "116 111")
    login(client, student)
    attrs = _attrs(client.get("/cyberhero/").get_data(as_text=True))
    assert attrs["user-id"] == str(student.id)
    assert attrs["user-name"].startswith("Nino")
    assert attrs["help-line"] == "116 111"
    # the cybercrime contact stays hidden until an admin marks it verified
    assert attrs["cybercrime-contact"] == ""
    settings_service.set_value("cyberhero.cybercrime_contact_verified", True)
    attrs = _attrs(client.get("/cyberhero/").get_data(as_text=True))
    assert attrs["cybercrime-contact"] == "+995 32 241 19 19"


def test_unbuilt_bundle_shows_a_helpful_message(client):  # type: ignore[no-untyped-def]
    client.application.config["CYBERHERO_STATIC_DIR"] = "/nonexistent/path"
    response = client.get("/cyberhero/")
    assert response.status_code == 200
    assert b"npm run build" in response.data


def test_asset_paths_and_disabled_flag_return_404(client, built):  # type: ignore[no-untyped-def]
    assert client.get("/cyberhero/assets/main.js").status_code == 404
    assert client.get("/cyberhero/.vite/manifest.json").status_code == 404
    feature_flags.set_flag("CYBERHERO_ENABLED", False)
    feature_flags.invalidate()
    assert client.get("/cyberhero/").status_code == 404
    assert client.get("/api/v1/cyberhero/tracks").status_code == 404


def test_tutor_csp_exception_is_scoped(client, built):  # type: ignore[no-untyped-def]
    feature_flags.set_flag("CYBERHERO_IO_CHAT_ENABLED", True)
    feature_flags.invalidate()
    # flag on but no model configured: CSP unchanged (lookup mode needs no wasm)
    csp = client.get("/cyberhero/io-chat").headers["Content-Security-Policy"]
    assert "wasm-unsafe-eval" not in csp
    client.application.config["CYBERHERO_TUTOR_MODEL_URL"] = "/static/models/io/"
    csp = client.get("/cyberhero/io-chat").headers["Content-Security-Policy"]
    assert "script-src 'self' 'wasm-unsafe-eval'" in csp
    assert "unsafe-inline" not in csp
    # other pages keep the strict policy
    assert "wasm" not in client.get("/").headers["Content-Security-Policy"]
    attrs = _attrs(client.get("/cyberhero/").get_data(as_text=True))
    assert attrs["tutor-model-url"] == "/static/models/io/"
