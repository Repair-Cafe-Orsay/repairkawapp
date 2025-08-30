"""Module API de RepairKawapp.

RepairKawapp – Repair Café management application
Licence: MIT (voir fichier LICENSE)
Auteur principal: Jean Senellart

Nettoyage global : imports organisés, PEP8, docstrings, harmonisation du style.
"""

import glob
import os
from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required
from flask_mail import Message
from werkzeug.utils import secure_filename

from . import db, mail
from .models import (
    Brand,
    Location,
    Notification,
    NotificationType,
    Repair,
    Session as SessionModel,
    SpareStatus,
    User,
)
from .services.session_service import (
    change_session_owner,
    close_session,
    join_session,
    leave_session,
    open_session,
    reopen_session,
    session_stats,
    update_session_details,
)
from .services.spare_service import add_spare, delete_spare
from .services.stats_service import compute_stats, get_cached_lists, parse_period

api = Blueprint("api", __name__)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
    )


@api.route("/new_spare/<string:repair_id>")
@login_required
def new_spare(repair_id):
    """Ajout d'une pièce détachée à une réparation (service)."""
    sp, log_entry = add_spare(
        db.session,
        repair_id,
        item=request.args.get("item"),
        status_id=int(request.args.get("status_id")),
        source=request.args.get("source"),
        note=request.args.get("note"),
    )
    db.session.commit()
    return jsonify(
        {
            "sparepart": render_template(
                "sparepart.html",
                sp=sp,
                spare_statuses=SpareStatus.query.order_by(SpareStatus.id).all(),
            ),
            "log": render_template("log.html", log=log_entry),
        }
    )


@api.route("/del_spare/<string:repair_id>")
@login_required
def del_spare(repair_id):
    """Suppression d'une pièce détachée d'une réparation (service)."""
    delete_spare(db.session, int(request.args.get("id")))
    db.session.commit()
    return jsonify(True)


@api.route("/api/brandsearch", methods=["GET"])
def brandsearch():
    """Recherche dynamique de marque (insensible à la casse)."""
    search = request.args.get("q")
    query = db.session.query(Brand.name).filter(Brand.name.like(str(search) + "%"))
    results = [mv[0] for mv in query.all()]
    return jsonify(matching_results=results)


@api.route("/api/brands", methods=["GET"])
def api_brands():
    """Liste de marques (préfixe optionnel) max 50 résultats triés alpha.

    Utilise ILIKE si disponible, sinon LIKE (collation DB pour insensibilité).
    """
    q = (request.args.get("q") or "").strip()
    query = db.session.query(Brand)
    if q:
        like = f"{q}%"
        try:
            query = query.filter(Brand.name.ilike(like))  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - fallback si SGBD ne supporte pas ILIKE
            query = query.filter(Brand.name.like(like))
    names = [b.name for b in query.order_by(Brand.name.asc()).limit(50).all()]
    return jsonify(names)


@api.route("/deleteimg/<string:repair_id>/<path:path>", methods=["GET"])
@login_required
def del_file(repair_id, path):
    """Suppression d'une image attachée à une réparation."""
    filename = os.path.join(current_app.config["UPLOAD_FOLDER"], path)
    if os.path.exists(filename):
        os.remove(filename)
    fileprefix = ".".join(path.split(".")[:-1])
    for f in glob.glob(
        os.path.join(current_app.config["THUMBNAIL_MEDIA_THUMBNAIL_ROOT"], fileprefix + "*.*")
    ):
        os.remove(f)
    return jsonify(True)


@api.route("/uploadimg/<string:repair_id>", methods=["POST"])
@login_required
def post_file(repair_id):
    r"""post an image"""
    file = request.files.get("file")
    if file:
        if allowed_file(file.filename):
            filename = os.path.join(
                current_app.config["UPLOAD_FOLDER"],
                repair_id + "_" + secure_filename(file.filename),
            )
            if os.path.exists(filename):
                return jsonify("existing file"), 409
            file.save(filename)
            return jsonify(filename.split("/")[-1])
        else:
            return jsonify("unauthorized file"), 403
    return jsonify(None)


