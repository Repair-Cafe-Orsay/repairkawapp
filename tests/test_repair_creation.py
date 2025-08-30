import tempfile
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import Category, CloseStatus, Repair, State, User


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
        }
    )
    with app.app_context():
        db.create_all()
        # minimal reference data
        cat = Category(name="Electronique", rm_icon_id=1, icon_name="lightning")
        st = State(label="Réception")
        cs = CloseStatus(id=1, label="Ouverte")
        db.session.add_all([cat, st, cs])
        user = User(email="tech@example.org", name="Tech")
        user.password = generate_password_hash("password")
        db.session.add(user)
        db.session.commit()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    # login user created in app fixture
    client.post("/login", data={"email": "tech@example.org", "password": "password"})
    return client


def test_create_repair(login):
    # prepare form data
    form_date = date(2025, 8, 28).strftime("%Y-%m-%d")
    with login.application.app_context():
        cat_id = Category.query.first().id
        state_id = State.query.first().id
    data = {
        "brand": "Sony",
        "category": str(cat_id),
        "initial_state": str(state_id),
        "date": form_date,
        "value": "120",
        "weight": "3",
        "year": "2019",
        "age": "5",
        "manual_id": "001",
        "name": "Client Test",
        "email": "client@test.org",
        "phone": "0102030405",
        "otype": "Radio",
        "model": "RX-200",
        "sn": "SN-XYZ",
        "description": "Ne s allume plus",
        "validated": "on",
    }
    resp = login.post("/new", data=data, follow_redirects=False)
    assert resp.status_code == 302
    assert "/update/" in resp.headers["Location"]

    # follow and verify stored object
    update_resp = login.get(resp.headers["Location"])
    assert update_resp.status_code == 200

    with login.application.app_context():
        repairs = Repair.query.all()
        assert len(repairs) == 1
        r = repairs[0]
        # Normalisation désormais en majuscules (voir normalize_brand)
        assert r.brand.name == "SONY"
        assert r.name == "Client Test"
        assert r.display_id.startswith("25")  # year prefix (25 for 2025)
        assert r.validated is True
        assert r.created.strftime("%Y-%m-%d") == form_date
