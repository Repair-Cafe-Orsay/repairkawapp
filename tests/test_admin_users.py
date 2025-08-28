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
        'SECRET_KEY': 'test',
        'URL_SERIALIZER_SECRET': 'secret',
        'UPLOAD_FOLDER': upload_dir,
        'THUMBNAIL_MEDIA_THUMBNAIL_ROOT': thumb_dir
    })
    with app.app_context():
        db.create_all()
        # admin user
        admin = User(email="admin@example.org", name="Admin", admin=True)
        admin.password = generate_password_hash("password")
        db.session.add(admin)
        db.session.commit()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def login_admin(client):
    resp = client.post('/login', data={'email': 'admin@example.org', 'password': 'password'})
    assert resp.status_code == 302
    return client


def test_create_member_with_membership_year(login_admin):
    resp = login_admin.post('/admin/new', data={
        'name': 'Nouveau Membre',
        'email': 'membre@example.org',
        'last_membership': '2025',
        'admin': ''
    }, follow_redirects=False)
    assert resp.status_code == 302
    with login_admin.application.app_context():
        u = User.query.filter_by(email='membre@example.org').first()
        assert u is not None
        assert u.last_membership == 2025
        assert u.admin is False


def test_update_member_membership_year(login_admin):
    # create user first (without membership)
    with login_admin.application.app_context():
        u = User(email='update@example.org', name='Update Test')
        db.session.add(u)
        db.session.commit()
        uid = u.id
    # update membership year
    resp = login_admin.post(f'/admin/edit/{uid}', data={
        'name': 'Update Test',
        'email': 'update@example.org',
        'last_membership': '2024',
        'admin': ''
    }, follow_redirects=False)
    assert resp.status_code == 302
    with login_admin.application.app_context():
        u = User.query.filter_by(id=uid).first()
        assert u.last_membership == 2024


def test_clear_membership_year(login_admin):
    # create user with membership
    with login_admin.application.app_context():
        u = User(email='clear@example.org', name='Clear Test', last_membership=2023)
        db.session.add(u)
        db.session.commit()
        uid = u.id
    # clear membership by sending empty string
    resp = login_admin.post(f'/admin/edit/{uid}', data={
        'name': 'Clear Test',
        'email': 'clear@example.org',
        'last_membership': '',
        'admin': ''
    }, follow_redirects=False)
    assert resp.status_code == 302
    with login_admin.application.app_context():
        u = User.query.filter_by(id=uid).first()
        assert u.last_membership is None


def test_get_new_user_form(login_admin):
    resp = login_admin.get('/admin/new')
    assert resp.status_code == 200
    txt = resp.data.decode('utf-8').lower()
    assert 'cotisation' in txt


def test_get_edit_user_form(login_admin):
    # récupérer l'admin existant
    with login_admin.application.app_context():
        admin_user = User.query.filter_by(email='admin@example.org').first()
        uid = admin_user.id
    resp = login_admin.get(f'/admin/edit/{uid}')
    assert resp.status_code == 200
    assert b'Admin' in resp.data


def test_duplicate_email_creation(login_admin):
    # créer première fois
    login_admin.post('/admin/new', data={
        'name': 'Dup One', 'email': 'dup@example.org', 'last_membership': '2025'
    })
    # tentative doublon
    resp = login_admin.post('/admin/new', data={
        'name': 'Dup Two', 'email': 'dup@example.org', 'last_membership': '2025'
    })
    # devrait ré-afficher le formulaire (200) car user_exists True
    assert resp.status_code == 200
    assert b'already' in resp.data.lower() or b'exist' in resp.data.lower() or b'existe' in resp.data.lower()


def test_set_admin_flag(login_admin):
    resp = login_admin.post('/admin/new', data={
        'name': 'AdminFlag', 'email': 'flag@example.org', 'last_membership': '2025', 'admin': '1'
    })
    assert resp.status_code == 302
    with login_admin.application.app_context():
        u = User.query.filter_by(email='flag@example.org').first()
        assert u.admin is True


def test_invalid_membership_year_ignored(login_admin):
    resp = login_admin.post('/admin/new', data={
        'name': 'BadYear', 'email': 'badyear@example.org', 'last_membership': 'abcd'
    })
    assert resp.status_code == 302
    with login_admin.application.app_context():
        u = User.query.filter_by(email='badyear@example.org').first()
        assert u.last_membership is None