@api.route("/api/add_todo")
def add_todo():
    r"""add a notification"""
    note_id = request.args.get("note_id")
    if not note_id:
        return jsonify(False), 500
    existing_notification = (
        Notification.query.filter_by(note_id=note_id).filter_by(user_id=current_user.id).count()
    )
    if existing_notification:
        return jsonify(False), 500

    notification = Notification(
        note_id=note_id,
        user_id=current_user.id,
        notification_type=NotificationType.todo,
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify(notification.id)


@api.route("/api/del_notification")
def del_notification():
    r"""remove a notification"""
    notification_id = request.args.get("notification_id")
    Notification.query.filter_by(id=notification_id).delete()
    db.session.commit()

    return jsonify(None)


@api.route("/api/get_notifs")
@login_required
def get_notifs():
    """Retourne le fragment HTML listant les notifications de l'utilisateur courant.

    Nécessaire pour les appels AJAX dans base.html (bouton notifications).
    """
    notifs = (
        Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).all()
    )
    return render_template("notif_list.html", notifs=notifs)


@api.route("/api/get_notifcount")
@login_required
def get_notifcount():
    """Compte simple des notifications de l'utilisateur courant.

    Utilisé par le JS pour afficher/masquer le badge de notification.
    """
    count = Notification.query.filter_by(user_id=current_user.id).count()
    return jsonify(count)


@api.route("/api/repairsearch")
def repairsearch():
    r"""Recherche paginée des réparations."""
    length = request.args.get("length", current_app.config.get("PAGE_SIZE", 25), type=int)
    page = (request.args.get("start", 0, type=int) / length) + 1
    searchValue = request.args.get("search[value]")
    repairs = Repair.query
    status = request.args.get("status")
    if status != "all":
        if status == "opened":
            repairs = repairs.filter_by(close_status_id=1)
        else:
            repairs = repairs.filter(Repair.close_status_id > 1)
    user = request.args.get("user")
    if user:
        if int(user):
            repairs = repairs.join(User, Repair.users).filter_by(id=int(user))
        else:
            repairs = repairs.outerjoin(User, Repair.users).filter(User.id.is_(None))
    if searchValue:
        repairs = repairs.join(Brand)
        repairs = repairs.filter(
            Repair.display_id.like(searchValue + "%")
            | Repair.name.like("%" + searchValue + "%")
            | Repair.otype.like("%" + searchValue + "%")
            | Brand.name.like(searchValue + "%")
        )
    if request.args.get("category"):
        repairs = repairs.filter_by(category_id=request.args.get("category"))
    session_id = request.args.get("session_id") or request.args.get("session")
    if session_id:
        try:
            sid_int = int(session_id)
            repairs = repairs.filter(Repair.session_id == sid_int)
        except ValueError:
            # ignore invalid session id (no filter applied)
            pass
    nbFiltered = repairs.count()
    repairs = repairs.order_by(Repair.display_id.desc()).paginate(
        page=page, per_page=length, error_out=False
    )
    json = jsonify(
        {
            "repairs": [
                {
                    "id": r.display_id,
                    "name": r.name,
                    "category": r.category.name,
                    "otype": r.otype,
                    "brand": r.brand and r.brand.name or "",
                    "close_status": r.close_status.label[0],
                }
                for r in repairs.items
            ],
            "draw": request.args.get("draw", 1, type=int),
            "recordsTotal": db.session.query(Repair).count(),
            "recordsFiltered": nbFiltered,
            "has_next": repairs.has_next,
            "has_prev": repairs.has_prev,
            "next_num": repairs.next_num,
            "prev_num": repairs.prev_num,
        }
    )
    return json


# caches
all_categories = []
all_status = []


