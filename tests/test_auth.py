import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash
from repairkawapp import create_app, db
from repairkawapp.models import User

@pytest.fixture
def app():
    upload_dir = tempfile.mkdtemp(prefix="uploads_")
    thumb_dir = tempfile.mkdtemp(prefix="thumbs_")
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret',
        'URL_SERIALIZER_SECRET': 'serializer-secret',
        'UPLOAD_FOLDER': upload_dir,
        'THUMBNAIL_MEDIA_THUMBNAIL_ROOT': thumb_dir
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def user(app):
    with app.app_context():
        u = User(email="user@example.org", name="Test User")
    u.password = generate_password_hash("password")
    db.session.add(u)
    db.session.commit()
    return u

def test_protected_redirect(client):
    """Accès non authentifié doit rediriger vers /login."""
    resp = client.get('/profile')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

def test_login_success(client, user):
    resp = client.post('/login', data={'email': user.email, 'password': 'password'}, follow_redirects=False)
    assert resp.status_code == 302
    assert '/profile' in resp.headers['Location']

    # Accès après login (en suivant la redirection)
    resp2 = client.get('/profile', follow_redirects=True)
    assert resp2.status_code == 200
    assert b'profile' in resp2.data.lower() or b'profil' in resp2.data.lower()

def test_login_fail(client, user):
    resp = client.post('/login', data={'email': user.email, 'password': 'wrong'}, follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

def test_logout_flow(client, user):
    client.post('/login', data={'email': user.email, 'password': 'password'})
    resp = client.get('/logout')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

    # Après logout, retour sur page protégée => redirection
    resp2 = client.get('/profile')
    assert resp2.status_code == 302
    assert '/login' in resp2.headers['Location']

def test_login_fail_unknown_user(client):
    resp = client.post('/login', data={'email': 'nobody@example.org', 'password': 'whatever'})
    assert resp.status_code == 302 and '/login' in resp.headers['Location']


def test_login_legacy_hash_upgrade(app, client):
    # Crée un user avec ancien format sha256$<salt>$<hash>
    with app.app_context():
        import hashlib, time
        salt = 'abc123'
        pwd = 'oldlegacy'
        legacy_hash = hashlib.sha256((salt + pwd).encode()).hexdigest()
        u = User(email='legacy@example.org', name='Legacy User', password=f'sha256${salt}${legacy_hash}', seqid=1)
        db.session.add(u)
        db.session.commit()
    # Première connexion utilise legacy puis upgrade
    resp = client.post('/login', data={'email': 'legacy@example.org', 'password': 'oldlegacy'})
    assert resp.status_code == 302 and '/profile' in resp.headers['Location']
    # Vérifie que le hash a été migré
    with app.app_context():
        u2 = User.query.filter_by(email='legacy@example.org').first()
        assert u2 and not u2.password.startswith('sha256$')
