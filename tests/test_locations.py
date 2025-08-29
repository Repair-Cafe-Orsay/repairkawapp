import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import Location, Session, User


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test",
            "URL_SERIALIZER_SECRET": "secret",
        }
    )
    with app.app_context():
        db.create_all()
        u1 = User(
            email="user@example.org",
            name="User",
            password=generate_password_hash("pwd"),
        )
        db.session.add(u1)
        db.session.commit()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client):
    return client.post("/login", data={"email": "user@example.org", "password": "pwd"})


def test_open_session_without_location_forbidden(client, app):
    login(client)
    resp = client.post("/api/session/open", json={"location": ""})
    assert resp.status_code == 400


def test_open_session_with_new_location(client, app):
    login(client)
    resp = client.post("/api/session/open", json={"location": "Maison des Assos"})
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.query(Location).filter_by(name="Maison des Assos").count() == 1
        # réouverture le même jour doit réutiliser la session
        resp2 = client.post("/api/session/open", json={"location": "Maison des Assos"})
        assert resp2.status_code == 200
        assert db.session.query(Session).count() == 1


def test_locations_endpoint(client, app):
    login(client)
    client.post("/api/session/open", json={"location": "Gymnase"})
    resp = client.get("/api/locations?q=Gy")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "Gymnase" in data
