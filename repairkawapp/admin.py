"""Module d'administration de RepairKawapp.

RepairKawapp – Repair Café management application
Licence: MIT (voir fichier LICENSE)
Auteur principal: Jean Senellart

Nettoyage global : imports organisés, PEP8, docstrings, harmonisation du style.
"""

import os
import uuid
from datetime import date

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
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from . import db
from .models import (
    AppSetting,
    BoardRoleLog,
    CafeFile,
    Category,
    MembershipLog,
    ObjectSubtype,
    ObjectType,
    ObjectVariant,
    Repair,
    RepairCafe,
    User,
    user_repaircafe,
)
from .services.image_service import process_user_photo
from .services.tenant_service import (
    ensure_cafe_upload_folder,
    get_cafe_upload_relative_path,
    get_mail_sender,
    get_user_cafe_photo,
    is_cafe_admin,
    require_active_repaircafe,
    set_user_cafe_photo,
)

admin = Blueprint("admin", __name__)
LOCAL_TIMEZONE = pytz.timezone("Europe/Paris")
ALLOWED_CAFE_FILE_EXTENSIONS = {
    "pdf",
    "txt",
    "csv",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "odt",
    "ods",
    "odp",
    "jpg",
    "jpeg",
    "png",
    "gif",
}


def _is_allowed_cafe_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_CAFE_FILE_EXTENSIONS


@admin.route("/admin")
@login_required
def user_list():
    """Page principale d'administration (liste des réparateurs)."""
    _admin_only()
    cafe = require_active_repaircafe()
    email = request.args.get("email", None)
    users_q = (
        User.query.join(user_repaircafe)
        .filter(user_repaircafe.c.repaircafe_id == cafe.id)
        .order_by(User.last_membership.desc())
        .order_by(User.name)
    )
    return render_template(
        "user_list.html",
        name=current_user.name,
        filter_email=email,
        users=users_q.all(),
    )


@admin.route("/admin/files")
@login_required
def file_system():
    _admin_only()
    cafe = require_active_repaircafe()
    rows = (
        db.session.query(CafeFile, User)
        .join(User, User.id == CafeFile.sender_id)
        .filter(CafeFile.repaircafe_id == cafe.id)
        .order_by(CafeFile.file_name.asc())
        .all()
    )
    return render_template(
        "file_system.html",
        name=current_user.name,
        files=rows,
    )


@admin.route("/admin/files/new", methods=["GET", "POST"])
@login_required
def file_new():
    _admin_only()
    cafe = require_active_repaircafe()
    if request.method == "GET":
        return render_template("file_new.html", name=current_user.name)

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return redirect(request.url)

    display_name = (request.form.get("name") or "").strip()
    if not display_name:
        return redirect(request.url)

    if not _is_allowed_cafe_file(uploaded.filename):
        return redirect(request.url)

    display_name = secure_filename(display_name)
    stored_name = f"file_{uuid.uuid4().hex}_{secure_filename(uploaded.filename)}"
    upload_dir = ensure_cafe_upload_folder(current_app.config["UPLOAD_FOLDER"], cafe)
    stored_path = get_cafe_upload_relative_path(cafe, stored_name)
    dest = os.path.join(upload_dir, stored_name)
    uploaded.save(dest)

    db.session.add(
        CafeFile(
            repaircafe_id=cafe.id,
            sender_id=current_user.id,
            file_name=display_name,
            file_path=stored_path,
        )
    )
    db.session.commit()
    return redirect(url_for("admin.file_system"), code=302)


