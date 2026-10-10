---
lab3_first_draft:
  source: ai
  tool: "Claude Code (Claude Sonnet 5, Anthropic), 10 October 2026"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
  verdict: refuted
  evidence: {p99_seconds: 0.1119, bucket: [0.1, 0.25], relative_width: 1.340}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.1119, bucket: [0.04, 0.5], relative_width: 4.111}
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

Measured with `./itsmlab.sh load 3` (login `krystianf3008`, 10 October 2026): q (the checker's p99 over the
60-second open-loop run) is **111.9 ms**. This service's kb-index profile is bimodal: about 96 % of requests
answer under 46 ms, then a narrow slow mode from roughly 96 to 134 ms holds the rest, and q falls inside it.

The draft ladder's finite boundaries bracketing q are 0.1 and 0.25, so q lands in the bucket **(0.1, 0.25]**,
0.15 s wide - **134.0 %** of q, nearly seven times the 20 % M-11 allows. `histogram_quantile` could report
anywhere from 100 ms to 250 ms for this service's p99 from that one bucket, which is most of the slow mode's
entire range swallowed by a single guess. **Verdict: refuted.** The lecture's prediction holds for this
distribution too: a ladder chosen without a measurement default to a scale no finer than roughly the number
itself, and this service's whole slow mode is narrower than that scale.

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

The same p99, 111.9 ms. `buckets-flawed.example.yml`'s finite boundaries bracketing it are 0.04 and 0.5, so q
lands in **(0.04, 0.5]**, 0.46 s wide - **411.1 %** of q. Twelve of its fourteen boundaries are spent below
40 ms, resolving a median this service does not even have trouble with, and then it jumps straight to 500 ms,
spanning the entire slow mode and most of the fast path in one bucket. **Verdict: refuted** - by a wider margin
than the draft ladder, because none of its resolution was spent anywhere near where this service's p99 actually
lives.
