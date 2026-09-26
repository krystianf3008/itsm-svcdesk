# ai-generated: 90% - Claude Code drafted from METRIC-SPEC.md, reviewed by me
"""DORA delivery metrics computed from an event log (METRIC-SPEC.md) and the ticket lifecycle stream."""
import re
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from math import floor

from .domain import fmt, invalid, parse

SPEC_VERSION = "1.0.0"
MICRO = 10**6
DAY = 86400
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


# --- parsing and well-formedness (section 1) ---------------------------------------------------------------

def _instant(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not _INSTANT.match(value):
        raise invalid(f"{label} must be an RFC 3339 instant with an offset")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00").replace("t", "T"))
    except ValueError:
        raise invalid(f"{label} is not a valid instant") from None


def _micros(instant: datetime) -> int:
    return (instant - _EPOCH) // timedelta(microseconds=1)


def _text(event: dict, name: str, where: str, nullable: bool = False) -> str | None:
    value = event.get(name)
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise invalid(f"{where}: {name} must be a non-empty string" + (" or null" if nullable else ""))
    return value


def _texts(event: dict, name: str, where: str) -> list[str]:
    value = event.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise invalid(f"{where}: {name} must be an array of strings")
    return value


def _event(raw: object, where: str) -> dict:
    if not isinstance(raw, dict):
        raise invalid(f"{where}: an event must be an object")
    kind = raw.get("type")
    event = {
        "event_id": raw["event_id"],
        "type": kind,
        "at": _micros(_instant(raw.get("at"), f"{where}: at")),
    }
    if kind == "commit":
        event.update(sha=_text(raw, "sha", where), branch=_text(raw, "branch", where),
                     change_id=_text(raw, "change_id", where, nullable=True),
                     reverts=_text(raw, "reverts", where, nullable=True))
        if (event["change_id"] is None) == (event["reverts"] is None):
            raise invalid(f"{where}: a commit carries a change_id exactly when reverts is null")
    elif kind == "deployment":
        if raw.get("outcome") not in ("success", "failure"):
            raise invalid(f"{where}: outcome must be success or failure")
        if not isinstance(raw.get("unplanned"), bool):
            raise invalid(f"{where}: unplanned must be a boolean")
        event.update(deployment_id=_text(raw, "deployment_id", where), environment=_text(raw, "environment", where),
                     outcome=raw["outcome"], commits=_texts(raw, "commits", where), unplanned=raw["unplanned"],
                     caused_by=_text(raw, "caused_by", where, nullable=True))
    elif kind == "incident":
        if raw.get("phase") not in ("opened", "resolved"):
            raise invalid(f"{where}: phase must be opened or resolved")
        event.update(incident_id=_text(raw, "incident_id", where), phase=raw["phase"],
                     deployments=_texts(raw, "deployments", where))
    else:
        raise invalid(f"{where}: type must be commit, deployment or incident")
    return event


def parse_events(raw: object) -> list[dict]:
    """Validate the log; an event_id seen again is ignored, never an error (R-05)."""
    if not isinstance(raw, list):
        raise invalid("events must be an array")
    seen: set[str] = set()
    events = []
    for index, item in enumerate(raw):
        where = f"events[{index}]"
        event_id = item.get("event_id") if isinstance(item, dict) else None
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
            raise invalid(f"{where}: event_id must be a string of 1 to 64 characters")
        if event_id in seen:
            continue
        seen.add(event_id)
        events.append(_event(item, where))
    _check_references(events)
    return events


def _check_references(events: list[dict]) -> None:
    shas: dict[str, dict] = {}
    for event in events:
        if event["type"] == "commit":
            if event["sha"] in shas:
                raise invalid(f"sha {event['sha']} is not unique")
            shas[event["sha"]] = event
    deployment_ids = {e["deployment_id"] for e in events if e["type"] == "deployment"}
    phases: dict[tuple[str, str], int] = {}
    for event in events:
        if event["type"] == "incident":
            key = (event["incident_id"], event["phase"])
            phases[key] = phases.get(key, 0) + 1
            if phases[key] > 1:
                raise invalid(f"incident {event['incident_id']} has two {event['phase']} events")
    incident_ids = {incident_id for incident_id, _ in phases}
    for incident_id, phase in phases:
        if phase == "resolved" and (incident_id, "opened") not in phases:
            raise invalid(f"incident {incident_id} resolved without being opened")
    for event in events:
        if event["type"] == "commit" and event["reverts"] is not None and event["reverts"] not in shas:
            raise invalid(f"reverts names an unknown sha {event['reverts']}")
        if event["type"] == "deployment":
            for sha in event["commits"]:
                if sha not in shas:
                    raise invalid(f"deployment {event['deployment_id']} carries an unknown sha {sha}")
            if event["caused_by"] is not None and event["caused_by"] not in incident_ids:
                raise invalid(f"caused_by names an unknown incident {event['caused_by']}")
        if event["type"] == "incident":
            for deployment_id in event["deployments"]:
                if deployment_id not in deployment_ids:
                    raise invalid(f"incident {event['incident_id']} names an unknown deployment {deployment_id}")


# --- arithmetic (R-03, R-04) --------------------------------------------------------------------------------

def _half_up(value: Fraction) -> int:
    return floor(value + Fraction(1, 2))


def _median_seconds(durations: list[int]) -> int | None:
    """Median of durations given in microseconds, reported in whole seconds, rounded half-up."""
    if not durations:
        return None
    ordered = sorted(durations)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        centre = Fraction(ordered[middle])
    else:
        centre = Fraction(ordered[middle - 1] + ordered[middle], 2)
    return _half_up(centre / MICRO)


def _rate(numerator: Fraction | int, denominator: Fraction | int) -> float | None:
    if denominator == 0:
        return None
    return _half_up(Fraction(numerator) / Fraction(denominator) * MICRO) / MICRO


# --- the metrics (sections 3 to 5) --------------------------------------------------------------------------

def _resolve_change(sha: str, commits: dict[str, dict]) -> str:
    """R-06: a revert inherits, transitively, the change of the commit it reverts."""
    seen: set[str] = set()
    while commits[sha]["reverts"] is not None:
        if sha in seen:
            raise invalid("reverts form a cycle")
        seen.add(sha)
        sha = commits[sha]["reverts"]
    return commits[sha]["change_id"]


def _incidents(events: list[dict]) -> dict[str, dict]:
    incidents: dict[str, dict] = {}
    for event in events:
        if event["type"] != "incident":
            continue
        incident = incidents.setdefault(
            event["incident_id"], {"id": event["incident_id"], "opened": None, "resolved": None, "deployments": set()})
        incident[event["phase"]] = event["at"]
        incident["deployments"].update(event["deployments"])
    return incidents


def compute(start: int, end: int, events: list[dict]) -> dict:
    commits = {e["sha"]: e for e in events if e["type"] == "commit"}
    change_of = {sha: _resolve_change(sha, commits) for sha in commits}
    first_commit: dict[str, int] = {}
    for sha, commit in commits.items():
        change = change_of[sha]
        first_commit[change] = min(first_commit.get(change, commit["at"]), commit["at"])

    # R-01, R-02: production deployments inside the half-open window; commits and incidents are never filtered.
    deployments = sorted(
        (e for e in events if e["type"] == "deployment" and e["environment"] == "production" and start <= e["at"] < end),
        key=lambda d: (d["at"], d["deployment_id"]))
    successful = [d for d in deployments if d["outcome"] == "success"]
    failed = [d for d in deployments if d["outcome"] == "failure"]

    # R-08: one pair per commit, at its first successful deployment in the window (E1 clamps and counts).
    delivered_shas: set[str] = set()
    pairs = []
    for deployment in successful:
        for sha in deployment["commits"]:
            if sha not in delivered_shas:
                delivered_shas.add(sha)
                pairs.append(deployment["at"] - commits[sha]["at"])
    negative_pairs = sum(1 for pair in pairs if pair < 0)

    # R-12, R-13: recovery per failed deployment through its earliest-opened covering incident.
    incidents = _incidents(events)
    recoveries = []
    open_failures = 0
    for deployment in failed:
        covering = [i for i in incidents.values() if deployment["deployment_id"] in i["deployments"]]
        cover = min(covering, key=lambda i: (i["opened"], i["id"]), default=None)
        if cover is None or cover["resolved"] is None:
            open_failures += 1
        else:
            recoveries.append(max(cover["resolved"] - deployment["at"], 0))
    spans = [(i["opened"], i["resolved"] if i["resolved"] is not None else end) for i in incidents.values()]
    overlapping = sum(1 for a in range(len(spans)) for b in range(a + 1, len(spans))
                      if spans[a][0] < spans[b][1] and spans[b][0] < spans[a][1])

    rework = sum(1 for d in deployments if d["unplanned"] and d["caused_by"] is not None)
    frequency = _rate(len(deployments) * DAY * MICRO, end - start)

    # R-16, R-17: ground truth over changes, from each change's earliest commit anywhere in the log.
    delivered_at: dict[str, int] = {}
    for deployment in successful:
        for sha in deployment["commits"]:
            delivered_at.setdefault(change_of[sha], deployment["at"])
    true_lead = [max(at - first_commit[change], 0) for change, at in delivered_at.items()]

    return {
        "spec_version": SPEC_VERSION,
        "deployment_frequency_per_day": frequency,
        "change_lead_time_seconds_p50": _median_seconds([max(pair, 0) for pair in pairs]),
        "failed_deployment_recovery_time_seconds_p50": _median_seconds(recoveries),
        "change_fail_rate": _rate(len(failed), len(deployments)),
        "deployment_rework_rate": _rate(rework, len(deployments)),
        "counts": {
            "deployments": len(deployments),
            "successful_deployments": len(successful),
            "failed_deployments": len(failed),
            "recovered_failures": len(recoveries),
            "open_failures": open_failures,
            "rework_deployments": rework,
            "lead_time_pairs": len(pairs),
            "changes": len(first_commit),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_pairs,
            "deployments_without_commits": sum(1 for d in deployments if not d["commits"]),
            "commits_never_on_main": len({sha for d in deployments for sha in d["commits"]
                                          if commits[sha]["branch"] != "main"}),
            "revert_chains_collapsed": sum(1 for c in commits.values() if c["reverts"] is not None),
            "overlapping_incident_pairs": overlapping,
        },
        "ground_truth": {
            "changes_delivered": len(delivered_at),
            "true_change_lead_time_seconds_p50": _median_seconds(true_lead),
        },
    }


def metrics_response(body: object) -> dict:
    """POST /dora/metrics: a pure function of the request body (spec section 6)."""
    if not isinstance(body, dict):
        raise invalid("body must be a JSON object")
    window = body.get("window")
    if not isinstance(window, dict):
        raise invalid("window is required")
    start = _instant(window.get("from"), "window.from")
    end = _instant(window.get("to"), "window.to")
    if end <= start:
        raise invalid("window.to must be after window.from")
    if "events" not in body:
        raise invalid("events is required")
    events = parse_events(body["events"])
    result = compute(_micros(start), _micros(end), events)
    return {"spec_version": result.pop("spec_version"), "window": {"from": fmt(start), "to": fmt(end)}, **result}


# --- GET /dora/ticket-events (spec section 7) ---------------------------------------------------------------

_PHASES = (("created", "created_at", "new"), ("acknowledged", "acknowledged_at", "acknowledged"),
           ("resolved", "resolved_at", "resolved"), ("closed", "closed_at", "closed"))


def ticket_events(tickets: list[dict]) -> list[dict]:
    """One event per lifecycle instant a ticket actually holds, ordered by (at, ticket_id)."""
    events = [{"ticket_id": t["id"], "at": t[field], "phase": phase, "priority": t["priority"], "state": state}
              for t in tickets for phase, field, state in _PHASES if t.get(field) is not None]
    events.sort(key=lambda e: (parse(e["at"]), e["ticket_id"]))
    return events
