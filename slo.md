---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 30d
  slis:
    availability:
      objective: 0.99
      good: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code!~"5.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 432}
    latency:
      objective: 0.95
      threshold_seconds: 0.09
      good: 'sum(rate(http_server_request_duration_seconds_bucket{job="svcdesk", http_route="/kb/search", le="0.09"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.05, minutes: 2160}
  alerts:
    - {alert: KbSearchAvailabilityFastBurn, sli: availability, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchAvailabilitySlowBurn, sli: availability, burn_rate: 6, long_window: 6h, short_window: 30m}
---
<!-- ai-generated: 55% - Claude Code proposed the structure and arithmetic from the measurement; I chose the objectives and threshold and reviewed the prose -->

# SLO for `GET /kb/search`

## Availability

The SLI is the share of `/kb/search` requests that do not answer with a 5xx status, over a 30-day window.
Objective **0.99** (error budget: 1 %, 432 minutes over 30 days). `kb-index` itself has a small baseline error
probability unrelated to anything `svcdesk` does - a single 60-second measurement at this login's profile saw
6 failures out of 2,400 requests (0.25 %). An objective of 0.99 leaves roughly four times that observed baseline
as budget, so routine upstream noise does not by itself page anyone, while an objective closer to 100 % would
make the budget a rounding error away from being spent by `kb-index`'s ordinary behaviour, which `svcdesk`
cannot fix by itself - only observe and surface. Anything that visibly erodes budget below that margin is a real
change in upstream health worth a human's attention.

## Latency

The SLI is the share of `/kb/search` requests that answer at or below **90 ms**, over 30 days. Objective **0.95**
(error budget: 5 %, 2,160 minutes). This service's own measurement (`./itsmlab.sh load 3`, login `krystianf3008`,
10 October 2026) found a bimodal distribution: p50 22.0 ms, p95 45.0 ms, p99 111.9 ms, with about 96 % of requests
answering under 46 ms and the rest falling into a narrow slow mode from roughly 96 to 134 ms. 90 ms sits in the
gap between those two modes - below every ordinary request and below the entire slow mode - so the threshold is
not a guess at a percentile, it is a line between "answered normally" and "fell into the slow mode". An objective
of 0.95 matches what this service already does on an unremarkable day (roughly 96 % of requests are fast), so the
budget exists to absorb a slightly worse day, not to be spent by nothing happening; it starts burning as soon as
the slow mode grows past its ordinary ~4 % share of traffic, which is exactly the condition worth alerting on.
(Lab 6 reads this window, these two objectives and this threshold as a canary gate's thresholds; 90 ms is well
inside the 1 s ceiling it requires.)

## Alerts

| alert | SLI | burn rate | long / short window | budget spent when it fires | severity: page or chat |
|---|---|---|---|---|---|
| KbSearchAvailabilityFastBurn | availability | 14.4 | 1h / 5m | 2 % of the 30-day budget per hour it burns | P1: page |
| KbSearchAvailabilitySlowBurn | availability | 6 | 6h / 30m | 2.5 % of the 30-day budget per 6 hours it burns | P2: chat |

`KbSearchAvailabilityFastBurn` pages (P1): at burn rate 14.4 the 30-day budget is gone in about 50 hours, so a
page at 2-3 a.m. costs the on-call person a disrupted night, but the alternative - finding out at the Monday
report that the knowledge-base search was down all weekend - costs every reporter who tried it in between a
failed search with no human told. `KbSearchAvailabilitySlowBurn` goes to chat (P2): at burn rate 6 the budget
lasts about five days, which is well inside a working day's notice; nobody should lose sleep over a problem that
slow, but it should be looked at before the budget actually runs out.

## Buckets

The ladder (`src/svcdesk/metrics.py`, 26 boundaries): 0.005 to 0.05 in nine steps across the fast path, 0.06 to
0.09 bridging the gap, 0.095 to 0.14 in eleven 5 ms steps around q, then 0.2, 0.5 and 1.0 for the rare slower
tail.

q = 111.9 ms falls in **(0.11, 0.115]**, 5 ms wide - **4.5 %** of q, well inside the 20 % M-11 allows. The band
resolved at that resolution runs from 0.095 to 0.14 s, which is q from **-15 % to +25 %**, past the ±10 % the
run-to-run variance calls for. The other 15 boundaries are spent making the fast path (where 96 % of traffic
lives, and where the latency SLI's 90 ms threshold sits) legible on the dashboard too, rather than on the tail
above 134 ms, which this login's profile essentially never reaches.
