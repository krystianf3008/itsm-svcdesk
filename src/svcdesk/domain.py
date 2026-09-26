# ai-generated: 90% - Claude Code drafted from specs/001-svcdesk/spec.md, reviewed by me
"""Errors, timestamps, priority and request validation (spec sections 3, 4, 7)."""
import re
from datetime import datetime, timezone

MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def invalid(message: str) -> ApiError:
    return ApiError(422, "validation", message)


def compute_priority(impact: int, urgency: int, vip: bool) -> str:
    priority = MATRIX[(impact, urgency)]
    # C3 = vip: a VIP ticket is never lower than P2; P1 and P2 are unchanged.
    if vip and priority in ("P3", "P4"):
        return "P2"
    return priority


def fmt(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


_CLOCK = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d{1,6})?([Zz]|[+-]\d{2}:\d{2})$")


def parse_clock(raw: str) -> datetime:
    """RFC 3339 instant with an offset; a naive or unparsable value is refused."""
    if not _CLOCK.match(raw):
        raise ApiError(400, "invalid_clock", "X-Test-Clock must be an RFC 3339 instant with an offset")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00").replace("z", "+00:00").replace("t", "T"))
    except ValueError:
        raise ApiError(400, "invalid_clock", "X-Test-Clock is not a valid instant") from None


def _text(source: dict, name: str, low: int, high: int, required: bool, where: str = "") -> str | None:
    value = source.get(name)
    label = where + name
    if value is None:
        if required:
            raise invalid(f"{label} is required")
        return None
    if not isinstance(value, str):
        raise invalid(f"{label} must be a string")
    if not low <= len(value) <= high:
        raise invalid(f"{label} must be {low}..{high} characters")
    return value


def _level(body: dict, name: str) -> int:
    value = body.get(name)
    # bool is an int subclass in Python; true is not a valid level.
    if type(value) is not int or not 1 <= value <= 3:
        raise invalid(f"{name} must be an integer from 1 to 3")
    return value


def validate_new_ticket(body: object) -> dict:
    """Return the client-owned fields of a valid ticket; server-owned and unknown fields are dropped."""
    if not isinstance(body, dict):
        raise invalid("body must be a JSON object")
    title = _text(body, "title", 1, 200, True)
    description = _text(body, "description", 0, 4000, False) or ""
    reporter = body.get("reporter")
    if not isinstance(reporter, dict):
        raise invalid("reporter is required")
    name = _text(reporter, "name", 1, 100, True, "reporter.")
    email = reporter.get("email")
    if email is not None and not isinstance(email, str):
        raise invalid("reporter.email must be a string or null")
    vip = reporter.get("vip")
    if vip is None:
        vip = False
    if not isinstance(vip, bool):
        raise invalid("reporter.vip must be a boolean")
    related = body.get("related_to")
    return {
        "title": title,
        "description": description,
        "reporter": {"name": name, "email": email, "vip": vip},
        "impact": _level(body, "impact"),
        "urgency": _level(body, "urgency"),
        "related_to": related if isinstance(related, str) else None,
    }
