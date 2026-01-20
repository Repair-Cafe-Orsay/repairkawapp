import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db as _db
from repairkawapp.models import User


@pytest.fixture()
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        _db.create_all()
        u = User(
            name="Test User",
            email="test@example.org",
            password=generate_password_hash("oldpass"),
            seqid=1,
        )
        _db.session.add(u)
        _db.session.commit()
    yield app
    with app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login(client):
    # simulate login by setting session directly if possible else via POST if route exists
    client.post("/login", data={"email": "test@example.org", "password": "oldpass"})
    yield


def test_change_password_success(client, app, login):
    r = client.post(
        "/change_password_logged",
        json={"old_password": "oldpass", "new_password": "newpass123"},
    )
    assert r.status_code == 200
    with app.app_context():
        u = User.query.filter_by(email="test@example.org").first()
        assert u and u.password != "oldpass"


def test_change_password_bad_old(client, login):
    r = client.post(
        "/change_password_logged",
        json={"old_password": "wrong", "new_password": "newpass123"},
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "bad_old"


def test_change_password_too_short(client, login):
    r = client.post(
        "/change_password_logged",
        json={"old_password": "oldpass", "new_password": "xx"},
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "too_short"
