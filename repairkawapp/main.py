import glob
import os
from flask_login import login_required, current_user
from datetime import date, datetime
from sqlalchemy import and_
import pytz
from flask import current_app, Blueprint, render_template, request, redirect, url_for, send_from_directory
from .models import Category, Repair, Brand, State, User, Note, CloseStatus, SpareStatus, SpareChange, Log, Notification
from . import db, thumb

main = Blueprint('main', __name__)
LOCAL_TIMEZONE = pytz.timezone('Europe/Paris')

@main.route('/')
@login_required
def index():
    r"""main page"""
    return render_template('index.html',
                           name=current_user.name,
                           categories=Category.query.order_by(Category.name).all(),
                           users=User.query.order_by(User.name).all())

@main.route('/profile')
@login_required
def profile():
    r"""statistics"""
    return render_template('profile.html', name=current_user.name,
                           last_membership_ok=current_user.last_membership==date.today().year)

@main.route('/new')
@login_required
def new_repair():
    r"""new repair form"""
    from_id=request.args.get("from_id")
    from_user = {}
    if from_id:
        r = db.session.query(Repair).filter_by(display_id=from_id).first()
        from_user = {"name": r.name, "email": r.email, "phone": r.phone, "age": r.age}
    return render_template('form_new.html', today=date.today(),
                           categories=Category.query.order_by(Category.name).all(),
                           states=State.query.order_by(State.id).all(),
                           name=current_user.name,
                           from_user=from_user,
                           r="")

@main.route('/edit/<string:repair_id>')
@login_required
def edit_repair(repair_id):
    r"""edit repair form"""
    return render_template('form_new.html', today=date.today(),
                           categories=Category.query.order_by(Category.name).all(),
                           states=State.query.order_by(State.id).all(),
                           name=current_user.name,
                           from_user={},
                           r=db.session.query(Repair).filter_by(display_id=repair_id).first())


@main.route('/del/<string:repair_id>')
@login_required
def del_repair(repair_id):
    r"""delete a repair form"""
    r = db.session.query(Repair).filter_by(display_id=repair_id).delete()
    db.session().commit()
    return redirect(url_for("main.index"), code=302)

def get_or_create_brand(brand_name):
    brand = db.session.query(Brand).filter_by(name=brand_name).first()
    if not brand:
       brand = Brand(name=brand_name)
    return brand

def get_repairid(date, manual_id, existing_id=None):
    r"""generate repair id"""
    prefix = "%02d%02d%02d-" % (date.year-2000, date.month, date.day)
    if manual_id:
        if not manual_id.isdigit():
            manual_id = ("0000"+manual_id)[-4:]
            full_id = prefix+manual_id
        else:
            manual_id = ("0000"+manual_id)[-3:]
            incid = 0
            full_id = prefix+manual_id
            if full_id == existing_id:
                return full_id
            while Repair.query.filter_by(display_id=full_id).first():
                full_id = prefix+manual_id+chr(ord('a')+incid)
                incid += 1
        return full_id
    day_repairs = Repair.query.filter(Repair.display_id.like(prefix + '%'))
    return prefix + "%03d" % (day_repairs.count()+1) 

@main.route('/new', methods=['POST'])
@login_required
def post_object():
    r"""post a new object"""
    rid = request.form.get('rid')
    brand = get_or_create_brand(request.form['brand'])
    category = db.session.query(Category).filter_by(id=request.form["category"]).first()
    initial_state = db.session.query(State).filter_by(id=request.form["initial_state"]).first()
    if request.form.get('date'):
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')
    else:
        date = None
    value = request.form["value"] and int(request.form["value"]) or None
    weight = request.form["weight"] and int(request.form["weight"]) or None
    year = request.form["year"] and int(request.form["year"]) or None
    age = request.form.get("age") and int(request.form["age"]) or None

    if not rid:
        display_id = get_repairid(date, request.form["manual_id"])
        r = Repair()
        db.session.add(r)
        r.current_state = initial_state
    else:
        r = db.session.query(Repair).filter_by(id=rid).first()
        date = r.created
        display_id = get_repairid(date, request.form["manual_id"], r.display_id)

    if not rid:
        n = Log(user_id=current_user.id, content="Création de la fiche", repair=r)
    else:
        n = Log(user_id=current_user.id, content="Modification de la fiche", repair=r)

    db.session.add(n)

    r.display_id = display_id
    r.created = date
    r.age = age
    r.name = request.form["name"]
    r.email = request.form["email"]
    r.phone = request.form["phone"]
    r.category = category
    r.brand = brand
    r.initial_state = initial_state
    r.otype = request.form["otype"]
    r.model = request.form["model"]
    r.serial_number = request.form["sn"]
    r.year = year
    r.value = value
    r.weight = weight
    r.description = request.form["description"]
    r.validated = request.form["validated"] != ''

    db.session.commit()

    return redirect(url_for("main.update_object", id=r.display_id), code=302)

