---
svcdesk_decisions:
  C1: wallclock      # wallclock | business
  C2: immutable      # reopen | immutable
  C3: vip            # matrix | vip
---
<!-- ai-generated: 80% - Claude Code drafted the text and proposed the three resolutions; I reviewed and accepted them -->

# Decisions

## C1 - SLA clock for P1

**Decision:** The P1 acknowledgement target (15 minutes) and resolution target (4 hours) run on the wall clock, around
the clock and at weekends. P2, P3 and P4 keep the business-hours clock (Monday to Friday, 08:00 to 16:00, Europe/Warsaw).

**Rejected alternative:** Putting P1 on the business-hours clock as well, which is what R-13 says when it applies to
every SLA target. A P1 raised on Friday at 17:00 would then not be due until Monday morning.

**Reason:** R-14 states the intent of the P1 rule and gives the exact case: a P1 raised on Friday evening is late 15
minutes later, not on Monday. R-13 is a general rule whose purpose is not to blame the desk for hours when nobody is
staffed. I rejected only the word "any" in R-13, so R-13 still governs P2 to P4 and R-14 holds in full. A P1 on the
business clock would show an organisation-wide outage as "not breached" all weekend and hide the worst incidents from
the Monday report.

**Service owner:** The Service Desk product owner, together with the head of IT operations. The product owner owns the
SLA commitments in REQUIREMENTS.md, and the operations head has to staff the out-of-hours cover that a wall-clock P1
implies.

**Customer outcome:** A reporter of an organisation-wide outage sees the breach flagged 15 minutes or 4 hours after
creation, even on Friday evening, so it can be escalated. The cost is that the desk will report P1 breaches at weekends
unless someone is on call.

## C2 - Closed tickets and reopening

**Decision:** A reporter can reopen a ticket only from the state `resolved`, within 7 days of `resolved_at`. A closed
ticket answers 409 to a reopen at any age, and follow-up work goes into a new ticket whose `related_to` names the closed
one.

**Rejected alternative:** Also allowing reopen from `closed` within 7 days, which is the words "or closed" in R-10.

**Reason:** R-09 makes a closed ticket immutable, and closing is the moment the reporter has confirmed the fix (R-07)
and the figures are final. Reopening a closed ticket would rewrite `closed_at` and, since R-11 keeps the original
resolution target, turn an already reported ticket into a breach after the fact. The `resolved` state already gives the
reporter a 7-day window to say the fix failed, and `related_to` (R-03) exists for the later case. I rejected only "or
closed" in R-10, so reopen from `resolved` and the 7-day window are kept as written.

**Service owner:** The Service Desk product owner, because the reliability of the closed-ticket figures in the Monday
report is the thing this decision protects and the product owner is the one who is held to those figures.

**Customer outcome:** A reporter whose fix fails after closure files a new ticket and gets a new SLA clock, which is a
small extra step. The organisation gets closed tickets that never change and an auditable link between the two tickets.

## C3 - VIP reporters and the priority matrix

**Decision:** Priority comes from the matrix, and a ticket whose reporter has `vip` set is then raised to P2 if the
matrix gave P3 or P4. P1 and P2 are unchanged, and a `priority` sent by the client is still ignored.

**Rejected alternative:** Pure matrix priority with the VIP flag only stored, which is R-05 read as "and from nothing
else" (impact 3, urgency 3, VIP would be P4).

**Reason:** R-06 gives its purpose (executive issues must be visible to the desk immediately), and it collides with only
one clause of R-05. I rejected that clause for the VIP flag alone, so R-05 still forbids a client or an agent from
choosing a priority. The lift is a floor, not an assignment: the matrix still decides P1 and P2, so a VIP P1 stays P1.
The accepted risk is that `reporter.vip` is supplied in the request, so anyone who can create a ticket can claim it; the
value should come from a directory once there is one.

**Service owner:** The Service Desk product owner, because queue policy for the desk is theirs to set. Which people
count as VIP is owned by the executive office and should not be decided by the desk.

**Customer outcome:** Executives get a first response within an hour even for a minor problem. Other reporters with a
real P3 or P4 wait behind more P2 tickets, and the flag can be abused until it is sourced from a directory.
