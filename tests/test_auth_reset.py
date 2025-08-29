import tempfile
import time

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

import repairkawapp
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
            "SECRET_KEY": "test-secret",
            "URL_SERIALIZER_SECRET": "serializer-secret",
            "UPLOAD_FOLDER": upload_dir,
            "THUMBNAIL_MEDIA_THUMBNAIL_ROOT": thumb_dir,
        }
    )
    with app.app_context():
        db.create_all()
        u = User(email="reset@example.org", name="Reset User")
        u.password = generate_password_hash("oldpass")
        db.session.add(u)
        db.session.commit()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_change_password_request_success(client):
    resp = client.post("/change_password", data={"email": "reset@example.org"})
    # retourne JSON [True, "Vérifiez vos emails"]
    assert resp.status_code == 200
    js = resp.get_json()
    assert js[0] is True


def test_change_password_request_unknown_user(client):
    resp = client.post("/change_password", data={"email": "unknown@example.org"})
    assert resp.status_code == 200
    js = resp.get_json()
    assert js[0] is False


def test_init_password_and_set_new(client, app):
    # simulation du lien reçu par email
    with app.app_context():
        u = User.query.filter_by(email="reset@example.org").first()
        data = {"i": str(u.id), "s": u.seqid, "t": int(time.time() / 3600)}
    token = repairkawapp.serializer.dumps(data)
    # accès à la page de reset (GET)
    resp_page = client.get(f"/init_password/{token}")
    assert resp_page.status_code == 200
    # maintenant on soumet un nouveau mot de passe
    with app.app_context():
        u = User.query.filter_by(email="reset@example.org").first()
    new_token = repairkawapp.serializer.dumps({"i": str(u.id), "s": u.seqid})
    resp_post = client.post(
        "/init_password",
        data={"token": new_token, "email": "reset@example.org", "password": "newpass"},
    )
    assert resp_post.status_code == 200
    # vérification de la mise à jour
    with app.app_context():
        u = User.query.filter_by(email="reset@example.org").first()
        assert check_password_hash(u.password, "newpass")


def test_init_password_expired_token(client, app, monkeypatch):
    # créer un token vieux de 2 heures
    with app.app_context():
        u = User.query.filter_by(email="reset@example.org").first()
        old_hour = int(time.time() / 3600) - 2
    token = repairkawapp.serializer.dumps({"i": str(u.id), "s": u.seqid, "t": old_hour})
    resp = client.get(f"/init_password/{token}", follow_redirects=False)
    # devrait rediriger vers /login (token expiré)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
