"""
Module API de RepairKawapp.
Nettoyage global : imports organisés, PEP8, docstrings, harmonisation du style.
"""
import os
import glob
from datetime import datetime
from flask import (
    current_app, Blueprint, request, jsonify, render_template
)
from flask_login import login_required, current_user
from flask_mail import Message
from werkzeug.utils import secure_filename
from sqlalchemy import func, distinct
from .models import (
    Brand, Repair, User, SpareStatus, SpareChange, Note, Log,
    Notification, NotificationType, CloseStatus, Category
)
from . import db, mail
from .services.spare_service import add_spare, delete_spare
from .services.stats_service import parse_period, get_cached_lists, compute_stats

api = Blueprint('api', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@api.route('/new_spare/<string:repair_id>')
@login_required
def new_spare(repair_id):
    """Ajout d'une pièce détachée à une réparation (service)."""
    sp, l = add_spare(
        db.session,
        repair_id,
        item=request.args.get("item"),
        status_id=int(request.args.get("status_id")),
        source=request.args.get("source"),
        note=request.args.get("note")
    )
    db.session.commit()
    return jsonify({
        "sparepart": render_template('sparepart.html', sp=sp,
                                      spare_statuses=SpareStatus.query.order_by(SpareStatus.id).all()),
        "log": render_template('log.html', log=l)
    })

@api.route('/del_spare/<string:repair_id>')
@login_required
def del_spare(repair_id):
    """Suppression d'une pièce détachée d'une réparation (service)."""
    delete_spare(db.session, int(request.args.get("id")))
    db.session.commit()
    return jsonify(True)

@api.route('/api/brandsearch', methods=['GET'])
def brandsearch():
    """Recherche dynamique de marque (insensible à la casse)."""
    search = request.args.get('q')
    query = db.session.query(Brand.name).filter(Brand.name.like(str(search) + '%'))
    results = [mv[0] for mv in query.all()]
    return jsonify(matching_results=results)

@api.route('/deleteimg/<string:repair_id>/<path:path>', methods=['GET'])
@login_required
def del_file(repair_id, path):
    """Suppression d'une image attachée à une réparation."""
    filename = os.path.join(current_app.config['UPLOAD_FOLDER'], path)
    if os.path.exists(filename):
        os.remove(filename)
    fileprefix = ".".join(path.split(".")[:-1])
    for f in glob.glob(os.path.join(current_app.config['THUMBNAIL_MEDIA_THUMBNAIL_ROOT'], fileprefix+"*.*")):
        os.remove(f)
    return jsonify(True)

@api.route('/uploadimg/<string:repair_id>', methods=['POST'])
@login_required
def post_file(repair_id):
    r"""post an image"""
    file = request.files.get("file")
    if file:
        if allowed_file(file.filename):
            filename = os.path.join(current_app.config['UPLOAD_FOLDER'], repair_id+"_"+secure_filename(file.filename))
            if os.path.exists(filename):
                return jsonify("existing file"), 409
            file.save(filename)
            return jsonify(filename.split("/")[-1])
        else:
            return jsonify("unauthorized file"), 403
    return jsonify(None)

@api.route('/api/add_todo')
def add_todo():
    r"""add a notification"""
    note_id = request.args.get("note_id")
    if not note_id:
        return jsonify(False), 500
    existing_notification = Notification.query.filter_by(note_id=note_id).filter_by(user_id=current_user.id).count()
    if existing_notification:
        return jsonify(False), 500

    notification = Notification(
        note_id=note_id,
        user_id=current_user.id,
        notification_type=NotificationType.todo
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify(notification.id)

@api.route('/api/del_notification')
def del_notification():
    r"""remove a notification"""
    notification_id = request.args.get("notification_id")
    Notification.query.filter_by(id=notification_id).delete()
    db.session.commit()

    return jsonify(None)

@api.route('/api/get_notifs')
@login_required
def get_notifs():
    """Retourne le fragment HTML listant les notifications de l'utilisateur courant.

    Nécessaire pour les appels AJAX dans base.html (bouton notifications).
    """
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).all()
    return render_template('notif_list.html', notifs=notifs)

@api.route('/api/get_notifcount')
@login_required
def get_notifcount():
    """Compte simple des notifications de l'utilisateur courant.

    Utilisé par le JS pour afficher/masquer le badge de notification.
    """
    count = Notification.query.filter_by(user_id=current_user.id).count()
    return jsonify(count)

@api.route('/api/repairsearch')
def repairsearch():
    r"""Recherche paginée des réparations."""
    length = request.args.get('length', current_app.config.get('PAGE_SIZE', 25), type=int)
    page = (request.args.get('start', 0, type=int) / length) + 1
    searchValue = request.args.get('search[value]')
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
            repairs = repairs.outerjoin(User, Repair.users).filter(User.id == None)
    if searchValue:
        repairs = repairs.join(Brand)
        repairs = repairs.filter(Repair.display_id.like(searchValue + '%') |
                                 Repair.name.like('%' + searchValue + '%') |
                                 Repair.otype.like('%' + searchValue + '%') |
                                 Brand.name.like(searchValue + '%'))
    if request.args.get('category'):
        repairs = repairs.filter_by(category_id=request.args.get('category'))
    nbFiltered = repairs.count()
    repairs = repairs.order_by(Repair.display_id.desc()).paginate(page=page, per_page=length, error_out=False)
    json = jsonify({"repairs": [{"id": r.display_id, "name": r.name, "category": r.category.name, "otype": r.otype,
                                 "brand": r.brand and r.brand.name or "", "close_status": r.close_status.label[0]}
                                for r in repairs.items],
                    "draw": request.args.get('draw', 1, type=int),
                    "recordsTotal": db.session.query(Repair).count(),
                    "recordsFiltered": nbFiltered,
                    "has_next": repairs.has_next,
                    "has_prev": repairs.has_prev,
                    "next_num": repairs.next_num,
                    "prev_num": repairs.prev_num})
    return json

# caches
all_categories = []
all_status = []

@api.route('/api/stats')
def stats():
    r"""API stats refactorisée via service."""
    date_from, date_to = parse_period(request.args.get('from'), request.args.get('to'))
    if not date_from:
        return {}
    global all_categories, all_status
    get_cached_lists(db.session, all_categories, all_status)
    stats_raw = compute_stats(db.session, date_from, date_to)
    return jsonify({
        'from': date_from,
        'to': date_to,
        'categories': all_categories,
        'status': all_status,
        'count_by_status': {id: [status, count] for (count, id, status) in stats_raw['status_raw']},
        'count_by_category': {category: (count, icon_id) for (category, count, icon_id) in stats_raw['categories_raw']},
        'visitors': stats_raw['visitors'],
        'total': stats_raw['total']
    })

@api.route('/sendmail')
def sendmail():
    msg = Message( 
                'Hello', 
                sender ='app@repaircafe-orsay.org', 
                recipients = ['jean@repaircafe-orsay.org'] 
    ) 
    msg.body = 'Hello Flask message sent from Flask-Mail'
    mail.send(msg)
    return jsonify(True)