@api.route("/api/stats")
def stats():
    r"""API stats refactorisée via service."""
    date_from, date_to = parse_period(request.args.get("from"), request.args.get("to"))
    if not date_from:
        return {}
    global all_categories, all_status
    get_cached_lists(db.session, all_categories, all_status)
    stats_raw = compute_stats(db.session, date_from, date_to)
    return jsonify(
        {
            "from": date_from,
            "to": date_to,
            "categories": all_categories,
            "status": all_status,
            "count_by_status": {
                id: [status, count] for (count, id, status) in stats_raw["status_raw"]
            },
            "count_by_category": {
                category: (count, icon_id)
                for (category, count, icon_id) in stats_raw["categories_raw"]
            },
            "visitors": stats_raw["visitors"],
            "total": stats_raw["total"],
            "total_sessions": stats_raw.get("total_sessions", 0),
        }
    )


@api.route("/sendmail")
def sendmail():
    msg = Message(
        "Hello",
        sender="app@repaircafe-orsay.org",
        recipients=["jean@repaircafe-orsay.org"],
    )
    msg.body = "Hello Flask message sent from Flask-Mail"
    mail.send(msg)
    return jsonify(True)


# -------------------- Sessions --------------------


@api.route("/api/session/open", methods=["POST"])
@login_required
def api_session_open():
    payload = request.get_json(silent=True) or {}
    location = payload.get("location") or request.form.get("location")
    opened_time = payload.get("opened_time") or request.form.get("opened_time")  # HH:MM locale
    try:
        manual_opened_at = None
        if opened_time:
            try:
                from datetime import time as dtime

                import pytz

                hh, mm = opened_time.split(":", 1)
                hh = int(hh)
                mm = int(mm)
                today_local = datetime.now(pytz.timezone("Europe/Paris")).date()
                naive_local = datetime.combine(today_local, dtime(hh, mm))
                tz = pytz.timezone("Europe/Paris")
                local_dt = tz.localize(naive_local)
                manual_opened_at = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            except Exception:
                return jsonify({"error": "invalid opened_time"}), 400
        # Réutilisation rapide (contourne bug constaté dans service) : même lieu, ouverte, même jour
        if location and location.strip():
            loc_obj = db.session.query(Location).filter_by(name=location.strip()).first()
            if loc_obj:
                from .models import Session as SessionModel

                existing = (
                    db.session.query(SessionModel)
                    .filter(SessionModel.closed_at.is_(None))
                    .filter(SessionModel.location_id == loc_obj.id)
                    .order_by(SessionModel.opened_at.asc())
                    .first()
                )
                if existing and existing.opened_at.date() == datetime.utcnow().date():
                    # Ajouter participant si absent
                    if current_user not in existing.participants:
                        existing.participants.append(current_user)
                    s = existing
                else:
                    s = open_session(db.session, location, opened_at=manual_opened_at)
            else:
                s = open_session(db.session, location, opened_at=manual_opened_at)
        else:
            s = open_session(db.session, location, opened_at=manual_opened_at)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    db.session.commit()
    opened_iso = s.opened_at.isoformat() + "Z"
    return jsonify(
        {
            "id": s.id,
            "location": s.location and s.location.name,
            "opened_at": opened_iso,
        }
    )


@api.route("/api/session/join/<int:session_id>", methods=["POST"])
@login_required
def api_session_join(session_id):
    s = join_session(db.session, session_id)
    if not s:
        return jsonify(False), 404
    db.session.commit()
    return jsonify({"id": s.id, "participants": [u.id for u in s.participants]})


@api.route("/api/session/leave/<int:session_id>", methods=["POST"])
@login_required
def api_session_leave(session_id):
    s = leave_session(db.session, session_id)
    if not s:
        return jsonify(False), 404
    db.session.commit()
    return jsonify({"id": s.id, "participants": [u.id for u in s.participants]})


