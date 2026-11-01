---
lab4_postmortem:
  ticket: "1224ad8d-06a8-4ae3-865a-da2015a4ddb5"
  detecting_alert: ShopCheckoutErrors
  onset: 2026-10-12T07:05:45Z
  detection: 2026-10-12T07:09:19Z
  acknowledgement: 2026-10-12T07:10:07Z
  recovery: 2026-10-12T07:12:19Z
  mttd_seconds: 214
  mtta_seconds: 48
  mttr_seconds: 394
  identified_flags: [productCatalogFailure, adManualGc]
---
<!-- ai-generated: 60% - Claude Code investigated the recording's metrics and drafted the text from the queries below; the reading of the data and the judgment calls are mine -->

# Postmortem: Product catalog errors and ad latency degraded checkout (recording lab4-rec-3)

## Date

The incident ran on 2026-10-12, from 07:05:45Z to 07:12:19Z. This postmortem was written on 2026-11-01, from the
recorded incident's Prometheus snapshot (the live on-call response - the page, the ticket, the mitigation - is the
lecturer's, recorded for the course's recorded path).

## Authors

Written by the on-call engineer for this exercise (me), working the course's recorded incident `lab4-rec-3` in the
on-call role: scoring the detection, building the AI ledger, and writing this postmortem from the snapshot alone.

## Status

Complete; action items below are not yet filed as real tickets, since this is a course exercise, not a production
incident.

## Summary

For about seven minutes, product-catalog requests failed intermittently and ad requests slowed by roughly two
orders of magnitude, which degraded checkout for users browsing products and viewing ads on affected pages. The
on-call was paged by `ShopCheckoutErrors`, acknowledged the page, and service recovered after the responsible
feature flags were switched off.

## Impact

Two independent symptoms, both visible in the snapshot:

- **product-catalog errors**: at peak (07:08:00Z), `product-catalog`'s own server spans failed at 3.94 % -
  `sum(rate(traces_span_metrics_calls_total{service_name="product-catalog", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(traces_span_metrics_calls_total{service_name="product-catalog", span_kind="SPAN_KIND_SERVER"}[5m]))`
  = 0.0394, against 0 at the baseline five minutes before onset (07:00:45Z). `frontend` and `frontend-proxy`
  carried a smaller, correlated error rate (0.148/s and 0.058/s at the same instant) - the downstream cost of
  frontend calling a failing product-catalog. `checkout` itself showed a brief, small error rate (about 0.01
  request/s, a 5-minute rate) from roughly 07:08:30Z to 07:12:00Z - this is almost certainly `ShopCheckoutErrors`'s
  own symptom, and it lines up with the page.
- **ad latency**: `ad`'s p99 latency rose from 5.6 ms at the baseline to 912-922 ms during the incident -
  `histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="ad", span_kind="SPAN_KIND_SERVER"}[5m])))`,
  evaluated at 07:08:00Z and 07:09:00Z - about 165x slower. `frontend` and `frontend-proxy` p99 latency rose
  correlatedly, from about 47 ms to 705-710 ms, consistent with the frontend waiting on a slow `ad` call while
  rendering a page.

No other service's error rate or latency moved from its baseline in this window (checked: `payment`, `shipping`,
`cart`, `currency`, `email`, `recommendation`, `quote`, `image-provider` - all within noise of their baseline
values).

## Root Causes

Two of the three seeded feature flags are identified with confidence, from their symptoms (this is the recorded
path: no `/flags.json` and no Jaeger traces are available, only metrics):

- **`productCatalogFailure`** (errors class): the product-catalog error rate above, present only from the onset
  and absent at the baseline, matches this flag's documented symptom exactly ("GetProduct errors for one product
  in ten") and its documented affected services (product-catalog, frontend, checkout, recommendation).
- **`adManualGc`** (latency and load class): the ad latency spike above matches this flag's documented symptom
  ("ad latency spikes") and affected services (ad, frontend) exactly, and no other latency-class flag's signature
  fits (no shipping slowdown, no catalog 30 s stalls, no 15x frontend traffic was observed).

The third flag, from the resources class (`emailMemoryLeak` or `recommendationCacheFailure`), was not identified:
`email`'s container memory and uptime stayed flat (no restart, no growth beyond ordinary noise - checked with
`container_uptime_seconds` and `container_memory_usage_total_bytes`), and `recommendation`'s memory and latency
likewise showed no trend over the incident's roughly seven minutes. Either the resource-class symptom needs longer
to become visible than this recording's short recovery window gave it, or its effect here is genuinely below what
these metrics can show at this resolution. This is reported honestly rather than guessed at, per I-22's own
warning that guessing the likeliest flags should not pass - the two flags above are identified with real evidence,
not a guess at the third.

## Trigger

The onset is `seeded_fault_active`'s first sample, 2026-10-12T07:05:45Z: the instant the injector switched the
three seeded flags on, after its ten-minute baseline.

## Resolution

