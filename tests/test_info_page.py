from repairkawapp import create_app, db
from repairkawapp.models import Location, RepairCafe


def test_info_page_public():
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
        cafe = RepairCafe(
            name="Repair Café Orsay",
            slug="repaircafe-orsay",
            code="rco",
            email="contact@repaircafe.org",
            phone="0102030405",
            website_url="https://example.org",
        )
        db.session.add(cafe)
        db.session.commit()
        db.session.add(
            Location(
                name="Maison des Assos",
                full_name="Maison des Associations",
                address="1 rue du Test",
                is_recurring=True,
                repaircafe=cafe,
            )
        )
        db.session.commit()
    client = app.test_client()
    resp = client.get("/infos", environ_base={"REPAIRCAFE_CODE": "rco"})
    assert resp.status_code == 200
    data = resp.data
    assert b"Repair Caf" in data
    assert b"contact@repaircafe.org" in data
    assert b"0102030405" in data
    assert b"Maison des Associations" in data
