"""CyberHero content seeding, API contract, progress sync, certificates and shell."""

from __future__ import annotations

import json

import pytest

from app.extensions import db
from app.models import CyberCertificate, CyberMission, CyberProgress, FeatureFlag
from app.services import cyberhero_service as ch
from app.services import feature_flags
from tests.conftest import login, post_json


@pytest.fixture
def seeded(app):  # type: ignore[no-untyped-def]
    ch.seed_all()
    return app


def test_seed_is_idempotent(seeded):  # type: ignore[no-untyped-def]
    first = db.session.query(CyberMission).count()
    ch.seed_all()
    assert db.session.query(CyberMission).count() == first == 10


def test_bootstrap_contract(client, seeded):  # type: ignore[no-untyped-def]
    data = client.get("/api/v1/cyberhero/bootstrap?locale=en").get_json()
    assert data["locale"] == "en"
    assert data["flags"] == {"CYBERHERO_IO_CHAT_ENABLED": False}
    assert data["user"] is None
    assert data["settings"]["emergency_phone"] == "112"
    assert data["settings"]["cybercrime_contact"] == ""
    ids = [t["id"] for t in data["tiers"]]
    assert "guardians" in ids and "parents" in ids
    guardians = next(t for t in data["tiers"] if t["id"] == "guardians")
    assert guardians["active"] is True and guardians["name"]["ka"]
    assert len(data["mascot"]["tips"]) > 10
    assert "mission" in data["mascot"]["reactions"]


def test_mission_list_and_detail_shapes(client, seeded):  # type: ignore[no-untyped-def]
    items = client.get("/api/v1/cyberhero/missions").get_json()["items"]
    assert [m["id"] for m in items] == [f"g{i}" for i in range(1, 11)]
    assert items[9]["final"] is True and items[3]["sensitive"] is True
    for item in items:
        assert "brief" not in item and item["color"] in {
            "blue",
            "cyan",
            "green",
            "pink",
            "amber",
            "violet",
            "orange",
            "accent",
        }
    g4 = client.get("/api/v1/cyberhero/missions/g4").get_json()
    assert g4["brief"]["ka"] and g4["helpStrip"]["en"]
    assert len(g4["theory"]) >= 3 and len(g4["takeaways"]) >= 3
    branch = g4["rounds"][0]
    assert branch["type"] == "branch" and branch["start"] in branch["nodes"]
    node = branch["nodes"][branch["start"]]
    assert node["chat"][0]["text"]["ka"] and node["choices"][0]["next"] in branch["nodes"]
    g1 = client.get("/api/v1/cyberhero/missions/g1").get_json()
    assert g1["rounds"][0]["type"] == "choice" and g1["rounds"][0]["card"]["body"]["en"]
    assert sum(1 for o in g1["rounds"][0]["options"] if o["correct"]) == 1
    flags = g1["rounds"][-1]
    assert flags["type"] == "flags" and any(i["flag"] for i in flags["items"])
    g3 = client.get("/api/v1/cyberhero/missions/g3").get_json()
    builder = next(r for r in g3["rounds"] if r["type"] == "builder")
    assert builder["target"] > 0 and builder["meterLow"]["ka"]
    assert client.get("/api/v1/cyberhero/missions/nope").status_code == 404


def test_articles_and_agreement(client, seeded):  # type: ignore[no-untyped-def]
    items = client.get("/api/v1/cyberhero/articles").get_json()["items"]
    assert len(items) == 16 and items[0]["id"] == "a1"
    shelf_b = client.get("/api/v1/cyberhero/articles?shelf=b").get_json()["items"]
    assert {a["shelf"] for a in shelf_b} == {"B"} and len(shelf_b) == 5
    a3 = client.get("/api/v1/cyberhero/articles/a3").get_json()
    assert a3["priority"] is True
    types = {b["type"] for b in a3["body"]}
    assert {"h2", "p"} <= types
    callout = next(b for b in a3["body"] if b["type"] == "callout")
    assert callout["variant"] and callout["title"]["ka"]
    assert a3["sources"]
    agreement = client.get("/api/v1/cyberhero/agreement").get_json()
    assert agreement["title"]["ka"] and len(agreement["sections"]) == 4
    assert agreement["sections"][-1]["writeLines"] == 3
    assert agreement["signatures"]["child"]["en"].startswith("Signature")


def test_resources_and_courses(client, seeded):  # type: ignore[no-untyped-def]
    playbook = client.get("/api/v1/cyberhero/resources/playbook").get_json()
    assert len(playbook["items"]) == 6
    assert all(len(r["steps"]["ka"]) >= 5 for r in playbook["items"])
    contacts = client.get("/api/v1/cyberhero/resources/emergency_contact").get_json()["items"]
    assert contacts[0]["contact_value"] == "112"
    assert client.get("/api/v1/cyberhero/resources/other").status_code == 404
    courses = client.get("/api/v1/cyberhero/courses").get_json()["items"]
    assert courses[0]["slug"] == "cyber-guardians" and courses[0]["lesson_count"] == 9
    course = client.get("/api/v1/cyberhero/courses/cyber-guardians").get_json()
    assert len(course["modules"]) == 3 and len(course["missions"]) == 10
    first = course["modules"][0]["lessons"][0]["slug"]
    lesson = client.get(f"/api/v1/cyberhero/courses/cyber-guardians/lessons/{first}").get_json()
    assert lesson["index"] == 1 and lesson["total"] == 9 and lesson["next"]
    assert "<p>" in lesson["content"]["ka"] and "<script" not in lesson["content"]["ka"]
    # eLearning catalogue must NOT list CyberHero courses
    catalog = client.get("/api/v1/courses").get_json()
    assert all(c["slug"] != "cyber-guardians" for c in catalog["items"])


