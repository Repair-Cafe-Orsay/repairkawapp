import tempfile
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import User, Category, State, CloseStatus, Repair, Brand, Note, Log


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
        # reference data
        Category(name="Electronique", rm_icon_id=1)
        db.session.add(Category(name="Electro", rm_icon_id=2))
        st1 = State(label="Réception")
        st2 = State(label="Diagnostic")
        db.session.add_all([st1, st2])
        db.session.add_all([
            CloseStatus(id=1, label="Ouverte"),
            CloseStatus(id=2, label="Réparée"),
            CloseStatus(id=3, label="Inréparable")
        ])
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
    client.post('/login', data={'email': 'tech@example.org', 'password': 'password'})
    return client


def _create_repair(client, manual_id="001"):
    form_date = date(2025, 8, 28).strftime('%Y-%m-%d')
    with client.application.app_context():
        cat_id = Category.query.first().id
        state_id = State.query.first().id
    data = {
        'brand': 'Sony',
        'category': str(cat_id),
        'initial_state': str(state_id),
        'date': form_date,
        'value': '50',
        'weight': '1',
        'year': '2020',
        'age': '4',
        'manual_id': manual_id,
        'name': 'Client',
        'email': 'c@test.org',
        'phone': '0102',
        'otype': 'Radio',
        'model': 'RX',
        'sn': 'SN1',
        'description': 'HS',
        'validated': 'on'
    }
    resp = client.post('/new', data=data, follow_redirects=False)
    assert resp.status_code == 302
    return resp.headers['Location'].split('/update/')[1]


def test_manual_id_conflict(login):
    id1 = _create_repair(login, manual_id="001")
    id2 = _create_repair(login, manual_id="001")
    assert id1 != id2
    assert id1.endswith('001')  # premier
    assert id2.endswith('001a')  # suffixe lettre pour conflit


def test_update_add_note_and_changes(login):
    rid = _create_repair(login)
    with login.application.app_context():
        repair = Repair.query.filter_by(display_id=rid).first()
        st_initial = repair.current_state_id
        st_new = State.query.filter(State.id != st_initial).first().id
        user_id = User.query.first().id

    form = {
        'previous_users': '',
        'users': str(user_id),
        'previous_state': str(st_initial),
        'current_state': str(st_new),
        'previous_location': 'Local',
        'current_location': 'Atelier',
        'note': 'Diagnostic réalisé',
        'closeChoice': '0'
    }
    resp = login.post(f'/update/{rid}', data=form, follow_redirects=False)
    assert resp.status_code == 302

    with login.application.app_context():
        repair = Repair.query.filter_by(display_id=rid).first()
        assert repair.location == 'Atelier'
        assert repair.current_state_id == st_new
        assert len(repair.users) == 1
        assert repair.users[0].name == 'Tech'
        # note créée
        note = Note.query.filter_by(repair_id=repair.id).first()
        assert note and 'Diagnostic' in note.content
        # logs contiennent état et localisation
        logs = '\n'.join(l.content for l in Log.query.filter_by(repair_id=repair.id).all())
        assert 'Etat changé' in logs or 'Etat changé' in logs
        assert 'Localisation changée' in logs


def test_close_repair(login):
    rid = _create_repair(login)
    with login.application.app_context():
        repair = Repair.query.filter_by(display_id=rid).first()
        st_initial = repair.current_state_id

    form = {
        'previous_users': '',
        'users': '',
        'previous_state': str(st_initial),
        'current_state': str(st_initial),
        'previous_location': 'Local',
        'current_location': 'Local',
        'note': '',
        'closeChoice': '2'  # fermeture
    }
    resp = login.post(f'/update/{rid}', data=form, follow_redirects=False)
    assert resp.status_code == 302

    with login.application.app_context():
        repair = Repair.query.filter_by(display_id=rid).first()
        assert repair.close_status_id == 2
        logs = '\n'.join(l.content for l in Log.query.filter_by(repair_id=repair.id).all())
        assert 'Fermeture fiche' in logs
