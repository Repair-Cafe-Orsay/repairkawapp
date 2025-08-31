"""Module d'authentification pour RepairKawapp.

RepairKawapp – Repair Café management application
Licence: MIT (voir fichier LICENSE)
Auteur principal: Jean Senellart

Nettoyage global : imports organisés, PEP8, docstrings, harmonisation du style.
"""

import hashlib
import time

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required, login_user, logout_user
from flask_mail import Message
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, mail
from .models import User


def _s():
    """Retourne dynamiquement le serializer courant (évite références figées)."""
    from . import serializer as current_serializer  # re-résolution

    return current_serializer


auth = Blueprint("auth", __name__)


@auth.route("/login")
def login():
    """Affiche la page de login et déconnecte l'utilisateur courant."""
    logout_user()
    return render_template("login.html")


@auth.route("/login", methods=["POST"])
def login_post():
    """Traite le formulaire de login utilisateur."""
    email = request.form.get("email")
    password = request.form.get("password")
    remember = True if request.form.get("remember") else False
    user = User.query.filter_by(email=email).first()
    if not user or not user.password:
        flash("Mot de passe incorrect")
        return redirect(url_for("auth.login"))

    # Gestion legacy: anciens hachages simples 'sha256$<salt>$<hash>' (Werkzeug versions anciennes)
    if user.password.startswith("sha256$"):
        try:
            _method, salt, old_hash = user.password.split("$", 2)
            calc = hashlib.sha256((salt + password).encode()).hexdigest()
            if calc != old_hash:
                flash("Mot de passe incorrect")
                return redirect(url_for("auth.login"))
            # upgrade vers algo moderne par défaut
            user.password = generate_password_hash(password)
            db.session.commit()
        except Exception:
            flash("Mot de passe incorrect")
            return redirect(url_for("auth.login"))
    else:
        try:
            if not check_password_hash(user.password, password):
                flash("Mot de passe incorrect")
                return redirect(url_for("auth.login"))
        except ValueError:
            # hash inconnu -> échec silencieux
            flash("Mot de passe incorrect")
            return redirect(url_for("auth.login"))
    login_user(user, remember=remember)
    # Redirection prioritaire vers ?next= si présent et interne
    next_url = request.args.get("next") or request.form.get("next")
    if next_url:
        # sécurité: only internal relative paths
        try:
            from urllib.parse import urlparse

            parts = urlparse(next_url)
            if parts.netloc or parts.scheme:
                next_url = None
            elif not parts.path.startswith("/"):
                next_url = None
        except Exception:
            next_url = None
    # Fallback vers le dashboard racine (/)
    return redirect(next_url or url_for("main.dashboard"))


@auth.route("/forgot_password")
def forgot_password():
    """Affiche la page de mot de passe oublié."""
    return render_template("forgot_password.html")


@auth.route("/change_password", methods=["POST"])
def change_password():
    """Envoie un email de lien de réinitialisation."""
    email = request.form.get("email")
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify([False, "Cet user n'a pas de compte"])

    data = {"i": str(user.id), "s": user.seqid, "t": int(time.time() / 3600)}
    token = _s().dumps(data)

    msg = Message("Mot de passe oublié", sender="app@repaircafe-orsay.org", recipients=[email])
    msg.body = """Hello,

Vous recevez cet email car quelqu'un a demandé une réinitalisation de votre password
sur {}. Si c'est bien vous, pour réinitialiser votre mot de passe,
rendez-vous sur cette url: {}{}""".format(
        current_app.config["APP_URL"],
        current_app.config["APP_URL"],
        url_for("auth.init_password", token=token),
    )
    mail.send(msg)

    return jsonify([True, "Vérifiez vos emails"])


@auth.route("/logout")
@login_required
def logout():
    """Déconnecte l'utilisateur et redirige vers login."""
    logout_user()
    return redirect(url_for("auth.login"))


@auth.route("/init_password/<string:token>", methods=["GET"])
def init_password(token):
    """Affiche le formulaire de changement de mot de passe via token."""
    logout_user()

    data = _s().loads(token)
    user = User.query.filter_by(id=data["i"]).first()

    if user.seqid != data["s"] or int(time.time() / 3600) - data["t"] >= 1:
        flash("Le lien pour changer le password n'est plus valide")
        return redirect(url_for("auth.login"))

    user.seqid = user.seqid + 1
    db.session.commit()

    return render_template(
        "new_password.html",
        email=user.email,
        token=_s().dumps({"i": str(user.id), "s": user.seqid}),
    )


@auth.route("/init_password", methods=["POST"])
def post_new_password():
    """Finalise le changement de mot de passe depuis le formulaire token."""
    logout_user()

    data = _s().loads(request.form.get("token"))
    password = request.form.get("password")

    user = User.query.filter_by(id=data["i"]).first()

    if user.seqid != data["s"]:
        flash("Le lien pour changer le password n'est plus valide")
        return redirect(url_for("auth.login"))

    user.seqid = user.seqid + 1
    # Utilise l'algorithme par défaut (pbkdf2:sha256) de Werkzeug
    user.password = generate_password_hash(password)
    db.session.commit()

    return render_template("login.html")


@auth.route("/change_password_logged", methods=["POST"])
@login_required
def change_password_logged():
    """Change le mot de passe de l'utilisateur connecté (flux direct profil).

    Attend old_password, new_password (>=6 chars). Retour JSON.
    """
    import json as _json

    from flask_login import current_user

    payload = request.get_json(silent=True) or request.form
    old_password = payload.get("old_password") or ""
    new_password = payload.get("new_password") or ""
    if len(new_password) < 6:
        return (
            _json.dumps({"ok": False, "error": "too_short"}),
            400,
            {"Content-Type": "application/json"},
        )
    # Si un password existe on valide l'ancien, sinon on autorise set direct
    if current_user.password and not current_user.password.startswith("sha256$"):
        try:
            if not check_password_hash(current_user.password, old_password):
                return (
                    _json.dumps({"ok": False, "error": "bad_old"}),
                    403,
                    {"Content-Type": "application/json"},
                )
        except ValueError:
            return (
                _json.dumps({"ok": False, "error": "bad_old"}),
                403,
                {"Content-Type": "application/json"},
            )
    elif current_user.password and current_user.password.startswith("sha256$"):
        # Ancien format legacy
        try:
            _method, salt, old_hash = current_user.password.split("$", 2)
            import hashlib as _h

            calc = _h.sha256((salt + old_password).encode()).hexdigest()
            if calc != old_hash:
                return (
                    _json.dumps({"ok": False, "error": "bad_old"}),
                    403,
                    {"Content-Type": "application/json"},
                )
        except Exception:
            return (
                _json.dumps({"ok": False, "error": "bad_old"}),
                403,
                {"Content-Type": "application/json"},
            )
    # Mise à jour
    current_user.password = generate_password_hash(new_password)
    # Invalidation seqid (force invalidation anciens tokens reset) en l'incrémentant
    current_user.seqid = (current_user.seqid or 0) + 1
    db.session.commit()
    return _json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}
