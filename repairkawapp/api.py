"""Endpoints API (JSON/AJAX) de RepairKawapp.

Ce fichier avait été corrompu (imports/blueprint supprimés). Restauration des
imports essentiels + création du blueprint `api`.
"""

from __future__ import annotations

import glob
import os
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from . import db, mail
from .models import (
    Brand,
    Category,
    Location,
    Message as MessageModel,
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
from .services.tenant_service import (
    ensure_cafe_upload_folder,
    filter_active_membership_or_founder,
    get_cafe_upload_relative_path,
    get_mail_sender,
    get_upload_prefix,
    is_cafe_admin,
    require_active_repaircafe,
)

try:  # mail peut ne pas être configuré en tests
    from flask_mail import Message as MailMessage
except Exception:  # pragma: no cover
    MailMessage = None  # type: ignore

api = Blueprint("api", __name__)


def _active_cafe():
    """Return the active RepairCafe for request-scoped filtering."""
    return require_active_repaircafe()


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
    active_cafe = _active_cafe()
    upload_root = current_app.config["UPLOAD_FOLDER"]
    prefix = get_upload_prefix(active_cafe)
    rel_path = path
    if prefix and not path.startswith(prefix + "/"):
        return jsonify(False), 403
    filename = os.path.join(upload_root, rel_path)
    if os.path.exists(filename):
        os.remove(filename)
    fileprefix = ".".join(rel_path.split(".")[:-1])
    for f in glob.glob(
        os.path.join(current_app.config["THUMBNAIL_MEDIA_THUMBNAIL_ROOT"], fileprefix + "*.*")
    ):
        os.remove(f)
    return jsonify(True)


@api.route("/uploadimg/<string:repair_id>", methods=["POST"])
@login_required
def post_file(repair_id):
    r"""post an image"""
    active_cafe = _active_cafe()
    file = request.files.get("file")
    if file:
        if allowed_file(file.filename):
            stored_filename = repair_id + "_" + secure_filename(file.filename)
            upload_dir = ensure_cafe_upload_folder(current_app.config["UPLOAD_FOLDER"], active_cafe)
            filename = os.path.join(upload_dir, stored_filename)
            if os.path.exists(filename):
                return jsonify("existing file"), 409
            file.save(filename)
            return jsonify(get_cafe_upload_relative_path(active_cafe, stored_filename))
        else:
            return jsonify("unauthorized file"), 403
    return jsonify(None)


@api.route("/api/add_todo")
def add_todo():
    r"""add a notification"""
    active_cafe = _active_cafe()
    note_id = request.args.get("note_id")
    if not note_id:
        return jsonify(False), 500
    existing_notification = (
        Notification.query.filter_by(note_id=note_id)
        .filter_by(user_id=current_user.id)
        .filter(Notification.repaircafe_id == active_cafe.id)
        .count()
    )
    if existing_notification:
        return jsonify(False), 500

    notification = Notification(
        note_id=note_id,
        user_id=current_user.id,
        repaircafe_id=active_cafe.id,
        notification_type=NotificationType.todo,
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify(notification.id)


@api.route("/api/del_notification")
def del_notification():
    r"""remove a notification"""
    active_cafe = _active_cafe()
    notification_id = request.args.get("notification_id")
    Notification.query.filter_by(id=notification_id).filter(
        Notification.repaircafe_id == active_cafe.id
    ).delete()
    db.session.commit()

    return jsonify(None)


@api.route("/api/get_notifs")
@login_required
def get_notifs():
    """Retourne le fragment HTML listant les notifications du réparateur courant.

    Nécessaire pour les appels AJAX dans base.html (bouton notifications).
    """
    active_cafe = _active_cafe()
    notifs = (
        Notification.query.filter_by(user_id=current_user.id)
        .filter(Notification.repaircafe_id == active_cafe.id)
        .order_by(Notification.id.desc())
        .all()
    )
    return render_template("notif_list.html", notifs=notifs)


@api.route("/api/notifs_debug")
@login_required
def notifs_debug():
    """Endpoint de debug JSON pour diagnostiquer l'affichage vide du dropdown.

    Fournit: count, entries (id, note_id, has_note, has_repair, repair_display_id, content_preview).
    """
    active_cafe = _active_cafe()
    rows = (
        Notification.query.filter_by(user_id=current_user.id)
        .filter(Notification.repaircafe_id == active_cafe.id)
        .order_by(Notification.id.desc())
        .all()
    )
    out = []
    for n in rows:
        note = getattr(n, "note", None)
        repair = getattr(note, "repair", None) if note else None
        out.append(
            {
                "id": n.id,
                "note_id": getattr(note, "id", None),
                "has_note": bool(note),
                "has_repair": bool(repair),
                "repair_display_id": getattr(repair, "display_id", None),
                "content_preview": (note.content[:120] if note and note.content else None),
            }
        )
    return jsonify({"count": len(rows), "entries": out})


# -------------------- Messages (messagerie interne) --------------------


def _serialize_message(m, current_id: int):  # type: ignore[override]
    """Sérialisation JSON minimale d'un message.

    current_id: id de l'utilisateur courant pour orienter les labels.
    """
    return {
        "id": m.id,
        "sender_id": m.sender_id,
        "recipient_id": m.recipient_id,
        "sender_name": getattr(m.sender, "name", None) or getattr(m.sender, "email", None),
        "recipient_name": getattr(m.recipient, "name", None) or getattr(m.recipient, "email", None),
        "subject": m.subject,
        "body": m.body,
        "repair_id": m.repair_id,
        # expose display_id pour lien direct si fiche associée
        "repair_display_id": getattr(getattr(m, "repair", None), "display_id", None),
        "note_id": m.note_id,
        "created_at": m.created_at.isoformat() + "Z" if m.created_at else None,
        "read_at": m.read_at.isoformat() + "Z" if m.read_at else None,
        "direction": "out" if m.sender_id == current_id else "in",
    }


@api.route("/api/messages", methods=["GET"])
@login_required
def api_messages_list():
    """Liste des messages (boîte de réception + envoyés) récents de l'utilisateur.

    Paramètres optionnels:
      - box=in|out (filtre)
      - limit (défaut 100)
    """
    box = request.args.get("box")
    limit = min(int(request.args.get("limit", 100)), 500)
    active_cafe = _active_cafe()
    q = db.session.query(MessageModel).filter(MessageModel.repaircafe_id == active_cafe.id)
    if box == "out":
        q = q.filter(
            MessageModel.sender_id == current_user.id, MessageModel.deleted_sender.is_(False)
        )
    elif box == "in":
        q = q.filter(
            MessageModel.recipient_id == current_user.id,
            MessageModel.deleted_recipient.is_(False),
        )
    else:  # combinaison (in + out)
        from sqlalchemy import and_, or_

        q = q.filter(
            or_(
                and_(
                    MessageModel.recipient_id == current_user.id,
                    MessageModel.deleted_recipient.is_(False),
                ),
                and_(
                    MessageModel.sender_id == current_user.id,
                    MessageModel.deleted_sender.is_(False),
                ),
            )
        )
    msgs = q.order_by(MessageModel.created_at.desc()).limit(limit).all()  # ordre anti-chronologique
    return jsonify([_serialize_message(m, current_user.id) for m in msgs])


@api.route("/api/repairs/<int:repair_id>/messages", methods=["GET"])
@login_required
def api_repair_messages(repair_id: int):
    """Messages liés à une fiche (repair_id) quel que soit l'expéditeur/destinataire.

    Usage: onglet "Messages" sur la page /update/<display_id>.
    Paramètres optionnels:
      - limit (défaut 200)
    Sécurité minimale: accès seulement si l'utilisateur peut voir la fiche (actuellement: connecté).
    TODO (éventuel): restreindre aux réparateurs impliqués / staff.
    """
    active_cafe = _active_cafe()
    repair = (
        db.session.query(Repair)
        .filter_by(id=repair_id)
        .filter(Repair.repaircafe_id == active_cafe.id)
        .first()
    )
    if not repair:
        return jsonify({"error": "repair_not_found"}), 404
    limit = min(int(request.args.get("limit", 200)), 500)
    q = (
        db.session.query(MessageModel)
        .filter(MessageModel.repair_id == repair_id)
        .filter(MessageModel.repaircafe_id == active_cafe.id)
    )
    # Exclure les messages que l'utilisateur a « supprimés » de sa vue (soft delete)
    from sqlalchemy import and_, or_

    q = q.filter(
        or_(
            # l'utilisateur n'est pas le sender -> peu importe deleted_sender
            MessageModel.sender_id != current_user.id,
            # ou il est sender mais pas marqué supprimé côté sender
            and_(MessageModel.sender_id == current_user.id, MessageModel.deleted_sender.is_(False)),
        )
    ).filter(
        or_(
            MessageModel.recipient_id != current_user.id,
            and_(
                MessageModel.recipient_id == current_user.id,
                MessageModel.deleted_recipient.is_(False),
            ),
        )
    )
    q = q.order_by(MessageModel.created_at.desc()).limit(limit)
    rows = q.all()
    return jsonify([_serialize_message(m, current_user.id) for m in rows])


@api.route("/api/messages/unread", methods=["GET"])
@login_required
def api_messages_unread():
    """Liste des messages non lus (inbox) limités à 100."""
    active_cafe = _active_cafe()
    q = (
        db.session.query(MessageModel)
        .filter(MessageModel.recipient_id == current_user.id)
        .filter(MessageModel.deleted_recipient.is_(False))
        .filter(MessageModel.read_at.is_(None))
        .filter(MessageModel.repaircafe_id == active_cafe.id)
        .order_by(MessageModel.created_at.desc())
        .limit(100)
    )
    return jsonify([_serialize_message(m, current_user.id) for m in q.all()])


@api.route("/api/messages/unread_count", methods=["GET"])
@login_required
def api_messages_unread_count():
    active_cafe = _active_cafe()
    count = (
        db.session.query(MessageModel)
        .filter(MessageModel.recipient_id == current_user.id)
        .filter(MessageModel.deleted_recipient.is_(False))
        .filter(MessageModel.read_at.is_(None))
        .filter(MessageModel.repaircafe_id == active_cafe.id)
        .count()
    )
    return jsonify(count)


@api.route("/api/messages", methods=["POST"])
@login_required
def api_messages_create():
    """Création d'un message direct.

    JSON ou form:
      recipient_id (int, obligatoire)
      subject (<=120, optionnel)
      body (<=250, obligatoire non vide)
      repair_id / note_id (optionnels contexte)
    Note: l'expéditeur peut être le destinataire (auto-message) – utile pour tests / brouillons.
    """
    active_cafe = _active_cafe()
    payload = request.get_json(silent=True) or request.form
    try:
        recipient_id = int(payload.get("recipient_id"))
    except Exception:
        return jsonify({"error": "invalid_recipient"}), 400
    recipient = db.session.query(User).filter_by(id=recipient_id).first()
    if not recipient:
        return jsonify({"error": "recipient_not_found"}), 404
    subject = (payload.get("subject") or "").strip()
    if not subject:
        return jsonify({"error": "missing_subject"}), 400
    if len(subject) > 120:
        return jsonify({"error": "subject_too_long"}), 400
    body = (payload.get("body") or "").strip()
    # body devient optionnel (peut être vide)
    if len(body) > 250:
        return jsonify({"error": "body_too_long"}), 400
    repair_id = payload.get("repair_id")
    note_id = payload.get("note_id")
    try:
        repair_id = int(repair_id) if repair_id is not None else None
    except Exception:
        repair_id = None
    try:
        note_id = int(note_id) if note_id is not None else None
    except Exception:
        note_id = None
    if repair_id is not None:
        repair = (
            db.session.query(Repair)
            .filter_by(id=repair_id)
            .filter(Repair.repaircafe_id == active_cafe.id)
            .first()
        )
        if not repair:
            return jsonify({"error": "repair_not_found"}), 404
    m = MessageModel(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        subject=subject,
        body=body,
        repair_id=repair_id,
        note_id=note_id,
    )
    m.repaircafe_id = active_cafe.id
    db.session.add(m)
    db.session.commit()
    return jsonify(_serialize_message(m, current_user.id)), 201


@api.route("/api/messages/<int:msg_id>", methods=["GET"])
@login_required
def api_messages_detail(msg_id: int):
    active_cafe = _active_cafe()
    m = (
        db.session.query(MessageModel)
        .filter_by(id=msg_id)
        .filter(MessageModel.repaircafe_id == active_cafe.id)
        .first()
    )
    if not m:
        return jsonify({"error": "not_found"}), 404
    if m.sender_id != current_user.id and m.recipient_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    # marquer comme lu si destinataire
    if m.recipient_id == current_user.id and not m.read_at:
        m.mark_read()
        db.session.commit()
    return jsonify(_serialize_message(m, current_user.id))


@api.route("/api/messages/<int:msg_id>/read", methods=["POST"])
@login_required
def api_messages_mark_read(msg_id: int):
    active_cafe = _active_cafe()
    m = (
        db.session.query(MessageModel)
        .filter_by(id=msg_id)
        .filter(MessageModel.repaircafe_id == active_cafe.id)
        .first()
    )
    if not m:
        return jsonify({"error": "not_found"}), 404
    if m.recipient_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    if not m.read_at:
        m.mark_read()
        db.session.commit()
    return jsonify({"status": "ok", "read_at": m.read_at.isoformat() + "Z"})


@api.route("/api/messages/<int:msg_id>", methods=["DELETE"])
@login_required
def api_messages_delete(msg_id: int):
    active_cafe = _active_cafe()
    m = (
        db.session.query(MessageModel)
        .filter_by(id=msg_id)
        .filter(MessageModel.repaircafe_id == active_cafe.id)
        .first()
    )
    if not m:
        return jsonify({"error": "not_found"}), 404
    if m.sender_id != current_user.id and m.recipient_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    if m.sender_id == current_user.id:
        m.deleted_sender = True
    if m.recipient_id == current_user.id:
        m.deleted_recipient = True
    db.session.commit()
    return jsonify({"status": "ok"})


@api.route("/api/messages/<int:msg_id>/unread", methods=["POST"])
@login_required
def api_messages_toggle_unread(msg_id: int):
    """Bascule état lu/non-lu pour le destinataire.

    Payload JSON: {"unread": true|false}
    unread=true force read_at=NULL (revient dans le compteur).
    unread=false marque comme lu (si pas déjà lu).
    """
    active_cafe = _active_cafe()
    m = (
        db.session.query(MessageModel)
        .filter_by(id=msg_id)
        .filter(MessageModel.repaircafe_id == active_cafe.id)
        .first()
    )
    if not m:
        return jsonify({"error": "not_found"}), 404
    if m.recipient_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    unread = bool(payload.get("unread"))
    from datetime import datetime, timezone

    if unread:
        m.read_at = None
    else:
        if not m.read_at:
            m.read_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"status": "ok", "read_at": m.read_at.isoformat() + "Z" if m.read_at else None})


