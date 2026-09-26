<!-- ai-generated: 85% - Claude Code compared the specification with the code and the checker output; I reviewed it -->
# Converge report - specification versus implementation

Compared: `specs/001-svcdesk/spec.md` against `src/svcdesk/` after a local `./itsmlab.sh verify 1` run in which
L1-CORE-1 to L1-CORE-4 passed (all 49 conformance checks) and the observed resolutions were C1=wallclock,
C2=immutable, C3=vip, the same values as `DECISIONS.md`.

## Converged

- **R-01, R-02, R-17, R-25**: JSON only, `/health` body, UTC `Z` instants, JSON 404 for unknown paths and ids
  (`main.py`: `handle_http_error`, `ApiError`, `fmt`).
- **R-03, R-18, R-20**: the ticket model and validation (`domain.validate_new_ticket`); ids are UUIDs; owned and unknown
  fields are dropped rather than rejected.
- **R-04, R-05, R-06 (C3)**: `domain.compute_priority` applies the matrix, then lifts a VIP P3 or P4 to P2.
- **R-07, R-08, R-09, R-10, R-11 (C2)**: the `ACTIONS` table and the reopen branch in `main.act`; reopen only from
  `resolved` inside 7 days, a closed ticket is always 409, and `sla` is never recomputed on reopen.
- **R-12, R-13, R-14 (C1), R-15, R-16**: `sla.due_instants` (wall clock for P1, business hours for P2 to P4, tie at
  16:00) and the breach and pause rules in `main.get_sla`.
- **R-19, R-21**: exact-match `state` and `priority` filters; `X-Test-Clock` is per request and an unparsable value is 400.
- **R-22, R-24**: the compose file builds `svcdesk`, uses a named volume, no bind mounts, and a healthcheck.

## Diverges or is unverified

- **R-23 (persistence)**: implemented with SQLite on the named volume, but nothing in Tier A restarts the container, so
  it has not been demonstrated by a test.
- **Test vectors T6 and T8**: the checker exercises T1 to T5 and T7. T6 and T8 were traced by hand against the
  algorithm, not executed.
- **R-06**: `reporter.vip` is trusted as sent by the client, so any caller can claim it; this is recorded as an accepted
  risk in `DECISIONS.md`.
- **R-03**: `related_to` is stored but not checked against existing tickets, which API.md allows in Lab 1.
- **R-20**: a title that is only whitespace is accepted; the specification only limits its length.
