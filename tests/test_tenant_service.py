import tempfile

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import RepairCafe, User, user_repaircafe
from repairkawapp.services.tenant_service import (
    filter_active_membership_or_founder,
    get_user_cafe_board_title,
    get_user_cafe_founder,
    set_user_cafe_board_title,
    set_user_cafe_founder,
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
        user = User(email="multi@example.org", name="Multi")
        user.password = generate_password_hash("password")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_board_roles_per_repair_cafe(app):
    with app.app_context():
        user = User.query.filter_by(email="multi@example.org").first()
        cafe1 = RepairCafe.query.first()
        cafe2 = RepairCafe(name="RC2", slug="rc2", code="rc2")
        db.session.add(cafe2)
        db.session.commit()

        if cafe1:
            existing = (
                db.session.query(user_repaircafe)
                .filter(user_repaircafe.c.user_id == user.id)
                .filter(user_repaircafe.c.repaircafe_id == cafe1.id)
                .first()
            )
            if not existing:
                db.session.execute(
                    user_repaircafe.insert().values(
                        user_id=user.id,
                        repaircafe_id=cafe1.id,
                        role=None,
                    )
                )
        db.session.execute(
            user_repaircafe.insert().values(
                user_id=user.id,
                repaircafe_id=cafe2.id,
                role=None,
            )
        )
        db.session.commit()

        set_user_cafe_board_title(user.id, cafe1.id, "président")
        set_user_cafe_board_title(user.id, cafe2.id, "trésorier")
        set_user_cafe_founder(user.id, cafe1.id, True)
        set_user_cafe_founder(user.id, cafe2.id, False)
        db.session.commit()

        assert get_user_cafe_board_title(user.id, cafe1.id) == "président"
        assert get_user_cafe_board_title(user.id, cafe2.id) == "trésorier"
        assert get_user_cafe_founder(user.id, cafe1.id) is True
        assert get_user_cafe_founder(user.id, cafe2.id) is False

        query = User.query
        assert filter_active_membership_or_founder(query, cafe1.id).count() == 1
        assert filter_active_membership_or_founder(query, cafe2.id).count() == 0
