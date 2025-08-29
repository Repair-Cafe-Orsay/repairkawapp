"""Service métier pour gestion des sessions de réparation.

RepairKawapp – Repair Café management application
Licence: MIT (voir fichier LICENSE)
Auteur principal: Jean Senellart
"""

from datetime import date, datetime

from flask_login import current_user
from flask_mail import Message
from sqlalchemy.orm import Session as SASession

from .. import mail
from ..models import Location, Repair, Session, User


def _get_or_create_location(db: SASession, name: str) -> Location:
    loc = db.query(Location).filter_by(name=name).first()
    if not loc:
        loc = Location(name=name)
        db.add(loc)
    return loc


def open_session(db: SASession, location: str | None = None, tz=None, opened_at=None) -> Session:
    """Ouvre une session pour aujourd'hui ou réutilise celle déjà ouverte aujourd'hui.

    Logique de réutilisation (compat tests):
    - S'il existe une session ouverte aujourd'hui (n'importe owner) au même lieu -> réutiliser.
      - Sinon si utilisateur possède déjà une session ouverte aujourd'hui -> la réutiliser.
      - Sinon créer une nouvelle session (lieu obligatoire).
    """
    if tz is None:
        today_local = date.today()
    else:
        today_local = datetime.now(tz).date()
    # 1. Réutilisation par lieu (si location fourni)
    if location and location.strip():
        loc_name = location.strip()
        # Cherche une location existante (sans créer) pour récupérer son id
        loc_existing = db.query(Location).filter_by(name=loc_name).first()
        if loc_existing:
            existing_same_loc = (
                db.query(Session)
                .filter(Session.closed_at.is_(None))
                .filter(Session.opened_at >= datetime.combine(today_local, datetime.min.time()))
                .filter(Session.location_id == loc_existing.id)
                .order_by(Session.opened_at.asc())
                .first()
            )
            if existing_same_loc and existing_same_loc.opened_at.date() == today_local:
                if current_user not in existing_same_loc.participants:
                    existing_same_loc.participants.append(current_user)
                return existing_same_loc
    # 2. Réutilisation session personnelle ouverte aujourd'hui
    existing_user = (
        db.query(Session)
        .filter(Session.owner_id == current_user.id, Session.closed_at.is_(None))
        .order_by(Session.opened_at.desc())
        .first()
    )
    if existing_user and existing_user.opened_at.date() == today_local:
        if current_user not in existing_user.participants:
            existing_user.participants.append(current_user)
        return existing_user
    # 3. Création
    if not location or not location.strip():
        raise ValueError("Location obligatoire pour ouvrir une session")
    loc_obj = _get_or_create_location(db, location.strip())
    s = Session(location=loc_obj, owner_id=current_user.id)
    if opened_at is not None:
        s.opened_at = opened_at
    s.participants.append(current_user)
    db.add(s)
    return s


def join_session(db: SASession, session_id: int) -> Session | None:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s or s.closed_at:
        return None
    if current_user not in s.participants:
        s.participants.append(current_user)
    return s


def leave_session(db: SASession, session_id: int) -> Session | None:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s or s.closed_at:
        return None
    if current_user in s.participants:
        s.participants.remove(current_user)
    return s


def close_session(
    db: SASession,
    session_id: int,
    comment: str | None = None,
    closed_at: datetime | None = None,
) -> Session | None:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s or s.closed_at:
        return None
    # Seul owner ou admin
    if current_user.id != s.owner_id and not getattr(current_user, "admin", False):
        return None
    s.closed_at = closed_at or datetime.utcnow()
    if comment:
        s.comment = comment
    return s


def reopen_session(db: SASession, session_id: int) -> Session | None:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s or not s.closed_at:
        return None
    # propriétaire ou admin
    if current_user.id != s.owner_id and not getattr(current_user, "admin", False):
        return None
    s.closed_at = None
    return s


