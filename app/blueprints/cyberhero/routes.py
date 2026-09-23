"""Serves the CyberHero single-page app shell for every /cyberhero/ route.

Runtime configuration reaches the React app only through ``data-*``
attributes on ``#cyberhero-root`` (no inline scripts, CSP-safe)."""

from __future__ import annotations

import json
from pathlib import Path

from flask import abort, current_app, make_response, render_template, url_for
from flask_babel import get_locale
from flask_login import current_user

from app.blueprints.cyberhero import bp
from app.security import build_csp
from app.services import feature_flags, settings_service

_manifest_cache: dict[str, tuple[float, dict]] = {}

# the two Vite entries of the bundle (cyberhero/vite.config.js)
ENTRY_APP = "src/main.jsx"  # the CyberHero app, served by this shell
ENTRY_IO_HOST = "src/io-host.jsx"  # IO as the welcome host on the eLearning home page


def read_manifest() -> dict | None:
    """Vite manifest (cached by mtime). ``None`` when the bundle is not built."""
    static_dir = Path(current_app.config["CYBERHERO_STATIC_DIR"])
    path = static_dir / ".vite" / "manifest.json"
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    cached = _manifest_cache.get(str(path))
    if cached and cached[0] == mtime:
        return cached[1]
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    _manifest_cache[str(path)] = (mtime, data)
    return data


def bundle_assets(entry_name: str = ENTRY_APP) -> dict[str, list[str]]:
    """Hashed JS/CSS/preload URLs of one Vite entry (empty when not built)."""
    manifest = read_manifest()
    if not manifest:
        return {"js": [], "css": [], "preload": []}
    entry = manifest.get(entry_name)
    if not entry and entry_name == ENTRY_APP:
        entry = next((v for v in manifest.values() if v.get("isEntry")), None)
    if not entry:
        return {"js": [], "css": [], "preload": []}
    base = "cyberhero/"
    css = [url_for("static", filename=base + f) for f in entry.get("css", [])]
    preload = []
    for key in entry.get("imports", []):
        chunk = manifest.get(key) or {}
        if chunk.get("file"):
            preload.append(url_for("static", filename=base + chunk["file"]))
        css += [url_for("static", filename=base + f) for f in chunk.get("css", [])]
    return {
        "js": [url_for("static", filename=base + entry["file"])],
        "css": css,
        "preload": preload,
    }


@bp.route("/", defaults={"path": ""})
@bp.route("/<path:path>")
def shell(path: str):  # type: ignore[no-untyped-def]
    if not feature_flags.is_enabled("CYBERHERO_ENABLED"):
        abort(404)
    if path.startswith(("assets/", ".vite/")):
        abort(404)
    locale = str(get_locale() or "ka")
    assets = bundle_assets()
    flags = {"CYBERHERO_IO_CHAT_ENABLED": feature_flags.is_enabled("CYBERHERO_IO_CHAT_ENABLED")}
    cybercrime = ""
    if settings_service.get("cyberhero.cybercrime_contact_verified", False):
        cybercrime = str(settings_service.get("cyberhero.cybercrime_contact", "") or "")
    current_path = url_for("cyberhero.shell", path=path)
    response = make_response(
        render_template(
            "cyberhero/shell.html",
            assets=assets,
            bundle_missing=not assets["js"],
            locale=locale,
            flags_json=json.dumps(flags, separators=(",", ":")),
            user_name=current_user.name if current_user.is_authenticated else "",
            user_id=current_user.id if current_user.is_authenticated else "",
            emergency_phone=str(settings_service.get("cyberhero.emergency_phone", "112")),
            cybercrime_contact=cybercrime,
            help_line=str(settings_service.get("cyberhero.help_line", "") or ""),
            tutor_model_url=str(current_app.config.get("CYBERHERO_TUTOR_MODEL_URL", "") or ""),
            lang_switch_ka=f"{current_path}?lang=ka",
            lang_switch_en=f"{current_path}?lang=en",
            login_url=url_for("auth.login", next=current_path),
        )
    )
    if flags["CYBERHERO_IO_CHAT_ENABLED"] and current_app.config.get("CYBERHERO_TUTOR_MODEL_URL"):
        # WebLLM compiles the model runtime with WebAssembly; the platform
        # stays inline-script-free, so only the wasm exception is added here.
        response.headers["Content-Security-Policy"] = build_csp(
            {"script-src": "'self' 'wasm-unsafe-eval'"}
        )
    return response