@api.route("/api/users/simple", methods=["GET"])
@login_required
def api_users_simple():
    """Liste simple des utilisateurs (id, name) pour autocomplétion / sélection destinataire.

    Paramètres optionnels:
        - q (préfixe insensible)
        - limit (max 500, défaut 50)
    """
    active_cafe = _active_cafe()
    from .models import user_repaircafe

    q = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit", 50))
    except Exception:
        limit = 50
    limit = max(1, min(limit, 500))
    base_query = db.session.query(User).join(user_repaircafe)
    base_query = base_query.filter(user_repaircafe.c.repaircafe_id == active_cafe.id)
    query = filter_active_membership_or_founder(base_query)
    if q:
        like = f"{q}%"
        query = query.filter(User.name.like(like))
    users = query.order_by(User.name.asc()).limit(limit).all()
    # Assurer présence des fondateurs même si limite atteinte
    founder_users = base_query.filter(User.founder.is_(True)).all()
    existing_ids = {u.id for u in users}
    for u in founder_users:
        if u.id not in existing_ids:
            users.append(u)
    return jsonify([{"id": u.id, "name": u.name or u.email} for u in users])


@api.route("/api/get_notifcount")
@login_required
def get_notifcount():
    """Compte simple des notifications du réparateur courant.

    Utilisé par le JS pour afficher/masquer le badge de notification.
    """
    active_cafe = _active_cafe()
    count = (
        Notification.query.filter_by(user_id=current_user.id)
        .filter(Notification.repaircafe_id == active_cafe.id)
        .count()
    )
    return jsonify(count)


