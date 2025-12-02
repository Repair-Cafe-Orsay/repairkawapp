"""Helper utilities for synchronising repairs with RepairMonitor."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from ..models import Repair

# Only the "closed" statuses are eligible for upload (IDs mirror init_db seeding order).
SYNCABLE_CLOSE_STATUS_IDS: Sequence[int] = (2, 3, 4)
DEFAULT_SYNC_LIMIT = 20
MAX_SYNC_LIMIT = 200

# RepairMonitor web endpoints/constants
LOGIN_PAGE_URL = "https://www.repairmonitor.org/"
SITE_BASE_URL = "https://www.repairmonitor.org/"
DASHBOARD_URL_TEMPLATE = "https://dashboard.repairmonitor.org/?language={language}"
REPAIR_FORM_RELATIVE_PATH = "node/add/repair"
REPAIR_FORM_REQUIRED_FIELDS: Sequence[str] = (
    "changed",
    "form_build_id",
    "form_token",
    "form_id",
)
RM_HTTP_TIMEOUT = 30
USER_AGENT = "repairkawapp/1.0 (+https://repaircafe-orsay.org)"


class RepairMonitorLoginError(RuntimeError):
    """Raised when RepairMonitor authentication or navigation fails."""


def clamp_limit(requested: int | None) -> int:
    """Normalize requested batch size to stay within safe boundaries."""
    if not requested or requested < 1:
        return DEFAULT_SYNC_LIMIT
    return min(requested, MAX_SYNC_LIMIT)


def _apply_year_filter(query, year: int | None):
    if year:
        start = date(year, 1, 1)
        end = date(year + 1, 1, 1)
        query = query.filter(Repair.created >= start, Repair.created < end)
    return query


def get_repairs_pending_upload(
    session: Session, limit: int, year: int | None = None
) -> list[Repair]:
    """Return at most ``limit`` repairs ready to be uploaded to RepairMonitor."""
    limit = clamp_limit(limit)
    if limit == 0:
        return []
    query = (
        session.query(Repair)
        .filter(Repair.close_status_id.in_(SYNCABLE_CLOSE_STATUS_IDS))
        .filter(Repair.rm_uploaded.is_(None))
    )
    query = _apply_year_filter(query, year)
    query = query.order_by(Repair.registered.asc()).limit(limit)
    return query.all()


def count_repairs_pending_upload(session: Session, year: int | None = None) -> int:
    query = (
        session.query(Repair)
        .filter(Repair.close_status_id.in_(SYNCABLE_CLOSE_STATUS_IDS))
        .filter(Repair.rm_uploaded.is_(None))
    )
    query = _apply_year_filter(query, year)
    return query.count()


def serialize_repair_stub(repair: Repair) -> dict:
    """Small JSON-friendly projection for preview/debug purposes."""
    return {
        "id": repair.id,
        "display_id": repair.display_id,
        "created": repair.created.isoformat() if repair.created else None,
        "close_status_id": repair.close_status_id,
        "rm_uploaded": repair.rm_uploaded.isoformat() if repair.rm_uploaded else None,
    }


def _create_session(language: str | None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": (language or "fr"),
        }
    )
    return session


def _fetch_login_form(session: requests.Session, timeout: int) -> tuple[str, dict[str, str]]:
    try:
        response = session.get(LOGIN_PAGE_URL, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network
        raise RepairMonitorLoginError(f"Unable to reach RepairMonitor login page: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    form = None
    for candidate in soup.find_all("form"):
        form_id = candidate.find("input", attrs={"name": "form_id"})
        if form_id and "user_login_form" in (form_id.get("value") or ""):
            form = candidate
            break
    if form is None:
        raise RepairMonitorLoginError("Login form not found on RepairMonitor landing page.")

    action = form.get("action") or LOGIN_PAGE_URL
    payload: dict[str, str] = {}
    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        if not name:
            continue
        input_type = (input_tag.get("type") or "text").lower()
        if input_type in {"checkbox", "radio"} and not input_tag.has_attr("checked"):
            continue
        payload[name] = input_tag.get("value", "")

    action_url = urljoin(LOGIN_PAGE_URL, action)
    logging.debug("RepairMonitor login form action: %s", action_url)
    return action_url, payload


def _extract_error_message(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    message = soup.find(class_="messages--error") or soup.find(class_="messages__content")
    if message:
        return " ".join(message.get_text(strip=True).split())
    return "Unknown error"


def create_authenticated_session(
    username: str,
    password: str,
    *,
    language: str = "fr",
    timeout: int = RM_HTTP_TIMEOUT,
) -> requests.Session:
    """Log into RepairMonitor and return a configured authenticated session."""

    if not username or not password:
        raise RepairMonitorLoginError("RepairMonitor credentials are missing.")

    session = _create_session(language)
    action_url, payload = _fetch_login_form(session, timeout)
    payload["name"] = username
    payload["pass"] = password

    try:
        response = session.post(action_url, data=payload, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network
        raise RepairMonitorLoginError(f"Login request failed: {exc}") from exc

    if "user/login" in response.url:
        detail = _extract_error_message(response.text)
        raise RepairMonitorLoginError(f"Login failed: {detail}")

    return session


def fetch_dashboard(
    session: requests.Session,
    *,
    language: str = "fr",
    timeout: int = RM_HTTP_TIMEOUT,
):
    """Fetch the RepairMonitor dashboard to ensure the session stays authenticated."""

    dashboard_url = DASHBOARD_URL_TEMPLATE.format(language=language or "fr")
    try:
        response = session.get(dashboard_url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover
        raise RepairMonitorLoginError(f"Failed to reach dashboard: {exc}") from exc

    if "user/login" in response.url:
        raise RepairMonitorLoginError("Dashboard redirected to login page; session invalid.")
    return response


def fetch_relative_page(
    session: requests.Session,
    *,
    language: str = "fr",
    relative_path: str,
    timeout: int = RM_HTTP_TIMEOUT,
):
    """Fetch a localized page (e.g., /fr/node/add/repair) while ensuring authentication."""

    lang_segment = (language or "").strip("/")
    lang_prefix = f"/{lang_segment}" if lang_segment else ""
    normalized_path = relative_path if relative_path.startswith("/") else f"/{relative_path}"
    absolute_path = f"{lang_prefix}{normalized_path}"
    absolute_url = urljoin(SITE_BASE_URL, absolute_path)

    try:
        response = session.get(absolute_url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover
        raise RepairMonitorLoginError(f"Failed to fetch {absolute_path}: {exc}") from exc

    if "user/login" in response.url:
        raise RepairMonitorLoginError(f"Request to {absolute_path} redirected to login.")
    return response


def fetch_repair_form_tokens(
    session: requests.Session,
    *,
    language: str = "fr",
    timeout: int = RM_HTTP_TIMEOUT,
) -> dict[str, str]:
    """Retrieve hidden CSRF fields from the Repair form page."""

    response = fetch_relative_page(
        session,
        language=language,
        relative_path=REPAIR_FORM_RELATIVE_PATH,
        timeout=timeout,
    )
    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.find("form", id="node-repair-form") or soup.find("form", attrs={"id": True})
    if form is None:
        raise RepairMonitorLoginError("Repair form not found on page.")
    tokens: dict[str, str] = {}
    for field in REPAIR_FORM_REQUIRED_FIELDS:
        input_tag = form.find("input", attrs={"name": field})
        value = input_tag.get("value") if input_tag else None
        if value:
            tokens[field] = value
    missing = [field for field in REPAIR_FORM_REQUIRED_FIELDS if field not in tokens]
    if missing:
        raise RepairMonitorLoginError("Missing hidden fields on repair form: " + ", ".join(missing))
    return tokens


def verify_credentials(
    username: str,
    password: str,
    *,
    language: str = "fr",
    timeout: int = RM_HTTP_TIMEOUT,
) -> None:
    """Ensure the provided credentials allow access to the dashboard."""

    session = create_authenticated_session(username, password, language=language, timeout=timeout)
    fetch_dashboard(session, language=language, timeout=timeout)
