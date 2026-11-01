---
lab4_comms:
  awareness: 2026-10-12T07:11:00Z
  detection: 2026-10-12T07:09:19Z
  classification: 2026-10-12T07:20:00Z
  nis2:
    early_warning_due: 2026-10-13T07:11:00Z
    notification_due: 2026-10-15T07:11:00Z
    notification_sent: 2026-10-12T20:00:00Z
    final_report_due: 2026-11-12T20:00:00Z
  ksc:
    early_warning_due: 2026-10-13T07:09:19Z
    notification_due: 2026-10-15T07:09:19Z
    notification_sent: 2026-10-12T20:00:00Z
    final_report_due: 2026-11-12T20:00:00Z
  dora:
    initial_due: 2026-10-12T11:20:00Z
    initial_sent: 2026-10-12T10:00:00Z
    intermediate_due: 2026-10-15T10:00:00Z
    intermediate_sent: 2026-10-15T09:00:00Z
    final_due: 2026-11-15T09:00:00Z
  log:
    - {at: 2026-10-12T10:00:00Z, to: the financial supervisor, what: DORA initial notification}
    - {at: 2026-10-12T20:00:00Z, to: the CSIRT, what: NIS2 and KSC incident notification}
    - {at: 2026-10-15T09:00:00Z, to: the financial supervisor, what: DORA intermediate report}
---
<!-- ai-generated: 55% - Claude Code proposed which instant maps to which regulator and drafted the arithmetic; I reviewed the reasoning and the numbers -->

# Communications log: the regulators' clocks

Suppose the shop is an entity NIS2, the Polish KSC act and DORA all apply to, and that this incident (`lab4-rec-3`,
2026-10-12) was significant under the first two and major under the third.

## The three instants you defend

**Detection (KSC), 2026-10-12T07:09:19Z.** KSC's clock runs from "od momentu jego wykrycia" - the moment of
detection, not of human judgment. That is exactly `itsmlab incident 4`'s `detection` instant: the instant
`ShopCheckoutErrors` started its firing run. There is no judgment call here; the law names a machine-observable
event, and the postmortem already has it to the second.

**Awareness (NIS2), 2026-10-12T07:11:00Z.** NIS2's clock runs from becoming aware that the incident is
significant, which is a human judgment, not the alert's own instant - the postmortem's acknowledgement
(07:10:07Z) is when the on-call took the page, not yet when they knew enough to call it significant. Fifty-three
seconds later, with the ticket acknowledged and the `product-catalog` error rate confirmed ongoing (not a
single blip), the on-call has what NIS2 means by "aware": a real, continuing effect on checkout. That is later
than detection, as it should be - a machine detecting a symptom and a person judging its significance are not the
same event - and it is not later than it needs to be: nothing between acknowledgement and this instant changes
the judgment, it only confirms it.

**Classification as major (DORA), 2026-10-12T07:20:00Z.** DORA's major/non-major classification needs more than
"checkout is failing" - it needs an assessment of scope and duration against DORA's own criteria (clients
affected, service downtime, geographical spread, data losses, criticality of the affected services), which takes
longer to establish than the first two clocks. Recovery was at 07:12:19Z; the eight extra minutes to 07:20:00Z are
the time to confirm the incident is over, start sizing its impact (the `product-catalog` error count, about 38
failed `GetProduct` calls; the `ad` latency spike; the roughly 7-minute duration) and conclude it clears DORA's
major threshold - a slower, more deliberate judgment than NIS2's "is this worth telling someone about at all".

## The log

| when (UTC) | to | what | answers |
|---|---|---|---|
| 2026-10-12T10:00:00Z | the financial supervisor | DORA initial notification | `dora.initial_sent`, before the 11:20:00Z deadline (classification + 4 h, which binds here because the classification fell inside 24 h of awareness) |
| 2026-10-12T20:00:00Z | the CSIRT | NIS2 and KSC incident notification, covering both regimes in one submission | `nis2.notification_sent` and `ksc.notification_sent`, both comfortably inside their 72-hour windows (which start from different clocks - awareness for NIS2, detection for KSC - but land on the same calendar day here because awareness and detection are only 101 seconds apart) |
| 2026-10-15T09:00:00Z | the financial supervisor | DORA intermediate report | `dora.intermediate_sent`, one hour inside the 72-hour window from the initial notification |

Final reports (NIS2, KSC: one month after each notification_sent; DORA: one month after the intermediate report)
are not logged as separate entries here - they are due in mid-November, well after this exercise's incident
window, and nothing changes about who they go to.
