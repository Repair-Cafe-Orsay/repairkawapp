"""Module principal de l'application RepairKawapp (routes principales).

RepairKawapp – Repair Café management application
Licence: MIT (voir fichier LICENSE)
Auteur principal: Jean Senellart

Nettoyage global : imports organisés, PEP8, docstrings, suppression des répétitions.
"""

import glob
import os
from datetime import date, datetime

import pytz
from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import and_

from . import db, thumb
from .models import (
    Category,
    CloseStatus,
    Log,
    Note,
    Notification,
    Repair,
    Session,
    SpareChange,
    SpareStatus,
    State,
    User,
)
from .services.image_service import process_user_photo
from .services.repair_service import (
    apply_update,
    create_repair,
    get_or_create_brand,
    update_repair,
)

main = Blueprint("main", __name__)
LOCAL_TIMEZONE = pytz.timezone("Europe/Paris")


@main.route("/")
@login_required
def dashboard():
    """Dashboard d'accueil avec message de bienvenue et statistiques."""
    # Informations cotisation pour affichage rapide
    today = date.today()
    current_start = _current_academic_start(today)
    last_start = current_user.last_membership
    last_membership_ok = last_start == current_start
    user_period = (last_start, last_start + 1) if last_start is not None else None
    return render_template(
        "dashboard.html",
        name=current_user.name,
        user_period=user_period,
        last_membership_ok=last_membership_ok,
    )


def _current_academic_start(today: date) -> int:
    """Retourne l'année de début de la période de cotisation académique courante.

    La période va du 1er septembre de N au 31 août de N+1. Avant septembre on est
    toujours dans la période commencée l'année précédente.
    """
    return today.year if today.month >= 9 else today.year - 1


@main.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Page profil utilisateur (dashboard + cotisation + présentation)."""
    today = date.today()
    current_start = _current_academic_start(today)
    last_start = current_user.last_membership
    last_membership_ok = last_start == current_start
    user_period = (last_start, last_start + 1) if last_start is not None else None
    photo_error = None
    if request.method == "POST":
        # Mise à jour biographie (toujours sauvegardée même si erreur photo)
        current_user.biography = request.form.get("biography") or None
        if "photo" in request.files and request.files["photo"].filename:
            raw = request.files["photo"].read()
            filename, err = process_user_photo(
                raw,
                current_app.config["UPLOAD_FOLDER"],
                current_user.id,
                request.form.get,
            )
            if err:
                photo_error = err
            else:
                current_user.photo_filename = filename
        db.session.commit()
        if not photo_error:
            return redirect(url_for("main.profile"))
    return render_template(
        "profile.html",
        name=current_user.name,
        last_membership_ok=last_membership_ok,
        user_period=user_period,
        biography=current_user.biography,
        photo_filename=current_user.photo_filename,
        photo_error=photo_error,
    )


@main.route("/new")
@login_required
def new_repair():
    """Formulaire de création d'une nouvelle réparation."""
    from_id = request.args.get("from_id")
    from_user = {}
    if from_id:
        r = db.session.query(Repair).filter_by(display_id=from_id).first()
        from_user = {"name": r.name, "email": r.email, "phone": r.phone, "age": r.age}
    current_session = (
        db.session.query(Session)
        .filter(Session.closed_at.is_(None))
        .order_by(Session.opened_at.desc())
        .first()
    )
    return render_template(
        "form_new.html",
        today=date.today(),
        categories=Category.query.order_by(Category.name).all(),
        states=State.query.order_by(State.id).all(),
        name=current_user.name,
        from_user=from_user,
        r="",
        current_session=current_session,
    )


@main.route("/edit/<string:repair_id>")
@login_required
def edit_repair(repair_id):
    """Formulaire d'édition d'une réparation existante."""
    current_session = (
        db.session.query(Session)
        .filter(Session.closed_at.is_(None))
        .order_by(Session.opened_at.desc())
        .first()
    )
    return render_template(
        "form_new.html",
        today=date.today(),
        categories=Category.query.order_by(Category.name).all(),
        states=State.query.order_by(State.id).all(),
        name=current_user.name,
        from_user={},
        r=db.session.query(Repair).filter_by(display_id=repair_id).first(),
        current_session=current_session,
    )


@main.route("/del/<string:repair_id>")
@login_required
def del_repair(repair_id):
    """Suppression d'une fiche réparation."""
    db.session.query(Repair).filter_by(display_id=repair_id).delete()
    db.session().commit()
    return redirect(url_for("main.index"), code=302)


