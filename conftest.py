# Configure PYTHONPATH pour permettre l'import du package local quand pytest est lancé
import os
import sys

import pytest

from repairkawapp import db
from repairkawapp.models import (
    Location,
    Log,
    Message,
    Note,
    Notification,
    Repair,
    RepairCafe,
    Session,
    SpareChange,
    User,
    user_repaircafe,
)

root = os.path.abspath(os.path.dirname(__file__))
if root not in sys.path:
    sys.path.insert(0, root)


@pytest.fixture(autouse=True)
def _ensure_default_repaircafe(request):
    """Ensure a default RepairCafe and user membership for tests."""
    app = None
    if "app" in request.fixturenames:
        app = request.getfixturevalue("app")
    elif "client" in request.fixturenames:
        client = request.getfixturevalue("client")
        app = client.application
    if app is None:
        yield
        return
    with app.app_context():
        cafe = RepairCafe.query.first()
        if not cafe:
            cafe = RepairCafe(name="Repair Café Orsay", slug="repaircafe-orsay", code="rco")
            db.session.add(cafe)
            db.session.commit()
        users = User.query.all()
        for user in users:
            existing = (
                db.session.query(user_repaircafe)
                .filter(user_repaircafe.c.user_id == user.id)
                .filter(user_repaircafe.c.repaircafe_id == cafe.id)
                .first()
            )
            if not existing:
                db.session.execute(
                    user_repaircafe.insert().values(
                        user_id=user.id,
                        repaircafe_id=cafe.id,
                        role="admin" if user.admin else None,
                    )
                )
            if not user.active_repaircafe_id:
                user.active_repaircafe_id = cafe.id
        # Ensure tenant scoping for existing records in tests
        for model in (Repair, Session, Location, Note, Log, Notification, Message, SpareChange):
            for row in db.session.query(model).all():
                if hasattr(row, "repaircafe_id") and row.repaircafe_id is None:
                    row.repaircafe_id = cafe.id
        db.session.commit()
    yield
    with app.app_context():
        db.session.remove()
