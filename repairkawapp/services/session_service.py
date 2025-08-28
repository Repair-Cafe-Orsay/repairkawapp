"""Service métier pour gestion des sessions de réparation."""
from datetime import datetime
from typing import Optional
from flask_login import current_user
from sqlalchemy.orm import Session as SASession
from ..models import Session, Repair, User


def open_session(db: SASession, location: str | None = None) -> Session:
    # Empêche un user d'avoir deux sessions ouvertes comme owner
    existing = db.query(Session).filter(Session.owner_id == current_user.id, Session.closed_at == None).first()
    if existing:
        return existing
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
