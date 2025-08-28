"""Service pour la gestion des pièces détachées d'une réparation."""
from flask_login import current_user
from sqlalchemy.orm import Session
from ..models import SpareChange, Log


def add_spare(session: Session, repair_id: str, *, item: str, status_id: int, source: str | None, note: str | None):
    """Crée une pièce détachée et enregistre le log associé.
    Retourne (SpareChange, Log)."""
    sp = SpareChange(
        item=item,
        spare_status_id=status_id,
        source=source,
        note=note,
        repair_id=repair_id
    )
    session.add(sp)
    log = Log(user_id=current_user.id, content="Ajout d'une pièce détachée", repair_id=repair_id)
    session.add(log)
    return sp, log


def delete_spare(session: Session, spare_id: int):
    """Supprime une pièce détachée."""
    session.query(SpareChange).filter(SpareChange.id == spare_id).delete()
