<!-- ai-generated: 85% - Claude Code drafted from REQUIREMENTS.md and API.md; I chose the three resolutions and reviewed the text -->
# svcdesk - specification (Lab 1)

Status: written before any code. Sources: REQUIREMENTS.md (R-01..R-25) and API.md (the enforced contract). Where they
differ in precision, API.md wins (REQUIREMENTS.md, Purpose).

## 1. Scope

`svcdesk` is a JSON-over-HTTP ticketing service on port 8080 for a 400-person service desk (R-01). It computes the
priority of each ticket, keeps two SLA clocks per ticket, enforces a five-state workflow, and refuses inputs that would
corrupt reports. It ships as a Docker Compose project (R-22) and keeps tickets in SQLite on a named volume (R-23).

## 2. Contradictions and the chosen resolutions

REQUIREMENTS.md contains three pairs that cannot both hold. In each pair the minimal conflicting part of one
requirement is rejected and everything else is kept, so both sides stay testable.

| id | pair | the conflict | resolution | what is rejected |
|---|---|---|---|---|
| C1 | R-13 vs R-14 | R-13 pauses every SLA clock outside business hours; R-14 says a P1 is measured around the clock ("late at 15 minutes past, not on Monday morning") | `wallclock` | the words "any SLA target" in R-13, for P1 only |
| C2 | R-09 vs R-10 | R-09 makes a closed ticket immutable; R-10 lets a reporter reopen a resolved or closed ticket within 7 days | `immutable` | the words "or closed" in R-10 |
| C3 | R-05 vs R-06 | R-05 derives priority from the matrix "and from nothing else"; R-06 lifts VIP tickets to at least P2 | `vip` | the words "and from nothing else" in R-05, for the VIP flag only |

Consequences that this specification fixes:

- **C1 = wallclock.** Both P1 targets are `created_at + 15 min` and `created_at + 4 h`. P2, P3 and P4 use the
  business-hours clock. `paused` is always false for P1.
- **C2 = immutable.** Reopen is allowed from `resolved` only. A closed ticket answers 409 on reopen at any age; the
  client opens a new ticket with `related_to` set to the closed one.
- **C3 = vip.** After the matrix, a ticket with `reporter.vip = true` at P3 or P4 becomes P2. P1 and P2 are unchanged.
  A `priority` field sent by the client is still ignored (R-05, its remaining part).

## 3. Interface (API.md 1, 2, 7)

| method and path | success | failure |
|---|---|---|
| `GET /health` | 200 `{"status":"ok","service":"svcdesk"}` | - |
| `POST /tickets` | 201 Ticket | 400 or 422 with `{"error": {...}}` |
| `GET /tickets` | 200 array, optional exact filters `state`, `priority`, no pagination | - |
| `GET /tickets/{id}` | 200 Ticket | 404 with `error` |
| `GET /tickets/{id}/sla` | 200 SLA block | 404 with `error` |
| `POST /tickets/{id}/ack`, `start`, `resolve`, `close`, `reopen` | 200 full Ticket | 409 invalid transition, 404 unknown id |
| any unknown path | - | 404 with a JSON body |

Every response is `application/json`. Ticket fields: `id` (opaque UUID, R-18), `title` (1..200), `description`
(0..4000, default ""), `reporter {name 1..100, email or null, vip default false}`, `impact` and `urgency` (integers
1..3), `priority`, `state`, `created_at`, `acknowledged_at`, `resolved_at`, `closed_at` (null until they happen),
`related_to` (string or null, not validated), `sla {ack_due_at, resolve_due_at}`. All instants are RFC 3339 in UTC
with a `Z` suffix (R-17).

Validation (R-20): missing or over-long title, missing reporter name, `impact` or `urgency` that is not an integer in
1..3 (a string such as "high" is an error, and so is a boolean) give 400 or 422 with a top-level `error` object.
Server-owned fields (`id`, `priority`, `state`, timestamps, `sla`) and unknown fields in a request body are ignored,
never rejected.

## 4. Priority (R-04, R-05, R-06)

| impact \ urgency | 1 | 2 | 3 |
|---|---|---|---|
| 1 | P1 | P2 | P3 |
| 2 | P2 | P3 | P4 |
| 3 | P3 | P4 | P4 |

Under C3 = vip a VIP ticket at P3 or P4 is raised to P2; impact 3 / urgency 3 / VIP is therefore P2, and impact 1 /
urgency 1 / VIP stays P1. Priority is computed once at creation.

## 5. Workflow (R-07, R-08, R-10, R-11, R-09)

| action | from | to | side effect |
|---|---|---|---|
| ack | new | acknowledged | `acknowledged_at = now` |
| start | acknowledged | in_progress | - |
| resolve | in_progress | resolved | `resolved_at = now` |
| close | resolved | closed | `closed_at = now` |
| reopen | resolved | in_progress | clears `resolved_at` and `closed_at` |

