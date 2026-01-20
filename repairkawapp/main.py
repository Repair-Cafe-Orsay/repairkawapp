"""Module principal de l'application RepairKawapp (routes principales).

RepairKawapp – Repair Café management application
Licence: MIT (voir fichier LICENSE)
Auteur principal: Jean Senellart

Nettoyage global : imports organisés, PEP8, docstrings, suppression des répétitions.
"""

import glob
import hashlib
import os
from datetime import date, datetime

import pytz
from flask import (
    Blueprint,
    Response,
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
    Brand,
    Category,
    CloseStatus,
    Log,
    Note,
    Notification,
    Repair,
    RepairCafe,
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
from .services.tenant_service import (
    ensure_cafe_upload_folder,
    get_active_repaircafe,
    get_cafe_upload_folder,
    get_cafe_upload_relative_path,
    get_upload_prefix,
    get_user_cafe_photo,
    is_cafe_admin,
    require_active_repaircafe,
    set_user_cafe_photo,
)

main = Blueprint("main", __name__)
LOCAL_TIMEZONE = pytz.timezone("Europe/Paris")


def _pastel_color_for(name: str) -> str:
    """Retourne une couleur vive (mais douce) hex stable dérivée du nom.

    HSL choisi pour meilleure lisibilité dans de très petites pastilles :
    S=65%, L=60% (contre 40/75 auparavant trop délavé).
    Hue = hash(name) % 360.
    """
    if not name:
        return "#cccccc"
    hval = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:8], 16)
    h = hval % 360
    s = 0.65
    light = 0.60
    c = (1 - abs(2 * light - 1)) * s
    hp = h / 60.0
    x = c * (1 - abs(hp % 2 - 1))
    if 0 <= hp < 1:
        r1, g1, b1 = c, x, 0
    elif 1 <= hp < 2:
        r1, g1, b1 = x, c, 0
    elif 2 <= hp < 3:
        r1, g1, b1 = 0, c, x
    elif 3 <= hp < 4:
        r1, g1, b1 = 0, x, c
    elif 4 <= hp < 5:
        r1, g1, b1 = x, 0, c
    else:
        r1, g1, b1 = c, 0, x
    m = light - c / 2
    r, g, b = (int(round(255 * (v + m))) for v in (r1, g1, b1))
    return f"#{r:02x}{g:02x}{b:02x}"


def _location_color(loc) -> str:
    """Couleur pour un objet Location en fonction de son id (répartition uniforme).

    Utilise l'angle d'or (~137.508°) pour espacer les teintes afin d'éviter
    les couleurs proches pour les ids consécutifs. Saturation/Luminosité comme
    les pastilles vives (S=65%, L=60%).
    """
    try:
        lid = getattr(loc, "id", None)
        name = getattr(loc, "name", "") or "?"
        if lid is None:
            # fallback sur hash du nom si id encore absent (cas migration)
            return _pastel_color_for(name)
        golden = 137.508
        h = (lid * golden) % 360
        s = 0.65
        light = 0.60
        c = (1 - abs(2 * light - 1)) * s
        hp = h / 60.0
        x = c * (1 - abs(hp % 2 - 1))
        if 0 <= hp < 1:
            r1, g1, b1 = c, x, 0
        elif 1 <= hp < 2:
            r1, g1, b1 = x, c, 0
        elif 2 <= hp < 3:
            r1, g1, b1 = 0, c, x
        elif 3 <= hp < 4:
            r1, g1, b1 = 0, x, c
        elif 4 <= hp < 5:
            r1, g1, b1 = x, 0, c
        else:
            r1, g1, b1 = c, 0, x
        m = light - c / 2
        r, g, b = (int(round(255 * (v + m))) for v in (r1, g1, b1))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:  # pragma: no cover
        return "#cccccc"


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
    """Page profil réparateur (dashboard + cotisation + présentation)."""
    today = date.today()
    current_start = _current_academic_start(today)
    last_start = current_user.last_membership
    last_membership_ok = last_start == current_start
    user_period = (last_start, last_start + 1) if last_start is not None else None
    photo_error = None
    active_cafe = get_active_repaircafe(current_user)
    if request.method == "POST":
        # Champs simples
        current_user.biography = request.form.get("biography") or None
        new_email = request.form.get("email") or ""
        if new_email and new_email != current_user.email:
            # Vérifie unicité basique
            exists = (
                db.session.query(User)
                .filter(User.email == new_email, User.id != current_user.id)
                .first()
            )
            if exists:
                photo_error = "Email déjà utilisé."
            else:
                current_user.email = new_email
        current_user.phone = request.form.get("phone") or None
        current_user.visibility_public_trombi = bool(request.form.get("visibility_public_trombi"))
        if "photo" in request.files and request.files["photo"].filename:
            active_cafe = require_active_repaircafe()
            raw = request.files["photo"].read()
            upload_dir = ensure_cafe_upload_folder(current_app.config["UPLOAD_FOLDER"], active_cafe)
            filename, err = process_user_photo(
                raw,
                upload_dir,
                current_user.id,
                request.form.get,
            )
            if err:
                photo_error = err
            else:
                set_user_cafe_photo(
                    current_user.id,
                    active_cafe.id,
                    get_cafe_upload_relative_path(active_cafe, filename),
                )
        db.session.commit()
        if not photo_error:
            return redirect(url_for("main.profile"))
    photo_filename = get_user_cafe_photo(current_user.id, active_cafe.id) if active_cafe else None
    return render_template(
        "profile.html",
        name=current_user.name,
        last_membership_ok=last_membership_ok,
        user_period=user_period,
        biography=current_user.biography,
        photo_filename=photo_filename,
        photo_error=photo_error,
    )


