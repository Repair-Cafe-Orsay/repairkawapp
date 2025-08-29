import pytest

from repairkawapp import create_app, db
from repairkawapp.models import Session, User


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test",
            "URL_SERIALIZER_SECRET": "ser",
        }
    )
    with app.app_context():
        db.create_all()
        # Users
        u1 = User(email="u1@example.org", name="User1", password="x")
        u2 = User(email="u2@example.org", name="User2", password="x")
        db.session.add_all([u1, u2])
        db.session.commit()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login_user1(client):
    # Simplification login tests : on utilise login classique (hash correct) puis cookie session.
    from werkzeug.security import generate_password_hash

    from repairkawapp import db as _db
    from repairkawapp.models import User

    with client.application.app_context():
        u = User.query.filter_by(email="u1@example.org").first()
        u.password = generate_password_hash("pwd")
        _db.session.commit()
    client.post("/login", data={"email": "u1@example.org", "password": "pwd"})
    return


def test_open_reuse_close_reopen_owner(app, client, login_user1):
    # Ouvre une session (owner = user1)
    r = client.post("/api/session/open", json={"location": "Salle A"})
    assert r.status_code == 200
    sid = r.get_json()["id"]
    # Réouverture (réutilisation) même jour même lieu -> doit renvoyer même id
    r2 = client.post("/api/session/open", json={"location": "Salle A"})
    assert r2.status_code == 200
    assert r2.get_json()["id"] == sid
    # Ajoute user2 comme participant (sinon transfert owner refusé) via join direct DB
    with app.app_context():
        u2 = User.query.filter_by(email="u2@example.org").first()
        s = Session.query.get(sid)
        s.participants.append(u2)
        from repairkawapp import db as _db

        _db.session.commit()
        u2_id = u2.id
    # Transfert propriétaire
    r_owner = client.post(f"/api/session/owner/{sid}", json={"owner_id": u2_id})
    assert r_owner.status_code == 200
    # Login comme user2 pour fermer (il est owner maintenant)
    # On refait un login avec user2
    from werkzeug.security import generate_password_hash

    with client.application.app_context():
        u2 = User.query.get(u2_id)
        u2.password = generate_password_hash("pwd2")
        from repairkawapp import db as _db

        _db.session.commit()
    client.post("/login", data={"email": "u2@example.org", "password": "pwd2"})
    # Fermeture sans heure explicite (now)
    r_close = client.post(f"/api/session/close/{sid}", json={"comment": "Fin ok"})
    assert r_close.status_code == 200
    # Reopen (toujours owner user2)
    r_reopen = client.post(f"/api/session/reopen/{sid}")
    assert r_reopen.status_code == 200
    # Close again with explicit time (simulate plus tard: utiliser heure courante HH:MM)
    import datetime as _dt

    hhmm = _dt.datetime.now().strftime("%H:%M")
    r_close2 = client.post(
        f"/api/session/close/{sid}", json={"comment": "Refin", "closed_time": hhmm}
    )
    assert r_close2.status_code == 200
    # Vérifications finales DB
    with app.app_context():
        s = Session.query.get(sid)
        assert s.owner_id == u2_id
        assert s.closed_at is not None


def test_close_forbidden_when_not_owner(app, client, login_user1):
    # user1 ouvre la session
    r = client.post("/api/session/open", json={"location": "Salle B"})
    sid = r.get_json()["id"]
    # Prépare user2 avec password + login pour tenter fermeture non autorisée
    from werkzeug.security import generate_password_hash

    with client.application.app_context():
        u2 = User.query.filter_by(email="u2@example.org").first()
        u2.password = generate_password_hash("pwd2")
        from repairkawapp import db as _db

        _db.session.commit()
    client.post("/login", data={"email": "u2@example.org", "password": "pwd2"})
    # user2 n'est ni owner ni admin -> 403
    r_close = client.post(f"/api/session/close/{sid}", json={"comment": "abcd"})
    assert r_close.status_code == 403


def test_close_comment_validation(app, client, login_user1):
    # user1 ouvre la session
    r = client.post("/api/session/open", json={"location": "Salle C"})
    sid = r.get_json()["id"]
    # Commentaire trop court
    r_close = client.post(f"/api/session/close/{sid}", json={"comment": "abc"})
    assert r_close.status_code == 400
    assert r_close.get_json()["error"] == "comment_too_short"
    # Commentaire suffisant
    r_close2 = client.post(f"/api/session/close/{sid}", json={"comment": "abcd"})
    assert r_close2.status_code == 200
