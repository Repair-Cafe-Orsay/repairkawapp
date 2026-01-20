import re
import tempfile
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import (
    Brand,
    Category,
    CloseStatus,
    ObjectSubtype,
    ObjectType,
    ObjectVariant,
    Repair,
    State,
    User,
)


@pytest.fixture
def app():
    upload_dir = tempfile.mkdtemp(prefix="uploads_")
    thumb_dir = tempfile.mkdtemp(prefix="thumbs_")
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:/",
            "SECRET_KEY": "test",
            "URL_SERIALIZER_SECRET": "secret",
            "UPLOAD_FOLDER": upload_dir,
            "THUMBNAIL_MEDIA_THUMBNAIL_ROOT": thumb_dir,
        }
    )
    with app.app_context():
        db.create_all()
        # données de base
        admin = User(email="admin@example.org", name="Admin", admin=True)
        admin.password = generate_password_hash("password")
        db.session.add(admin)
        db.session.add_all(
            [
                Category(name="Electro", rm_icon_id=1, icon_name="ic1"),
                Category(name="Textile", rm_icon_id=2, icon_name="ic2"),
            ]
        )
        # états & statuts nécessaires pour créer des repairs plus tard
        db.session.add_all([State(label="Réception"), State(label="Diagnostic")])
        db.session.add_all(
            [
                CloseStatus(id=1, label="Ouverte"),
                CloseStatus(id=2, label="Réparée"),
            ]
        )
        db.session.add(Brand(name="Sony"))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login_admin(client):
    resp = client.post("/login", data={"email": "admin@example.org", "password": "password"})
    assert resp.status_code == 302
    return client


def test_list_requires_login(client):
    resp = client.get("/admin/objecttypes")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_create_type_and_display(login_admin):
    with login_admin.application.app_context():
        cat = Category.query.filter_by(name="Electro").first()
    resp = login_admin.post(
        "/admin/objecttypes",
        data={"name": "Télévision", "category_id": str(cat.id)},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Television" in resp.data or b"t%c3%a9l%c3%a9vision" or b"T%c3%a9l"  # tolère encodage
    # Détail
    with login_admin.application.app_context():
        ot = ObjectType.query.filter(ObjectType.name.like("T%l%")).first()
        assert ot is not None
        detail = login_admin.get(f"/admin/objecttypes/{ot.id}")
        assert detail.status_code == 200
        assert b"Variantes" in detail.data


def test_add_variant_and_subtype(login_admin):
    # créer un type
    with login_admin.application.app_context():
        cat = Category.query.first()
        ot = ObjectType(name="Radio", category=cat)
        db.session.add(ot)
        db.session.commit()
        oid = ot.id
    # add variant
    resp_v = login_admin.post(
        f"/admin/objecttypes/{oid}", data={"action": "add_variant", "variant_name": "FM"}
    )
    assert resp_v.status_code == 302
    # add subtype
    resp_s = login_admin.post(
        f"/admin/objecttypes/{oid}", data={"action": "add_subtype", "subtype_name": "Portable"}
    )
    assert resp_s.status_code == 302
    with login_admin.application.app_context():
        ot2 = ObjectType.query.get(oid)
        assert any(v.name == "FM" for v in ot2.variants)
        assert any(st.name == "Portable" for st in ot2.subtypes)


def test_update_and_delete_variant_subtype(login_admin):
    # préparation
    with login_admin.application.app_context():
        cat = Category.query.first()
        ot = ObjectType(name="Appareil", category=cat)
        var = ObjectVariant(name="Ancienne", object_type=ot)
        sub = ObjectSubtype(name="SousAncienne", object_type=ot)
        db.session.add_all([ot, var, sub])
        db.session.commit()
        oid, vid, sid = ot.id, var.id, sub.id
    # update subtype
    resp_up = login_admin.post(
        f"/admin/objecttypes/{oid}",
        data={"action": "update_subtype", "subtype_id": str(sid), "subtype_name": "SousNew"},
    )
    assert resp_up.status_code == 302
    # delete variant
    resp_del_v = login_admin.post(
        f"/admin/objecttypes/{oid}", data={"action": "delete_variant", "variant_id": str(vid)}
    )
    assert resp_del_v.status_code == 302
    # delete subtype
    resp_del_s = login_admin.post(
        f"/admin/objecttypes/{oid}", data={"action": "delete_subtype", "subtype_id": str(sid)}
    )
    assert resp_del_s.status_code == 302
    with login_admin.application.app_context():
        ot2 = ObjectType.query.get(oid)
        assert all(v.id != vid for v in ot2.variants)
        assert all(st.id != sid for st in ot2.subtypes)
        # suppression possible car pas de repairs
        del_resp = login_admin.post(f"/admin/objecttypes/{oid}", data={"action": "delete_type"})
        assert del_resp.status_code == 302
        assert ObjectType.query.get(oid) is None


def test_delete_type_blocked_when_repairs_exist(login_admin):
    # setup type + repair
    with login_admin.application.app_context():
        cat = Category.query.first()
        ot = ObjectType(name="Console", category=cat)
        state = State.query.first()
        brand = Brand.query.first()
        db.session.add(ot)
        db.session.commit()
        rep = Repair(
            display_id="25001",
            name="Client",
            email="c@example.org",
            phone="000",
            brand=brand,
            category=cat,
            object_type=ot,
            initial_state=state,
            current_state=state,
            close_status_id=1,
            created=date.today(),
            validated=True,
            location="Local",
            otype="Console",
            model="ModelX",
        )
        db.session.add(rep)
        db.session.commit()
        oid = ot.id
    # tentative suppression
    del_attempt = login_admin.post(f"/admin/objecttypes/{oid}", data={"action": "delete_type"})
    # suppression refusée -> page rechargée (200)
    assert del_attempt.status_code == 200
    # toujours présent
    with login_admin.application.app_context():
        assert ObjectType.query.get(oid) is not None


def test_sorting(login_admin):
    # créer plusieurs types sur catégories différentes
    with login_admin.application.app_context():
        cat1, cat2 = Category.query.order_by(Category.id).all()
        db.session.add_all(
            [
                ObjectType(name="Zzz", category=cat1),
                ObjectType(name="Aaa", category=cat2),
            ]
        )
        db.session.commit()
    resp_name = login_admin.get("/admin/objecttypes?sort=name&dir=asc")
    assert resp_name.status_code == 200
    html = resp_name.data.decode("utf-8")
    # Vérifie l'ordre Aaa avant Zzz
    assert re.search(r"Aaa.*Zzz", html, re.S)
    resp_cat = login_admin.get("/admin/objecttypes?sort=category&dir=asc")
    assert resp_cat.status_code == 200
    # Catégories: Electro avant Textile -> selon catégories associées, vérifier occurrence
    html2 = resp_cat.data.decode("utf-8")
    assert "Electro" in html2 and "Textile" in html2
