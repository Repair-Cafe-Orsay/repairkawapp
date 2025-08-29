import tempfile
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import (
    Brand,
    Category,
    CloseStatus,
    Repair,
    SpareStatus,
    State,
    User,
)


@pytest.fixture
def app():
    upload_dir = tempfile.mkdtemp(prefix="uploads_")
    thumb_dir = tempfile.mkdtemp(prefix="thumbs_")
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test",
            "URL_SERIALIZER_SECRET": "secret",
            "UPLOAD_FOLDER": upload_dir,
            "THUMBNAIL_MEDIA_THUMBNAIL_ROOT": thumb_dir,
            "PAGE_SIZE": 10,
        }
    )
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Category(name="Electro", rm_icon_id=1),
                Category(name="Textile", rm_icon_id=2),
            ]
        )
        st1 = State(label="Réception")
        st2 = State(label="Diagnostic")
        db.session.add_all([st1, st2])
        db.session.add_all(
            [
                CloseStatus(id=1, label="Ouverte"),
                CloseStatus(id=2, label="Réparée"),
                CloseStatus(id=3, label="Inréparable"),
            ]
        )
        db.session.add_all(
            [SpareStatus(id=0, label="Inconnu"), SpareStatus(id=1, label="Commandé")]
        )
        user = User(email="tech@example.org", name="Tech")
        user.password = generate_password_hash("password")
        db.session.add(user)
        db.session.add_all([Brand(name="Sony"), Brand(name="Sagem"), Brand(name="Philips")])
        db.session.commit()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    client.post("/login", data={"email": "tech@example.org", "password": "password"})
    return client


def _create_repair(client, display_manual="001"):
    from datetime import date

    with client.application.app_context():
        cat = Category.query.first()
        st = State.query.first()
        brand = Brand.query.filter_by(name="Sony").first()
    form_date = date.today().strftime("%Y-%m-%d")
    data = {
        "brand": brand.name,
        "category": str(cat.id),
        "initial_state": str(st.id),
        "date": form_date,
        "value": "10",
        "weight": "1",
        "year": "2024",
        "age": "1",
        "manual_id": display_manual,
        "name": "Client",
        "email": "c@example.org",
        "phone": "0102",
        "otype": "Radio",
        "model": "RX",
        "sn": "SN",
        "description": "HS",
        "validated": "on",
    }
    resp = client.post("/new", data=data)
    assert resp.status_code == 302
    return resp.headers["Location"].split("/update/")[1]


def test_brandsearch(client):
    resp = client.get("/api/brandsearch?q=Sa")
    assert resp.status_code == 200
    js = resp.get_json()
    assert "matching_results" in js
    assert any(b.startswith("Sa") for b in js["matching_results"])


def test_new_and_delete_spare(login):
    rid = _create_repair(login)
    # add spare
    resp_add = login.get(f"/new_spare/{rid}?item=Vis&status_id=1&source=Magasin&note=Remplacer")
    assert resp_add.status_code == 200
    js = resp_add.get_json()
    assert "sparepart" in js and "log" in js
    # retrieve spare id from rendered snippet (simple parse)
    import re

    match = re.search(r"id=\"spare-card-(\d+)\"", js["sparepart"])
    spare_id = match.group(1) if match else None
    assert spare_id is not None
    # delete spare
    resp_del = login.get(f"/del_spare/{rid}?id={spare_id}")
    assert resp_del.status_code == 200
    assert resp_del.get_json() is True


def test_repairsearch_basic(login):
    rid = _create_repair(login)
    resp = login.get("/api/repairsearch?length=10&status=all")
    assert resp.status_code == 200
    js = resp.get_json()
    assert "repairs" in js
    assert any(r["id"] == rid for r in js["repairs"])


def test_stats(login):
    # créer deux réparations dans deux catégories/statuts
    _create_repair(login, display_manual="010")
    rid2 = _create_repair(login, display_manual="011")
    # fermer la seconde
    with login.application.app_context():
        rep2 = Repair.query.filter_by(display_id=rid2).first()
        rep2.close_status_id = 2
        db.session.commit()
    today = date.today().strftime("%Y-%m-%d")
    resp = login.get(f"/api/stats?from={today}&to={today}")
    assert resp.status_code == 200
    js = resp.get_json()
    assert "count_by_status" in js
    # total = 2 repairs
    assert js["total"] >= 2
