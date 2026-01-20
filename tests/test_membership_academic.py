import tempfile
from datetime import date

from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import RepairCafe, User, user_repaircafe
from repairkawapp.services.tenant_service import get_user_cafe_membership


def _expected_academic_start(d: date) -> int:
    return d.year if d.month >= 9 else d.year - 1


def setup_app():
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
    return app


def test_admin_set_current_membership():
    app = setup_app()
    with app.app_context():
        db.create_all()
        cafe = RepairCafe(name="Repair Café Orsay", slug="repaircafe-orsay", code="rco")
        db.session.add(cafe)
        # user without membership
        u = User(email="membre@example.org", name="Membre Test")
        u.password = generate_password_hash("pass")
        db.session.add(u)
        # admin
        admin = User(email="admin@example.org", name="Admin", admin=True)
        admin.password = generate_password_hash("admin")
        db.session.add(admin)
        db.session.commit()
        for user in (u, admin):
            db.session.execute(
                user_repaircafe.insert().values(
                    user_id=user.id,
                    repaircafe_id=cafe.id,
                    role="admin" if user.admin else None,
                )
            )
            user.active_repaircafe_id = cafe.id
        db.session.commit()
        uid = u.id
        cafe_id = cafe.id
    client = app.test_client()
    # login as admin
    resp = client.post("/login", data={"email": "admin@example.org", "password": "admin"})
    assert resp.status_code == 302
    # invoke quick action
    resp = client.post(f"/admin/edit/{uid}", data={"action": "set_current_membership"})
    assert resp.status_code == 302
    with app.app_context():
        u = User.query.get(uid)
        # Après changement de logique : si mois en {7,8} on vise acad +1
        today = date.today()
        expected = (
            (_expected_academic_start(today) + 1)
            if today.month in (7, 8)
            else _expected_academic_start(today)
        )
        assert get_user_cafe_membership(u.id, cafe_id) == expected
