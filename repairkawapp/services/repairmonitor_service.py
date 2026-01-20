"""Helper utilities for synchronising repairs with RepairMonitor."""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections.abc import Sequence
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from flask import current_app
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Category, Repair

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
BASE_USER_AGENT = "repairkawapp/1.0"
SYNC_SESSION_TTL_SECONDS = 600
REFERENCE_NUMBER_FIELD_NAME = "field_reference_number[0][value]"
REFERENCE_SUFFIX_WIDTH = 3
SUBMIT_BUTTON_VALUE = "Achever la réparation "
DRAFT_BUTTON_VALUE = "Sauvegarder brouillon"
CATEGORY_NAME_FALLBACKS = {
    "a - électroménager": 1678,
    "b - article ménager non électrique": 5343,
    "c - jouet non électrique": 1693,
    "d - jouet électrique": 1692,
    "e - matériel d'image et de son": 1689,
    "f - matériel informatique/téléphones": 1677,
    "g - outil non électrique": 1691,
    "h - outil électrique": 1690,
    "i - meuble": 1683,
    "j - bijou": 18707,
    "k - pendule, horloge ou réveil": 18706,
    "l - textile": 1684,
    "m - vélo": 1679,
    # Local sub-buckets O/P/Q all collapse to RM "Autres" (1685)
    "n - autre": 1685,
    "o - éclairage": 1685,
    "p - chauffage/climatisation": 1685,
    "q - sécurité/domotique": 1685,
}


_SYNC_SESSION_LOCK = threading.Lock()
_SYNC_SESSIONS: dict[str, dict] = {}


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
        "rm_uploaded": repair.rm_uploaded,
    }


def _create_session(language: str | None) -> requests.Session:
    base_url = None
    try:
        base_url = current_app.config.get("APP_URL")
    except Exception:
        base_url = None
    user_agent = f"{BASE_USER_AGENT} (+{base_url})" if base_url else BASE_USER_AGENT
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
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


def _extract_reference_metadata(form: BeautifulSoup) -> tuple[str | None, str | None]:
    reference_input = form.find("input", attrs={"name": REFERENCE_NUMBER_FIELD_NAME})
    if reference_input is None:
        return None, None
    prefix_span = reference_input.find_previous("span", class_="field-prefix")
    prefix = prefix_span.get_text(strip=True) if prefix_span else None
    return prefix or None, reference_input.get("name")


def _extract_autocomplete_paths(form: BeautifulSoup) -> dict[str, str | None]:
    """Collect autocomplete endpoints from the form for reuse.

    The form renders data-autocomplete-path attributes on inputs; we capture the
    ones we care about to resolve existing values instead of creating new ones.
    """

    paths: dict[str, str | None] = {
        "kind_product": None,
        "brand": None,
        "model": None,
        "repairer": None,
    }

    field_map = {
        "field_kind_product[0][target_id]": "kind_product",
        "field_brand[0][target_id]": "brand",
        "field_model[0][target_id]": "model",
        "field_repairer[0][target_id]": "repairer",
    }

    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        if not name or name not in field_map:
            continue
        path = input_tag.get("data-autocomplete-path")
        if path:
            paths[field_map[name]] = path

    return paths


def submit_repair_form(
    session: requests.Session,
    *,
    language: str,
    payload: dict[str, str],
    submit_label: str | None = None,
    timeout: int = RM_HTTP_TIMEOUT,
) -> requests.Response:
    """Submit a repair form to RepairMonitor using an authenticated session."""

    lang_segment = (language or "").strip("/")
    lang_prefix = f"/{lang_segment}" if lang_segment else ""
    normalized_path = (
        REPAIR_FORM_RELATIVE_PATH
        if REPAIR_FORM_RELATIVE_PATH.startswith("/")
        else f"/{REPAIR_FORM_RELATIVE_PATH}"
    )
    absolute_path = f"{lang_prefix}{normalized_path}"
    absolute_url = urljoin(SITE_BASE_URL, absolute_path)

    # Ensure a submit button value is present to mimic real form posts
    payload = dict(payload)
    payload["op"] = submit_label or payload.get("op") or SUBMIT_BUTTON_VALUE

    response = session.post(
        absolute_url,
        data=payload,
        timeout=timeout,
        allow_redirects=True,
    )
    return response