@main.route('/media/<path:filename>')
def media_file(filename):
    r"""api to retrieve files without direct access to upload directory"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@main.route('/update/<string:id>', methods=['POST'])
@login_required
def update_object(id):
    r"""post update on an object"""
    r = db.session.query(Repair).filter_by(display_id=id).first()

    if request.method == 'POST':
        current_users = sorted(request.form.getlist('users'))
        previous_users = sorted(request.form.getlist('previous_users'))
        previous_state = request.form.get('previous_state')
        current_state = request.form.get('current_state')
        previous_location = request.form.get('previous_location')
        current_location = request.form.get('current_location')
        note = request.form.get('note')
        change = False
        closeChoice = request.form.get('closeChoice')
        closeChoice = closeChoice and int(request.form.get('closeChoice')) or 0
        if closeChoice > 1:
            new_close_status = db.session.query(CloseStatus).filter_by(id=closeChoice).first()
            db.session.add(Log(user_id=current_user.id, repair=r,
                               content="Fermeture fiche (%s)" % new_close_status.label))
            r.close_status = db.session.query(CloseStatus).filter_by(id=closeChoice).first()
            change = True
        elif closeChoice == 1:
            db.session.add(Log(user_id=current_user.id, repair=r,
                               content="Réouverture fiche"))
            r.close_status = db.session.query(CloseStatus).filter_by(id=closeChoice).first()
            change = True
        if current_users != previous_users: 
            r.users = [db.session.query(User).filter_by(id=uid).first() for uid in current_users]
            db.session.add(Log(user_id=current_user.id, repair=r,
                               content="Réparateurs changés (→ %s)" % ", ".join([u.name for u in r.users])))
            change = True
        if current_state is not None and previous_state != current_state:
            r.current_state_id=int(current_state)
            db.session.add(Log(user_id=current_user.id, repair=r,
                               content="Etat changé (→ %s)" % r.current_state.label))
            change = True
        if current_location != previous_location:
            r.location = current_location
            db.session.add(Log(user_id=current_user.id, repair=r,
                               content="Localisation changé (→ '%s')" % current_location))
            change = True
        if note:
            n = Note(user_id=current_user.id, content=note, repair=r)
            db.session.add(n)
            change = True
        if change:
            db.session.commit()
    return redirect(url_for("main.get_update", id=r.display_id), code=302)

@main.route('/update/<string:id>', methods=['GET'])
@login_required
def get_update(id):
    r"""update page for an object"""
    r = db.session.query(Repair).filter_by(display_id=id).first()
    # get image list
    images = glob.glob(os.path.join(current_app.config['UPLOAD_FOLDER'], id+"_*"))
    images_idx = []
    for p in images:
        images_idx.append((len(images_idx), p.split("/")[-1], "cache/"+thumb.get_thumbnail(p.split("/")[-1], "200x200").split("/")[-1]))
    return render_template('update.html',
                           name=current_user.name,
                           categories=Category.query.order_by(Category.name).all(),
                           states=State.query.order_by(State.id).all(),
                           users=User.query.order_by(User.name).all(),
                           notes=db.session.query(Note, Notification).filter_by(repair=r).order_by(Note.id.desc())\
                                        .outerjoin(Notification, and_(Notification.note_id==Note.id, Notification.user_id==current_user.id)),
                           logs=Log.query.filter_by(repair=r).order_by(Log.id.desc()),
                           r=r,
                           current_users=[u.id for u in r.users],
                           closestatus=CloseStatus.query.order_by(CloseStatus.id).all(),
                           images=images_idx,
                           splist=SpareChange.query.filter_by(repair=r).order_by(SpareChange.id.asc()),
                           spare_statuses=SpareStatus.query.order_by(SpareStatus.id).all())