@main.route("/switch_cafe/<int:cafe_id>")
@login_required
def switch_cafe(cafe_id: int):
    """Switch active RepairCafe for the current user."""
    if getattr(current_user, "super_admin", False):
        return redirect(url_for("main.dashboard"))
    cafes = list(getattr(current_user, "repaircafes", []) or [])
    target = next((c for c in cafes if c.id == cafe_id), None)
    if not target:
        return redirect(url_for("main.dashboard"))
    current_user.active_repaircafe = target
    db.session.commit()
    return redirect(url_for("main.dashboard"))


@main.route("/new")
@login_required
def new_repair():
    """Formulaire de création d'une nouvelle réparation."""
    active_cafe = require_active_repaircafe()
    from_id = request.args.get("from_id")
    from_user = {}
    if from_id:
        r = (
            db.session.query(Repair)
            .filter_by(display_id=from_id)
            .filter(Repair.repaircafe_id == active_cafe.id)
            .first()
        )
        from_user = {"name": r.name, "email": r.email, "phone": r.phone, "age": r.age}
    current_session = (
        db.session.query(Session)
        .filter(Session.closed_at.is_(None))
        .filter(Session.repaircafe_id == active_cafe.id)
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
    active_cafe = require_active_repaircafe()
    current_session = (
        db.session.query(Session)
        .filter(Session.closed_at.is_(None))
        .filter(Session.repaircafe_id == active_cafe.id)
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
        r=(
            db.session.query(Repair)
            .filter_by(display_id=repair_id)
            .filter(Repair.repaircafe_id == active_cafe.id)
            .first()
        ),
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
    active_cafe = require_active_repaircafe()
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
        r = create_repair(
            db.session,
            request.form,
            category,
            initial_state,
            brand,
            repaircafe_id=active_cafe.id,
        )
    else:
        r = db.session.query(Repair).filter_by(id=rid).first()
        r = update_repair(db.session, r, request.form, category, initial_state, brand)
    if r and r.repaircafe_id is None:
        r.repaircafe = active_cafe
    # Attache à la session ouverte (si une session où le réparateur est participant et non close)
    if not rid:
        open_session = (
            db.session.query(Session)
            .join(Session.participants)
            .filter(
                User.id == current_user.id,
                Session.closed_at.is_(None),
                Session.repaircafe_id == active_cafe.id,
            )
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
    require_active_repaircafe()
    return render_template(
        "index.html",
        name=current_user.name,
        categories=Category.query.order_by(Category.name).all(),
        users=User.query.order_by(User.name).all(),
    )


@main.route("/repairs/download")
@login_required
def repairs_download():
    """Export CSV des réparations (respecte mêmes filtres query si présents)."""
    active_cafe = require_active_repaircafe()
    repairs = Repair.query.filter(Repair.repaircafe_id == active_cafe.id)
    status = request.args.get("status")
    if status and status != "all":
        if status == "opened":
            repairs = repairs.filter_by(close_status_id=1)
        else:
            repairs = repairs.filter(Repair.close_status_id > 1)
    user = request.args.get("user")
    if user:
        try:
            if int(user):
                repairs = repairs.join(User, Repair.users).filter_by(id=int(user))
        except ValueError:
            pass
    session_id = request.args.get("session_id") or request.args.get("session")
    if session_id:
        try:
            repairs = repairs.filter(Repair.session_id == int(session_id))
        except ValueError:
            pass
    # Recherche texte simple (reprend champs principaux)
    searchValue = request.args.get("q") or request.args.get("search")
    if searchValue:
        from .models import ObjectType as OT

        repairs = repairs.join(Brand)
        repairs = repairs.outerjoin(OT, Repair.object_type_id == OT.id)
        like_any = f"%{searchValue}%"
        prefix = f"{searchValue}%"
        repairs = repairs.filter(
            Repair.display_id.like(prefix)
            | Repair.name.like(like_any)
            | Repair.otype.like(like_any)
            | Brand.name.like(prefix)
            | OT.name.like(like_any)
        )
    rows = repairs.order_by(Repair.display_id.desc()).limit(2000).all()
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Statut",
            "Catégorie",
            "Type",
            "Marque",
            "Visiteur",
            "Session",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.display_id,
                r.close_status.label if r.close_status else "",
                r.category.name if r.category else "",
                r.otype or (r.object_type and r.object_type.name) or "",
                r.brand.name if r.brand else "",
                r.name or "",
                r.session_id or "",
            ]
        )
    from datetime import datetime as _dt

    stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    resp = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename=repairs-{stamp}.csv"
    return resp


@main.route("/attach_session/<string:repair_id>", methods=["POST"])
@login_required
def attach_session(repair_id):
    """Rattache une réparation à la séance ouverte où le réparateur est participant.

    Confirmation réparateur gérée côté JS (pas ici).
    Si aucune séance ouverte ou déjà rattachée à cette séance -> retour immédiat.
    """
    active_cafe = require_active_repaircafe()
    repair = (
        db.session.query(Repair)
        .filter_by(display_id=repair_id)
        .filter(Repair.repaircafe_id == active_cafe.id)
        .first()
    )
    if not repair:
        return redirect(url_for("main.index"))
    open_session = (
        db.session.query(Session)
        .join(Session.participants)
        .filter(
            User.id == current_user.id,
            Session.closed_at.is_(None),
            Session.repaircafe_id == active_cafe.id,
        )
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
            repaircafe_id=repair.repaircafe_id,
        )
    )
    db.session.commit()
    return redirect(url_for("main.edit_repair", repair_id=repair_id))


