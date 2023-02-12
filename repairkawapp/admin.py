from flask_login import login_required, current_user
import pytz
from flask import Blueprint, render_template, request, redirect, url_for
from .models import RepairCafe, User
from . import db

admin = Blueprint('admin', __name__)
LOCAL_TIMEZONE = pytz.timezone('Europe/Paris')

@admin.route('/admin')
@login_required
def user_list():
    r"""main admin page"""
    email = request.args.get('email', None)
    if current_user.super_admin:
        users = User.query.order_by(User.last_membership.desc()).order_by(User.name).all()
    else:
        # TODO: join request to keep only users from listed repaircafes
        users = User.query.order_by(User.last_membership.desc()).order_by(User.name).all()
    return render_template('user_list.html',
                           name=current_user.name,
                           filter_email=email,
                           repaircafes=current_user.repaircafes,
                           users=users)

@admin.route('/admin/edit/<string:user_id>', methods=['POST', 'GET'])
@login_required
def user_edit(user_id):
    r"""main admin page"""
    u = db.session.query(User).filter_by(id=user_id).first()
    if request.method == 'POST':
        repaircafes = request.form.getlist('repaircafes')
        previous_repaircafes = request.form.getlist('previous_repaircafes')
        u.name = request.form.get('name')
        u.email = request.form.get('email')
        if request.form.get('last_membership'):
            u.last_membership = request.form.get('last_membership')
        else:
            u.last_membership = None
        u.admin = request.form.get('admin', False) and True
        if repaircafes != previous_repaircafes:
            u.repaircafes = [db.session.query(RepairCafe).filter_by(id=rc_id).first() for rc_id in repaircafes]
        db.session.commit()
        return redirect(url_for("admin.user_list", email=u.email), code=302)
    else:
        return render_template('user_edit.html',
                               name=current_user.name,
                               repaircafes=current_user.super_admin and RepairCafe.query.order_by(RepairCafe.name).all()
                                           or current_user.repaircafes,
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
                               repaircafes=current_user.repaircafes,
                               name=current_user.name)
