# ai-generated: 90% - Claude Code drafted from specs/001-svcdesk/spec.md, reviewed by me
"""SLA due instants and the business-hours clock (spec section 6)."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
OPENING = time(8, 0)
CLOSING = time(16, 0)

# (acknowledge, resolve) targets in minutes.
TARGETS = {"P1": (15, 240), "P2": (60, 480), "P3": (240, 1440), "P4": (480, 4320)}


def runs_on_business_clock(priority: str) -> bool:
    # C1 = wallclock: P1 is measured around the clock, P2..P4 on business hours.
    return priority != "P1"


def in_business_hours(instant: datetime) -> bool:
    local = instant.astimezone(WARSAW)
    return local.weekday() < 5 and OPENING <= local.time() < CLOSING


def _next_business_day(day: date) -> date:
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _opening_on_or_after(local: datetime) -> datetime:
    if local.weekday() < 5:
        if local.time() < OPENING:
            return datetime.combine(local.date(), OPENING)
        if local.time() < CLOSING:
            return local
    return datetime.combine(_next_business_day(local.date()), OPENING)


def business_due(created: datetime, minutes: int) -> datetime:
    """Consume `minutes` from consecutive business windows, in Europe/Warsaw wall-clock time."""
    current = _opening_on_or_after(created.astimezone(WARSAW).replace(tzinfo=None))
    remaining = timedelta(minutes=minutes)
    while True:
        room = datetime.combine(current.date(), CLOSING) - current
        # `<=` is the tie rule: a target ending exactly at closing is due at 16:00, not at the next opening.
        if remaining <= room:
            return (current + remaining).replace(tzinfo=WARSAW).astimezone(timezone.utc)
        remaining -= room
        current = datetime.combine(_next_business_day(current.date()), OPENING)


def due_instants(priority: str, created: datetime) -> tuple[datetime, datetime]:
    ack, resolve = TARGETS[priority]
    if runs_on_business_clock(priority):
        return business_due(created, ack), business_due(created, resolve)
    return created + timedelta(minutes=ack), created + timedelta(minutes=resolve)