def fetch_autocomplete_suggestion(
    session: requests.Session,
    *,
    path: str | None,
    term: str | None,
    language: str = "fr",
    timeout: int = RM_HTTP_TIMEOUT,
) -> str | None:
    """Fetch the first autocomplete suggestion for a term.

    Drupal autocomplete endpoints typically return either JSON or plain text
    suggestions. We accept either and return the first label/value line.
    """

    if not path or not term:
        return None

    lang_segment = (language or "").strip("/")
    lang_prefix = f"/{lang_segment}" if lang_segment else ""
    normalized_path = path if path.startswith("/") else f"/{path}"
    absolute_url = urljoin(SITE_BASE_URL, f"{lang_prefix}{normalized_path}")

    try:
        response = session.get(absolute_url, params={"q": term}, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return None

    text = response.text or ""
    # Try JSON payload first
    try:
        data = response.json()
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict) and first.get("value"):
                return str(first.get("value"))
            if isinstance(first, str):
                text = first
    except Exception:
        pass

    # Fallback: plain text lines, take first non-empty
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            return line.split("|", 1)[0].strip()
        return line

    return None


def extract_form_messages(html: str) -> dict[str, list[str]]:
    """Extract Drupal form messages (errors, warnings, status) for logging/debug."""

    soup = BeautifulSoup(html or "", "html.parser")
    buckets: dict[str, list[str]] = {"error": [], "status": [], "warning": []}
    for klass, key in (
        ("messages--error", "error"),
        ("messages--status", "status"),
        ("messages--warning", "warning"),
    ):
        for node in soup.find_all(class_=klass):
            text = " ".join(node.get_text(strip=True).split())
            if text:
                buckets[key].append(text)
    return buckets


def extract_rm_reference_id(html: str | None) -> str | None:
    """Try to extract the created reference id from the response body (BigPipe message)."""

    if not html:
        return None
    match = re.search(r"(\d{4}_\d{4}_\d{4}_\d{3})", html)
    if match:
        return match.group(1)
    return None


def extract_rm_node_id(
    response_url: str | None,
    html: str | None,
    *,
    history_urls: Sequence[str] | None = None,
) -> int | None:
    """Try to extract the created node id from the response body or redirects.

    Priority: creation messages in HTML (status/bigpipe) -> redirect history -> final URL.
    Avoid picking menu links by ignoring /node/add/* and only accepting explicit node paths.
    """

    def _from_url(url: str | None) -> int | None:
        if not url or "/node/add/" in url:
            return None
        m = re.search(r"/node/(\d+)", url)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
        return None

    # 1) Look for creation message in HTML (BigPipe JSON or rendered messages)
    if html:
        creation_match = re.search(r"Le contenu[^<]*?/node/(\d+)", html, re.IGNORECASE)
        if creation_match:
            try:
                return int(creation_match.group(1))
            except Exception:
                pass

        soup = BeautifulSoup(html, "html.parser")
        for node in soup.find_all(class_="messages--status"):
            text = node.get_text(" ", strip=True)
            m = re.search(r"/node/(\d+)", text)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    return None

    # 2) Inspect redirect history (first hit wins, starting from latest)
    if history_urls:
        for url in reversed(list(history_urls)):
            node_id = _from_url(url)
            if node_id:
                return node_id

    # 3) Fallback to final URL only if it points directly to a node page (not add form)
    node_id = _from_url(response_url)
    if node_id:
        return node_id

    return None


def map_category_to_rm_id(category: Category | None) -> int | None:
    """Return the RepairMonitor category id for a local category.

    Uses the stored rm_icon_id when present; otherwise falls back to name-based
    mapping (covers O/P/Q collapsing to RM "Autres" = 1685).
    """

    if category is None:
        return None
    if getattr(category, "rm_icon_id", None):
        return category.rm_icon_id
    normalized = (getattr(category, "name", "") or "").strip().lower()
    return CATEGORY_NAME_FALLBACKS.get(normalized)


def fetch_repair_form_tokens(
    session: requests.Session,
    *,
    language: str = "fr",
    timeout: int = RM_HTTP_TIMEOUT,
) -> dict[str, str | dict | None]:
    """Retrieve hidden CSRF fields and useful metadata from the Repair form page."""

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
    prefix, field_name = _extract_reference_metadata(form)
    reference_input = form.find("input", attrs={"name": REFERENCE_NUMBER_FIELD_NAME})
    reference_value = reference_input.get("value") if reference_input else None
    autocomplete_paths = _extract_autocomplete_paths(form)
    return {
        "tokens": tokens,
        "reference_prefix": prefix,
        "reference_field_name": field_name,
        "reference_value": reference_value,
        "autocomplete_paths": autocomplete_paths,
    }