## Anciennes fonctions déplacées dans services/repair_service.py


@main.route("/new", methods=["POST"])
@login_required
def post_object():
    """Création ou modification d'une réparation (POST)."""
    rid = request.form.get("rid")
    try:
        category_id = request.form["category"]
        initial_state_id = request.form["initial_state"]
        brand_name = request.form["brand"]
    except KeyError:
        return "Champs requis manquants", 400
    category = db.session.query(Category).filter_by(id=category_id).first()
    initial_state = db.session.query(State).filter_by(id=initial_state_id).first()
    brand = get_or_create_brand(db.session, brand_name)
    if not rid:
        r = create_repair(db.session, request.form, category, initial_state, brand)
    else:
        r = db.session.query(Repair).filter_by(id=rid).first()
        r = update_repair(db.session, r, request.form, category, initial_state, brand)
    # Attache à la session ouverte (si une session où l'utilisateur est participant et non close)
    if not rid:
        open_session = (
            db.session.query(Session)
            .join(Session.participants)
            .filter(User.id == current_user.id, Session.closed_at.is_(None))
            .order_by(Session.opened_at.desc())
            .first()
        )
        if open_session:
            r.session = open_session
    db.session.commit()

    return redirect(url_for("main.update_object", id=r.display_id), code=302)


@main.route("/repairs")
@login_required
def repairs_home():
    """Ancienne page d'accueil listant les fiches (déplacée)."""
    return render_template(
        "index.html",
        name=current_user.name,
        categories=Category.query.order_by(Category.name).all(),
        users=User.query.order_by(User.name).all(),
    )


@main.route("/attach_session/<string:repair_id>", methods=["POST"])
@login_required
def attach_session(repair_id):
    """Rattache une réparation à la séance ouverte où l'utilisateur est participant.

    Confirmation utilisateur gérée côté JS (pas ici).
    Si aucune séance ouverte ou déjà rattachée à cette séance -> retour immédiat.
    """
    repair = db.session.query(Repair).filter_by(display_id=repair_id).first()
    if not repair:
        return redirect(url_for("main.index"))
    open_session = (
        db.session.query(Session)
        .join(Session.participants)
        .filter(User.id == current_user.id, Session.closed_at.is_(None))
        .order_by(Session.opened_at.desc())
        .first()
    )
    if not open_session or repair.session_id == open_session.id:
        return redirect(url_for("main.edit_repair", repair_id=repair_id))
    previous = repair.session_id
    repair.session = open_session
    db.session.add(
        Log(
            user_id=current_user.id,
            repair=repair,
            content=(
                ("Rattachée à la séance %s" % open_session.id)
                if not previous
                else ("Changement de séance → %s" % open_session.id)
            ),
        )
    )
    db.session.commit()
    return redirect(url_for("main.edit_repair", repair_id=repair_id))