Every other transition, including resolve from `acknowledged`, is 409 with `{"error": {"code": "invalid_transition"}}`.
Reopen from `resolved` needs `now <= resolved_at + 7 days`; at 7 days + 1 s it is 409 (`reopen_window_expired`).
Reopening never changes `sla.resolve_due_at` (R-11). Reopen from `closed` is always 409 (`ticket_closed`, C2).

## 6. SLA (R-12, R-13, R-14, R-15, R-16)

| priority | acknowledge within | resolve within |
|---|---|---|
| P1 | 15 min | 4 h |
| P2 | 1 h | 8 h |
| P3 | 4 h | 24 h |
| P4 | 8 h | 72 h |

Wall-clock target: `created_at + target` (P1 only, C1). Business-hours target (P2..P4): business hours are Monday to
Friday, half-open window [08:00, 16:00) in `Europe/Warsaw`, DST-aware, public holidays are ordinary business days.

1. Convert `created_at` to Europe/Warsaw local time.
2. If it is outside a window, move to the next opening: 08:00 the same day if before opening on a business day,
   otherwise 08:00 on the next business day.
3. Consume the target from consecutive business windows, working in local wall-clock time.
4. Tie rule: a target that ends exactly at 16:00 is due at 16:00 that day, not 08:00 the next business day.
5. Convert the due instant to UTC.

The service needs the IANA tz database at build time (the base image ships it).

`GET /tickets/{id}/sla` returns `{priority, ack_due_at, resolve_due_at, ack_breached, resolve_breached, paused}`
evaluated at the request's `now`:

- `ack_breached`: not acknowledged and `now > ack_due_at`, or acknowledged and `acknowledged_at > ack_due_at`.
- `resolve_breached`: not resolved and `now > resolve_due_at`, or resolved and `resolved_at > resolve_due_at`. A reopened
  ticket counts as not resolved.
- `paused`: ticket neither resolved nor closed, its resolution target on the business-hours clock (so never for P1),
  and `now` outside a business window.
- Equality with the due instant is never a breach.

Test vectors the implementation must reproduce (UTC, from API.md 4):

| id | prio | created_at | ack due | resolve due |
|---|---|---|---|---|
| T1 | P1 | 2026-10-14T10:00:00Z | 2026-10-14T10:15:00Z | 2026-10-14T14:00:00Z |
| T2 | P3 | 2026-10-16T13:30:00Z | 2026-10-19T09:30:00Z | 2026-10-21T13:30:00Z |
| T3 | P1 | 2026-10-16T15:00:00Z | 2026-10-16T15:15:00Z | 2026-10-16T19:00:00Z |
| T4 | P2 | 2026-10-17T10:00:00Z | 2026-10-19T07:00:00Z | 2026-10-19T14:00:00Z |
| T5 | P4 | 2027-01-14T14:30:00Z | 2027-01-15T14:30:00Z | 2027-01-27T14:30:00Z |
| T6 | P1 | 2027-01-15T15:50:00Z | 2027-01-15T16:05:00Z | 2027-01-15T19:50:00Z |
| T7 | P2 | 2026-10-14T10:00:00Z | 2026-10-14T11:00:00Z | 2026-10-15T10:00:00Z |
| T8 | P3 | 2026-10-23T13:00:00Z | 2026-10-26T10:00:00Z | 2026-10-28T14:00:00Z |

## 7. Test clock (R-21)

If `SVCDESK_TEST_CLOCK` is `1` or `true`, a request may carry `X-Test-Clock`, an RFC 3339 instant with an offset. It
is `now` for that request only: it is never compared with another request's clock, never has to be monotonic, and never
causes a refusal because it is earlier than a stored timestamp. A header that does not parse (including a naive
timestamp or "yesterday") is 400 or 422. When the variable is unset or `0` the header is ignored. Without the header
`now` is real UTC.

## 8. Deployment (R-22, R-23, R-24, R-25)

`docker-compose.yml` defines a service `svcdesk` with `build:`, port 8080, `SVCDESK_TEST_CLOCK: "1"`, and a named
volume for the SQLite file. There are no bind mounts on any service, and no network access is needed after the image is
built. `docker compose up --wait` must leave `/health` answering 200 within 120 s. Tickets survive a container restart.
Unknown paths and unknown ticket ids answer 404 with a JSON body carrying an `error` object.

## 9. Acceptance

The published Tier A checker (`./itsmlab.sh verify 1`) passes every Core spec. The values in `DECISIONS.md` are
C1 = wallclock, C2 = immutable, C3 = vip, and the running service exhibits exactly those.