def compute_reference_sequence(
    session: Session,
    *,
    prefix: str,
    width: int = REFERENCE_SUFFIX_WIDTH,
) -> dict[str, str | int | None]:
    """Derive the next RepairMonitor identifier based on existing uploads."""

    normalized_prefix = prefix or ""
    if not normalized_prefix:
        return {
            "prefix": None,
            "previous_reference": None,
            "next_number": None,
            "next_suffix": None,
            "reference_id": None,
        }

    like_pattern = f"{normalized_prefix}%"
    latest_value = (
        session.query(func.max(Repair.rm_uploaded))
        .filter(Repair.rm_uploaded.isnot(None))
        .filter(Repair.rm_uploaded.like(like_pattern))
        .scalar()
    )

    last_number = None
    if (
        latest_value
        and isinstance(latest_value, str)
        and latest_value.startswith(normalized_prefix)
    ):
        suffix = latest_value[len(normalized_prefix) :]
        if suffix.isdigit():
            last_number = int(suffix)

    next_number = (last_number or 0) + 1
    padded_suffix = str(next_number).zfill(width)
    return {
        "prefix": normalized_prefix,
        "previous_reference": latest_value,
        "next_number": next_number,
        "next_suffix": padded_suffix,
        "reference_id": f"{normalized_prefix}{padded_suffix}",
    }


def _format_date(value):
    if not value:
        return None
    try:
        return value.strftime("%Y-%m-%d")
    except Exception:
        return None


def _format_repairer(users) -> str:
    if not users:
        return ""
    first_parts = []
    for u in users:
        nm = getattr(u, "name", "") or getattr(u, "email", "") or ""
        part = (nm.strip().split() or [""])[0]
        part = part.capitalize() if part else ""
        if part:
            first_parts.append(part)
    return "/".join(first_parts)


def _map_close_status(close_status_id: int | None) -> str | None:
    mapping = {2: "yes", 3: "half", 4: "no"}
    return mapping.get(close_status_id)


def build_repairmonitor_payload(
    repair: Repair,
    *,
    form_tokens: dict[str, str],
    reference_prefix: str | None,
    reference_sequence: dict | None,
    reference_value: str | None = None,
    resolved_kind: str | None = None,
    resolved_brand: str | None = None,
    resolved_model: str | None = None,
    resolved_repairer: str | None = None,
    extra_comment: str | None = None,
) -> dict[str, str]:
    """Build a submission payload using available local data (no autocomplete lookups)."""

    payload: dict[str, str] = dict(form_tokens)

    # Reference number (prefix provided by RM, suffix computed locally)
    if reference_value:
        payload[REFERENCE_NUMBER_FIELD_NAME] = reference_value
    elif reference_prefix:
        suffix = None
        if reference_sequence:
            suffix = reference_sequence.get("next_number") or reference_sequence.get("next_suffix")
        if suffix is None:
            suffix = 1
        try:
            suffix = str(int(suffix))  # ensure plain integer, no zero padding
        except Exception:
            suffix = "1"
        payload[REFERENCE_NUMBER_FIELD_NAME] = suffix

    # Date
    date_value = _format_date(getattr(repair, "created", None))
    if date_value:
        payload["field_repair_date[0][value]"] = date_value

    # Category
    rm_category_id = map_category_to_rm_id(getattr(repair, "category", None))
    if rm_category_id:
        payload["field_categorie"] = str(rm_category_id)

    # Product: prefer resolved autocomplete label; otherwise create-as-other with explicit flag
    otype_value = getattr(repair, "otype", "") or ""
    if not otype_value:
        # Fallback if kind/product is empty: reuse category name or a generic label
        # to satisfy RM requirement
        otype_value = getattr(getattr(repair, "category", None), "name", None) or "Objet"
    if resolved_kind:
        payload["field_kind_product[0][target_id]"] = resolved_kind
        payload["field_kind_product[0][kp_other]"] = ""
        payload["field_kind_product[0][autocomplete_fill_field]"] = resolved_kind
    else:
        payload["field_kind_product[0][target_id]"] = ""
        payload["field_kind_product[0][kp_other]"] = otype_value
        payload["field_kind_product[0][autocomplete_fill_field]"] = "Ajouter un nouveau produit"

    # Brand: prefer resolved autocomplete label; fallback to posting typed value
    brand_name = getattr(getattr(repair, "brand", None), "name", None) or ""
    if resolved_brand:
        payload["field_brand[0][target_id]"] = resolved_brand
        payload["field_brand[0][other]"] = ""
        payload["field_brand[0][autocomplete_fill_field]"] = resolved_brand
    else:
        payload["field_brand[0][target_id]"] = ""
        payload["field_brand[0][other]"] = brand_name
        payload["field_brand[0][autocomplete_fill_field]"] = "Ajouter une nouvelle marque"

    # Model: prefer resolved autocomplete label; otherwise place value directly
    model_value = getattr(repair, "model", "") or ""
    if resolved_model:
        payload["field_model[0][target_id]"] = resolved_model
    else:
        payload["field_model[0][target_id]"] = model_value

    # Build year
    year_value = getattr(repair, "year", None)
    if year_value:
        payload["field_product_buildyear[0][value]"] = str(year_value)

    # Descriptions
    description = getattr(repair, "description", "") or ""
    payload["field_cause_of_fault[0][value]"] = description
    payload["field_fault[0][value]"] = description

    # Outcome
    status_value = _map_close_status(getattr(repair, "close_status_id", None))
    if status_value:
        payload["field_product_repaired"] = status_value
        if status_value == "yes":
            payload["field_solution[0][value]"] = description
        elif status_value == "half":
            payload["field_advice[0][value]"] = description
        elif status_value == "no":
            payload["field_repair_failed"] = "_none"

    # Repairer: prefer resolved autocomplete label; otherwise use formatted local list
    formatted_repairer = _format_repairer(getattr(repair, "users", []) or [])
    if resolved_repairer:
        payload["field_repairer[0][target_id]"] = resolved_repairer
    else:
        payload["field_repairer[0][target_id]"] = formatted_repairer

    # Add local metadata / notes into RM hint/comment field
    if extra_comment:
        payload["field_hint[0][value]"] = extra_comment
    else:
        payload["field_hint[0][value]"] = ""

    # Explicitly leave repairability, repair information, and hints empty
    return payload


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


