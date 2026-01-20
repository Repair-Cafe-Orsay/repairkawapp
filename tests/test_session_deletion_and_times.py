from datetime import datetime

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import (
    Brand,
    Category,
    Repair,
    Session as SessionModel,
    State,
    User,
)


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
        # données minimales
        u1 = User(email="u1@example.org", name="U1", password=generate_password_hash("pwd"))
        u2 = User(email="u2@example.org", name="U2", password=generate_password_hash("pwd"))
        db.session.add_all([u1, u2])
        # catalogue minimal pour créer une réparation
        cat = Category(name="Electroménager")
        br = Brand(name="BrandX")
        st = State(label="Neuf")
        st2 = State(label="Diagnostiqué")
        db.session.add_all([cat, br, st, st2])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email):
    return client.post("/login", data={"email": email, "password": "pwd"})


def test_close_requires_comment(client, app):
    login(client, "u1@example.org")
    r = client.post("/api/session/open", json={"location": "Salle Test"})
    assert r.status_code == 200
    sid = r.get_json()["id"]
    # tentative sans commentaire
    resp = client.post(f"/api/session/close/{sid}", json={"comment": "a"})
    assert resp.status_code == 400
    # valide
    resp = client.post(f"/api/session/close/{sid}", json={"comment": "fin ok"})
    assert resp.status_code == 200


def test_manual_times(client, app, monkeypatch):
    login(client, "u1@example.org")
    r = client.post("/api/session/open", json={"location": "Salle Horloge", "opened_time": "09:15"})
    assert r.status_code == 200
    sid = r.get_json()["id"]
    # fermeture avec heure spécifique
    resp = client.post(
        f"/api/session/close/{sid}",
        json={"comment": "fermeture test", "closed_time": "11:45"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["closed_at"].endswith("Z")


def test_delete_empty_session(client, app):
    login(client, "u1@example.org")
    r = client.post("/api/session/open", json={"location": "Salle Supp"})
    sid = r.get_json()["id"]
    # suppression OK car vide
    resp = client.delete(f"/api/session/delete/{sid}")
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.query(SessionModel).count() == 0


def test_delete_non_empty_session_forbidden(client, app):
    login(client, "u1@example.org")
    r = client.post("/api/session/open", json={"location": "Salle Occupée"})
    sid = r.get_json()["id"]
    # créer une réparation attachée
    with app.app_context():
        db.session.query(User).filter_by(email="u1@example.org").first()
        cat = db.session.query(Category).first()
        br = db.session.query(Brand).first()
        st = db.session.query(State).first()
        st2 = db.session.query(State).filter(State.id != st.id).first()
        rep = Repair(
            created=datetime.utcnow().date(),
            display_id="20250101-001",
            category=cat,
            brand=br,
            initial_state=st,
            current_state=st2,
            otype="Obj",
            model="M1",
        )
        rep.session_id = sid
        db.session.add(rep)
        db.session.commit()
    # tentative suppression -> 400
    resp = client.delete(f"/api/session/delete/{sid}")
    assert resp.status_code == 400
