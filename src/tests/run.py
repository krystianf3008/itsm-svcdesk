# ai-generated: 90% - Claude Code wrote the suite from specs/001-svcdesk/spec.md and METRIC-SPEC.md, reviewed by me
"""Own test suite: HTTP checks against the running svcdesk (SVCDESK_URL). The last line is the summary."""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("SVCDESK_URL", "http://svcdesk:8080").rstrip("/")
T1 = "2026-10-14T10:00:00Z"
WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}


# --- helpers ------------------------------------------------------------------------------------------------

def call(method, path, body=None, clock=None):
    data = json.dumps(body).encode() if body is not None else (b"{}" if method == "POST" else None)
    headers = {"Content-Type": "application/json"}
    if clock:
        headers["X-Test-Clock"] = clock
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        raw = error.read()
        return error.code, json.loads(raw) if raw else None


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def parse(instant):
    return datetime.fromisoformat(instant.replace("Z", "+00:00"))


def later(instant, **delta):
    return (parse(instant) + timedelta(**delta)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_ticket(clock=T1, impact=2, urgency=1, vip=False, title="test ticket"):
    body = {"title": title, "reporter": {"name": "Tester", "vip": vip}, "impact": impact, "urgency": urgency}
    status, ticket = call("POST", "/tickets", body, clock)
    expect(status == 201, f"create answered {status}: {ticket}")
    return ticket


def act(ticket, action, clock):
    return call("POST", f"/tickets/{ticket['id']}/{action}", clock=clock)


def resolved_ticket(clock=T1):
    """A ticket driven new -> acknowledged -> in_progress -> resolved; returns it and the resolve instant."""
    ticket = new_ticket(clock)
    resolve_at = later(clock, hours=1)
    for action, when in (("ack", later(clock, minutes=5)), ("start", later(clock, minutes=10)), ("resolve", resolve_at)):
        status, ticket = act(ticket, action, when)
        expect(status == 200, f"{action} answered {status}")
    return ticket, resolve_at


def commit(sha, at, change="CHG-1", branch="main", reverts=None):
    return {"event_id": "c-" + sha, "type": "commit", "at": at, "sha": sha, "branch": branch,
            "change_id": None if reverts else change, "reverts": reverts}


def deploy(deployment_id, at, commits=(), outcome="success", environment="production", unplanned=False, caused_by=None):
    return {"event_id": "d-" + deployment_id, "type": "deployment", "at": at, "deployment_id": deployment_id,
            "environment": environment, "outcome": outcome, "commits": list(commits), "unplanned": unplanned,
            "caused_by": caused_by}


def incident(incident_id, phase, at, deployments=()):
    return {"event_id": f"i-{incident_id}-{phase}", "type": "incident", "at": at, "incident_id": incident_id,
            "phase": phase, "deployments": list(deployments)}


def metrics(events, window=WINDOW):
    status, body = call("POST", "/dora/metrics", {"window": window, "events": events})
    expect(status == 200, f"/dora/metrics answered {status}: {body}")
    return body


# --- ticket API ---------------------------------------------------------------------------------------------

def test_health():
    status, body = call("GET", "/health")
    expect(status == 200 and body["status"] == "ok" and body["service"] == "svcdesk", f"{status} {body}")


def test_unknown_routes_are_json_404():
    status, body = call("GET", "/no-such-route-9f3c")
    expect(status == 404 and isinstance(body, dict), f"route: {status} {body}")
    status, body = call("GET", "/tickets/does-not-exist-9f3c")
    expect(status == 404 and "error" in body, f"ticket: {status} {body}")


def test_priority_matrix():
    expected = {(1, 1): "P1", (1, 2): "P2", (1, 3): "P3", (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
                (3, 1): "P3", (3, 2): "P4", (3, 3): "P4"}
    for (impact, urgency), priority in expected.items():
        got = new_ticket(impact=impact, urgency=urgency)["priority"]
        expect(got == priority, f"impact {impact}, urgency {urgency}: {got}, want {priority}")


def test_vip_is_raised_to_p2():
    expect(new_ticket(impact=3, urgency=3, vip=True)["priority"] == "P2", "VIP P4 should become P2")
    expect(new_ticket(impact=2, urgency=2, vip=True)["priority"] == "P2", "VIP P3 should become P2")
    expect(new_ticket(impact=1, urgency=1, vip=True)["priority"] == "P1", "VIP P1 must stay P1")
    body = {"title": "t", "reporter": {"name": "T"}, "impact": 3, "urgency": 3, "priority": "P1"}
    status, ticket = call("POST", "/tickets", body, T1)
    expect(status == 201 and ticket["priority"] == "P4", f"client priority must be ignored: {ticket}")


def test_validation_rejects_bad_tickets():
    good = {"title": "t", "reporter": {"name": "T"}, "impact": 1, "urgency": 1}
    bad = [{**good, "title": None}, {**good, "impact": 5}, {**good, "urgency": "high"},
           {**good, "title": "x" * 201}, {**good, "reporter": {}}, {**good, "impact": True}]
    for body in bad:
        status, answer = call("POST", "/tickets", body, T1)
        expect(status in (400, 422) and "error" in answer, f"{body} answered {status}")


def test_malformed_clock_is_rejected():
    body = {"title": "t", "reporter": {"name": "T"}, "impact": 1, "urgency": 1}
    for clock in ("yesterday", "2026-10-14T10:00:00"):
        status, _ = call("POST", "/tickets", body, clock)
        expect(status in (400, 422), f"clock {clock!r} answered {status}")


def test_lifecycle_records_the_clock():
    ticket = new_ticket()
    expect(ticket["state"] == "new" and ticket["created_at"] == T1, f"created: {ticket}")
    for action, state, field, minutes in (("ack", "acknowledged", "acknowledged_at", 5), ("start", "in_progress", None, 10),
                                          ("resolve", "resolved", "resolved_at", 60), ("close", "closed", "closed_at", 120)):
        when = later(T1, minutes=minutes)
        status, ticket = act(ticket, action, when)
        expect(status == 200 and ticket["state"] == state, f"{action}: {status} {ticket}")
        if field:
            expect(ticket[field] == when, f"{field} is {ticket[field]}, want {when}")


def test_invalid_transitions_are_409():
    fresh = new_ticket()
    for action in ("start", "resolve", "close", "reopen"):
        status, _ = act(fresh, action, T1)
        expect(status == 409, f"{action} on new answered {status}")
    act(fresh, "ack", later(T1, minutes=5))
    for action in ("ack", "resolve"):
        status, _ = act(fresh, action, later(T1, minutes=6))
        expect(status == 409, f"{action} on acknowledged answered {status}")
    status, _ = call("POST", "/tickets/does-not-exist-9f3c/ack", clock=T1)
    expect(status == 404, f"ack on an unknown id answered {status}")


def test_reopen_window_is_seven_days():
    ticket, resolved_at = resolved_ticket()
    status, reopened = act(ticket, "reopen", later(resolved_at, days=6))
    expect(status == 200 and reopened["state"] == "in_progress" and reopened["resolved_at"] is None, f"6 days: {status}")
    ticket, resolved_at = resolved_ticket()
    status, _ = act(ticket, "reopen", later(resolved_at, days=7))
    expect(status == 200, f"exactly 7 days answered {status}")
    ticket, resolved_at = resolved_ticket()
    status, _ = act(ticket, "reopen", later(resolved_at, days=7, seconds=1))
    expect(status == 409, f"7 days + 1 s answered {status}")


def test_closed_ticket_is_immutable():
    ticket, resolved_at = resolved_ticket()
    status, closed = act(ticket, "close", later(resolved_at, hours=1))
    expect(status == 200, f"close answered {status}")
    status, body = act(closed, "reopen", later(resolved_at, hours=25))
    expect(status == 409 and "error" in body, f"reopen of a closed ticket answered {status}")


def test_list_filters():
    p1 = new_ticket(impact=1, urgency=1)
    p4 = new_ticket(impact=3, urgency=3)
    status, listed = call("GET", "/tickets?priority=P1")
    ids = {t["id"] for t in listed}
    expect(status == 200 and p1["id"] in ids and p4["id"] not in ids, "priority filter")
    status, listed = call("GET", "/tickets?state=new")
    expect(p4["id"] in {t["id"] for t in listed}, "state filter")


# --- SLA ----------------------------------------------------------------------------------------------------

def sla_due(ticket):
    return ticket["sla"]["ack_due_at"], ticket["sla"]["resolve_due_at"]


def test_p1_targets_run_on_the_wall_clock():
    expect(sla_due(new_ticket(T1, 1, 1)) == ("2026-10-14T10:15:00Z", "2026-10-14T14:00:00Z"), "T1")
    expect(sla_due(new_ticket("2026-10-16T15:00:00Z", 1, 1)) == ("2026-10-16T15:15:00Z", "2026-10-16T19:00:00Z"),
           "T3: a P1 raised on Friday 17:00 is due 15 minutes later")


def test_other_targets_run_on_business_hours():
    vectors = [(("2026-10-16T13:30:00Z", 2, 2), ("2026-10-19T09:30:00Z", "2026-10-21T13:30:00Z")),   # T2, P3
               (("2026-10-17T10:00:00Z", 1, 2), ("2026-10-19T07:00:00Z", "2026-10-19T14:00:00Z")),   # T4, tie at closing
               (("2027-01-14T14:30:00Z", 2, 3), ("2027-01-15T14:30:00Z", "2027-01-27T14:30:00Z")),   # T5, CET
               (("2026-10-14T10:00:00Z", 1, 2), ("2026-10-14T11:00:00Z", "2026-10-15T10:00:00Z")),   # T7, crosses closing
               (("2026-10-23T13:00:00Z", 2, 2), ("2026-10-26T10:00:00Z", "2026-10-28T14:00:00Z"))]   # T8, DST ends
    for (clock, impact, urgency), want in vectors:
        got = sla_due(new_ticket(clock, impact, urgency))
        expect(got == want, f"created {clock}: {got}, want {want}")


def test_breach_and_pause():
    ticket = new_ticket("2026-10-16T13:30:00Z", 2, 2)                # T2, ack due Monday 09:30Z
    path = f"/tickets/{ticket['id']}/sla"
    cases = [("2026-10-19T09:30:00Z", False, False), ("2026-10-19T09:31:00Z", True, False),
             ("2026-10-17T10:00:00Z", False, True), ("2026-10-19T09:00:00Z", False, False)]
    for clock, ack_breached, paused in cases:
        status, sla = call("GET", path, clock=clock)
        expect(status == 200 and sla["ack_breached"] is ack_breached and sla["paused"] is paused, f"{clock}: {sla}")
    p1 = new_ticket("2026-10-16T15:00:00Z", 1, 1)
    status, sla = call("GET", f"/tickets/{p1['id']}/sla", clock="2026-10-17T10:00:00Z")
    expect(sla["paused"] is False, "a P1 clock never pauses")


# --- DORA ---------------------------------------------------------------------------------------------------

def test_dora_negative_lead_time_is_clamped_and_counted():
    result = metrics([commit("a", "2026-09-02T10:10:00Z"), commit("b", "2026-09-02T09:00:00Z", "CHG-2"),
                      deploy("DEP-1", "2026-09-02T10:00:00Z", ["a", "b"])])
    expect(result["anomalies"]["negative_lead_time_pairs"] == 1, f"anomalies: {result['anomalies']}")
    expect(result["counts"]["lead_time_pairs"] == 2 and result["change_lead_time_seconds_p50"] == 1800, str(result))


def test_dora_revert_of_a_revert_is_one_change():
    result = metrics([commit("s1", "2026-09-02T08:00:00Z"), commit("s2", "2026-09-02T09:00:00Z", reverts="s1"),
                      commit("s3", "2026-09-02T10:00:00Z", reverts="s2"),
                      deploy("DEP-1", "2026-09-02T12:00:00Z", ["s3"])])
    expect(result["counts"]["changes"] == 1 and result["anomalies"]["revert_chains_collapsed"] == 2, str(result))
    expect(result["ground_truth"] == {"changes_delivered": 1, "true_change_lead_time_seconds_p50": 14400}, str(result))
    expect(result["change_lead_time_seconds_p50"] == 7200, "the pair is measured from the revert commit itself")


def test_dora_hotfix_off_main_still_counts():
    result = metrics([commit("h", "2026-09-02T08:00:00Z", branch="hotfix/1"),
                      deploy("DEP-1", "2026-09-02T08:30:00Z", ["h"])])
    expect(result["anomalies"]["commits_never_on_main"] == 1, str(result["anomalies"]))
    expect(result["counts"]["lead_time_pairs"] == 1 and result["change_lead_time_seconds_p50"] == 1800, str(result))


def test_dora_deployment_without_commits():
    result = metrics([deploy("DEP-1", "2026-09-02T10:00:00Z")])
    expect(result["anomalies"]["deployments_without_commits"] == 1 and result["counts"]["deployments"] == 1, str(result))
    expect(result["counts"]["lead_time_pairs"] == 0 and result["change_lead_time_seconds_p50"] is None, str(result))
    expect(result["deployment_frequency_per_day"] == 0.047619 and result["change_fail_rate"] == 0.0, str(result))


def test_dora_failure_that_never_recovered_is_open():
    result = metrics([deploy("DEP-1", "2026-09-02T10:00:00Z", outcome="failure"),
                      incident("INC-1", "opened", "2026-09-02T10:10:00Z", ["DEP-1"])])
    expect(result["counts"]["open_failures"] == 1 and result["counts"]["recovered_failures"] == 0, str(result["counts"]))
    expect(result["failed_deployment_recovery_time_seconds_p50"] is None and result["change_fail_rate"] == 1.0, str(result))


def test_dora_rework_and_recovery():
    result = metrics([deploy("DEP-1", "2026-09-02T10:00:00Z", outcome="failure"),
                      incident("INC-1", "opened", "2026-09-02T10:10:00Z", ["DEP-1"]),
                      incident("INC-1", "resolved", "2026-09-02T11:00:00Z", ["DEP-1"]),
                      deploy("DEP-2", "2026-09-02T12:00:00Z", unplanned=True, caused_by="INC-1")])
    expect(result["failed_deployment_recovery_time_seconds_p50"] == 3600, str(result))
    expect(result["change_fail_rate"] == 0.5 and result["deployment_rework_rate"] == 0.5, str(result))
    expect(result["counts"]["rework_deployments"] == 1 and result["deployment_frequency_per_day"] == 0.095238, str(result))


def overlapping_log():
    return [deploy("DEP-A", "2026-09-02T10:00:00Z", outcome="failure"), deploy("DEP-B", "2026-09-02T10:30:00Z", outcome="failure"),
            deploy("DEP-C", "2026-09-02T13:00:00Z", outcome="failure"),
            incident("INC-1", "opened", "2026-09-02T10:05:00Z", ["DEP-A"]), incident("INC-1", "resolved", "2026-09-02T12:00:00Z", ["DEP-A"]),
            incident("INC-2", "opened", "2026-09-02T10:35:00Z", ["DEP-B"]), incident("INC-2", "resolved", "2026-09-02T11:00:00Z", ["DEP-B"]),
            incident("INC-3", "opened", "2026-09-02T13:05:00Z", ["DEP-C"]), incident("INC-3", "resolved", "2026-09-02T13:20:00Z", ["DEP-C"])]


def test_dora_overlapping_incidents_are_not_merged():
    result = metrics(overlapping_log())
    expect(result["anomalies"]["overlapping_incident_pairs"] == 1, str(result["anomalies"]))
    expect(result["counts"]["recovered_failures"] == 3 and result["failed_deployment_recovery_time_seconds_p50"] == 1800,
           f"recoveries are per deployment (7200, 1800, 1200): {result}")


def test_dora_window_is_half_open_and_production_only():
    result = metrics([deploy("DEP-1", "2026-09-01T00:00:00Z"), deploy("DEP-2", "2026-09-22T00:00:00Z"),
                      deploy("DEP-3", "2026-09-05T00:00:00Z", environment="staging"),
                      deploy("DEP-4", "2026-08-31T23:59:59Z")])
    expect(result["counts"]["deployments"] == 1, f"only DEP-1 is in scope: {result['counts']}")


def test_dora_rejects_bad_requests():
    good = {"window": WINDOW, "events": []}
    bad = [{"events": []}, {**good, "window": {"from": WINDOW["to"], "to": WINDOW["from"]}}, {"window": WINDOW},
           {**good, "events": {}}, [], {**good, "events": [commit("a", "2026-09-02T08:00:00Z", reverts="ghost")]},
           {**good, "events": [deploy("DEP-1", "2026-09-02T08:00:00Z", outcome="maybe")]}]
    for body in bad:
        status, answer = call("POST", "/dora/metrics", body)
        expect(status in (400, 422) and "error" in answer, f"{str(body)[:80]} answered {status}")


def test_dora_is_pure_and_order_independent():
    events = overlapping_log()
    first = metrics(events)
    expect(metrics(events) == first, "same request, different answer")
    expect(metrics(list(reversed(events))) == first, "order matters")
    expect(metrics(events + events) == first, "duplicate events are counted twice")


def test_dora_empty_log():
    result = metrics([])
    expect(result["deployment_frequency_per_day"] == 0.0 and result["change_lead_time_seconds_p50"] is None
           and result["change_fail_rate"] is None and set(result["counts"].values()) == {0}, str(result))
    expect(result["spec_version"] == "1.0.0" and result["window"] == WINDOW, str(result))


def test_ticket_events_stream():
    ticket, resolved_at = resolved_ticket()
    status, events = call("GET", "/dora/ticket-events")
    expect(status == 200 and isinstance(events, list), f"status {status}")
    mine = [e for e in events if e["ticket_id"] == ticket["id"]]
    expect([e["phase"] for e in mine] == ["created", "acknowledged", "resolved"], f"phases: {mine}")
    expect([e["state"] for e in mine] == ["new", "acknowledged", "resolved"], f"states: {mine}")
    keys = [(parse(e["at"]), e["ticket_id"]) for e in events]
    expect(keys == sorted(keys), "the stream must be ordered by (at, ticket_id)")


# --- runner -------------------------------------------------------------------------------------------------

def wait_for_service(seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if call("GET", "/health")[0] == 200:
                return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(1)
    return False


def main():
    passed = failed = 0
    if wait_for_service():
        for name, test in [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]:
            try:
                test()
                passed += 1
                print(f"PASS {name}")
            except Exception as error:  # a failing test must not stop the run
                failed += 1
                print(f"FAIL {name}: {error}")
    else:
        failed += 1
        print(f"FAIL service did not answer /health at {BASE}")
    print(f"ITSMLAB-TESTS: passed={passed} failed={failed}", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