@main.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Servez un fichier uploadé (original ou vignette cache/...)."""
    upload_root = current_app.config["UPLOAD_FOLDER"]
    active_cafe = None
    try:
        active_cafe = get_active_repaircafe(current_user)
    except Exception:
        active_cafe = None
    prefix = get_upload_prefix(active_cafe)
    # Si un préfixe est attendu, on empêche l'accès aux autres cafés.
    if prefix and not filename.startswith(prefix + "/"):
        return ("", 404)
    return send_from_directory(upload_root, filename)


# Route legacy conservée (redirection permanente) pour compatibilité anciens liens
@main.route("/media/<path:filename>")
def legacy_media_file(filename):  # pragma: no cover - simple redirection
    from flask import redirect

    return redirect(url_for("main.uploaded_file", filename=filename), code=301)


@main.route("/update/<string:id>", methods=["POST"])
@login_required
def update_object(id):
    r"""post update on an object"""
    active_cafe = require_active_repaircafe()
    r = (
        db.session.query(Repair)
        .filter_by(display_id=id)
        .filter(Repair.repaircafe_id == active_cafe.id)
        .first()
    )
    if request.method == "POST":
        if apply_update(db.session, r, request.form):
            db.session.commit()
    return redirect(url_for("main.get_update", id=r.display_id), code=302)


@main.route("/update/<string:id>", methods=["GET"])
@login_required
def get_update(id):
    r"""update page for an object"""
    active_cafe = require_active_repaircafe()
    r = (
        db.session.query(Repair)
        .filter_by(display_id=id)
        .filter(Repair.repaircafe_id == active_cafe.id)
        .first()
    )
    # séance ouverte courante (si existe)
    current_session = (
        db.session.query(Session)
        .filter(Session.closed_at.is_(None))
        .filter(Session.repaircafe_id == active_cafe.id)
        .order_by(Session.opened_at.desc())
        .first()
    )
    # get image list
    upload_root = current_app.config["UPLOAD_FOLDER"]
    prefix = get_upload_prefix(active_cafe)
    cafe_upload_dir = get_cafe_upload_folder(upload_root, active_cafe)
    images = glob.glob(os.path.join(cafe_upload_dir, id + "_*"))
    images_idx = []
    for p in images:
        base = os.path.basename(p)
        rel = f"{prefix}/{base}" if prefix else base
        thumb_url = thumb.get_thumbnail(rel, "200x200")
        thumb_prefix = current_app.config.get("THUMBNAIL_MEDIA_THUMBNAIL_URL", "/media/cache/")
        if thumb_url.startswith(thumb_prefix):
            thumb_rel = thumb_url[len(thumb_prefix) :].lstrip("/")
            thumb_rel = f"cache/{thumb_rel}"
        else:
            thumb_rel = "cache/" + thumb_url.split("/")[-1]
        images_idx.append((len(images_idx), rel, thumb_rel))
    # Restriction : si la fiche est rattachée à une séance, on limite les réparateurs
    # sélectionnables aux participants de cette séance (participants + owner).
    if r.session_id:
        session_obj = r.session  # relationship déjà chargée (lazy) si accès.
        allowed_ids = {u.id for u in session_obj.participants}
        allowed_ids.add(session_obj.owner_id)
        # On récupère uniquement ces réparateurs pour l'affichage (hors déjà sélectionnés).
        # Les réparateurs déjà associés (r.users) restent listés même s'ils ne
        # sont plus participants : on peut les retirer mais pas les réajouter.
        candidate_users = (
            User.query.filter(User.id.in_(allowed_ids)).order_by(User.name.asc()).all()
            if allowed_ids
            else []
        )
    else:
        from .models import user_repaircafe

        candidate_users = (
            User.query.join(user_repaircafe)
            .filter(user_repaircafe.c.repaircafe_id == active_cafe.id)
            .order_by(User.name.asc())
            .all()
        )

    return render_template(
        "update.html",
        name=current_user.name,
        current_user_id=current_user.id,
        categories=Category.query.order_by(Category.name).all(),
        states=State.query.order_by(State.id).all(),
        users=candidate_users,
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
    active_cafe = require_active_repaircafe()
    q = db.session.query(Session).filter(Session.repaircafe_id == active_cafe.id)
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
    day_colors = {}  # date iso -> set(colors)
    location_colors = {}
    for s in sessions:
        if s.opened_at:
            d = s.opened_at.date().isoformat()
            if d not in session_days:
                session_days.append(d)
            if s.location and s.location.name:
                col = location_colors.setdefault(s.location.name, _location_color(s.location))
                day_colors.setdefault(d, set()).add(col)
    # Sérialisation couleurs
    day_colors_serializable = [
        {"date": d, "colors": sorted(list(cols))} for d, cols in day_colors.items()
    ]
    return render_template(
        "sessions.html",
        name=current_user.name,
        sessions=sessions,
        lieux=lieux,
        lieu_actif=lieu,
        session_days=session_days,
        day_colors=day_colors_serializable,
        location_colors=location_colors,
    )


@main.route("/sessions/download")
@login_required
def sessions_download():
    """Export CSV des séances (mêmes filtres de lieu)."""
    q = db.session.query(Session)
    lieu = request.args.get("lieu")
    if lieu:
        from .models import Location

        q = q.join(Location).filter(Location.name == lieu)
    from sqlalchemy import case

    q = q.order_by(case((Session.closed_at.is_(None), 0), else_=1), Session.opened_at.desc())
    sessions = q.limit(500).all()
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Lieu",
            "Ouverture (UTC)",
            "Fermeture (UTC)",
            "Responsable",
            "Participants",
            "Nb fiches",
            "Commentaire",
        ]
    )
    for s in sessions:
        writer.writerow(
            [
                s.id,
                s.location.name if s.location else "",
                s.opened_at.isoformat(sep=" ") if s.opened_at else "",
                s.closed_at.isoformat(sep=" ") if s.closed_at else "",
                s.owner.name if s.owner else "",
                len(s.participants),
                len(s.repairs),
                (s.comment or "").replace("\n", " ")[:500],
            ]
        )
    from datetime import datetime as _dt

    stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    resp = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename=sessions-{stamp}.csv"
    return resp


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
    location_color = None
    location_colors = {}
    try:
        from .models import Location  # import local pour éviter circular

        all_locs = db.session.query(Location).order_by(Location.name.asc()).all()
        for loc in all_locs:
            if loc.name:
                location_colors[loc.name] = _location_color(loc)
        if s.location and s.location.name:
            location_color = location_colors.get(s.location.name) or _location_color(s.location)
    except Exception:  # pragma: no cover
        location_color = None
    return render_template(
        "session_detail.html",
        name=current_user.name,
        session=s,
        participants=s.participants,
        show_now_button=show_now_button,
        all_users=User.query.order_by(User.name.asc()).all(),
        location_color=location_color,
        location_colors=location_colors,
    )


@main.route("/trombinoscope")
def trombinoscope():
    """Page publique listant les réparateurs (trombinoscope).

    Première ligne : membres du bureau (ordre défini) avec titre et nom séparés.
    Lignes suivantes : autres membres (réparateurs sans rôle de bureau).
    Accessible sans authentification.
    """
    # Politique d'affichage :
    # - Public (non connecté) : uniquement réparateurs ayant opté pour l'affichage public
    # - Réparateur connecté non admin : idem (respect du choix de visibilité)
    # - Admin : tous les réparateurs (vue complète interne)
    from .models import RepairCafe, user_repaircafe

    active_cafe = get_active_repaircafe() if current_user.is_authenticated else None
    if not active_cafe:
        code = request.environ.get("REPAIRCAFE_CODE")
        if code:
            active_cafe = RepairCafe.query.filter_by(code=code).first()
    base_query = db.session.query(User)
    if active_cafe:
        base_query = base_query.join(user_repaircafe).filter(
            user_repaircafe.c.repaircafe_id == active_cafe.id
        )
    if (
        current_user.is_authenticated
        and active_cafe
        and is_cafe_admin(current_user, active_cafe.id)
    ):
        # Vue complète interne (pas de filtrage cotisation)
        all_users = base_query.all()
    else:
        # Filtrer visibilité publique
        visibility_query = base_query.filter(User.visibility_public_trombi.is_(True))
        users_visibles = visibility_query.all()
        if current_user.is_authenticated:
            # Connecté non admin: respecte visibilité, pas de filtre cotisation supplémentaire
            all_users = users_visibles
        else:
            # Public non connecté: exige cotisation année précédente,
            # courante ou N+1
            from datetime import date as _date

            today = _date.today()
            acad_start = today.year if today.month >= 9 else today.year - 1
            previous_acad = acad_start - 1
            next_acad = acad_start + 1
            allowed = {previous_acad, acad_start, next_acad}
            all_users = [u for u in users_visibles if u.last_membership in allowed]
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
    # Statuts pour badges (nouveau: jamais cotisé, ancien: cotisation < année précédente)
    from datetime import date as _date

    today = _date.today()
    acad_start = today.year if today.month >= 9 else today.year - 1
    previous_acad = acad_start - 1

    def classify(u):  # noqa: D401 simple helper
        if u.last_membership is None:
            return "nouveau"
        if u.last_membership < previous_acad:
            return "ancien"
        return "normal"

    annotated = [(u, classify(u)) for u in others]
    # Seuls les "anciens" vont à la fin; "nouveau" et "normal" restent triés ensemble.
    order_priority = {"normal": 0, "nouveau": 0, "ancien": 1}
    annotated.sort(key=lambda t: (order_priority[t[1]], (t[0].name or "").lower()))
    others = [u for u, _ in annotated]
    # Inclure aussi board dans map statut pour affichage badge éventuel
    status_map = {u.id: classify(u) for u in board}
    status_map.update({u.id: s for u, s in annotated})
    photo_map = {}
    if active_cafe and all_users:
        user_ids = [u.id for u in all_users]
        rows = (
            db.session.query(user_repaircafe.c.user_id, user_repaircafe.c.photo_filename)
            .filter(user_repaircafe.c.repaircafe_id == active_cafe.id)
            .filter(user_repaircafe.c.user_id.in_(user_ids))
            .all()
        )
        photo_map = {uid: photo for uid, photo in rows if photo}
    return render_template(
        "trombinoscope.html",
        board=board,
        others=others,
        status_map=status_map,
        photo_map=photo_map,
        active_cafe=active_cafe,
        active_repaircafe=active_cafe,
        name=current_user.name if current_user.is_authenticated else None,
    )


@main.route("/repaircafes")
def repaircafes_public():
    """Liste publique des Repair Cafés (pour accès au trombinoscope)."""
    cafes = RepairCafe.query.order_by(RepairCafe.name.asc()).all()
    return render_template("repaircafes_public.html", cafes=cafes)


@main.route("/help")
@login_required
def user_help():  # rétrocompatibilité -> redirection vers le guide d'utilisation
    from flask import redirect, url_for

    return redirect(url_for("docs.guide"), code=302)
