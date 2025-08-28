"""Module d'administration de RepairKawapp.

Nettoyage global : imports organisés, PEP8, docstrings, harmonisation du style.
"""
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
import pytz

from .models import User
from . import db

admin = Blueprint('admin', __name__)
LOCAL_TIMEZONE = pytz.timezone('Europe/Paris')

@admin.route('/admin')
@login_required
def user_list():
    """Page principale d'administration (liste des utilisateurs)."""
    email = request.args.get('email', None)
    return render_template('user_list.html',
                           name=current_user.name,
                           filter_email=email,
                           users=User.query.order_by(User.last_membership.desc()).order_by(User.name).all())

@admin.route('/admin/edit/<string:user_id>', methods=['POST', 'GET'])
@login_required
def user_edit(user_id):
    """Edition d'un utilisateur (admin)."""
    u = db.session.query(User).filter_by(id=user_id).first()
    if request.method == 'POST':
        u.name = request.form.get('name')
        u.email = request.form.get('email')
        if request.form.get('last_membership'):
            try:
                u.last_membership = int(request.form.get('last_membership'))
            except ValueError:
                u.last_membership = None
        else:
            u.last_membership = None
        # Conversion explicite en booléen pour éviter les valeurs '' dans la colonne Boolean
        u.admin = True if request.form.get('admin') else False
        db.session.commit()
        return redirect(url_for("admin.user_list", email=u.email), code=302)
    else:
        return render_template('user_edit.html',
                               name=current_user.name,
                               u=u)

@admin.route('/admin/new', methods=['POST', 'GET'])
@login_required
def user_new():
    """Création d'un nouvel utilisateur (admin)."""
    user_exists = request.method == 'POST' and db.session.query(User).filter_by(email=request.form.get('email')).count() != 0
    if request.method == 'POST' and not user_exists:
        u = User()
        db.session.add(u)
        u.name = request.form.get('name')
        u.email = request.form.get('email')
        if request.form.get('last_membership'):
            try:
                u.last_membership = int(request.form.get('last_membership'))
            except ValueError:
                u.last_membership = None
        # Affectation booléenne claire (checkbox => 'on' / '1' sinon absent)
        u.admin = True if request.form.get('admin') else False
        db.session.commit()
        return redirect(url_for("admin.user_list", email=u.email), code=302)
    else:
        return render_template('user_new.html',
                               already_exists=user_exists,
                               name=current_user.name)
