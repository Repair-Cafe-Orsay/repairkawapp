import pytest
from werkzeug.security import generate_password_hash
from repairkawapp import create_app, db
from repairkawapp.models import User, Session as SessionModel, Repair, Brand, Category, State
from datetime import datetime, date

@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test',
        'URL_SERIALIZER_SECRET': 'secret'
    })
    with app.app_context():
        db.create_all()
        u1 = User(email='owner@example.org', name='Owner', password=generate_password_hash('pwd'))
        u2 = User(email='other@example.org', name='Other', password=generate_password_hash('pwd'))
        admin = User(email='admin@example.org', name='Admin', password=generate_password_hash('pwd'), admin=True)
        db.session.add_all([u1, u2, admin])
        # base data for repairs
        cat = Category(name='Cat')
        br = Brand(name='BR')
        st = State(label='Init')
        st2 = State(label='Cur')
        db.session.add_all([cat, br, st, st2])
        db.session.commit()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email):
    return client.post('/login', data={'email': email, 'password': 'pwd'})


def _open_session(client, location='LieuX'):
    r = client.post('/api/session/open', json={'location': location})
    assert r.status_code == 200
    return r.get_json()['id']


def test_join_leave_owner_change(client, app):
    login(client, 'owner@example.org')
    sid = _open_session(client)
    # second user join
    login(client, 'other@example.org')
    r = client.post(f'/api/session/join/{sid}')
    assert r.status_code == 200
    # change owner as other (must be participant) -> take ownership
    r = client.post(f'/api/session/owner/{sid}', json={'owner_id': 2})
    assert r.status_code == 200
    # leave session
    r = client.post(f'/api/session/leave/{sid}')
    assert r.status_code == 200
    # ensure still participant list decreased
    data = r.get_json()
    assert 2 not in data['participants']  # user left


def test_reopen_session(client, app):
    login(client, 'owner@example.org')
    sid = _open_session(client)
    # close
    r = client.post(f'/api/session/close/{sid}', json={'comment': 'fin ok'})
    assert r.status_code == 200
    # reopen (same owner)
    r = client.post(f'/api/session/reopen/{sid}')
    assert r.status_code == 200
    assert r.get_json()['closed_at'] is None


def test_repair_auto_attach_to_open_session(client, app):
    # open session as owner
    login(client, 'owner@example.org')
    sid = _open_session(client, 'Salle R')
    # create repair -> should attach automatically
    from datetime import date as _d
    resp = client.post('/new', data={
        'date': _d.today().isoformat(),
        'name': 'Visiteur',
        'otype': 'Objet',
        'brand': 'BR',
        'model': 'M',
        'category': 1,
        'initial_state': 1,
        'description': 'Problème',
        'validated': 1
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        rep = db.session.query(Repair).first()
        assert rep is not None
        assert rep.session_id == sid


def test_update_session_details(client, app):
    login(client, 'owner@example.org')
    sid = _open_session(client, 'Ancien Lieu')
    r = client.post(f'/api/session/update/{sid}', json={'location': 'Nouveau Lieu', 'comment': 'note'})
    assert r.status_code == 200
    with app.app_context():
        s = db.session.query(SessionModel).get(sid)
        assert s.location.name == 'Nouveau Lieu'
        assert s.comment == 'note'


def test_delete_session_as_admin(client, app):
    login(client, 'owner@example.org')
    sid = _open_session(client)
    # switch to admin user -> delete OK
    login(client, 'admin@example.org')
    r = client.delete(f'/api/session/delete/{sid}')
    assert r.status_code == 200
    with app.app_context():
        assert db.session.query(SessionModel).count() == 0


def test_attach_repair_switch_session(client, app):
    """Création d'une réparation dans une séance, fermeture, ouverture nouvelle séance puis rattachement."""
    login(client, 'owner@example.org')
    sid1 = _open_session(client, 'Salle A')
    # créer repair auto-attachée à sid1
    from datetime import date as _d
    resp = client.post('/new', data={
        'date': _d.today().isoformat(),
        'name': 'Visiteur',
        'otype': 'Objet',
        'brand': 'BR',
        'model': 'M',
        'category': 1,
        'initial_state': 1,
        'description': 'Problème',
        'validated': 1
    }, follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        rep = db.session.query(Repair).first()
        assert rep.session_id == sid1
        rid = rep.display_id
    # fermer première séance
    r = client.post(f'/api/session/close/{sid1}', json={'comment': 'fin ok'})
    assert r.status_code == 200
    # ouvrir nouvelle séance
    sid2 = _open_session(client, 'Salle B')
    assert sid2 != sid1
    # rattacher (changement de séance)
    r = client.post(f'/attach_session/{rid}', follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        rep2 = db.session.query(Repair).first()
        assert rep2.session_id == sid2
        # vérifier log de changement
        from repairkawapp.models import Log as LogModel
        logs = [l.content for l in db.session.query(LogModel).filter_by(repair_id=rep2.id).all()]
        assert any('Changement de séance' in c for c in logs)
