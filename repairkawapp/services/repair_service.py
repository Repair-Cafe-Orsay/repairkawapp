"""Services métier pour les réparations (isoler la logique de `main.py`)."""
from datetime import datetime, date
from typing import Optional, Sequence
from sqlalchemy.orm import Session
from flask_login import current_user

from ..models import Repair, Brand, Category, State, Log, CloseStatus, User, Note


def get_or_create_brand(session: Session, brand_name: str) -> Brand:
    brand = session.query(Brand).filter_by(name=brand_name).first()
    if not brand:
        brand = Brand(name=brand_name)
        session.add(brand)
    return brand


def generate_display_id(session: Session, created_date: date, manual_id: str | None, existing_id: str | None = None) -> str:
    prefix = f"{created_date.year-2000:02d}{created_date.month:02d}{created_date.day:02d}-"
    if manual_id:
        if not manual_id.isdigit():
            manual_id = ("0000" + manual_id)[-4:]
            full_id = prefix + manual_id
        else:
            manual_id = ("0000" + manual_id)[-3:]
            incid = 0
            full_id = prefix + manual_id
            if full_id == existing_id:
                return full_id
            while session.query(Repair).filter_by(display_id=full_id).first():
                full_id = prefix + manual_id + chr(ord('a') + incid)
                incid += 1
        return full_id
    day_repairs = session.query(Repair).filter(Repair.display_id.like(prefix + '%'))
    return prefix + f"{day_repairs.count()+1:03d}"


def create_repair(session: Session, form, category: Category, state: State, brand: Brand) -> Repair:
    created_date = datetime.strptime(form['date'], '%Y-%m-%d') if form.get('date') else date.today()
    # Champs optionnels accédés via get() pour éviter BadRequestKeyError si absents du formulaire
    r = Repair(
        display_id=generate_display_id(session, created_date, form.get('manual_id')),
        created=created_date,
        age=form.get('age') and int(form['age']) or None,
        name=form['name'],  # requis (attribut required dans le formulaire)
        email=form.get('email'),  # optionnel
        phone=form.get('phone'),  # optionnel
        category=category,
        brand=brand,
        initial_state=state,
        current_state=state,
        otype=form['otype'],  # requis
        model=form['model'],  # requis
        serial_number=form.get('sn'),  # optionnel
        year=form.get('year') and int(form['year']) or None,
        value=form.get('value') and int(form['value']) or None,
        weight=form.get('weight') and int(form['weight']) or None,
        description=form['description'],  # requis (required dans le formulaire)
        validated=form.get('validated') != ''
    )
    session.add(r)
    session.add(Log(user_id=current_user.id, content="Création de la fiche", repair=r))
    return r


def update_repair(session: Session, repair: Repair, form, category: Category, state: State, brand: Brand) -> Repair:
    created_date = repair.created
    repair.display_id = generate_display_id(session, created_date, form.get('manual_id'), repair.display_id)
    repair.age = form.get('age') and int(form['age']) or None
    repair.name = form['name']
    # Champs optionnels via get()
    repair.email = form.get('email')
    repair.phone = form.get('phone')
    repair.category = category
    repair.brand = brand
    repair.initial_state = state
    repair.otype = form['otype']
    repair.model = form['model']
    repair.serial_number = form.get('sn')
    repair.year = form.get('year') and int(form['year']) or None
    repair.value = form.get('value') and int(form['value']) or None
    repair.weight = form.get('weight') and int(form['weight']) or None
    repair.description = form['description']
    repair.validated = form.get('validated') != ''
    session.add(Log(user_id=current_user.id, content="Modification de la fiche", repair=repair))
    return repair


def apply_update(session: Session, repair: Repair, form) -> bool:
    """Applique les modifications issues du formulaire d'update (users, state, location, note, fermeture).

    Reproduit exactement les side-effects et messages de log de l'ancienne implémentation de main.update_object.
    Retourne True si des changements nécessitent un commit.
    """
    change = False
    current_users = sorted(form.getlist('users'))
    previous_users = sorted(form.getlist('previous_users'))
    previous_state = form.get('previous_state')
    current_state = form.get('current_state')
    previous_location = form.get('previous_location')
    current_location = form.get('current_location')
    note_content = form.get('note')
    closeChoice = form.get('closeChoice')
    closeChoice = closeChoice and int(closeChoice) or 0

    if closeChoice > 1:
        new_close_status = session.query(CloseStatus).filter_by(id=closeChoice).first()
        session.add(Log(user_id=current_user.id, repair=repair,
                        content="Fermeture fiche (%s)" % new_close_status.label))
        repair.close_status = new_close_status
        change = True
    elif closeChoice == 1:
        session.add(Log(user_id=current_user.id, repair=repair,
                        content="Réouverture fiche"))
        repair.close_status = session.query(CloseStatus).filter_by(id=closeChoice).first()
        change = True

    if current_users != previous_users:
        repair.users = [session.query(User).filter_by(id=uid).first() for uid in current_users]
        session.add(Log(user_id=current_user.id, repair=repair,
                        content="Réparateurs changés (→ %s)" % ", ".join([u.name for u in repair.users])))
        change = True

    if current_state is not None and previous_state != current_state:
        repair.current_state_id = int(current_state)
        session.add(Log(user_id=current_user.id, repair=repair,
                        content="Etat changé (→ %s)" % repair.current_state.label))
        change = True

    if current_location != previous_location:
        repair.location = current_location
        session.add(Log(user_id=current_user.id, repair=repair,
                        content="Localisation changée (→ '%s')" % current_location))
        change = True

    if note_content:
        n = Note(user_id=current_user.id, content=note_content, repair=repair)
        session.add(n)
        change = True

    return change
