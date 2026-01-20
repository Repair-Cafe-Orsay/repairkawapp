import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import User


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
        u1 = User(email="u1@example.org", name="U1", password=generate_password_hash("pwd"))
        u2 = User(email="u2@example.org", name="U2", password=generate_password_hash("pwd"))
        db.session.add_all([u1, u2])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email):
    return client.post("/login", data={"email": email, "password": "pwd"})


def test_open_join_close_session(client, app):
    r = login(client, "u1@example.org")
    assert r.status_code == 302
    resp = client.post("/api/session/open", json={"location": "Salle A"})
    assert resp.status_code == 200
    sid = resp.get_json()["id"]
    # second user joins
    r = login(client, "u2@example.org")
    assert r.status_code == 302
    resp = client.post(f"/api/session/join/{sid}")
    assert resp.status_code == 200
    # list sessions
    resp = client.get("/api/sessions")
    sessions = resp.get_json()
    assert len(sessions) == 1
    # close as non-owner (should fail 403 forbidden)
    resp = client.post(f"/api/session/close/{sid}", json={"comment": "fin"})
    assert resp.status_code == 403
    # back to owner
    login(client, "u1@example.org")
    resp = client.post(f"/api/session/close/{sid}", json={"comment": "fin ok"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["comment"] == "fin ok"
    # detail
    resp = client.get(f"/api/session/{sid}")
    assert resp.status_code == 200
    detail = resp.get_json()
    assert detail["nb_participants"] == 2
