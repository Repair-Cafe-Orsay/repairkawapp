"""Module d'administration de RepairKawapp.

RepairKawapp – Repair Café management application
Licence: MIT (voir fichier LICENSE)
Auteur principal: Jean Senellart

Nettoyage global : imports organisés, PEP8, docstrings, harmonisation du style.
"""

from datetime import date

import pytz
from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from . import db
from .models import BoardRoleLog, MembershipLog, User
from .services.image_service import process_user_photo

admin = Blueprint("admin", __name__)
LOCAL_TIMEZONE = pytz.timezone("Europe/Paris")


@admin.route("/admin")
@login_required
def user_list():
    """Page principale d'administration (liste des utilisateurs)."""
    email = request.args.get("email", None)
    return render_template(
        "user_list.html",
        name=current_user.name,
        filter_email=email,
        users=User.query.order_by(User.last_membership.desc()).order_by(User.name).all(),
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
    """Edition d'un utilisateur (admin)."""
    u = db.session.query(User).filter_by(id=user_id).first()
    photo_error = None
    password_error = None
    if request.method == "POST":
        # Bouton d'action rapide "set_current_membership"
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
        u.name = request.form.get("name")
        u.email = request.form.get("email")
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
        # Upload photo (admin) même logique que profil utilisateur
        if "photo" in request.files and request.files["photo"].filename:
            raw = request.files["photo"].read()
            filename, err = process_user_photo(
                raw, current_app.config["UPLOAD_FOLDER"], u.id, request.form.get
            )
            if err:
                photo_error = err
            else:
                u.photo_filename = filename
        # On ne modifie plus last_membership via le formulaire standard (lecture seule)
        # Conversion explicite en booléen pour éviter les valeurs '' dans la colonne Boolean
        u.admin = True if request.form.get("admin") else False
        # Commit seulement si pas d'erreur photo ou password
        if not photo_error and not password_error:
            db.session.commit()
            return redirect(url_for("admin.user_list"), code=302)
        else:
            # Commit final : si seule la photo est en erreur on sauvegarde le reste.
            db.session.commit()
            # Recharger page avec erreurs (photo_error / password_error)
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
    )


@admin.route("/admin/new", methods=["POST", "GET"])
@login_required
def user_new():
    """Création d'un nouvel utilisateur (admin)."""
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
        u.admin = True if request.form.get("admin") else False
        db.session.commit()
        # Redirection sans filtre email pour afficher la liste complète
        return redirect(url_for("admin.user_list"), code=302)
    else:
        return render_template("user_new.html", already_exists=user_exists, name=current_user.name)
