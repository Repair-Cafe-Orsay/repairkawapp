from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import (
    Brand,
    Category,
    CloseStatus,
    Log,
    Message,
    Note,
    Notification,
    NotificationType,
    Repair,
    SpareChange,
    SpareStatus,
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
            "UPLOAD_FOLDER": "/tmp",
            "PAGE_SIZE": 10,
        }
    )
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Category(name="Electro", rm_icon_id=1, icon_name="lightning"),
                Category(name="Textile", rm_icon_id=2, icon_name="thread"),
            ]
        )
        st1 = State(label="Réception")
        st2 = State(label="Diagnostic")
        db.session.add_all([st1, st2])
        db.session.add_all(
            [
                CloseStatus(id=1, label="Ouverte"),
                CloseStatus(id=2, label="Réparée"),
                CloseStatus(id=3, label="Inréparable"),
            ]
        )
        db.session.add_all(
            [SpareStatus(id=0, label="Inconnu"), SpareStatus(id=1, label="Commandé")]
        )
        admin = User(email="admin@example.org", name="Admin", admin=True)
        admin.password = generate_password_hash("password")
        db.session.add(admin)
        user = User(email="user@example.org", name="User", admin=False)
        user.password = generate_password_hash("password")
        db.session.add(user)
        db.session.add_all([Brand(name="Sony"), Brand(name="Sagem"), Brand(name="Philips")])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    client.post("/login", data={"email": "admin@example.org", "password": "password"})
    return client


@pytest.fixture
def login_user(client):
    client.post("/login", data={"email": "user@example.org", "password": "password"})
    return client


def _create_repair(client, display_manual="001"):
    with client.application.app_context():
        cat = Category.query.first()
        st = State.query.first()
        brand = Brand.query.filter_by(name="Sony").first()
    form_date = date.today().strftime("%Y-%m-%d")
    data = {
        "brand": brand.name,
        "category": str(cat.id),
        "initial_state": str(st.id),
        "date": form_date,
        "value": "10",
        "weight": "1",
        "year": "2024",
        "age": "1",
        "manual_id": display_manual,
        "name": "Client",
        "email": "c@example.org",
        "phone": "0102",
        "otype": "Radio",
        "model": "RX",
        "sn": "SN",
        "description": "HS",
        "validated": "on",
    }
    resp = client.post("/new", data=data)
    assert resp.status_code == 302
    return resp.headers["Location"].split("/update/")[1]


def test_delete_repair_admin(login):
    display_id = _create_repair(login)
    with login.application.app_context():
        repair = Repair.query.filter_by(display_id=display_id).first()
        assert repair is not None
        admin = User.query.filter_by(email="admin@example.org").first()
        assert admin is not None
        note = Note(
            user_id=admin.id,
            content="Test",
            repair=repair,
            repaircafe_id=repair.repaircafe_id,
        )
        db.session.add(note)
        db.session.flush()
        db.session.add(
            Notification(
                user_id=admin.id,
                note_id=note.id,
                notification_type=NotificationType.todo,
                repaircafe_id=repair.repaircafe_id,
            )
        )
        db.session.add(
            Message(
                sender_id=admin.id,
                recipient_id=admin.id,
                subject="Test",
                body="Body",
                repair_id=repair.id,
                note_id=note.id,
            )
        )
        db.session.add(
            SpareChange(
                repair_id=repair.id,
                item="Vis",
                spare_status_id=0,
                repaircafe_id=repair.repaircafe_id,
            )
        )
        db.session.add(
            Log(
                user_id=admin.id,
                content="Log",
                repair=repair,
                repaircafe_id=repair.repaircafe_id,
            )
        )
        db.session.commit()
    resp = login.post(f"/update/{display_id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    with login.application.app_context():
        assert Repair.query.filter_by(display_id=display_id).first() is None
        assert Note.query.count() == 0
        assert Log.query.count() == 0
        assert Notification.query.count() == 0
        assert Message.query.count() == 0
        assert SpareChange.query.count() == 0


def test_delete_repair_non_admin_forbidden(login_user):
    display_id = _create_repair(login_user)
    resp = login_user.post(f"/update/{display_id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    with login_user.application.app_context():
        assert Repair.query.filter_by(display_id=display_id).first() is not None
