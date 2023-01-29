import glob
import os
from flask_login import login_required, current_user
from datetime import date, datetime
from sqlalchemy import and_
import pytz
from flask import current_app, Blueprint, render_template, request, redirect, url_for, send_from_directory
from .models import Category, Repair, Brand, State, User, Note, CloseStatus, SpareStatus, SpareChange, Log, Notification
from . import db, thumb

admin = Blueprint('admin', __name__)
LOCAL_TIMEZONE = pytz.timezone('Europe/Paris')

@admin.route('/admin')
@login_required
def user_list():
    r"""main admin page"""
    email = request.args.get('email', None)
    return render_template('user_list.html',
                           name=current_user.name,
                           filter_email=email,
                           users=User.query.order_by(User.last_membership.desc()).order_by(User.name).all())

@admin.route('/admin/edit/<string:user_id>', methods=['POST', 'GET'])
@login_required
def user_edit(user_id):
    r"""main admin page"""
    u = db.session.query(User).filter_by(id=user_id).first()
    if request.method == 'POST':
        u.name = request.form.get('name')
        u.email = request.form.get('email')
        if request.form.get('last_membership'):
            u.last_membership = request.form.get('last_membership')
        else:
            u.last_membership = None
        u.admin = request.form.get('admin', False) and True
        db.session.commit()
        return redirect(url_for("admin.user_list", email=u.email), code=302)
    else:
        return render_template('user_edit.html',
                               name=current_user.name,
                               u=u)

@admin.route('/admin/new', methods=['POST', 'GET'])
@login_required
def user_new():
    r"""main admin page"""
    user_exists = request.method == 'POST' and db.session.query(User).filter_by(email=request.form.get('email')).count() != 0
    if request.method == 'POST' and not user_exists:
        u = User()
        db.session.add(u)
        u.name = request.form.get('name')
        u.email = request.form.get('email')
        if request.form.get('last_membership'):
            u.last_membership = request.form.get('last_membership')
        if request.form.get('admin'):
            u.admin = request.form.get('admin')
        db.session.commit()
        return redirect(url_for("admin.user_list", email=u.email), code=302)
    else:
        return render_template('user_new.html',
                               already_exists=user_exists,
                               name=current_user.name)