@main.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Servez un fichier uploadé (original ou vignette cache/...)."""
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


# Route legacy conservée (redirection permanente) pour compatibilité anciens liens
@main.route("/media/<path:filename>")
def legacy_media_file(filename):  # pragma: no cover - simple redirection
    from flask import redirect

    return redirect(url_for("main.uploaded_file", filename=filename), code=301)


@main.route("/update/<string:id>", methods=["POST"])
@login_required
def update_object(id):
    r"""post update on an object"""
    r = db.session.query(Repair).filter_by(display_id=id).first()
    if request.method == "POST":
        if apply_update(db.session, r, request.form):
            db.session.commit()
    return redirect(url_for("main.get_update", id=r.display_id), code=302)


@main.route("/update/<string:id>", methods=["GET"])
@login_required
def get_update(id):
    r"""update page for an object"""
    r = db.session.query(Repair).filter_by(display_id=id).first()
    # séance ouverte courante (si existe)
    current_session = (
        db.session.query(Session)
        .filter(Session.closed_at.is_(None))
        .order_by(Session.opened_at.desc())
        .first()
    )
    # get image list
    images = glob.glob(os.path.join(current_app.config["UPLOAD_FOLDER"], id + "_*"))
    images_idx = []
    for p in images:
        images_idx.append(
            (
                len(images_idx),
                p.split("/")[-1],
                "cache/" + thumb.get_thumbnail(p.split("/")[-1], "200x200").split("/")[-1],
            )
        )
    return render_template(
        "update.html",
        name=current_user.name,
        categories=Category.query.order_by(Category.name).all(),
        states=State.query.order_by(State.id).all(),
        users=User.query.order_by(User.name).all(),
        notes=db.session.query(Note, Notification)
        .filter_by(repair=r)
        .order_by(Note.id.desc())
        .outerjoin(
            Notification,
            and_(Notification.note_id == Note.id, Notification.user_id == current_user.id),
        ),
        logs=Log.query.filter_by(repair=r).order_by(Log.id.desc()),
        r=r,
        current_session_id=current_session.id if current_session else None,
        current_users=[u.id for u in r.users],
        closestatus=CloseStatus.query.order_by(CloseStatus.id).all(),
        images=images_idx,
        splist=SpareChange.query.filter_by(repair=r).order_by(SpareChange.id.asc()),
        spare_statuses=SpareStatus.query.order_by(SpareStatus.id).all(),
    )


@main.route("/sessions")
@login_required
def sessions_page():
    """Page listant les séances récentes avec filtre lieu (param ?lieu=)."""
    q = db.session.query(Session)
    lieu = request.args.get("lieu")
    if lieu:
        from .models import Location

        q = q.join(Location).filter(Location.name == lieu)
    # Ouvertes d'abord (closed_at NULL), puis par date d'ouverture décroissante
    from sqlalchemy import case

    q = q.order_by(case((Session.closed_at.is_(None), 0), else_=1), Session.opened_at.desc())
    sessions = q.limit(200).all()
    # Liste des lieux distincts pour filtre
    try:
        from .models import Location

        lieux = [loc.name for loc in db.session.query(Location).order_by(Location.name.asc()).all()]
    except Exception:  # pragma: no cover - fallback si table absente en migration
        lieux = []
    # Prépare les dates (jour local) où il y a eu ouverture de séance pour affichage calendrier
    session_days = []
    for s in sessions:
        if s.opened_at:
            d = s.opened_at.date().isoformat()
            if d not in session_days:
                session_days.append(d)
    return render_template(
        "sessions.html",
        name=current_user.name,
        sessions=sessions,
        lieux=lieux,
        lieu_actif=lieu,
        session_days=session_days,
    )


@main.route("/sessions/<int:session_id>")
@login_required
def session_detail(session_id):
    s = db.session.query(Session).filter_by(id=session_id).first()
    if not s:
        return redirect(url_for("main.sessions_page"))
    # Bouton "Maintenant" seulement si la séance est encore ouverte ET même jour local d'ouverture
    show_now_button = False
    if s and not s.closed_at and s.opened_at:
        try:
            # Convertit en fuseau Europe/Paris si naïf
            opened_dt = s.opened_at
            if opened_dt.tzinfo is None:
                opened_dt = LOCAL_TIMEZONE.localize(opened_dt)
            today_paris = datetime.now(LOCAL_TIMEZONE).date()
            show_now_button = opened_dt.astimezone(LOCAL_TIMEZONE).date() == today_paris
        except Exception:
            show_now_button = False
    return render_template(
        "session_detail.html",
        name=current_user.name,
        session=s,
        participants=s.participants,
        show_now_button=show_now_button,
        all_users=User.query.order_by(User.name.asc()).all(),
    )


@main.route("/trombinoscope")
def trombinoscope():
    """Page publique listant les réparateurs (trombinoscope).

    Première ligne : membres du bureau (ordre défini) avec titre et nom séparés.
    Lignes suivantes : autres membres (utilisateurs sans rôle de bureau).
    Accessible sans authentification.
    """
    # Récupère tous les utilisateurs
    all_users = db.session.query(User).all()
    # Sépare bureau / autres
    board = [u for u in all_users if u.board_title]
    others = [u for u in all_users if not u.board_title]
    # Ordre personnalisé des rôles de bureau
    # Ordre demandé: 1 président, 2 trésorier, 3 secrétaire, 4 vice-présidents
    order = [
        "président",
        "president",
        "trésorier",
        "tresorier",
        "trésorière",
        "tresoriere",
        "secrétaire",
        "secretaire",
        "vice-président",
        "vice president",
        "vice-présidente",
        "vice-presidents",
        "vice-présidents",
    ]

    def board_key(u):
        bt = (u.board_title or "").lower()
        try:
            return (order.index(bt), bt)
        except ValueError:
            return (len(order), bt)

    board.sort(key=board_key)
    others.sort(key=lambda u: (u.name or "").lower())
    return render_template(
        "trombinoscope.html",
        board=board,
        others=others,
        name=current_user.name if current_user.is_authenticated else None,
    )
