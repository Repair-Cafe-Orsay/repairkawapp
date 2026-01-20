import pytest

from repairkawapp import create_app, db


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
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_index_redirect(client):
    """Vérifie que la page d'accueil redirige vers login si non authentifié."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
