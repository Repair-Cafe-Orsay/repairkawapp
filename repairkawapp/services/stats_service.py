"""Service de calcul des statistiques sur les réparations."""
from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session
from ..models import Repair, CloseStatus, Category


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


def compute_stats(session: Session, date_from: date, date_to: date):
    repairs_status = session.query(func.count(Repair.close_status_id), Repair.close_status_id, CloseStatus.label) \
        .outerjoin(CloseStatus, Repair.close_status_id == CloseStatus.id) \
        .filter(Repair.created >= date_from) \
        .filter(Repair.created <= date_to)
    all_repairs_close_status = repairs_status.group_by(Repair.close_status_id).all()

    repairs_category = session.query(Category.name, func.count(Repair.category_id), Category.rm_icon_id) \
        .outerjoin(Repair, Repair.category_id == Category.id) \
        .filter(Repair.created >= date_from) \
        .filter(Repair.created <= date_to)
    all_repairs_category = repairs_category.group_by(Category.id).all()

    visitors = session.query(func.count(distinct(Repair.email))) \
        .filter(Repair.created >= date_from) \
        .filter(Repair.created <= date_to) \
        .all()[0][0]

    total = sum(count for count, _, _ in all_repairs_close_status)
    return {
        'categories_raw': all_repairs_category,
        'status_raw': all_repairs_close_status,
        'visitors': visitors,
        'total': total
    }
