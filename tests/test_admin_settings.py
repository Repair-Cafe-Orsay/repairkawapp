import datetime as _dt

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import AppSetting, RepairCafe, User, user_repaircafe


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret",
            "URL_SERIALIZER_SECRET": "serializer-secret",
            "UPLOAD_FOLDER": "/tmp",
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    with app.app_context():
        u = User(email="admin@example.org", name="Admin User", admin=True, super_admin=True)
        u.password = generate_password_hash("password")
        db.session.add(u)
        cafe = RepairCafe.query.first()
        if not cafe:
            cafe = RepairCafe(name="Repair Café Orsay", slug="repaircafe-orsay", code="rco")
            db.session.add(cafe)
            db.session.commit()
        db.session.execute(
            user_repaircafe.insert().values(
                user_id=u.id,
                repaircafe_id=cafe.id,
                role="admin",
            )
        )
        u.active_repaircafe_id = cafe.id
        db.session.commit()
        # On retourne l'ID pour éviter objet détaché
        return u.id


def login(client, email, password):
    return client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=False
    )


def test_settings_page_toggle_maintenance(client, admin_user, app):
    # Login admin
    # Recharger l'email en DB
    with app.app_context():
        admin_email = db.session.get(User, admin_user).email
    resp = login(client, admin_email, "password")
    assert resp.status_code == 302
    # Accès page réglages
    resp2 = client.get("/admin/settings")
    assert resp2.status_code == 200
    assert b"Param\xc3\xa8tres site" in resp2.data
    # Active maintenance avec date future
    future = (_dt.datetime.utcnow() + _dt.timedelta(hours=2)).replace(
        minute=0, second=0, microsecond=0
    )
    future_local = future.strftime("%Y-%m-%dT%H:%M")
    resp3 = client.post(
        "/admin/settings",
        data={
            "action": "maintenance",
            "maintenance_mode": "1",
            "maintenance_until": future_local,
        },
        follow_redirects=False,
    )
    assert resp3.status_code in (302, 303)
    with app.app_context():
        setting = db.session.get(AppSetting, 1)
        assert setting is not None
        assert setting.maintenance_mode is True
        assert setting.maintenance_until is not None
    # Déconnexion et tentative de login d'un non-admin bloqué
    client.get("/logout")
    with app.app_context():
        u2 = User(email="user@example.org", name="User")
        u2.password = generate_password_hash("passuser")
        db.session.add(u2)
        db.session.commit()
    # Page login doit afficher bannière
    resp4 = client.get("/login")
    assert b"maintenance" in resp4.data.lower()
    # Tentative login user classique => reste sur page login
    resp5 = client.post(
        "/login",
        data={"email": "user@example.org", "password": "passuser"},
        follow_redirects=False,
    )
    # Comme on renvoie render_template directement en cas de blocage maintenance, status 200
    assert resp5.status_code == 200
    assert b"maintenance" in resp5.data.lower()
    # Admin peut toujours se reconnecter
    resp6 = client.post(
        "/login", data={"email": admin_email, "password": "password"}, follow_redirects=False
    )
    assert resp6.status_code == 302


def test_settings_link_in_menu(client, admin_user, app):
    with app.app_context():
        local_admin = User(email="local-admin@example.org", name="Local Admin", admin=True)
        local_admin.password = generate_password_hash("password")
        db.session.add(local_admin)
        cafe = RepairCafe.query.first()
        if not cafe:
            cafe = RepairCafe(name="Repair Café Orsay", slug="repaircafe-orsay", code="rco")
            db.session.add(cafe)
            db.session.commit()
        db.session.execute(
            user_repaircafe.insert().values(
                user_id=local_admin.id,
                repaircafe_id=cafe.id,
                role="admin",
            )
        )
        local_admin.active_repaircafe_id = cafe.id
        db.session.commit()
        admin_email = local_admin.email
    login(client, admin_email, "password")
    resp = client.get("/")
    assert resp.status_code == 200
    # Lien vers Paramètres site présent
    assert b"Param\xc3\xa8tres site" in resp.data