@admin.route("/admin/files/<int:file_id>/download", methods=["GET"])
@login_required
def file_download(file_id: int):
    _admin_only()
    cafe = require_active_repaircafe()
    file = (
        db.session.query(CafeFile)
        .filter(CafeFile.id == file_id)
        .filter(CafeFile.repaircafe_id == cafe.id)
        .first()
    )
    if not file:
        return ("", 404)
    upload_root = current_app.config["UPLOAD_FOLDER"]
    response = send_from_directory(
        upload_root,
        file.file_path,
        download_name=file.file_name,
        as_attachment=True,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@admin.route("/admin/files/<int:file_id>/delete", methods=["POST"])
@login_required
def file_delete(file_id: int):
    _admin_only()
    cafe = require_active_repaircafe()
    file = (
        db.session.query(CafeFile)
        .filter(CafeFile.id == file_id)
        .filter(CafeFile.repaircafe_id == cafe.id)
        .first()
    )
    if not file:
        return redirect(url_for("admin.file_system"))

    upload_root = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(upload_root, file.file_path)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(file)
    db.session.commit()
    return redirect(url_for("admin.file_system"))


@admin.route("/admin/users/download")
@login_required
def users_download():
    _admin_only()
    cafe = require_active_repaircafe()
    users = (
        User.query.join(user_repaircafe)
        .filter(user_repaircafe.c.repaircafe_id == cafe.id)
        .order_by(User.name.asc())
        .all()
    )
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Nom",
            "Email",
            "Téléphone",
            "Public",
            "Admin",
            "Rôle",
            "Cotisation",
            "Dernière connexion (UTC)",
        ]
    )
    for u in users:
        last_conn = u.last_connection.isoformat().replace("T", " ") if u.last_connection else ""
        membership = (
            f"{u.last_membership}-{u.last_membership + 1}" if u.last_membership is not None else ""
        )
        writer.writerow(
            [
                u.id,
                u.name or "",
                u.email or "",
                u.phone or "",
                "Oui" if u.visibility_public_trombi else "Non",
                "Oui" if u.admin else "Non",
                u.board_title or "",
                membership,
                last_conn,
            ]
        )
    from datetime import datetime as _dt

    stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    resp = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename=users-{stamp}.csv"
    return resp


# ------------------------------- Gestion Types / Variantes -------------------------------


def _admin_only():
    cafe = require_active_repaircafe()
    if not is_cafe_admin(current_user, cafe.id):
        from flask import abort

        abort(403)


def _super_admin_only():
    if not getattr(current_user, "super_admin", False):
        from flask import abort

        abort(403)


def _slugify(name: str) -> str:
    """Create a URL-safe slug from a name."""
    import re
    import unicodedata

    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "repaircafe"


@admin.route("/admin/repaircafes", methods=["GET", "POST"])
@login_required
def repaircafe_list():
    """Super admin view to manage Repair Cafes."""
    _super_admin_only()
    creation_error = None
    admin_error = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_admin":
            cafe_id = request.form.get("cafe_id")
            admin_email = (request.form.get("admin_email") or "").strip().lower()
            if not cafe_id or not admin_email:
                admin_error = "Email admin obligatoire."
            else:
                cafe = RepairCafe.query.filter_by(id=int(cafe_id)).first()
                admin_user = User.query.filter_by(email=admin_email).first()
                if not cafe or not admin_user:
                    admin_error = "Réparateur introuvable."
                else:
                    update_res = db.session.execute(
                        user_repaircafe.update()
                        .where(
                            and_(
                                user_repaircafe.c.user_id == admin_user.id,
                                user_repaircafe.c.repaircafe_id == cafe.id,
                            )
                        )
                        .values(role="admin")
                    )
                    if not update_res.rowcount:
                        db.session.execute(
                            user_repaircafe.insert().values(
                                user_id=admin_user.id,
                                repaircafe_id=cafe.id,
                                role="admin",
                            )
                        )
                    admin_user.admin = True
                    if not admin_user.active_repaircafe_id:
                        admin_user.active_repaircafe_id = cafe.id
                    db.session.commit()
                    return redirect(url_for("admin.repaircafe_list"))
        else:
            name = (request.form.get("name") or "").strip()
            slug = (request.form.get("slug") or "").strip()
            code = (request.form.get("code") or "").strip().lower()
            email = (request.form.get("email") or "").strip() or None
            website_url = (request.form.get("website_url") or "").strip() or None
            if not name or not code:
                creation_error = "Nom et code obligatoires."
            else:
                if not slug:
                    slug = _slugify(name)
                exists = RepairCafe.query.filter(
                    (RepairCafe.name == name)
                    | (RepairCafe.slug == slug)
                    | (RepairCafe.code == code)
                ).first()
                if exists:
                    creation_error = "Nom ou slug déjà utilisé."
                else:
                    db.session.add(
                        RepairCafe(
                            name=name,
                            slug=slug,
                            code=code,
                            email=email,
                            website_url=website_url,
                        )
                    )
                    db.session.commit()
                    return redirect(url_for("admin.repaircafe_list"))

    cafes = RepairCafe.query.order_by(RepairCafe.name.asc()).all()
    from datetime import date as _date

    today = _date.today()
    start_year = today.year if today.month >= 9 else today.year - 1
    academic_start = _date(start_year, 9, 1)
    cafe_rows = []
    for cafe in cafes:
        admins = (
            db.session.query(User)
            .join(user_repaircafe)
            .filter(user_repaircafe.c.repaircafe_id == cafe.id)
            .filter(user_repaircafe.c.role == "admin")
            .order_by(User.name.asc())
            .all()
        )
        repairer_count = (
            db.session.query(user_repaircafe.c.user_id)
            .filter(user_repaircafe.c.repaircafe_id == cafe.id)
            .count()
        )
        total_repairs = db.session.query(Repair).filter(Repair.repaircafe_id == cafe.id).count()
        academic_repairs = (
            db.session.query(Repair)
            .filter(Repair.repaircafe_id == cafe.id)
            .filter(Repair.created >= academic_start)
            .count()
        )
        cafe_rows.append(
            {
                "cafe": cafe,
                "admins": admins,
                "repairer_count": repairer_count,
                "total_repairs": total_repairs,
                "academic_repairs": academic_repairs,
            }
        )
    return render_template(
        "admin_repaircafes.html",
        name=current_user.name,
        cafes=cafe_rows,
        creation_error=creation_error,
        admin_error=admin_error,
    )


