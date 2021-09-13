import glob
import os
from flask_login import login_required, current_user
from datetime import date, datetime
import pytz
from flask import current_app, Blueprint, render_template, request, redirect, url_for, send_from_directory
from .models import Category, State, Repair, Brand, State, User, Note, CloseStatus
from . import db, thumb
import thumbnails

main = Blueprint('main', __name__)
LOCAL_TIMEZONE = pytz.timezone('Europe/Paris')

@main.route('/')
@login_required
def index():
    return render_template('index.html',
                           name=current_user.name,
                           categories=Category.query.all(),
                           users=User.query.all())

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)

@main.route('/new')
@login_required
def categories():
    return render_template('form_new.html', today=date.today(),
                           categories=Category.query.all(),
                           states=State.query.all(),
                           name=current_user.name,
                           to_print=request.args.get("to_print"))

def get_or_create_brand(brand_name):
    brand = db.session.query(Brand).filter_by(name=brand_name).first()
    if not brand:
       brand = Brand(name=brand_name)
    return brand

def get_repairid(date):
    prefix = "%02d%02d%02d-" % (date.year-2000, date.month, date.day)
    day_repairs = db.session.query(Repair).filter(Repair.id.like(prefix + '%'))
    return prefix + "%03d" % (day_repairs.count()+1) 

@main.route('/new', methods=['POST'])
@login_required
def post_new_object():
    brand = get_or_create_brand(request.form['brand'])
    category = db.session.query(Category).filter_by(id=request.form["category"]).first()
    initial_state = db.session.query(State).filter_by(id=request.form["initial_state"]).first()
    date = datetime.strptime(request.form['date'], '%Y-%m-%d')
    value = request.form["value"] and float(request.form["value"]) or None
    year = request.form["year"] and int(request.form["year"]) or None
    repair_id = get_repairid(date)

    r = Repair(
        id = repair_id,
        created = date,
        name = request.form["name"],
        email = request.form["email"],
        phone = request.form["phone"],
        category = category,
        brand = brand,
        initial_state = initial_state,
        current_state = initial_state,
        otype = request.form["otype"],
        model = request.form["model"],
        serial_number = request.form["sn"],
        year = year,
        value = value,
        description = request.form["description"],
        validated = request.form["validated"] != ''
    )

    db.session.add(r)
    db.session.commit()

    return redirect(url_for("main.update_object", id=r.id), code=302)

@main.route('/media/<path:filename>')
def media_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@main.route('/update/<string:id>', methods=['GET', 'POST'])
@login_required
def update_object(id):
    r = db.session.query(Repair).filter_by(id=id).first()

    if request.method == 'POST':
        current_users = sorted(request.form.getlist('users'))
        previous_users = sorted(request.form.getlist('previous_users'))
        previous_state = request.form.get('previous_state')
        current_state = request.form.get('current_state')
        previous_location = request.form.get('previous_location')
        current_location = request.form.get('current_location')
        note = request.form.get('note')
        log = []
        change = False
        closeChoice = int(request.form.get('closeChoice') or 0)
        if closeChoice:
            new_close_status = db.session.query(CloseStatus).filter_by(id=closeChoice).first()
            log += ["Fermeture fiche (%s)" % new_close_status.label]
            r.close_status = db.session.query(CloseStatus).filter_by(id=closeChoice).first()
            change = True
        elif r.close_status.id > 0:
            log += ["Réouverture fiche"]
            r.close_status = db.session.query(CloseStatus).filter_by(id=closeChoice).first()
            change = True
        if current_users != previous_users: 
            r.users = [db.session.query(User).filter_by(id=uid).first() for uid in current_users]
            log += ["Réparateurs changés (→ %s)" % ", ".join([u.name for u in r.users])]
            change = True
        if current_state is not None and previous_state != current_state:
            r.current_state_id=int(current_state)
            log += ["Etat changé (→ %s)" % r.current_state.label]
            change = True
        if current_location != previous_location:
            r.location = current_location
            log += ["Localisation changé (→ '%s')" % current_location]
            change = True
        if note or log:
            n = Note(user_id=current_user.id, content=note, log=" ; ".join(log), repair_id=id)
            db.session.add(n)
            change = True
        if change:
            db.session.commit()
    # get image list
    images = glob.glob(os.path.join(current_app.config['UPLOAD_FOLDER'], id+"_*"))
    images_idx = []
    for p in images:
        images_idx.append((len(images_idx), p.split("/")[-1], "cache/"+thumb.get_thumbnail(p.split("/")[-1], "200x200").split("/")[-1]))
    return render_template('update.html',
                           name=current_user.name,
                           categories=Category.query.all(),
                           states=State.query.all(),
                           users=User.query.all(),
                           notes=Note.query.filter_by(repair_id=id).order_by(Note.id.desc()),
                           r=r,
                           current_users=[u.id for u in r.users],
                           closestatus=CloseStatus.query.all(),
                           images=images_idx)
