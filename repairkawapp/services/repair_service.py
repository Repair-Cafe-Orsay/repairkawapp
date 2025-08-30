"""Services métier pour les réparations (isoler la logique de `main.py`)."""

import re
import unicodedata
from datetime import date, datetime

from flask_login import current_user
from sqlalchemy.orm import Session

from ..models import (
    Brand,
    Category,
    CloseStatus,
    Log,
    Note,
    ObjectSubtype,
    ObjectType,
    Repair,
    State,
    User,
)


def normalize_brand(raw: str) -> str:
    """Normalise une marque (trim, désaccentue, majuscules, espaces réduits).

    Permet de réduire les doublons (ex: 'Philips', 'PHILIPS ', 'Phílïps').
    """
    if not raw:
        return ""
    s = raw.strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[\./,_-]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.upper()


def get_or_create_brand(session: Session, brand_name: str) -> Brand:
    norm = normalize_brand(brand_name)
    brand = session.query(Brand).filter_by(name=norm).first()
    if not brand:
        brand = Brand(name=norm)
        session.add(brand)
    return brand


def generate_display_id(
    session: Session,
    created_date: date,
    manual_id: str | None,
    existing_id: str | None = None,
) -> str:
    prefix = f"{created_date.year - 2000:02d}{created_date.month:02d}{created_date.day:02d}-"
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
                full_id = prefix + manual_id + chr(ord("a") + incid)
                incid += 1
        return full_id
    day_repairs = session.query(Repair).filter(Repair.display_id.like(prefix + "%"))
    return prefix + f"{day_repairs.count() + 1:03d}"


def _extract_object_refs(session: Session, form) -> tuple[ObjectType | None, ObjectSubtype | None]:
    """Récupère les références object_type/subtype selon champs du formulaire.

    Champs attendus:
      object_type_id (int) optionnel
      object_subtype_id (int) optionnel (validé seulement si parent correspond)
    """
    ot_id = form.get("object_type_id")
    st_id = form.get("object_subtype_id")
    ot = st = None
    if ot_id and ot_id.isdigit():
        ot = session.query(ObjectType).filter_by(id=int(ot_id)).first()
    if st_id and st_id.isdigit():
        st = session.query(ObjectSubtype).filter_by(id=int(st_id)).first()
        if st and ot and st.object_type_id != ot.id:
            st = None  # parent mismatch -> ignore
    return ot, st


def create_repair(session: Session, form, category: Category, state: State, brand: Brand) -> Repair:
    created_date = datetime.strptime(form["date"], "%Y-%m-%d") if form.get("date") else date.today()
    # Champs optionnels accédés via get() pour éviter BadRequestKeyError si absents du formulaire
    object_type, object_subtype = _extract_object_refs(session, form)
    r = Repair(
        display_id=generate_display_id(session, created_date, form.get("manual_id")),
        created=created_date,
        age=form.get("age") and int(form["age"]) or None,
        name=form["name"],  # requis (attribut required dans le formulaire)
        email=form.get("email"),  # optionnel
        phone=form.get("phone"),  # optionnel
        category=category,
        brand=brand,
        initial_state=state,
        current_state=state,
        # otype libre: ne copie plus systématiquement le nom du type standard pour éviter
        # confusion lors de l'édition. Si type standard choisi et aucun libre saisi => vide.
        otype=form.get("otype") or (object_type is None and (form.get("otype") or "")) or "",
        model=form["model"],  # requis
        serial_number=form.get("sn"),  # optionnel
        year=form.get("year") and int(form["year"]) or None,
        value=form.get("value") and int(form["value"]) or None,
        weight=form.get("weight") and int(form["weight"]) or None,
        description=form["description"],  # requis (required dans le formulaire)
        validated=form.get("validated") != "",
        object_type=object_type,
        object_subtype=object_subtype,
    )
    session.add(r)
    session.add(Log(user_id=current_user.id, content="Création de la fiche", repair=r))
    return r


def update_repair(
    session: Session,
    repair: Repair,
    form,
    category: Category,
    state: State,
    brand: Brand,
) -> Repair:
    created_date = repair.created
    repair.display_id = generate_display_id(
        session, created_date, form.get("manual_id"), repair.display_id
    )
    repair.age = form.get("age") and int(form["age"]) or None
    repair.name = form["name"]
    # Champs optionnels via get()
    repair.email = form.get("email")
    repair.phone = form.get("phone")
    repair.category = category
    repair.brand = brand
    repair.initial_state = state
    object_type, object_subtype = _extract_object_refs(session, form)
    repair.object_type = object_type
    repair.object_subtype = object_subtype if object_subtype and object_type else None
    # otype: libre si fourni; sinon passage libre->standard sans libre => efface.
    submitted_free = form.get("otype")
    if submitted_free is not None:
        if submitted_free.strip():
            repair.otype = submitted_free
        else:
            # vide explicite -> si object_type présent on garde vide, sinon on laisse précédent vide
            repair.otype = "" if object_type else ""
    repair.model = form["model"]
    repair.serial_number = form.get("sn")
    repair.year = form.get("year") and int(form["year"]) or None
    repair.value = form.get("value") and int(form["value"]) or None
    repair.weight = form.get("weight") and int(form["weight"]) or None
    repair.description = form["description"]
    repair.validated = form.get("validated") != ""
    session.add(Log(user_id=current_user.id, content="Modification de la fiche", repair=repair))
    return repair


def apply_update(session: Session, repair: Repair, form) -> bool:
    """Applique modifications du formulaire (users, state, location, note, fermeture).

    Reproduit les side-effects et logs de l'ancienne version main.update_object.
    Retourne True si des changements nécessitent un commit.
    """
    change = False
    current_users = sorted(form.getlist("users"))
    previous_users = sorted(form.getlist("previous_users"))
    previous_state = form.get("previous_state")
    current_state = form.get("current_state")
    previous_location = form.get("previous_location")
    current_location = form.get("current_location")
    note_content = form.get("note")
    closeChoice = form.get("closeChoice")
    closeChoice = closeChoice and int(closeChoice) or 0

    if closeChoice > 1:
        new_close_status = session.query(CloseStatus).filter_by(id=closeChoice).first()
        session.add(
            Log(
                user_id=current_user.id,
                repair=repair,
                content="Fermeture fiche (%s)" % new_close_status.label,
            )
        )
        repair.close_status = new_close_status
        change = True
    elif closeChoice == 1:
        session.add(Log(user_id=current_user.id, repair=repair, content="Réouverture fiche"))
        repair.close_status = session.query(CloseStatus).filter_by(id=closeChoice).first()
        change = True

    if current_users != previous_users:
        repair.users = [session.query(User).filter_by(id=uid).first() for uid in current_users]
        session.add(
            Log(
                user_id=current_user.id,
                repair=repair,
                content="Réparateurs changés (→ %s)" % ", ".join([u.name for u in repair.users]),
            )
        )
        change = True

    if current_state is not None and previous_state != current_state:
        repair.current_state_id = int(current_state)
        session.add(
            Log(
                user_id=current_user.id,
                repair=repair,
                content="Etat changé (→ %s)" % repair.current_state.label,
            )
        )
        change = True

    if current_location != previous_location:
        repair.location = current_location
        session.add(
            Log(
                user_id=current_user.id,
                repair=repair,
                content="Localisation changée (→ '%s')" % current_location,
            )
        )
        change = True

    if note_content:
        n = Note(user_id=current_user.id, content=note_content, repair=repair)
        session.add(n)
        change = True

    return change
