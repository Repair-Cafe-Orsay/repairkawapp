"""Service de calcul des statistiques sur les réparations."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from ..models import (
    Category,
    CloseStatus,
    ObjectType,
    Repair,
    Session as RepairSession,
)


def parse_period(arg_from: str | None, arg_to: str | None):
    try:
        date_from = datetime.strptime(arg_from, "%Y-%m-%d").date()
        date_to = datetime.strptime(arg_to, "%Y-%m-%d").date()
    except Exception:
        return None, None
    return date_from, date_to


def get_cached_lists(session: Session, cache_categories: list, cache_status: list):
    if not cache_categories:
        for c in session.query(Category).all():
            cache_categories.append((c.name, c.rm_icon_id))
    if not cache_status:
        for s in session.query(CloseStatus).order_by(CloseStatus.id).all():
            cache_status.append(s.label[0])


def compute_stats(session: Session, date_from: date, date_to: date, repaircafe_id=None):
    repairs_status = (
        session.query(
            func.count(Repair.close_status_id),
            Repair.close_status_id,
            CloseStatus.label,
        )
        .outerjoin(CloseStatus, Repair.close_status_id == CloseStatus.id)
        .filter(Repair.created >= date_from)
        .filter(Repair.created <= date_to)
    )
    if repaircafe_id is not None:
        repairs_status = repairs_status.filter(Repair.repaircafe_id == repaircafe_id)
    all_repairs_close_status = repairs_status.group_by(Repair.close_status_id).all()

    repairs_category = (
        session.query(Category.name, func.count(Repair.category_id), Category.icon_name)
        .outerjoin(Repair, Repair.category_id == Category.id)
        .filter(Repair.created >= date_from)
        .filter(Repair.created <= date_to)
    )
    if repaircafe_id is not None:
        repairs_category = repairs_category.filter(Repair.repaircafe_id == repaircafe_id)
    all_repairs_category = repairs_category.group_by(Category.id).all()

    visitors_query = (
        session.query(func.count(distinct(Repair.email)))
        .filter(Repair.created >= date_from)
        .filter(Repair.created <= date_to)
    )
    if repaircafe_id is not None:
        visitors_query = visitors_query.filter(Repair.repaircafe_id == repaircafe_id)
    visitors = visitors_query.all()[0][0]

    total = sum(count for count, _, _ in all_repairs_close_status)
    # Nombre de séances ouvertes (opened_at) dont l'ouverture dans la période
    total_sessions_query = (
        session.query(func.count(RepairSession.id))
        .filter(RepairSession.opened_at >= date_from)
        .filter(RepairSession.opened_at <= date_to)
    )
    if repaircafe_id is not None:
        total_sessions_query = total_sessions_query.filter(
            RepairSession.repaircafe_id == repaircafe_id
        )
    total_sessions = total_sessions_query.scalar()
    # Top 20 des types d'objet structurés (ignore legacy otype texte)
    object_types_query = (
        session.query(ObjectType.name, func.count(Repair.id))
        .join(Repair, Repair.object_type_id == ObjectType.id)
        .filter(Repair.created >= date_from)
        .filter(Repair.created <= date_to)
    )
    if repaircafe_id is not None:
        object_types_query = object_types_query.filter(Repair.repaircafe_id == repaircafe_id)
    object_types_top = (
        object_types_query.group_by(ObjectType.id)
        .order_by(func.count(Repair.id).desc())
        .limit(20)
        .all()
    )
    return {
        "categories_raw": all_repairs_category,
        "status_raw": all_repairs_close_status,
        "visitors": visitors,
        "total": total,
        "total_sessions": total_sessions,
        "object_types_top": object_types_top,
    }
