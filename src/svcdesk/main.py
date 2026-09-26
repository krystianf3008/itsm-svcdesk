# ai-generated: 90% - Claude Code drafted from specs/001-svcdesk/spec.md, reviewed by me
"""svcdesk HTTP API (spec sections 3, 5, 6, 7)."""
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import dora
from .domain import ApiError, compute_priority, fmt, parse, parse_clock, validate_new_ticket
from .sla import due_instants, in_business_hours, runs_on_business_clock
from .store import Store

app = FastAPI(title="svcdesk", docs_url=None, redoc_url=None, openapi_url=None)
store = Store(os.environ.get("SVCDESK_DB", "/data/svcdesk.db"))
TEST_CLOCK = os.environ.get("SVCDESK_TEST_CLOCK", "").lower() in ("1", "true")
REOPEN_WINDOW = timedelta(days=7)

# action -> (from state, to state, timestamp field set to `now`)
ACTIONS = {
    "ack": ("new", "acknowledged", "acknowledged_at"),
    "start": ("acknowledged", "in_progress", None),
    "resolve": ("in_progress", "resolved", "resolved_at"),
    "close": ("resolved", "closed", "closed_at"),
}


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status, exc.code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "not_found" if exc.status_code == 404 else "http_error"
    return error_response(exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    return error_response(500, "internal", "internal error")


def now_for(request: Request) -> datetime:
    """`now` for this request: the test-clock header when enabled, else real UTC time."""
    if TEST_CLOCK:
        raw = request.headers.get("x-test-clock")
        if raw is not None:
            return parse_clock(raw)
    return datetime.now(timezone.utc)


def load(ticket_id: str) -> dict:
    ticket = store.get(ticket_id)
    if ticket is None:
        raise ApiError(404, "not_found", "ticket not found")
    return ticket


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "svcdesk"}


@app.post("/tickets")
async def create_ticket(request: Request) -> JSONResponse:
    now = now_for(request)
    try:
        body = await request.json()
    except ValueError:
        raise ApiError(422, "validation", "body must be valid JSON") from None
    fields = validate_new_ticket(body)
    priority = compute_priority(fields["impact"], fields["urgency"], fields["reporter"]["vip"])
    ack_due, resolve_due = due_instants(priority, now)
    ticket = {
        "id": str(uuid.uuid4()),
        **fields,
        "priority": priority,
        "state": "new",
        "created_at": fmt(now),
        "acknowledged_at": None,
        "resolved_at": None,
        "closed_at": None,
        "sla": {"ack_due_at": fmt(ack_due), "resolve_due_at": fmt(resolve_due)},
    }
    store.add(ticket)
    return JSONResponse(ticket, status_code=201)


@app.get("/tickets")
async def list_tickets(request: Request) -> JSONResponse:
    tickets = store.all()
    for field in ("state", "priority"):
        wanted = request.query_params.get(field)
        if wanted is not None:
            tickets = [t for t in tickets if t[field] == wanted]
    return JSONResponse(tickets)


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str) -> JSONResponse:
    return JSONResponse(load(ticket_id))


@app.get("/tickets/{ticket_id}/sla")
async def get_sla(ticket_id: str, request: Request) -> JSONResponse:
    now = now_for(request)
    ticket = load(ticket_id)
    ack_due = parse(ticket["sla"]["ack_due_at"])
    resolve_due = parse(ticket["sla"]["resolve_due_at"])
    acknowledged_at, resolved_at = ticket["acknowledged_at"], ticket["resolved_at"]
    ack_breached = now > ack_due if acknowledged_at is None else parse(acknowledged_at) > ack_due
    resolve_breached = now > resolve_due if resolved_at is None else parse(resolved_at) > resolve_due
    still_open = ticket["state"] not in ("resolved", "closed")
    paused = still_open and runs_on_business_clock(ticket["priority"]) and not in_business_hours(now)
    return JSONResponse({
        "priority": ticket["priority"],
        "ack_due_at": ticket["sla"]["ack_due_at"],
        "resolve_due_at": ticket["sla"]["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused,
    })


@app.post("/dora/metrics")
async def dora_metrics(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except ValueError:
        raise ApiError(422, "validation", "body must be valid JSON") from None
    return JSONResponse(dora.metrics_response(body))


@app.get("/dora/ticket-events")
async def dora_ticket_events() -> JSONResponse:
    return JSONResponse(dora.ticket_events(store.all()))


def refuse_transition(ticket: dict, action: str) -> ApiError:
    return ApiError(409, "invalid_transition", f"cannot {action} a ticket that is {ticket['state']}")


@app.post("/tickets/{ticket_id}/{action}")
async def act(ticket_id: str, action: str, request: Request) -> JSONResponse:
    if action != "reopen" and action not in ACTIONS:
        raise ApiError(404, "not_found", "unknown action")
    now = now_for(request)
    ticket = load(ticket_id)

    if action == "reopen":
        # C2 = immutable: only a resolved ticket can be reopened; a closed one never can.
        if ticket["state"] == "closed":
            raise ApiError(409, "ticket_closed", "a closed ticket is immutable; open a new ticket with related_to")
        if ticket["state"] != "resolved":
            raise refuse_transition(ticket, action)
        if now > parse(ticket["resolved_at"]) + REOPEN_WINDOW:
            raise ApiError(409, "reopen_window_expired", "the 7-day reopen window has passed")
        ticket.update(state="in_progress", resolved_at=None, closed_at=None)
    else:
        source, target, stamp = ACTIONS[action]
        if ticket["state"] != source:
            raise refuse_transition(ticket, action)
        ticket["state"] = target
        if stamp:
            ticket[stamp] = fmt(now)

    store.update(ticket)
    return JSONResponse(ticket)