def change_session_owner(db: SASession, session_id: int, new_owner_id: int) -> Session | None:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s:
        return None
    # Tout participant peut prendre la main
    if current_user not in s.participants:
        return None
    new_owner = db.query(User).filter_by(id=new_owner_id).first()
    if not new_owner:
        return None
    if new_owner not in s.participants:
        s.participants.append(new_owner)
    s.owner_id = new_owner.id
    return s


def update_session_details(
    db: SASession,
    session_id: int,
    *,
    location: str | None = None,
    opened_at: datetime | None = None,
    closed_at: datetime | None = None,
    comment: str | None = None,
) -> Session | None:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s:
        return None
    # Seul owner ou admin pour ces changements
    if current_user.id != s.owner_id and not getattr(current_user, "admin", False):
        return None
    if location is not None:
        if location.strip():
            s.location = _get_or_create_location(db, location.strip())
        else:
            # ne pas autoriser location vide; ignorer
            pass
    if opened_at is not None:
        s.opened_at = opened_at
    if closed_at is not None:
        s.closed_at = closed_at
    elif closed_at is None and comment is not None and not s.closed_at:
        # On peut juste modifier le commentaire sans fermer
        pass
    if comment is not None:
        s.comment = comment
    return s


def attach_repair(db: SASession, repair: Repair, session_obj: Session):
    repair.session = session_obj
    return repair


def delete_session(db: SASession, session_id: int) -> bool:
    """Supprime une séance si aucune réparation associée et utilisateur autorisé.

    Retourne True si supprimée, False sinon."""
    s = db.query(Session).filter_by(id=session_id).first()
    if not s:
        return False
    if len(s.repairs) > 0:
        return False
    if current_user.id != s.owner_id and not getattr(current_user, "admin", False):
        return False
    db.delete(s)
    return True


def session_stats(db: SASession, session_id: int) -> dict | None:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s:
        return None
    # Nombre de repairs
    nb_repairs = len(s.repairs)
    nb_participants = len(s.participants)
    return {
        "id": s.id,
        "location": ((s.location and s.location.name) if hasattr(s, "location") else None),
        "opened_at": s.opened_at and (s.opened_at.isoformat() + "Z"),
        "closed_at": s.closed_at and (s.closed_at.isoformat() + "Z"),
        "owner_id": s.owner_id,
        "participants": [u.id for u in s.participants],
        "nb_repairs": nb_repairs,
        "nb_participants": nb_participants,
        "comment": s.comment,
    }


def collect_sessions_needing_reminder(
    db: SASession, reference_date: date | None = None
) -> list[Session]:
    """Liste les sessions ouvertes (non fermées) dont la date n'est pas aujourd'hui (expirées)."""
    if reference_date is None:
        reference_date = date.today()
    sessions = db.query(Session).filter(Session.closed_at.is_(None)).all()
    return [s for s in sessions if s.opened_at.date() != reference_date]


def send_session_reminders(db: SASession, reference_date: date | None = None) -> int:
    """Envoie un email de rappel de fermeture pour chaque session expirée non fermée.

    Retourne le nombre de mails envoyés.
    """
    sessions = collect_sessions_needing_reminder(db, reference_date)
    sent = 0
    for s in sessions:
        owner = db.query(User).filter_by(id=s.owner_id).first()
        if not owner or not owner.email:
            continue
        msg = Message(
            "Rappel: fermer la session %d" % s.id,
            recipients=[owner.email],
            sender="app@repaircafe-orsay.org",
        )
        msg.body = (
            "Bonjour,\n\nLa session #%d (%s) ouverte le %s n'est pas fermée. "
            "Merci de la clore et de renseigner le commentaire de fin.\n"
        ) % (s.id, s.location or "Lieu", s.opened_at)
        try:
            mail.send(msg)
            sent += 1
        except Exception:
            # ignorer les erreurs d'envoi
            pass
    return sent