@api.route("/api/session/close/<int:session_id>", methods=["POST"])
@login_required
def api_session_close(session_id):
    payload = request.get_json(silent=True) or {}
    comment = payload.get("comment") or request.form.get("comment")
    closed_time = payload.get("closed_time") or request.form.get(
        "closed_time"
    )  # format HH:MM (heure locale)
    s = db.session.query(SessionModel).filter_by(id=session_id).first()
    if not s:
        return jsonify(False), 404
    if s.closed_at:
        current_app.logger.debug("close_session %s refused: already closed", session_id)
        return jsonify({"error": "already closed"}), 400
    if current_user.id != s.owner_id and not current_user.admin:
        current_app.logger.debug(
            "close_session %s forbidden user=%s owner=%s",
            session_id,
            current_user.id,
            s.owner_id,
        )
        return jsonify({"error": "forbidden"}), 403
    # Validation commentaire: obligatoire >=4 caractères (nouveau ou déjà existant)
    effective_comment = (comment or s.comment or "").strip() if comment or s.comment else ""
    if len(effective_comment) < 4:
        current_app.logger.debug(
            "close_session %s comment too short (%s)", session_id, effective_comment
        )
        return jsonify({"error": "comment_too_short"}), 400
    manual_closed_at = None
    if closed_time:
        try:
            from datetime import time as dtime

            import pytz

            ct = closed_time.strip().lower().replace("h", ":")
            if ":" not in ct:
                ct = ct + ":00"
            parts = ct.split(":")
            if len(parts) < 2:
                parts.append("00")
            hh = int(parts[0])
            mm = int(parts[1])
            if not (0 <= hh < 24 and 0 <= mm < 60):
                raise ValueError("out_of_range")
            opened_day = s.opened_at.date()
            naive_local = datetime.combine(opened_day, dtime(hh, mm))
            tz = pytz.timezone("Europe/Paris")
            local_dt = tz.localize(naive_local)
            manual_closed_at = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
        except Exception as e:
            current_app.logger.debug(
                'close_session %s invalid time "%s": %s', session_id, closed_time, e
            )
            return jsonify({"error": "invalid_closed_time_format"}), 400
    # Utiliser le commentaire effectif si aucun nouveau fourni
    s = close_session(
        db.session, session_id, comment=comment or s.comment, closed_at=manual_closed_at
    )
    current_app.logger.debug(
        "close_session %s success closed_at=%s comment_len=%d",
        session_id,
        s.closed_at,
        len(s.comment or ""),
    )
    db.session.commit()
    return jsonify(
        {
            "id": s.id,
            "closed_at": s.closed_at and (s.closed_at.isoformat() + "Z"),
            "comment": s.comment,
        }
    )


@api.route("/api/session/reopen/<int:session_id>", methods=["POST"])
@login_required
def api_session_reopen(session_id):
    s = db.session.query(SessionModel).filter_by(id=session_id).first()
    if not s:
        return jsonify(False), 404
    if not s.closed_at:
        return jsonify({"error": "not closed"}), 400
    if current_user.id != s.owner_id and not current_user.admin:
        return jsonify({"error": "forbidden"}), 403
    s = reopen_session(db.session, session_id)
    db.session.commit()
    return jsonify({"id": s.id, "closed_at": None})


@api.route("/api/session/owner/<int:session_id>", methods=["POST"])
@login_required
def api_session_change_owner(session_id):
    payload = request.get_json(silent=True) or {}
    new_owner_id = payload.get("owner_id") or request.form.get("owner_id")
    if not new_owner_id:
        return jsonify(False), 400
    s = db.session.query(SessionModel).filter_by(id=session_id).first()
    if not s:
        return jsonify(False), 404
    # seuls participants peuvent prendre la main
    s = change_session_owner(db.session, session_id, int(new_owner_id))
    if not s:
        return jsonify({"error": "forbidden"}, 403)
    db.session.commit()
    return jsonify({"id": s.id, "owner_id": s.owner_id})


@api.route("/api/session/update/<int:session_id>", methods=["POST"])
@login_required
def api_session_update(session_id):
    payload = request.get_json(silent=True) or request.form
    s = db.session.query(SessionModel).filter_by(id=session_id).first()
    if not s:
        return jsonify(False), 404
    if current_user.id != s.owner_id and not current_user.admin:
        return jsonify({"error": "forbidden"}), 403
    s = update_session_details(
        db.session,
        session_id,
        location=payload.get("location"),
        comment=payload.get("comment"),
        participants=payload.get("participants"),
    )
    db.session.commit()
    return jsonify({"id": s.id, "location": s.location and s.location.name, "comment": s.comment})