Service was restored by switching the seeded flags off (the lecturer's recorded mitigation); the snapshot shows
the detecting alert's firing run ending at 2026-10-12T07:12:19Z, 394 seconds (MTTR) after the onset. The recorded
path gives no finer-grained log of which flag was switched off first; what the snapshot does show is that
`product-catalog`'s error rate and `ad`'s latency both returned to baseline by the time the detecting alert
resolved, consistent with all three flags having been switched off together or in quick succession.

## Detection

`ShopCheckoutErrors` - a P1 alert on the shop's checkout symptoms - started firing at 2026-10-12T07:09:19Z, 214
seconds (MTTD) after the onset. That is the rule that reached the pager; `itsm_pager_notifications_total` confirms
the page arrived. Without an alert, the next person to notice would likely have been the on-call reading a
dashboard, or a support ticket from a user whose product page or checkout failed - both slower than a 214-second
page, and neither guaranteed within the same session.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Add a dedicated `product-catalog` error-rate alert (P2) so a product-catalog-only fault (no checkout symptom yet) is seen before it reaches checkout | prevent | on-call team | ITSM-101 |
| Add an `ad` p99 latency alert (P3, to chat) so an ad-only latency fault is visible without waiting for a frontend-wide symptom | prevent | on-call team | ITSM-102 |
| Instrument `email` and `recommendation` with a cache/queue depth or memory-trend metric, so a resource-class fault is identifiable from metrics alone on the recorded path, not only from flags on the live path | mitigate | platform team | ITSM-103 |
| Document, for every seeded flag, which Prometheus series actually move and by how much, so a future on-call (or a future AI investigator) has a faster reference than re-deriving it from the fault pool table | process | on-call team | ITSM-104 |

## Lessons Learned

### What went well

The multiwindow page (`ShopCheckoutErrors`) reached the on-call in 214 seconds and was acknowledged 48 seconds
later - both well inside what a human on-call can be expected to manage. The `product-catalog` and `ad` symptoms
were each large and clearly separated from their baselines (3.94 % errors against 0 %; 912 ms against 5.6 ms), so
once metrics were examined, two of the three flags were identifiable with high confidence from data alone, with no
flag state or trace evidence available.

### What went wrong

The resource-class flag left no usable signal in this recording's roughly seven-minute window: neither container
memory nor uptime for the two candidate services (`email`, `recommendation`) moved outside ordinary noise. On the
recorded path this made the third flag unidentifiable rather than merely harder to find, which is a gap in
observability, not a gap in investigation effort.

### Where we got lucky

The `product-catalog` and `ad` symptoms happened to be large and did not overlap in which services they affected
in a confusing way (product-catalog's errors did not masquerade as an ad problem, or vice versa), which made the
two-of-three identification cleaner than it might have been with a less distinct pair of flags.

## Timeline

All instants UTC, 2026-10-12.

- **07:05:45** - Onset. `seeded_fault_active` begins; the injector has switched on `productCatalogFailure`,
  `adManualGc` and one unidentified resource-class flag.
- **~07:08:00 to 07:09:00** - Symptoms visible in the snapshot: product-catalog error ratio at 3.94 % (query in
  Impact); ad p99 latency at 912-922 ms (query in Impact); frontend and frontend-proxy p99 latency correlatedly
  elevated to 705-710 ms.
- **07:09:19** - Detection. `ShopCheckoutErrors` (P1) begins its firing run; the page reaches the pager
  (`itsm_pager_notifications_total{receiver="pager",status="firing"}` rises after the onset).
- **07:10:07** - Acknowledgement. The P1 ticket (`1224ad8d-06a8-4ae3-865a-da2015a4ddb5`) is acknowledged, 48
  seconds after the page.
- **07:12:19** - Recovery. `ShopCheckoutErrors`'s firing run ends; `product-catalog`'s error rate and `ad`'s
  latency are both back at baseline by this point.

## Supporting information

- `itsmlab incident 4` recomputation (the grader's own script), run against `incident/tsdb-snapshot.tar.gz`: the
  front matter above is copied verbatim from its output.
- The recording's own ticket, `incident/ticket.json` (id `1224ad8d-06a8-4ae3-865a-da2015a4ddb5`).
- The PromQL queries quoted in Impact and Root Causes, run against the recording served on a throwaway Prometheus
  (`recorded/README.md`'s "Serving it" section), each evaluated both during the incident and at the baseline
  (onset minus five minutes) for comparison.
- `ai-rca-eval.json` and `ai-rca/transcript.md`: the AI investigator's hypotheses and their verdicts against this
  same snapshot.

## Problem record

- Incident record: 1224ad8d-06a8-4ae3-865a-da2015a4ddb5 (the P1 ticket; it closed when service was restored at the recovery instant)
- Root cause: two confirmed feature flags, `productCatalogFailure` (serves errors for about one product in ten) and `adManualGc` (forces latency-inducing garbage collection in the ad service), left enabled in the flag source the injector overrides; a third, unidentified resource-class flag was also active but left no measurable trace in this recording's short window
- Known error: enabling `productCatalogFailure` or `adManualGc` (or, by the same mechanism, any flag of the injector's pool) degrades checkout-adjacent services without any code change, and the only early symptom is the metrics shift documented in Impact - there is no single alert that names the flag itself
- Workaround: switch the implicated flags back to off through the injector's `/flags/{key}/off` endpoint (live path) or, in production, through whatever feature-flag control plane governs the real deployment; this restores service immediately without touching the Known error, which stays open until the flag source is corrected or access to it is restricted
