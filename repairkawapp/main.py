"""
Module principal de l'application RepairKawapp (routes principales).
Nettoyage global : imports organisés, PEP8, docstrings, suppression des répétitions.
"""
import os
import glob
from datetime import date, datetime
import pytz
from sqlalchemy import and_
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    send_from_directory, current_app
)
from flask_login import login_required, current_user
from .models import (
    Category, Repair, Brand, State, User, Note, CloseStatus, Session,
    SpareStatus, SpareChange, Log, Notification
)
from . import db, thumb
from .services.repair_service import (
    get_or_create_brand, create_repair, update_repair, apply_update
)

main = Blueprint('main', __name__)
LOCAL_TIMEZONE = pytz.timezone('Europe/Paris')

@main.route('/')
@login_required
def index():
    """Page d'accueil principale."""
    return render_template(
        'index.html',
        name=current_user.name,
        categories=Category.query.order_by(Category.name).all(),
        users=User.query.order_by(User.name).all()
    )

@main.route('/profile')
@login_required
def profile():
    """Page profil utilisateur (statistiques)."""
    return render_template(
        'profile.html',
        name=current_user.name,
        last_membership_ok=current_user.last_membership == date.today().year
    )

@main.route('/new')
@login_required
def new_repair():
    """Formulaire de création d'une nouvelle réparation."""
    from_id = request.args.get("from_id")
    from_user = {}
    if from_id:
        r = db.session.query(Repair).filter_by(display_id=from_id).first()
        from_user = {"name": r.name, "email": r.email, "phone": r.phone, "age": r.age}
    return render_template(
        'form_new.html',
        today=date.today(),
        categories=Category.query.order_by(Category.name).all(),
        states=State.query.order_by(State.id).all(),
        name=current_user.name,
        from_user=from_user,
        r=""
    )

@main.route('/edit/<string:repair_id>')
@login_required
def edit_repair(repair_id):
    """Formulaire d'édition d'une réparation existante."""
    return render_template(
        'form_new.html',
        today=date.today(),
        categories=Category.query.order_by(Category.name).all(),
        states=State.query.order_by(State.id).all(),
        name=current_user.name,
        from_user={},
        r=db.session.query(Repair).filter_by(display_id=repair_id).first()
    )


@main.route('/del/<string:repair_id>')
@login_required
def del_repair(repair_id):
    """Suppression d'une fiche réparation."""
    db.session.query(Repair).filter_by(display_id=repair_id).delete()
    db.session().commit()
    return redirect(url_for("main.index"), code=302)

## Anciennes fonctions déplacées dans services/repair_service.py

@main.route('/new', methods=['POST'])
@login_required
def post_object():
    """Création ou modification d'une réparation (POST)."""
    rid = request.form.get('rid')
    category = db.session.query(Category).filter_by(id=request.form["category"]).first()
    initial_state = db.session.query(State).filter_by(id=request.form["initial_state"]).first()
    brand = get_or_create_brand(db.session, request.form['brand'])
    if not rid:
        r = create_repair(db.session, request.form, category, initial_state, brand)
    else:
        r = db.session.query(Repair).filter_by(id=rid).first()
        r = update_repair(db.session, r, request.form, category, initial_state, brand)
    # Attache à la session ouverte (si une session où l'utilisateur est participant et non close)
    if not rid:
        open_session = (db.session.query(Session)
                         .join(Session.participants)
                         .filter(User.id == current_user.id, Session.closed_at == None)
                         .order_by(Session.opened_at.desc())
                         .first())
        if open_session:
            r.session = open_session
    db.session.commit()

    return redirect(url_for("main.update_object", id=r.display_id), code=302)

@main.route('/media/<path:filename>')
def media_file(filename):
    r"""api to retrieve files without direct access to upload directory"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@main.route('/update/<string:id>', methods=['POST'])
@login_required
def update_object(id):
    r"""post update on an object"""
    r = db.session.query(Repair).filter_by(display_id=id).first()
    if request.method == 'POST':
        if apply_update(db.session, r, request.form):
            db.session.commit()
    return redirect(url_for("main.get_update", id=r.display_id), code=302)

@main.route('/update/<string:id>', methods=['GET'])
@login_required
def get_update(id):
    r"""update page for an object"""
    r = db.session.query(Repair).filter_by(display_id=id).first()
    # get image list
    images = glob.glob(os.path.join(current_app.config['UPLOAD_FOLDER'], id+"_*"))
    images_idx = []
    for p in images:
        images_idx.append((len(images_idx), p.split("/")[-1], "cache/"+thumb.get_thumbnail(p.split("/")[-1], "200x200").split("/")[-1]))
    return render_template('update.html',
                           name=current_user.name,
                           categories=Category.query.order_by(Category.name).all(),
                           states=State.query.order_by(State.id).all(),
                           users=User.query.order_by(User.name).all(),
                           notes=db.session.query(Note, Notification).filter_by(repair=r).order_by(Note.id.desc())\
                                        .outerjoin(Notification, and_(Notification.note_id==Note.id, Notification.user_id==current_user.id)),
                           logs=Log.query.filter_by(repair=r).order_by(Log.id.desc()),
                           r=r,
                           current_users=[u.id for u in r.users],
                           closestatus=CloseStatus.query.order_by(CloseStatus.id).all(),
                           images=images_idx,
                           splist=SpareChange.query.filter_by(repair=r).order_by(SpareChange.id.asc()),
                           spare_statuses=SpareStatus.query.order_by(SpareStatus.id).all())

@main.route('/sessions')
@login_required
def sessions_page():
    """Page listant les sessions (récentes)."""
    sessions = (db.session.query(Session)
                .order_by(Session.opened_at.desc())
                .limit(50).all())
    return render_template('sessions.html',
                           name=current_user.name,
                           sessions=sessions)

@main.route('/sessions/<int:session_id>')
@login_required
def session_detail(session_id):
    s = db.session.query(Session).filter_by(id=session_id).first()
    if not s:
        return redirect(url_for('main.sessions_page'))
    return render_template('session_detail.html',
                           name=current_user.name,
                           session=s,
                           participants=s.participants)
