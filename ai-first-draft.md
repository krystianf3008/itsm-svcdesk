---
lab3_first_draft:
  source: ai
  tool: "Claude Code (Claude Sonnet 5, Anthropic), 10 October 2026"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
  verdict: TODO                 # filled after ./itsmlab.sh load 3
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
---
<!-- ai-generated: 70% - Claude Code answered the prompt below and drafted the verdict sections; the measurement and the arithmetic are mine -->

# The assistant's first draft, and two verdicts

## Prompt

I'm instrumenting a FastAPI endpoint, `GET /kb/search`, that makes one HTTP call to an upstream dependency and
returns its result. I want to record request duration with a Prometheus histogram, in seconds, and I'll use it for
an SLO with availability and latency SLIs. I have not measured the endpoint's latency yet. What bucket boundaries
would you suggest for the histogram, and what would a reasonable multiwindow, multi-burn-rate Prometheus alerting
rule look like for this SLO?

## Answer

For a histogram where you don't yet know the latency distribution, a standard logarithmic ladder is a safe
starting point - it spreads resolution across orders of magnitude so you're not blind at any particular scale:

```
[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
```

(seconds; this happens to match the client library's own default bucket boundaries in several languages). Once you
have real traffic, check where your p99 falls and narrow the ladder around it if one bucket is too coarse.

For the alerting rule, the SRE Workbook's multiwindow, multi-burn-rate pattern uses two alerts on the same SLI, a
fast one with a short window and high burn rate and a slow one with a long window and low burn rate, for example
(availability SLI, objective 0.999, illustrative numbers):

```yaml
- alert: FastBurn
  expr: |
    sum(rate(errors_total[1h])) / sum(rate(requests_total[1h])) > 14.4 * (1 - 0.999)
    and
    sum(rate(errors_total[5m])) / sum(rate(requests_total[5m])) > 14.4 * (1 - 0.999)
  for: 2m
  labels: {severity: page}
- alert: SlowBurn
  expr: |
    sum(rate(errors_total[6h])) / sum(rate(requests_total[6h])) > 6 * (1 - 0.999)
    and
    sum(rate(errors_total[30m])) / sum(rate(requests_total[30m])) > 6 * (1 - 0.999)
  for: 15m
  labels: {severity: ticket}
```

Adjust the burn rates and windows to the objective you actually choose, and replace `errors_total` /
`requests_total` with your own good/bad counters.

## Verdict on the draft ladder

Filled in after `./itsmlab.sh load 3` has printed this service's own p99 (q). TODO.

## The draft alert rule

The shape (multiwindow: a long window paired with a short window, both must exceed the burn-rate threshold; two
alerts on the same SLI at different burn rates) is exactly MONITORING-SPEC.md's M-16/M-19 pattern, and
`prometheus/alerts.yml` follows it. What is specific to this draft and not reusable as written: the burn rates
(14.4 / 6) and objective (0.999) are illustrative numbers for a generic availability SLI, not derived from this
service's measured error rate or from the objective chosen in `slo.md`; the metric names (`errors_total`,
`requests_total`) do not exist here - the real rule selects `http_server_request_duration_seconds_count` filtered
by `http_route="/kb/search"` and status code, as MONITORING-SPEC.md section 6.1 requires. The windows (1h/5m,
6h/30m) and the `for` durations are kept as a reasonable starting shape.

## Verdict on the instructor's flawed ladder

Filled in after the measurement, from the same p99 as the draft's verdict (to 1 %, M-27). TODO.