@api.route("/api/session/<int:session_id>", methods=["GET"])
@login_required
def api_session_detail(session_id):
    stats = session_stats(db.session, session_id)
    if not stats:
        return jsonify(False), 404
    return jsonify(stats)


@api.route("/api/session/delete/<int:session_id>", methods=["DELETE"])
@login_required
def api_session_delete(session_id):
    from .services.session_service import delete_session as _del

    ok = _del(db.session, session_id)
    if not ok:
        return jsonify(False), 400
    db.session.commit()
    return jsonify(True)


@api.route("/api/sessions", methods=["GET"])
@login_required
def api_sessions_list():
    opened_only = request.args.get("opened") == "1"
    from .models import Session as SessionModel  # import tardif pour éviter cycle

    sessions_q = db.session.query(SessionModel)
    if opened_only:
        sessions_q = sessions_q.filter(SessionModel.closed_at.is_(None))
    sessions = sessions_q.order_by(SessionModel.opened_at.desc()).limit(100).all()
    return jsonify(
        [
            {
                "id": s.id,
                "location": ((s.location and s.location.name) if hasattr(s, "location") else None),
                "opened_at": (s.opened_at.isoformat() + "Z") if s.opened_at else None,
                "closed_at": (s.closed_at.isoformat() + "Z") if s.closed_at else None,
                "owner_id": s.owner_id,
                "participants": [u.id for u in s.participants],
                "nb_repairs": len(s.repairs),
            }
            for s in sessions
        ]
    )


@api.route("/api/locations", methods=["GET"])
@login_required
def api_locations():
    """Liste (option filtrée) des lieux existants pour autocomplétion."""
    q = request.args.get("q")
    query = db.session.query(Location)
    if q:
        like = f"{q}%"
        query = query.filter(Location.name.like(like))
    names = [loc.name for loc in query.order_by(Location.name.asc()).limit(50).all()]
    return jsonify(names)


# -------------------- Object Types --------------------


@api.route("/api/objecttypes", methods=["GET"])
@login_required
def api_objecttypes_search():
    """Recherche des ObjectType (nom ou variantes) – retourne 50 max.

    Paramètres:
      q: préfixe (insensible à la casse) – facultatif (sinon tout, limité)
    Réponse: liste de dicts {id,name,category_id,category_name,has_subtypes}
    """
    from .models import Category, ObjectType, ObjectVariant  # import tardif

    q = (request.args.get("q") or "").strip()
    query = db.session.query(ObjectType).join(Category)
    if q:
        like = f"{q}%"
        # jointure externe aux variantes pour matcher sur leurs noms aussi
        query = query.outerjoin(ObjectVariant).filter(
            (ObjectType.name.ilike(like))  # type: ignore[attr-defined]
            | (ObjectVariant.name.ilike(like))  # type: ignore[attr-defined]
        )
    # Limite de sécurité
    results = query.order_by(ObjectType.name.asc()).limit(50).all() if not q or len(q) < 100 else []
    # Pré-chargement subtypes pour indicateur (évite N requêtes) via relationship déjà lazy
    out = []
    for ot in results:
        has_subtypes = bool(getattr(ot, "subtypes", []))
        out.append(
            {
                "id": ot.id,
                "name": ot.name,
                "category_id": ot.category_id,
                "category_name": ot.category.name,
                "has_subtypes": has_subtypes,
            }
        )
    return jsonify(out)


@api.route("/api/objecttype/<int:ot_id>", methods=["GET"])
@login_required
def api_objecttype_detail(ot_id: int):
    """Détail d'un ObjectType (catégorie + sous-types)."""
    from .models import ObjectType  # import tardif

    ot = db.session.query(ObjectType).filter_by(id=ot_id).first()
    if not ot:
        return jsonify({}), 404
    subtypes = [
        {"id": st.id, "name": st.name} for st in sorted(ot.subtypes, key=lambda s: s.name.lower())
    ]
    return jsonify(
        {
            "id": ot.id,
            "name": ot.name,
            "category": {"id": ot.category_id, "name": ot.category.name},
            "subtypes": subtypes,
        }
    )