def test_knowledge_gated_by_flag(client, seeded):  # type: ignore[no-untyped-def]
    assert client.get("/api/v1/cyberhero/knowledge").status_code == 404
    feature_flags.set_flag("CYBERHERO_IO_CHAT_ENABLED", True)
    db.session.commit()
    data = client.get("/api/v1/cyberhero/knowledge").get_json()
    assert len(data["sections"]) == 11 and data["sections"][0]["chunks"]


def test_progress_requires_login_and_merges(client, seeded, student):  # type: ignore[no-untyped-def]
    assert client.get("/api/v1/cyberhero/progress").status_code == 401
    login(client, student)
    empty = client.get("/api/v1/cyberhero/progress").get_json()
    assert empty == {"guardians": {"missions": {}}, "lessons": {}}
    payload = {
        "guardians": {"missions": {"g1": {"done": True, "best": 40, "total": 70}}},
        "lessons": {"cyber-guardians/g1-phishing-hunter": {"done": True}},
    }
    merged = post_json(client, "/api/v1/cyberhero/progress", payload, method="put").get_json()
    assert merged["guardians"]["missions"]["g1"] == {"done": True, "best": 40, "total": 70}
    assert merged["lessons"]["cyber-guardians/g1-phishing-hunter"]["done"] is True
    # lower score never regresses, done never reverts
    merged = post_json(
        client,
        "/api/v1/cyberhero/progress",
        {"guardians": {"missions": {"g1": {"done": False, "best": 10, "total": 70}}}},
        method="put",
    ).get_json()
    assert (
        merged["guardians"]["missions"]["g1"]["best"] == 40
        and merged["guardians"]["missions"]["g1"]["done"]
    )
    assert db.session.query(CyberProgress).count() == 1
    # CSRF header is mandatory
    response = client.put("/api/v1/cyberhero/progress", json=payload)
    assert response.status_code == 400


def test_certificate_flow_anonymous(client, seeded):  # type: ignore[no-untyped-def]
    completed = {f"g{i}": {"done": True, "best": 10, "total": 20} for i in range(1, 11)}
    response = post_json(
        client,
        "/api/v1/cyberhero/certificates",
        {"track": "guardians", "display_name": "ნინო ბერიძე", "completed_missions": completed},
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    assert data["public_id"].startswith("CH-") and data["track_name"]["ka"]
    cert = db.session.query(CyberCertificate).one()
    assert cert.user_id is None and cert.display_name == "ნინო ბერიძე"
    verify = client.get(f"/api/v1/cyberhero/certificates/{data['public_id']}").get_json()
    assert verify["valid"] is True
    page = client.get(f"/certificates/verify/{data['public_id']}")
    assert page.status_code == 200 and "ნინო ბერიძე".encode() in page.data
    assert client.get("/api/v1/cyberhero/certificates/CH-0000-NOPE").status_code == 404


def test_certificate_requires_all_missions(client, seeded):  # type: ignore[no-untyped-def]
    response = post_json(
        client,
        "/api/v1/cyberhero/certificates",
        {"track": "guardians", "display_name": "Nino", "completed_missions": ["g1"]},
    )
    assert response.status_code == 400
    response = post_json(
        client,
        "/api/v1/cyberhero/certificates",
        {"track": "guardians", "display_name": "N", "completed_missions": []},
    )
    assert response.status_code == 400


def test_shell_passes_config_via_data_attributes(client, seeded, tmp_path, app):  # type: ignore[no-untyped-def]
    static_dir = tmp_path / "cyberhero"
    (static_dir / ".vite").mkdir(parents=True)
    (static_dir / "assets").mkdir()
    manifest = {
        "src/main.jsx": {
            "file": "assets/main-abc123.js",
            "css": ["assets/main-abc123.css"],
            "isEntry": True,
        }
    }
    (static_dir / ".vite" / "manifest.json").write_text(json.dumps(manifest))
    app.config["CYBERHERO_STATIC_DIR"] = str(static_dir)
    response = client.get("/cyberhero/guardians/mission/g1?lang=en")
    html = response.data.decode()
    assert response.status_code == 200
    assert 'id="cyberhero-root"' in html and 'data-basename="/cyberhero"' in html
    assert 'data-locale="en"' in html and '<html lang="en"' in html
    assert "data-flags='{&#34;CYBERHERO_IO_CHAT_ENABLED&#34;:false}'" in html  # entity-escaped JSON
    assert "/static/cyberhero/assets/main-abc123.js" in html and "main-abc123.css" in html
    assert "onclick" not in html and "<script>" not in html
    assert 'data-lang-switch-ka="/cyberhero/guardians/mission/g1?lang=ka"' in html
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]


def test_shell_reports_missing_bundle(client, seeded, tmp_path, app):  # type: ignore[no-untyped-def]
    app.config["CYBERHERO_STATIC_DIR"] = str(tmp_path / "missing")
    response = client.get("/cyberhero/")
    assert response.status_code == 200 and b"npm run build" in response.data


def test_cyberhero_disabled_flag_hides_everything(client, seeded):  # type: ignore[no-untyped-def]
    flag = db.session.query(FeatureFlag).filter_by(key="CYBERHERO_ENABLED").one()
    flag.enabled = False
    db.session.commit()
    assert client.get("/cyberhero/").status_code == 404
    assert client.get("/api/v1/cyberhero/missions").status_code == 404