@admin.route("/admin/repaircafes/<int:cafe_id>/reset_admin/<int:user_id>", methods=["POST"])
@login_required
def repaircafe_reset_admin(cafe_id: int, user_id: int):
    """Send a password reset email for a cafe admin user."""
    _super_admin_only()
    cafe = RepairCafe.query.filter_by(id=cafe_id).first()
    admin_user = (
        db.session.query(User)
        .join(user_repaircafe)
        .filter(User.id == user_id)
        .filter(user_repaircafe.c.repaircafe_id == cafe_id)
        .filter(user_repaircafe.c.role == "admin")
        .first()
    )
    if not admin_user:
        return redirect(url_for("admin.repaircafe_list"))
    try:
        import time

        from flask_mail import Message

        from . import mail, serializer

        data = {"i": str(admin_user.id), "s": admin_user.seqid, "t": int(time.time() / 3600)}
        token = serializer.dumps(data)
        reset_url = url_for("auth.init_password", token=token)
        sender = get_mail_sender(cafe)
        msg = Message(
            "Réinitialisation du mot de passe",
            sender=sender,
            recipients=[admin_user.email],
        )
        msg.body = (
            "Bonjour,\n\n"
            "Un super admin a demandé la réinitialisation de votre mot de passe. "
            "Pour le changer, utilisez ce lien:\n"
            f"{current_app.config['APP_URL']}{reset_url}\n"
        )
        mail.send(msg)
    except Exception:
        pass
    return redirect(url_for("admin.repaircafe_list"))


