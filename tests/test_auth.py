import tempfile

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import User


@pytest.fixture
def app():
    upload_dir = tempfile.mkdtemp(prefix="uploads_")
    thumb_dir = tempfile.mkdtemp(prefix="thumbs_")
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret",
            "URL_SERIALIZER_SECRET": "serializer-secret",
            "UPLOAD_FOLDER": upload_dir,
            "THUMBNAIL_MEDIA_THUMBNAIL_ROOT": thumb_dir,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(email="user@example.org", name="Test User")
    u.password = generate_password_hash("password")
    db.session.add(u)
    db.session.commit()
    return u


def test_protected_redirect(client):
    """Accès non authentifié doit rediriger vers /login."""
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_success(client, user):
    resp = client.post(
        "/login",
        data={"email": user.email, "password": "password"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Redirection par défaut désormais vers /
    assert resp.headers["Location"].endswith("/")

    # Accès après login (en suivant la redirection)
    resp2 = client.get("/profile", follow_redirects=True)
    assert resp2.status_code == 200
    assert b"profile" in resp2.data.lower() or b"profil" in resp2.data.lower()


def test_login_fail(client, user):
    resp = client.post(
        "/login",
        data={"email": user.email, "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_flow(client, user):
    client.post("/login", data={"email": user.email, "password": "password"})
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]

    # Après logout, retour sur page protégée => redirection
    resp2 = client.get("/profile")
    assert resp2.status_code == 302
    assert "/login" in resp2.headers["Location"]


def test_login_fail_unknown_user(client):
    resp = client.post("/login", data={"email": "nobody@example.org", "password": "whatever"})
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_login_with_next_internal(client, user):
    # Accès protégé => redirection vers /login?next=%2Frepairs
    resp = client.get("/repairs")
    assert (
        resp.status_code == 302
        and "/login" in resp.headers["Location"]
        and "next=%2Frepairs" in resp.headers["Location"]
    )
    # Connexion en conservant le paramètre next interne
    resp2 = client.post(
        "/login?next=/repairs",
        data={"email": user.email, "password": "password"},
        follow_redirects=False,
    )
    assert resp2.status_code == 302
    assert resp2.headers["Location"].endswith("/repairs")


def test_login_with_next_external_blocked(client, user):
    # next externe doit être ignoré -> fallback /
    resp = client.post(
        "/login?next=https://evil.example.com/phish",
        data={"email": user.email, "password": "password"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    loc = resp.headers["Location"]
    assert loc.endswith("/") and "evil.example.com" not in loc


def test_founder_flag_edit_restricted(client, app):
    """Seul un utilisateur déjà fondateur peut attribuer (ou retirer) le flag founder.

    Scénario ici : aucun fondateur initial => personne ne peut promouvoir qui que ce soit,
    ce qui vérifie la restriction. (Bootstrap du premier fondateur hors scope de ce test.)
    """
    # Création de deux admins "other" et "candidate" (aucun fondateur initial)
    with app.app_context():
        other = User(email="other@example.org", name="Other Admin", admin=True)
        other.password = generate_password_hash("secret123")
        candidate = User(email="candidate@example.org", name="Candidate Admin", admin=True)
        candidate.password = generate_password_hash("candipass")
        db.session.add_all([other, candidate])
        db.session.commit()
        candidate_id = candidate.id
    # Login en tant que other et tentative de promotion du candidat
    resp = client.post("/login", data={"email": "other@example.org", "password": "secret123"})
    assert resp.status_code == 302
    resp = client.post(
        f"/admin/edit/{candidate_id}",
        data={
            "name": "Candidate Admin",
            "email": "candidate@example.org",
            "founder": "1",  # tentative d'activation
            "admin": "1",
        },
    )
    assert resp.status_code in (200, 302)
    with app.app_context():
        assert db.session.get(User, candidate_id).founder is False
    # Logout puis login en tant que candidate : elle ne peut pas non plus s'auto-promouvoir
    client.get("/logout")
    resp = client.post("/login", data={"email": "candidate@example.org", "password": "candipass"})
    assert resp.status_code == 302
    resp = client.post(
        f"/admin/edit/{candidate_id}",
        data={
            "name": "Candidate Admin",
            "email": "candidate@example.org",
            "founder": "1",  # auto-promotion interdite (pas déjà founder)
            "admin": "1",
        },
    )
    assert resp.status_code in (200, 302)
    with app.app_context():
        assert db.session.get(User, candidate_id).founder is False


def test_login_legacy_hash_upgrade(app, client):
    # Crée un user avec ancien format sha256$<salt>$<hash>
    with app.app_context():
        import hashlib

        salt = "abc123"
        pwd = "oldlegacy"
        legacy_hash = hashlib.sha256((salt + pwd).encode()).hexdigest()
        u = User(
            email="legacy@example.org",
            name="Legacy User",
            password=f"sha256${salt}${legacy_hash}",
            seqid=1,
        )
        db.session.add(u)
        db.session.commit()
    # Première connexion utilise legacy puis upgrade
    resp = client.post(
        "/login",
        data={"email": "legacy@example.org", "password": "oldlegacy"},
        follow_redirects=False,
    )
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/")
    # Vérifie que le hash a été migré
    with app.app_context():
        u2 = User.query.filter_by(email="legacy@example.org").first()
        assert u2 and not u2.password.startswith("sha256$")
