#!/usr/bin/env python
"""Start Flask with a throwaway SQLite database seeded with demo + CyberHero
content, for Playwright smoke tests and screenshots.

    python scripts/e2e_server.py            # http://127.0.0.1:5055
    E2E_PORT=5056 python scripts/e2e_server.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_ENV", "development")

tmp = tempfile.mkdtemp(prefix="elearning-e2e-")
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/e2e.sqlite3"
os.environ["UPLOAD_PATH"] = f"{tmp}/uploads"
os.environ["SESSION_TYPE"] = "cachelib"
os.environ["CACHE_TYPE"] = "SimpleCache"
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"
os.environ["MAIL_SUPPRESS_SEND"] = "true"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ.setdefault("CYBERHERO_IO_CHAT_ENABLED", "false")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.services import feature_flags, seed_service, settings_service  # noqa: E402
from app.services.rbac import seed_roles_and_permissions  # noqa: E402
from app.services.user_service import create_user  # noqa: E402

app = create_app("development", overrides={"DEBUG": False, "RATELIMIT_ENABLED": False})
with app.app_context():
    db.create_all()
    seed_roles_and_permissions()
    settings_service.seed_defaults()
    feature_flags.seed_defaults()
    seed_service.seed_demo_content()
    seed_service.seed_cyberhero_content()
    create_user(
        email="admin@example.org",
        password="Admin-Passw0rd-E2E",  # noqa: S106
        first_name="Ana",
        last_name="Admin",
        roles=["admin", "instructor", "student"],
    )
    create_user(
        email="student@example.org",
        password="Student-Passw0rd-E2E",  # noqa: S106
        first_name="ნინო",
        last_name="ბერიძე",
        roles=["student"],
    )
    print(f"[e2e] database ready in {tmp}", flush=True)

port = int(os.environ.get("E2E_PORT", "5055"))
app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