@admin.route("/admin/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    is_super_admin = getattr(current_user, "super_admin", False)
    if not is_super_admin:
        _admin_only()
    cafe = require_active_repaircafe() if not is_super_admin else None
    setting = db.session.get(AppSetting, 1)
    if not setting:
        setting = AppSetting(id=1, maintenance_mode=False)
        db.session.add(setting)
        db.session.commit()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "maintenance" and is_super_admin:
            setting.maintenance_mode = bool(request.form.get("maintenance_mode"))
            # Parse datetime-local
            dt_raw = request.form.get("maintenance_until") or ""
            from datetime import datetime

            if dt_raw:
                try:
                    # Parse browser local datetime (naive) et stocke tel quel.
                    setting.maintenance_until = datetime.strptime(dt_raw, "%Y-%m-%dT%H:%M")
                except ValueError:
                    pass
            else:
                setting.maintenance_until = None
        if action == "logo" and cafe and "logo" in request.files and request.files["logo"].filename:
            from werkzeug.utils import secure_filename

            filename = secure_filename(request.files["logo"].filename)
            if filename:
                upload_dir = ensure_cafe_upload_folder(current_app.config["UPLOAD_FOLDER"], cafe)
                stored_name = get_cafe_upload_relative_path(cafe, filename)
                dest = os.path.join(upload_dir, filename)
                request.files["logo"].save(dest)
                cafe.logo_filename = stored_name
        db.session.commit()
        return redirect(url_for("admin.settings_page"))
    return render_template(
        "admin_settings.html",
        setting=setting,
        name=current_user.name,
        active_cafe=cafe,
        can_manage_maintenance=is_super_admin,
    )


@admin.route("/admin/objecttypes", methods=["GET", "POST"])
@login_required
def objecttypes_admin_list():
    _admin_only()
    q = (request.args.get("q") or "").strip().lower()
    sort = request.args.get("sort", "name")  # name | category
    direction = request.args.get("dir", "asc")  # asc | desc
    if sort not in {"name", "category"}:
        sort = "name"
    if direction not in {"asc", "desc"}:
        direction = "asc"
    types_query = (
        ObjectType.query.join(Category)
        .outerjoin(ObjectVariant)
        .add_columns(Category.name.label("cat_name"))
    )
    if q:
        like = f"%{q}%"
        types_query = types_query.filter(
            ObjectType.name.ilike(like)  # type: ignore[attr-defined]
            | Category.name.ilike(like)  # type: ignore[attr-defined]
            | ObjectVariant.name.ilike(like)  # type: ignore[attr-defined]
        )
    # Agrégations en mémoire (DB simple) pour compter objets & variantes
    rows = types_query.order_by(ObjectType.name.asc()).all() if len(q) < 100 else []
    # Préparer structure: {type: {variants:[], count_repairs:int}}
    # Récupération counts repairs via une requête groupée
    repair_counts = {
        rid: cnt
        for rid, cnt in (
            db.session.query(ObjectType.id, db.func.count(Repair.id))
            .outerjoin(Repair, Repair.object_type_id == ObjectType.id)
            .group_by(ObjectType.id)
            .all()
        )
    }
    out = []
    seen = set()
    for ot, cat_name in rows:  # type: ignore[misc]
        if ot.id in seen:
            continue
        seen.add(ot.id)
        variants = [v.name for v in ot.variants]
        out.append(
            {
                "id": ot.id,
                "name": ot.name,
                "category": cat_name,
                "variants": variants,
                "nb_repairs": repair_counts.get(ot.id, 0),
            }
        )
    # Tri en mémoire selon paramètres
    reverse = direction == "desc"
    if sort == "category":
        out.sort(key=lambda x: ((x["category"] or ""), x["name"]), reverse=reverse)
    else:  # default tri par nom
        out.sort(key=lambda x: x["name"], reverse=reverse)
    creation_error = None
    if request.method == "POST":
        # Création nouveau type (unicité name+category)
        name = (request.form.get("name") or "").strip()
        cat_id = request.form.get("category_id")
        if name and cat_id and cat_id.isdigit():
            cat = db.session.query(Category).filter_by(id=int(cat_id)).first()
            if cat:
                exists = (
                    db.session.query(ObjectType)
                    .filter(ObjectType.name == name, ObjectType.category_id == cat.id)
                    .first()
                )
                if exists:
                    creation_error = "Type déjà existant pour cette catégorie."
                else:
                    try:
                        db.session.add(ObjectType(name=name, category=cat))
                        db.session.commit()
                        return redirect(url_for("admin.objecttypes_admin_list"))
                    except Exception:  # fallback si contrainte DB atteint malgré check
                        db.session.rollback()
                        creation_error = "Contrainte d'unicité violée (nom+catégorie)."
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template(
        "objecttype_list.html",
        types=out,
        q=q,
        sort=sort,
        dir=direction,
        categories=categories,
        name=current_user.name,
        creation_error=creation_error,
    )


@admin.route("/admin/objecttypes/download")
@login_required
def objecttypes_download():
    _admin_only()
    q = (request.args.get("q") or "").strip().lower()
    sort = request.args.get("sort", "name")
    direction = request.args.get("dir", "asc")
    if sort not in {"name", "category"}:
        sort = "name"
    if direction not in {"asc", "desc"}:
        direction = "asc"
    types_query = (
        ObjectType.query.join(Category)
        .outerjoin(ObjectVariant)
        .add_columns(Category.name.label("cat_name"))
    )
    if q:
        like = f"%{q}%"
        types_query = types_query.filter(
            ObjectType.name.ilike(like) | Category.name.ilike(like) | ObjectVariant.name.ilike(like)
        )
    rows = types_query.order_by(ObjectType.name.asc()).all()
    repair_counts = {
        rid: cnt
        for rid, cnt in (
            db.session.query(ObjectType.id, db.func.count(Repair.id))
            .outerjoin(Repair, Repair.object_type_id == ObjectType.id)
            .group_by(ObjectType.id)
            .all()
        )
    }
    data = []
    seen = set()
    for ot, cat_name in rows:  # type: ignore[misc]
        if ot.id in seen:
            continue
        seen.add(ot.id)
        data.append(
            {
                "name": ot.name,
                "category": cat_name,
                "variants": ";".join(v.name for v in ot.variants) or "",
                "subtypes": ";".join(st.name for st in ot.subtypes) or "",
                "nb_repairs": str(repair_counts.get(ot.id, 0)),
            }
        )
    reverse = direction == "desc"
    if sort == "category":
        data.sort(key=lambda x: ((x["category"] or ""), x["name"]), reverse=reverse)
    else:
        data.sort(key=lambda x: x["name"], reverse=reverse)
    # Génération CSV simple
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Nom", "Catégorie", "Variantes", "Sous-types", "Nb réparations"])
    for row in data:
        writer.writerow(
            [
                row["name"],
                row["category"],
                row["variants"],
                row["subtypes"],
                row["nb_repairs"],
            ]
        )
    from datetime import datetime as _dt

    stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    resp = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename=objecttypes-{stamp}.csv"
    return resp


@admin.route("/admin/objecttypes/<int:ot_id>", methods=["GET", "POST", "DELETE"])
@login_required
def objecttype_admin_detail(ot_id: int):
    _admin_only()
    ot = db.session.query(ObjectType).filter_by(id=ot_id).first()
    if not ot:
        return redirect(url_for("admin.objecttypes_admin_list"))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_type":
            new_name = (request.form.get("name") or "").strip()
            cat_id = request.form.get("category_id")
            if new_name:
                ot.name = new_name
            if cat_id and cat_id.isdigit():
                cat = db.session.query(Category).filter_by(id=int(cat_id)).first()
                if cat:
                    ot.category = cat
            db.session.commit()
            return redirect(url_for("admin.objecttype_admin_detail", ot_id=ot.id))
        elif action == "add_variant":
            vname = (request.form.get("variant_name") or "").strip()
            if vname:
                db.session.add(ObjectVariant(name=vname, object_type=ot))
                db.session.commit()
            return redirect(url_for("admin.objecttype_admin_detail", ot_id=ot.id))
        elif action == "delete_variant":
            vid = request.form.get("variant_id")
            if vid and vid.isdigit():
                (
                    db.session.query(ObjectVariant)
                    .filter_by(id=int(vid), object_type_id=ot.id)
                    .delete()
                )
                db.session.commit()
            return redirect(url_for("admin.objecttype_admin_detail", ot_id=ot.id))
        elif action == "add_subtype":
            sname = (request.form.get("subtype_name") or "").strip()
            if sname:
                db.session.add(ObjectSubtype(name=sname, object_type=ot))
                db.session.commit()
            return redirect(url_for("admin.objecttype_admin_detail", ot_id=ot.id))
        elif action == "update_subtype":
            sid = request.form.get("subtype_id")
            sname = (request.form.get("subtype_name") or "").strip()
            if sid and sid.isdigit() and sname:
                st = (
                    db.session.query(ObjectSubtype)
                    .filter_by(id=int(sid), object_type_id=ot.id)
                    .first()
                )
                if st:
                    st.name = sname
                    db.session.commit()
            return redirect(url_for("admin.objecttype_admin_detail", ot_id=ot.id))
        elif action == "delete_subtype":
            sid = request.form.get("subtype_id")
            if sid and sid.isdigit():
                (
                    db.session.query(ObjectSubtype)
                    .filter_by(id=int(sid), object_type_id=ot.id)
                    .delete()
                )
                db.session.commit()
            return redirect(url_for("admin.objecttype_admin_detail", ot_id=ot.id))
        elif action == "delete_type":
            # Suppression si aucun Repair
            has_repairs = (
                db.session.query(Repair).filter(Repair.object_type_id == ot.id).first() is not None
            )
            if not has_repairs:
                db.session.query(ObjectType).filter_by(id=ot.id).delete()
                db.session.commit()
                return redirect(url_for("admin.objecttypes_admin_list"))
    categories = Category.query.order_by(Category.name.asc()).all()
    associated_repairs = (
        db.session.query(Repair)
        .filter(Repair.object_type_id == ot.id)
        .order_by(Repair.display_id)
        .all()
    )
    return render_template(
        "objecttype_detail.html",
        ot=ot,
        categories=categories,
        repairs=associated_repairs,
        has_repairs=len(associated_repairs) > 0,
        name=current_user.name,
    )


def _current_academic_start(today: date) -> int:
    return today.year if today.month >= 9 else today.year - 1


def _subscription_target_start(today: date) -> int:
    """Retourne l'année de début à enregistrer lors d'une souscription rapide.

    Règle : à partir du 1er juillet (mois 7 et 8) on enregistre la prochaine
    période (N+1 par rapport à l'année académique courante). Sinon, la période
    académique courante.
    """
    acad = _current_academic_start(today)
    if today.month in (7, 8):
        return acad + 1
    return acad


@admin.route("/admin/edit/<string:user_id>", methods=["POST", "GET"])
@login_required
def user_edit(user_id):
    """Edition d'un réparateur (admin)."""
    _admin_only()
    cafe = require_active_repaircafe()
    u = (
        db.session.query(User)
        .join(user_repaircafe)
        .filter(User.id == user_id)
        .filter(user_repaircafe.c.repaircafe_id == cafe.id)
        .first()
    )
    photo_error = None
    password_error = None
    if request.method == "POST":
        # Bouton d'action rapide "set_current_membership"
        if request.form.get("action") == "set_previous_membership":
            old = u.last_membership
            prev_val = _subscription_target_start(date.today()) - 1
            # On n'applique que si pas déjà positionné ou plus ancien
            if old != prev_val and (old is None or old < prev_val):
                u.last_membership = prev_val
                db.session.add(
                    MembershipLog(
                        admin_id=current_user.id,
                        user_id=u.id,
                        old_value=old,
                        new_value=prev_val,
                    )
                )
                db.session.commit()
            return redirect(url_for("admin.user_edit", user_id=user_id), code=302)
        if request.form.get("action") == "set_current_membership":
            old = u.last_membership
            new_val = _subscription_target_start(date.today())
            if old != new_val:
                u.last_membership = new_val
                db.session.add(
                    MembershipLog(
                        admin_id=current_user.id,
                        user_id=u.id,
                        old_value=old,
                        new_value=new_val,
                    )
                )
            db.session.commit()
            return redirect(url_for("admin.user_edit", user_id=user_id), code=302)
        # Mise à jour des champs standards
        u.name = request.form.get("name")
        u.email = request.form.get("email")
        u.phone = request.form.get("phone") or None

        # Rôle de bureau (admin only) + log si changement
        new_role = request.form.get("board_title") or None
        if new_role != u.board_title:
            old_role = u.board_title
            u.board_title = new_role
            db.session.add(
                BoardRoleLog(
                    admin_id=current_user.id,
                    user_id=u.id,
                    old_role=old_role,
                    new_role=new_role,
                )
            )

        # Biographie editable aussi côté admin
        u.biography = request.form.get("biography") or None

        # Changement mot de passe (admin)
        new_pwd = request.form.get("new_password") or ""
        new_pwd_conf = request.form.get("new_password_confirm") or ""
        if new_pwd or new_pwd_conf:
            if new_pwd != new_pwd_conf:
                password_error = "Confirmation différente."
            elif len(new_pwd) < 6:
                password_error = "Mot de passe trop court (≥6)."
            else:
                u.password = generate_password_hash(new_pwd)
                # Incrémente seqid si présent pour invalider resets précédents
                try:
                    u.seqid = (u.seqid or 0) + 1
                except Exception:
                    pass

        # Upload photo (admin) même logique que profil réparateur
        if "photo" in request.files and request.files["photo"].filename:
            raw = request.files["photo"].read()
            upload_dir = ensure_cafe_upload_folder(current_app.config["UPLOAD_FOLDER"], cafe)
            filename, err = process_user_photo(raw, upload_dir, u.id, request.form.get)
            if err:
                photo_error = err
            else:
                set_user_cafe_photo(
                    u.id,
                    cafe.id,
                    get_cafe_upload_relative_path(cafe, filename),
                )

        # Conversion explicite en booléen pour éviter les valeurs '' dans la colonne Boolean
        is_admin = True if request.form.get("admin") else False
        u.admin = is_admin
        # Sync per-cafe admin role
        update_res = db.session.execute(
            user_repaircafe.update()
            .where(
                and_(
                    user_repaircafe.c.user_id == u.id,
                    user_repaircafe.c.repaircafe_id == cafe.id,
                )
            )
            .values(role="admin" if is_admin else None)
        )
        if not update_res.rowcount:
            db.session.execute(
                user_repaircafe.insert().values(
                    user_id=u.id,
                    repaircafe_id=cafe.id,
                    role="admin" if is_admin else None,
                )
            )
        u.visibility_public_trombi = True if request.form.get("visibility_public_trombi") else False
        # Founder: seul un fondateur peut modifier ce flag
        if current_user.founder:
            u.founder = True if request.form.get("founder") else False
        # si non fondateur, founder reste inchangé (lecture seule côté template)

        # Commit seulement si pas d'erreur photo ou password -> redirection liste
        if not photo_error and not password_error:
            db.session.commit()
            return redirect(url_for("admin.user_list"), code=302)
        # Sinon on commit quand même (sauf photo/password)
        # puis on ré-affiche le formulaire avec erreurs
        db.session.commit()
        logs = (
            db.session.query(MembershipLog)
            .filter_by(user_id=u.id)
            .order_by(MembershipLog.date.desc())
            .limit(20)
            .all()
        )
        role_logs = (
            db.session.query(BoardRoleLog)
            .filter_by(user_id=u.id)
            .order_by(BoardRoleLog.date.desc())
            .limit(20)
            .all()
        )
        return render_template(
            "user_edit.html",
            name=current_user.name,
            u=u,
            current_academic_start=_current_academic_start(date.today()),
            subscription_target=_subscription_target_start(date.today()),
            membership_logs=logs,
            role_logs=role_logs,
            photo_error=photo_error,
            password_error=password_error,
            photo_filename=get_user_cafe_photo(u.id, cafe.id),
        )
    else:
        logs = (
            db.session.query(MembershipLog)
            .filter_by(user_id=u.id)
            .order_by(MembershipLog.date.desc())
            .limit(20)
            .all()
        )
        role_logs = (
            db.session.query(BoardRoleLog)
            .filter_by(user_id=u.id)
            .order_by(BoardRoleLog.date.desc())
            .limit(20)
            .all()
        )
    return render_template(
        "user_edit.html",
        name=current_user.name,
        u=u,
        current_academic_start=_current_academic_start(date.today()),
        subscription_target=_subscription_target_start(date.today()),
        membership_logs=logs,
        role_logs=role_logs,
        photo_error=photo_error,
        password_error=password_error,
        photo_filename=get_user_cafe_photo(u.id, cafe.id),
    )


@admin.route("/admin/new", methods=["POST", "GET"])
@login_required
def user_new():
    """Création d'un nouveau réparateur (admin)."""
    _admin_only()
    cafe = require_active_repaircafe()
    user_exists = (
        request.method == "POST"
        and db.session.query(User).filter_by(email=request.form.get("email")).count() != 0
    )
    if request.method == "POST" and not user_exists:
        u = User()
        db.session.add(u)
        u.name = request.form.get("name")
        u.email = request.form.get("email")
        if request.form.get("last_membership"):
            try:
                u.last_membership = int(request.form.get("last_membership"))
            except ValueError:
                pass
        is_admin = True if request.form.get("admin") else False
        u.admin = is_admin
        db.session.commit()
        db.session.execute(
            user_repaircafe.insert().values(
                user_id=u.id,
                repaircafe_id=cafe.id,
                role="admin" if is_admin else None,
            )
        )
        if not u.active_repaircafe_id:
            u.active_repaircafe_id = cafe.id
        db.session.commit()
        # Redirection sans filtre email pour afficher la liste complète
        return redirect(url_for("admin.user_list"), code=302)
    else:
        return render_template("user_new.html", already_exists=user_exists, name=current_user.name)
