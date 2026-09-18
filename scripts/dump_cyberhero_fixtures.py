#!/usr/bin/env python
"""Dump CyberHero API responses (from the seed files) as JSON fixtures for the
Vite mock server and the front-end unit tests.

    python scripts/dump_cyberhero_fixtures.py            # -> cyberhero/mock/fixtures/

Each fixture is named after the request path with "/" replaced by "__", e.g.
``missions__g1.json`` for ``/api/v1/cyberhero/missions/g1``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_ENV", "testing")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.services import (  # noqa: E402
    achievement_service,
    feature_flags,
    seed_service,
    settings_service,
)
from app.services.rbac import seed_roles_and_permissions  # noqa: E402

OUT = ROOT / "cyberhero" / "mock" / "fixtures"


def main() -> None:
    app = create_app("testing", overrides={"CYBERHERO_IO_CHAT_ENABLED": True})
    OUT.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db.create_all()
        seed_roles_and_permissions()
        settings_service.seed_defaults()
        feature_flags.seed_defaults()
        achievement_service.seed_defaults()
        seed_service.seed_demo_content()
        seed_service.seed_cyberhero_content()
        client = app.test_client()
        paths = [
            "bootstrap",
            "tracks",
            "missions",
            "articles",
            "agreement",
            "mascot",
            "knowledge",
            "courses",
        ]
        paths += [f"resources/{kind}" for kind in ("emergency_contact", "playbook", "guide")]
        tracks = client.get("/api/v1/cyberhero/tracks").get_json()["items"]
        paths += [f"tracks/{t['id']}" for t in tracks]
        missions = client.get("/api/v1/cyberhero/missions").get_json()["items"]
        paths += [f"missions/{m['id']}" for m in missions]
        articles = client.get("/api/v1/cyberhero/articles").get_json()["items"]
        paths += [f"articles/{a['id']}" for a in articles]
        courses = client.get("/api/v1/cyberhero/courses").get_json()["items"]
        for course in courses:
            paths.append(f"courses/{course['slug']}")
            detail = client.get(f"/api/v1/cyberhero/courses/{course['slug']}").get_json()
            for module in detail["modules"]:
                for lesson in module["lessons"]:
                    paths.append(f"courses/{course['slug']}/lessons/{lesson['slug']}")
        for path in paths:
            # the tutor flag is off by default; only the knowledge dump needs it on
            feature_flags.set_flag("CYBERHERO_IO_CHAT_ENABLED", path == "knowledge")
            feature_flags.invalidate()
            response = client.get(f"/api/v1/cyberhero/{path}")
            assert response.status_code == 200, (path, response.status_code)
            target = OUT / (path.replace("/", "__") + ".json")
            target.write_text(
                json.dumps(response.get_json(), ensure_ascii=False, indent=1, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        print(f"wrote {len(paths)} fixtures to {OUT}")


if __name__ == "__main__":
    main()
