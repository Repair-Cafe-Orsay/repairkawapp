import tempfile
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import (
    Brand,
    Category,
    CloseStatus,
    SpareStatus,
    State,
    User,
)
from repairkawapp.services.repair_service import (
    apply_update,
    create_repair,
    get_or_create_brand,
)
from repairkawapp.services.spare_service import add_spare, delete_spare
from repairkawapp.services.stats_service import (
    compute_stats,
    get_cached_lists,
    parse_period,
)


@pytest.fixture
def app():
    upload_dir = tempfile.mkdtemp(prefix="uploads_")
    thumb_dir = tempfile.mkdtemp(prefix="thumbs_")
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test",
            "URL_SERIALIZER_SECRET": "secret",
            "UPLOAD_FOLDER": upload_dir,
            "THUMBNAIL_MEDIA_THUMBNAIL_ROOT": thumb_dir,
        }
    )
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Category(name="Electro", rm_icon_id=1, icon_name="lightning"),
            ]
        )
        st1 = State(label="Réception")
        st2 = State(label="Diagnostic")
        db.session.add_all([st1, st2])
        db.session.add_all(
            [
                CloseStatus(id=1, label="Ouverte"),
                CloseStatus(id=2, label="Réparée"),
            ]
        )
        db.session.add_all(
            [SpareStatus(id=0, label="Inconnu"), SpareStatus(id=1, label="Commandé")]
        )
        user = User(email="tech@example.org", name="Tech")
        user.password = generate_password_hash("password")
        db.session.add(user)
        db.session.commit()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    client.post("/login", data={"email": "tech@example.org", "password": "password"})
    return client


def test_generate_display_id_conflicts(app):
    with app.app_context():
        # créer deux réparations même manual id pour générer suffixe
        cat = Category.query.first()
        st = State.query.first()
        brand = Brand(name="Sony")
        db.session.add(brand)
        db.session.commit()
        # simuler utilisateur connecté requis par create_repair (current_user)
        from flask_login import login_user

        user = User.query.filter_by(email="tech@example.org").first()
        login_user(user)
        form = {
            "date": date(2025, 8, 28).strftime("%Y-%m-%d"),
            "manual_id": "001",
            "age": "1",
            "name": "A",
            "email": "a@a",
            "phone": "",
            "otype": "Radio",
            "model": "M",
            "sn": "SN",
            "description": "Desc",
            "validated": "on",
            "value": "1",
            "weight": "1",
            "year": "2024",
        }
        r1 = create_repair(db.session, form, cat, st, brand)
        db.session.commit()
        r2 = create_repair(db.session, form, cat, st, brand)
        db.session.commit()
        assert r1.display_id != r2.display_id
        assert r2.display_id.endswith("a")


def test_parse_period_invalid():
    f, t = parse_period("2025-13-01", "2025-02-30")  # mois et jour invalides
    assert f is None and t is None


def test_stats_service_roundtrip(app):
    with app.app_context():
        cat = Category.query.first()
        st = State.query.first()
        brand = Brand(name="Sony")
        db.session.add(brand)
        db.session.commit()
        from flask_login import login_user

        user = User.query.filter_by(email="tech@example.org").first()
        login_user(user)
        form = {
            "date": date(2025, 8, 28).strftime("%Y-%m-%d"),
            "manual_id": None,
            "age": "1",
            "name": "A",
            "email": "a@a",
            "phone": "",
            "otype": "Radio",
            "model": "M",
            "sn": "SN",
            "description": "Desc",
            "validated": "on",
            "value": "1",
            "weight": "1",
            "year": "2024",
        }
        _ = create_repair(db.session, form, cat, st, get_or_create_brand(db.session, "Sony"))
        db.session.commit()
        period_from = date(2025, 8, 28)
        stats = compute_stats(db.session, period_from, period_from)
        assert stats["total"] == 1
        cats_cache, status_cache = [], []
        get_cached_lists(db.session, cats_cache, status_cache)
        assert len(cats_cache) >= 1 and len(status_cache) >= 1


def test_add_and_delete_spare(login):
    # créer une réparation d'abord
    with login.application.app_context():
        cat = Category.query.first()
        st = State.query.first()
        brand = Brand(name="Sony")
        db.session.add(brand)
        db.session.commit()
        from flask_login import login_user

        user = User.query.filter_by(email="tech@example.org").first()
        login_user(user)
        form = {
            "date": date(2025, 8, 28).strftime("%Y-%m-%d"),
            "manual_id": None,
            "age": "1",
            "name": "A",
            "email": "a@a",
            "phone": "",
            "otype": "Radio",
            "model": "M",
            "sn": "SN",
            "description": "Desc",
            "validated": "on",
            "value": "1",
            "weight": "1",
            "year": "2024",
        }
        r = create_repair(db.session, form, cat, st, get_or_create_brand(db.session, "Sony"))
        db.session.commit()
        rid = r.display_id
    # On teste directement les fonctions (add_spare etc.) ici.
    with login.application.app_context():
        from flask_login import login_user

        user = User.query.filter_by(email="tech@example.org").first()
        login_user(user)
        sp, log = add_spare(
            db.session, rid, item="Vis", status_id=1, source="Magasin", note="Remplacer"
        )
        db.session.commit()
        assert sp.id is not None and log.id is not None
        delete_spare(db.session, sp.id)
        db.session.commit()
        from repairkawapp.models import SpareChange

        assert SpareChange.query.filter_by(id=sp.id).first() is None


def test_apply_update_user_and_note(login):
    with login.application.app_context():
        cat = Category.query.first()
        st = State.query.first()
        brand = Brand(name="Sony")
        db.session.add(brand)
        db.session.commit()
        from flask_login import login_user

        user = User.query.filter_by(email="tech@example.org").first()
        login_user(user)
        form = {
            "date": date(2025, 8, 28).strftime("%Y-%m-%d"),
            "manual_id": None,
            "age": "1",
            "name": "A",
            "email": "a@a",
            "phone": "",
            "otype": "Radio",
            "model": "M",
            "sn": "SN",
            "description": "Desc",
            "validated": "on",
            "value": "1",
            "weight": "1",
            "year": "2024",
        }
        r = create_repair(db.session, form, cat, st, get_or_create_brand(db.session, "Sony"))
        db.session.commit()
        fake_form = type(
            "F",
            (),
            {
                "getlist": lambda self, k: ["1"] if k == "users" else [""],
                "get": lambda self, k: {
                    "previous_state": str(r.current_state_id),
                    "current_state": str(r.current_state_id),
                    "previous_location": "Local",
                    "current_location": "Local",
                    "note": "Note test",
                    "closeChoice": "0",
                }.get(k),
            },
        )()
        changed = apply_update(db.session, r, fake_form)
        assert changed is True
        db.session.commit()
        from repairkawapp.models import Note

        assert Note.query.filter_by(repair_id=r.id).count() == 1
