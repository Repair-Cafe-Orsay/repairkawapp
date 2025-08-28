"""Service métier pour gestion des sessions de réparation."""
from datetime import datetime, date, timezone
from typing import Optional, Iterable
from flask_login import current_user
from sqlalchemy.orm import Session as SASession
from ..models import Session, Repair, User
from flask_mail import Message
from .. import mail


def open_session(db: SASession, location: str | None = None, tz=None) -> Session:
    """Ouvre une session pour aujourd'hui ou réutilise celle déjà ouverte aujourd'hui.

    Une session est considérée *expirée* si sa date d'ouverture n'est pas celle du jour.
    """
    if tz is None:
        # On part sur UTC puis conversion date (ou config future)
        today_local = date.today()
    else:
        today_local = datetime.now(tz).date()
    existing = (db.query(Session)
                  .filter(Session.owner_id == current_user.id,
                          Session.closed_at == None)
                  .order_by(Session.opened_at.desc())
                  .first())
    if existing and existing.opened_at.date() == today_local:
        # Déjà une session pour aujourd'hui
        if current_user not in existing.participants:
            existing.participants.append(current_user)
        return existing
    # Sinon on crée une nouvelle session (l'ancienne est implicitement expirée)
    s = Session(location=location, owner_id=current_user.id)
    s.participants.append(current_user)
    db.add(s)
    return s


def join_session(db: SASession, session_id: int) -> Optional[Session]:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s or s.closed_at:
        return None
    if current_user not in s.participants:
        s.participants.append(current_user)
    return s


def leave_session(db: SASession, session_id: int) -> Optional[Session]:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s or s.closed_at:
        return None
    if current_user in s.participants:
        s.participants.remove(current_user)
    return s


def close_session(db: SASession, session_id: int, comment: str | None = None, closed_at: datetime | None = None) -> Optional[Session]:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s or s.closed_at:
        return None
    # Seul owner ou admin
    if current_user.id != s.owner_id and not getattr(current_user, 'admin', False):
        return None
    s.closed_at = closed_at or datetime.utcnow()
    if comment:
        s.comment = comment
    return s


def reopen_session(db: SASession, session_id: int) -> Optional[Session]:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s or not s.closed_at:
        return None
    # propriétaire ou admin
    if current_user.id != s.owner_id and not getattr(current_user, 'admin', False):
        return None
    s.closed_at = None
    return s


def change_session_owner(db: SASession, session_id: int, new_owner_id: int) -> Optional[Session]:
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


def update_session_details(db: SASession, session_id: int, *, location: str | None = None,
                           opened_at: datetime | None = None, closed_at: datetime | None = None,
                           comment: str | None = None) -> Optional[Session]:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s:
        return None
    # Seul owner ou admin pour ces changements
    if current_user.id != s.owner_id and not getattr(current_user, 'admin', False):
        return None
    if location is not None:
        s.location = location
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


def session_stats(db: SASession, session_id: int) -> dict | None:
    s = db.query(Session).filter_by(id=session_id).first()
    if not s:
        return None
    # Nombre de repairs
    nb_repairs = len(s.repairs)
    nb_participants = len(s.participants)
    return {
        'id': s.id,
        'location': s.location,
        'opened_at': s.opened_at,
        'closed_at': s.closed_at,
        'owner_id': s.owner_id,
        'participants': [u.id for u in s.participants],
        'nb_repairs': nb_repairs,
        'nb_participants': nb_participants,
        'comment': s.comment,
    }


def collect_sessions_needing_reminder(db: SASession, reference_date: date | None = None) -> list[Session]:
    """Liste les sessions ouvertes (non fermées) dont la date n'est pas aujourd'hui (expirées)."""
    if reference_date is None:
        reference_date = date.today()
    sessions = (db.query(Session)
                  .filter(Session.closed_at == None)
                  .all())
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
            'Rappel: fermer la session %d' % s.id,
            recipients=[owner.email],
            sender='app@repaircafe-orsay.org'
        )
        msg.body = ("Bonjour,\n\nLa session #%d (%s) ouverte le %s n'est pas fermée. "
                    "Merci de la clore et de renseigner le commentaire de fin.\n") % (
                        s.id, s.location or 'Lieu', s.opened_at)
        try:
            mail.send(msg)
            sent += 1
        except Exception:
            # ignorer les erreurs d'envoi
            pass
    return sent
