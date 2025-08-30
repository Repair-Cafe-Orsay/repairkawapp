import tempfile

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import Session, User


@pytest.fixture
def app():
    upload_dir = tempfile.mkdtemp(prefix="uploads_")
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:/",
            "SECRET_KEY": "test",
            "URL_SERIALIZER_SECRET": "secret",
            "UPLOAD_FOLDER": upload_dir,
        }
    )
    with app.app_context():
        db.create_all()
        admin = User(email="admin@example.org", name="Admin", admin=True)
        admin.password = generate_password_hash("password")
        user = User(email="user@example.org", name="User", admin=False)
        user.password = generate_password_hash("password")
        db.session.add_all([admin, user])
        db.session.commit()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login_admin(client):
    resp = client.post("/login", data={"email": "admin@example.org", "password": "password"})
    assert resp.status_code == 302
    return client


@pytest.fixture
def login_user(client):
    resp = client.post("/login", data={"email": "user@example.org", "password": "password"})
    assert resp.status_code == 302
    return client


def test_past_session_forbidden_for_non_admin(login_user):
    r = login_user.post(
        "/api/session/past", json={"date": "2024-01-01", "location": "Test", "time": "10:00"}
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "forbidden"


def test_past_session_missing_fields(login_admin):
    r = login_admin.post("/api/session/past", json={"date": "2024-01-01"})
    assert r.status_code == 400
    assert r.get_json()["error"] == "missing_fields"


def test_past_session_invalid_datetime(login_admin):
    r = login_admin.post("/api/session/past", json={"date": "bad", "location": "Lieu"})
    assert r.status_code == 400
    assert r.get_json()["error"] in {"invalid_datetime", "invalid_date"}


def test_past_session_success(login_admin, app):
    r = login_admin.post(
        "/api/session/past", json={"date": "2024-01-02", "location": "Entrepot", "time": "14:30"}
    )
    assert r.status_code == 200
    js = r.get_json()
    assert "id" in js
    with app.app_context():
        s = db.session.get(Session, js["id"])
        assert s is not None
        assert s.location.name == "Entrepot"


def test_past_session_block_when_open_exists(login_admin, app):
    # créer d'abord une session 'ouverte' actuelle via endpoint open
    r_open = login_admin.post(
        "/api/session/open", json={"location": "Local", "opened_time": "09:00"}
    )
    assert r_open.status_code == 200
    # tentative création séance passée -> erreur open_session_exists
    r = login_admin.post(
        "/api/session/past", json={"date": "2024-01-03", "location": "Autre", "time": "09:00"}
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "open_session_exists"
