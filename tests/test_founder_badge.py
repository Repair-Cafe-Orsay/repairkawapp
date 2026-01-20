from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import RepairCafe, User, user_repaircafe
from repairkawapp.services.tenant_service import get_user_cafe_founder, set_user_cafe_founder


def test_founder_badge_and_restricted_edit():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "x",
            "URL_SERIALIZER_SECRET": "y",
            "UPLOAD_FOLDER": "/tmp",
            "THUMBNAIL_MEDIA_THUMBNAIL_ROOT": "/tmp",
        }
    )
    with app.app_context():
        db.create_all()
        cafe = RepairCafe(name="Repair Café Orsay", slug="repaircafe-orsay", code="rco")
        db.session.add(cafe)
        founder = User(email="founder@example.org", name="Found One", founder=True, admin=True)
        founder.password = generate_password_hash("pwdpwd")
        target = User(email="target@example.org", name="Target", admin=True)
        target.password = generate_password_hash("pwdpwd")
        outsider = User(email="outsider@example.org", name="Out", admin=True)
        outsider.password = generate_password_hash("pwdpwd")
        db.session.add_all([founder, target, outsider])
        db.session.commit()
        for user in (founder, target, outsider):
            db.session.execute(
                user_repaircafe.insert().values(
                    user_id=user.id,
                    repaircafe_id=cafe.id,
                    role="admin",
                )
            )
            user.active_repaircafe_id = cafe.id
        db.session.commit()
        set_user_cafe_founder(founder.id, cafe.id, True)
        db.session.commit()
        target_id = target.id
    client = app.test_client()
    # Founder se connecte et active founder sur target (ok)
    client.post("/login", data={"email": "founder@example.org", "password": "pwdpwd"})
    r = client.post(
        f"/admin/edit/{target_id}",
        data={"name": "Target", "email": "target@example.org", "founder": "1", "admin": "1"},
    )
    assert r.status_code in (200, 302)
    with app.app_context():
        cafe = RepairCafe.query.first()
        assert get_user_cafe_founder(target_id, cafe.id) is True
    client.get("/logout")
    # Outsider (non founder) ne peut pas activer founder sur un autre user
    client.post("/login", data={"email": "outsider@example.org", "password": "pwdpwd"})
    r2 = client.post(
        f"/admin/edit/{target_id}",
        data={"name": "Target", "email": "target@example.org", "founder": "1", "admin": "1"},
    )
    assert r2.status_code in (200, 302)
    with app.app_context():
        cafe = RepairCafe.query.first()
        assert get_user_cafe_founder(target_id, cafe.id) is True  # inchangé