@api.route("/api/repairsearch")
def repairsearch():
    r"""Recherche paginée des réparations."""
    active_cafe = _active_cafe()
    length = request.args.get("length", current_app.config.get("PAGE_SIZE", 25), type=int)
    page = (request.args.get("start", 0, type=int) / length) + 1
    searchValue = request.args.get("search[value]")
    repairs = Repair.query.filter(Repair.repaircafe_id == active_cafe.id)
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
        from .models import ObjectType as OT, ObjectVariant as OV  # import tardif

        repairs = repairs.join(Brand)
        # gauche pour types (peut être NULL)
        repairs = repairs.outerjoin(OT, Repair.object_type_id == OT.id)
        repairs = repairs.outerjoin(OV, OV.object_type_id == OT.id)
        like_any = "%" + searchValue + "%"
        prefix = searchValue + "%"
        repairs = repairs.filter(
            Repair.display_id.like(prefix)
            | Repair.name.like(like_any)
            | Repair.otype.like(like_any)
            | Brand.name.like(prefix)
            | OT.name.like(like_any)
            | OV.name.like(like_any)
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

    def _format_otype(rep):  # otype affiché combiné libre + standard
        if rep.object_type and rep.object_type.name and rep.otype:
            return f"{rep.object_type.name} ({rep.otype})"
        return rep.otype or (rep.object_type and rep.object_type.name) or ""

    json = jsonify(
        {
            "repairs": [
                {
                    "id": r.display_id,
                    "name": r.name,
                    "category": r.category.name,
                    "otype": _format_otype(r),
                    "brand": r.brand.name if r.brand else "",
                    "object_type_name": r.object_type.name if r.object_type else "",
                    "close_status": r.close_status.label[0],
                }
                for r in repairs.items
            ],
            "draw": request.args.get("draw", 1, type=int),
            "recordsTotal": db.session.query(Repair)
            .filter(Repair.repaircafe_id == active_cafe.id)
            .count(),
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
    active_cafe = _active_cafe()
    date_from, date_to = parse_period(request.args.get("from"), request.args.get("to"))
    if not date_from:
        return {}
    global all_categories, all_status
    get_cached_lists(db.session, all_categories, all_status)
    stats_raw = compute_stats(db.session, date_from, date_to, repaircafe_id=active_cafe.id)
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
            "top_object_types": [
                {"name": name, "count": count}
                for (name, count) in stats_raw.get("object_types_top", [])
            ],
        }
    )


@api.route("/sendmail")
def sendmail():
    if not MailMessage:
        return jsonify({"error": "mail_not_configured"}), 503
    active_cafe = _active_cafe()
    sender = get_mail_sender(active_cafe)
    recipients = [active_cafe.email] if active_cafe and active_cafe.email else [sender]
    msg = MailMessage(
        "Hello",
        sender=sender,
        recipients=recipients,
    )
    msg.body = "Hello Flask message sent from Flask-Mail"
    mail.send(msg)
    return jsonify(True)


# -------------------- Sessions --------------------


@api.route("/api/session/open", methods=["POST"])
@login_required
def api_session_open():
    # Tout réparateur authentifié peut ouvrir une séance (owner = current_user)
    active_cafe = _active_cafe()
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
            loc_obj = (
                db.session.query(Location)
                .filter_by(name=location.strip())
                .filter(Location.repaircafe_id == active_cafe.id)
                .first()
            )
            if loc_obj:
                from .models import Session as SessionModel

                existing = (
                    db.session.query(SessionModel)
                    .filter(SessionModel.closed_at.is_(None))
                    .filter(SessionModel.location_id == loc_obj.id)
                    .filter(SessionModel.repaircafe_id == active_cafe.id)
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


@api.route("/api/session/past", methods=["POST"])
@login_required
def api_session_past_create():
    """Création d'une séance passée (admin uniquement).

    Payload JSON ou form:
      - date: YYYY-MM-DD (obligatoire)
      - location: nom lieu (obligatoire)
      - time: HH:MM (optionnel, heure locale) sinon 09:00 par défaut
    Refusé s'il existe une séance ouverte actuellement (doit être fermée d'abord).
    """
    if not getattr(current_user, "admin", False):
        return jsonify({"error": "forbidden"}), 403
    # Y a-t-il une séance ouverte ?
    active_cafe = _active_cafe()
    opened = (
        db.session.query(SessionModel)
        .filter(SessionModel.closed_at.is_(None))
        .filter(SessionModel.repaircafe_id == active_cafe.id)
        .order_by(SessionModel.opened_at.asc())
        .first()
    )
    if opened:
        return jsonify({"error": "open_session_exists", "session_id": opened.id}), 400
    payload = request.get_json(silent=True) or request.form
    date_str = (payload.get("date") or "").strip()
    location = (payload.get("location") or "").strip()
    time_str = (payload.get("time") or "09:00").strip() or "09:00"
    if not date_str or not location:
        return jsonify({"error": "missing_fields"}), 400
    try:
        from datetime import datetime as dt

        import pytz

        parts = date_str.split("-")
        if len(parts) != 3:
            raise ValueError("invalid_date")
        year, month, day = map(int, parts)
        hh, mm = 9, 0
        if time_str:
            try:
                hh, mm = map(int, time_str.split(":", 1))
            except Exception:
                pass
        naive = dt(year, month, day, hh, mm)
        tz = pytz.timezone("Europe/Paris")
        localized = tz.localize(naive)
        opened_at = localized.astimezone(pytz.utc).replace(tzinfo=None)
    except Exception:
        return jsonify({"error": "invalid_datetime"}), 400
    # Création manuelle sans réutilisation logique open_session
    from .models import Location as Loc, Session as Sess

    active_cafe = _active_cafe()
    loc = (
        db.session.query(Loc)
        .filter_by(name=location)
        .filter(Loc.repaircafe_id == active_cafe.id)
        .first()
    )
    if not loc:
        loc = Loc(name=location)
        loc.repaircafe = active_cafe
        db.session.add(loc)
        db.session.flush()
    s = Sess(location=loc, owner_id=current_user.id, opened_at=opened_at, repaircafe=active_cafe)
    s.participants.append(current_user)
    db.session.add(s)
    db.session.commit()
    return jsonify({"id": s.id, "opened_at": s.opened_at.isoformat() + "Z"})


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
    active_cafe = _active_cafe()
    if current_user.id != s.owner_id and not is_cafe_admin(current_user, active_cafe.id):
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
    active_cafe = _active_cafe()
    if current_user.id != s.owner_id and not is_cafe_admin(current_user, active_cafe.id):
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
    active_cafe = _active_cafe()
    if current_user.id != s.owner_id and not is_cafe_admin(current_user, active_cafe.id):
        return jsonify({"error": "forbidden"}, 403)
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
    active_cafe = _active_cafe()
    s = (
        db.session.query(SessionModel)
        .filter_by(id=session_id)
        .filter(SessionModel.repaircafe_id == active_cafe.id)
        .first()
    )
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
    active_cafe = _active_cafe()
    opened_only = request.args.get("opened") == "1"
    from .models import Session as SessionModel  # import tardif pour éviter cycle

    sessions_q = db.session.query(SessionModel).filter(SessionModel.repaircafe_id == active_cafe.id)
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
    active_cafe = _active_cafe()
    q = request.args.get("q")
    query = db.session.query(Location).filter(Location.repaircafe_id == active_cafe.id)
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
    from .models import ObjectType, ObjectVariant  # import tardif

    q = (request.args.get("q") or "").strip()
    query = db.session.query(ObjectType).join(Category)
    if q:
        like = f"{q}%"
        # jointure externe aux variantes pour matcher sur leurs noms aussi (prefix match)
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