def resolve_repair_autocomplete_values(
    session: requests.Session,
    *,
    form_snapshot: dict,
    repair: Repair,
    language: str = "fr",
    timeout: int = RM_HTTP_TIMEOUT,
) -> dict[str, str | None]:
    """Attempt to resolve product/brand/model/repairer via RM autocomplete.

    Returns a dict with potential labels to use as target_id. If no suggestion is
    found, values are left as None so callers can fall back to "other" paths.
    """

    paths = (form_snapshot or {}).get("autocomplete_paths") or {}
    otype_value = getattr(repair, "otype", "") or ""
    brand_name = getattr(getattr(repair, "brand", None), "name", None) or ""
    model_value = getattr(repair, "model", "") or ""
    repairer_value = _format_repairer(getattr(repair, "users", []) or [])

    return {
        "resolved_kind": fetch_autocomplete_suggestion(
            session,
            path=paths.get("kind_product"),
            term=otype_value,
            language=language,
            timeout=timeout,
        ),
        "resolved_brand": fetch_autocomplete_suggestion(
            session,
            path=paths.get("brand"),
            term=brand_name,
            language=language,
            timeout=timeout,
        ),
        "resolved_model": fetch_autocomplete_suggestion(
            session,
            path=paths.get("model"),
            term=model_value,
            language=language,
            timeout=timeout,
        ),
        "resolved_repairer": fetch_autocomplete_suggestion(
            session,
            path=paths.get("repairer"),
            term=repairer_value,
            language=language,
            timeout=timeout,
        ),
    }


def cache_sync_session(session: requests.Session, *, language: str) -> str:
    """Store an authenticated session for reuse during a single preview run."""

    sync_id = uuid.uuid4().hex
    now = time.time()
    with _SYNC_SESSION_LOCK:
        _cleanup_expired_sessions_locked(now)
        _SYNC_SESSIONS[sync_id] = {
            "session": session,
            "language": language,
            "created": now,
            "last_used": now,
        }
    return sync_id


def get_cached_sync_session(sync_id: str) -> dict | None:
    """Return cached session metadata (session + language) if still valid."""

    now = time.time()
    with _SYNC_SESSION_LOCK:
        _cleanup_expired_sessions_locked(now)
        meta = _SYNC_SESSIONS.get(sync_id)
        if not meta:
            return None
        meta["last_used"] = now
        return meta


def release_sync_session(sync_id: str) -> None:
    """Remove a cached session immediately (best-effort)."""

    with _SYNC_SESSION_LOCK:
        meta = _SYNC_SESSIONS.pop(sync_id, None)
    if not meta:
        return
    try:
        meta["session"].close()
    except Exception:  # pragma: no cover - defensive cleanup
        pass


def _cleanup_expired_sessions_locked(now: float) -> None:
    expire_before = now - SYNC_SESSION_TTL_SECONDS
    expired = [
        sid for sid, meta in _SYNC_SESSIONS.items() if meta.get("last_used", 0) < expire_before
    ]
    for sid in expired:
        session = _SYNC_SESSIONS.pop(sid)["session"]
        try:
            session.close()
        except Exception:  # pragma: no cover
            pass
