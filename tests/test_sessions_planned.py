from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import RepairCafe, Session, User, user_repaircafe


def _login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def test_create_planned_session_admin():
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
        cafe = RepairCafe(name="Repair Café Orsay", slug="repaircafe-orsay", code="rco")
        admin = User(email="admin@example.org", name="Admin", admin=True)
        admin.password = generate_password_hash("password")
        db.session.add_all([cafe, admin])
        db.session.commit()
        db.session.execute(
            user_repaircafe.insert().values(
                user_id=admin.id,
                repaircafe_id=cafe.id,
                role="admin",
            )
        )
        admin.active_repaircafe_id = cafe.id
        db.session.commit()
    client = app.test_client()
    _login(client, "admin@example.org", "password")
    future = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d")
    resp = client.post(
        "/sessions/agenda",
        data={
            "action": "create",
            "date": future,
            "time": "10:00",
            "end_time": "12:00",
            "location_select": "__new__",
            "location_new": "Maison des Assos",
        },
    )
    assert resp.status_code in (302, 303)
    with app.app_context():
        s = Session.query.filter_by(status="planned").first()
        assert s is not None
        assert s.location is not None
        assert s.location.name == "Maison des Assos"
        assert s.scheduled_end_at is not None


def test_public_agenda_shows_planned():
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
        cafe = RepairCafe(name="Repair Café Orsay", slug="repaircafe-orsay", code="rco")
        admin = User(email="admin@example.org", name="Admin", admin=True)
        admin.password = generate_password_hash("password")
        db.session.add_all([cafe, admin])
        db.session.commit()
        s = Session(
            repaircafe=cafe,
            owner_id=admin.id,
            status="planned",
            scheduled_at=datetime.utcnow() + timedelta(days=1),
            scheduled_end_at=datetime.utcnow() + timedelta(days=1, hours=2),
        )
        db.session.add(s)
        db.session.commit()
    client = app.test_client()
    resp = client.get("/agenda", environ_base={"REPAIRCAFE_CODE": "rco"})
    assert resp.status_code == 200
    assert b"Agenda" in resp.data
