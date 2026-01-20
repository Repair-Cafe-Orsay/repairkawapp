"""Tenant helpers for Repair Cafe scoping."""

from __future__ import annotations

import os
import re
from datetime import date as _date

from flask import abort, current_app
from flask_login import current_user
from sqlalchemy import or_

from .. import db
from ..models import RepairCafe, User, user_repaircafe


def is_cafe_admin(user: User, cafe_id: int | None) -> bool:
    """Return True if the user is admin for the given RepairCafe."""
    if not user or getattr(user, "super_admin", False):
        return False
    if getattr(user, "admin", False):
        return True
    if cafe_id is None:
        return False
    row = (
        db.session.query(user_repaircafe)
        .filter(user_repaircafe.c.user_id == user.id)
        .filter(user_repaircafe.c.repaircafe_id == cafe_id)
        .filter(user_repaircafe.c.role == "admin")
        .first()
    )
    return row is not None


def get_active_repaircafe(user: User | None = None) -> RepairCafe | None:
    """Return the active RepairCafe for the given user.

    Super admins are not scoped to a RepairCafe and return None.
    """
    user = user or current_user  # type: ignore[assignment]
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "super_admin", False):
        return None
    if getattr(user, "active_repaircafe", None):
        return user.active_repaircafe
    # Auto-select a default cafe if the user has one and none is active yet
    cafes = getattr(user, "repaircafes", []) or []
    if cafes:
        user.active_repaircafe = cafes[0]
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return user.active_repaircafe
    return None


def require_active_repaircafe(user: User | None = None) -> RepairCafe:
    """Return the active RepairCafe or abort if none is set."""
    cafe = get_active_repaircafe(user)
    if cafe is None:
        abort(403)
    return cafe


def get_upload_prefix(cafe: RepairCafe | None) -> str | None:
    """Return a safe upload prefix for the given cafe.

    Format: <code> where code is sanitized.
    """
    if not cafe:
        return None
    code = (cafe.code or "cafe").strip().lower()
    safe_code = re.sub(r"[^a-z0-9_-]+", "_", code)
    return safe_code


def get_cafe_upload_folder(upload_root: str, cafe: RepairCafe | None) -> str:
    """Return absolute upload folder for a cafe under the given root."""
    prefix = get_upload_prefix(cafe)
    if not prefix:
        return upload_root
    return os.path.join(upload_root, prefix)


def ensure_cafe_upload_folder(upload_root: str, cafe: RepairCafe | None) -> str:
    """Ensure the cafe upload folder exists and return its path."""
    folder = get_cafe_upload_folder(upload_root, cafe)
    os.makedirs(folder, exist_ok=True)
    return folder


def get_cafe_upload_relative_path(cafe: RepairCafe | None, filename: str) -> str:
    """Return a cafe-prefixed relative path for a filename."""
    prefix = get_upload_prefix(cafe)
    if not prefix:
        return filename
    return f"{prefix}/{filename}"


def get_user_cafe_photo(user_id: int, cafe_id: int) -> str | None:
    """Return the per-cafe photo filename for a user."""
    row = (
        db.session.query(user_repaircafe.c.photo_filename)
        .filter(user_repaircafe.c.user_id == user_id)
        .filter(user_repaircafe.c.repaircafe_id == cafe_id)
        .first()
    )
    return row[0] if row else None


def set_user_cafe_photo(user_id: int, cafe_id: int, filename: str | None) -> None:
    """Set the per-cafe photo filename for a user."""
    db.session.execute(
        user_repaircafe.update()
        .where(user_repaircafe.c.user_id == user_id)
        .where(user_repaircafe.c.repaircafe_id == cafe_id)
        .values(photo_filename=filename)
    )


def get_mail_sender(cafe: RepairCafe | None) -> str:
    """Return sender email for the given RepairCafe.

    Falls back to MAIL_DEFAULT_SENDER, MAIL_USERNAME, or a generic address.
    """
    if cafe and cafe.email:
        return cafe.email
    try:
        return (
            current_app.config.get("MAIL_DEFAULT_SENDER")
            or current_app.config.get("MAIL_USERNAME")
            or "noreply@repaircafe.local"
        )
    except Exception:
        return "noreply@repaircafe.local"


def get_allowed_memberships(today: _date | None = None) -> set[int]:
    """Return academic years allowed for active membership (N or N-1)."""
    today = today or _date.today()
    acad_start = today.year if today.month >= 9 else today.year - 1
    previous_acad = acad_start - 1
    return {previous_acad, acad_start}


def get_user_cafe_membership(user_id: int, cafe_id: int) -> int | None:
    """Return the per-cafe last membership year for a user."""
    row = (
        db.session.query(user_repaircafe.c.last_membership)
        .filter(user_repaircafe.c.user_id == user_id)
        .filter(user_repaircafe.c.repaircafe_id == cafe_id)
        .first()
    )
    return row[0] if row else None


def set_user_cafe_membership(user_id: int, cafe_id: int, value: int | None) -> None:
    """Set the per-cafe last membership year for a user."""
    db.session.execute(
        user_repaircafe.update()
        .where(user_repaircafe.c.user_id == user_id)
        .where(user_repaircafe.c.repaircafe_id == cafe_id)
        .values(last_membership=value)
    )


def get_user_cafe_founder(user_id: int, cafe_id: int) -> bool:
    """Return the per-cafe founder flag for a user."""
    row = (
        db.session.query(user_repaircafe.c.founder)
        .filter(user_repaircafe.c.user_id == user_id)
        .filter(user_repaircafe.c.repaircafe_id == cafe_id)
        .first()
    )
    return bool(row[0]) if row else False


def set_user_cafe_founder(user_id: int, cafe_id: int, value: bool) -> None:
    """Set the per-cafe founder flag for a user."""
    db.session.execute(
        user_repaircafe.update()
        .where(user_repaircafe.c.user_id == user_id)
        .where(user_repaircafe.c.repaircafe_id == cafe_id)
        .values(founder=bool(value))
    )


def get_user_cafe_board_title(user_id: int, cafe_id: int) -> str | None:
    """Return the per-cafe board title for a user."""
    row = (
        db.session.query(user_repaircafe.c.board_title)
        .filter(user_repaircafe.c.user_id == user_id)
        .filter(user_repaircafe.c.repaircafe_id == cafe_id)
        .first()
    )
    return row[0] if row else None


def set_user_cafe_board_title(user_id: int, cafe_id: int, value: str | None) -> None:
    """Set the per-cafe board title for a user."""
    db.session.execute(
        user_repaircafe.update()
        .where(user_repaircafe.c.user_id == user_id)
        .where(user_repaircafe.c.repaircafe_id == cafe_id)
        .values(board_title=value)
    )


def is_membership_allowed(
    user: User, cafe: RepairCafe | None = None, today: _date | None = None
) -> bool:
    """Return True if user is founder or has an active/previous membership year for cafe."""
    cafe = cafe or get_active_repaircafe(user)
    if not cafe:
        return True
    if get_user_cafe_founder(user.id, cafe.id):
        return True
    last = get_user_cafe_membership(user.id, cafe.id)
    return last in get_allowed_memberships(today)


def filter_active_membership_or_founder(query, cafe_id: int, today: _date | None = None):
    """Filter a User query to active/previous membership or founder for a cafe."""
    allowed = list(get_allowed_memberships(today))
    query = query.join(user_repaircafe).filter(user_repaircafe.c.repaircafe_id == cafe_id)
    return query.filter(
        or_(user_repaircafe.c.founder.is_(True), user_repaircafe.c.last_membership.in_(allowed))
    )
