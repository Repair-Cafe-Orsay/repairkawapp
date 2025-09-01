import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import User


@pytest.fixture
def client():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test",
        }
    )
    with app.app_context():
        db.create_all()
        u1 = User(email="alice@example.org", name="Alice")
        u1.password = generate_password_hash("pw")
        u2 = User(email="bob@example.org", name="Bob")
        u2.password = generate_password_hash("pw")
        db.session.add_all([u1, u2])
        db.session.commit()
        yield app.test_client()
        db.drop_all()


def login(client, email):
    resp = client.post("/login", data={"email": email, "password": "pw"})
    assert resp.status_code == 302


def test_create_message_and_list(client):
    login(client, "alice@example.org")
    # créer
    resp = client.post(
        "/api/messages",
        json={"recipient_id": 2, "subject": "Hello", "body": "Salut Bob"},
    )
    assert resp.status_code == 201
    js = resp.get_json()
    assert js["subject"] == "Hello"
    assert js["direction"] == "out"
    mid = js["id"]
    # inbox Bob
    client.get("/logout")
    login(client, "bob@example.org")
    resp_in = client.get("/api/messages?box=in")
    assert resp_in.status_code == 200
    inbox = resp_in.get_json()
    assert any(m["id"] == mid for m in inbox)
    # détail marque comme lu
    detail = client.get(f"/api/messages/{mid}")
    assert detail.status_code == 200
    jsd = detail.get_json()
    assert jsd["read_at"] is not None


def test_validation_errors(client):
    login(client, "alice@example.org")
    # self
    r = client.post("/api/messages", json={"recipient_id": 1, "body": "x"})
    assert r.status_code == 400
    # body vide
    r = client.post("/api/messages", json={"recipient_id": 2, "body": "  "})
    assert r.status_code == 400
    # body long
    r = client.post(
        "/api/messages",
        json={"recipient_id": 2, "body": "x" * 251},
    )
    assert r.status_code == 400
    # subject long
    r = client.post(
        "/api/messages",
        json={"recipient_id": 2, "subject": "s" * 121, "body": "ok"},
    )
    assert r.status_code == 400


def test_unread_count_and_mark_read(client):
    login(client, "alice@example.org")
    # 2 messages envoyés à Bob
    for i in range(2):
        client.post("/api/messages", json={"recipient_id": 2, "body": f"msg {i}"})
    client.get("/logout")
    login(client, "bob@example.org")
    c = client.get("/api/messages/unread_count")
    assert c.get_json() == 2
    # lister unread
    unread = client.get("/api/messages/unread").get_json()
    assert len(unread) == 2
    # mark read one
    mid = unread[0]["id"]
    mr = client.post(f"/api/messages/{mid}/read")
    assert mr.status_code == 200
    c2 = client.get("/api/messages/unread_count")
    assert c2.get_json() == 1
