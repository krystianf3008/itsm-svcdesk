<!-- ai-generated: 50% - Claude Code drafted the comparison from both ledgers; the reading of which investigator was more useful is mine -->
# Comparing the two investigators

**Investigator 1**: the course agent loop (`agent.py`) with `qwen3:4b-instruct`, scored from the recorded
transcript shipped with `lab4-rec-3` (`transcript-recorded.md`). **Investigator 2**: a fresh Claude Code 2.1.316
session (Claude Sonnet 5.5), run from an empty directory with only the course's read-only Prometheus MCP server
(`prom_mcp.py`) registered, asked the identical question with no access to this repository or its postmortem.

## Where they agreed

Both investigators independently landed on **product-catalog** as the failing service and **checkout** as the
place the failure surfaced for users, which is also the postmortem's own finding (`productCatalogFailure`).
Investigator 1's H1 and H2, and Investigator 2's H1 and H2, are the same underlying claim from two different
models: product-catalog's `GetProduct` server errors, and a small, flat count of checkout `PlaceOrder` errors
caused by them. All four of those entries scored `correct` against the same snapshot. Neither investigator
confused the direction of causality (both correctly treated product-catalog as upstream of checkout, not the
reverse).

## Where they parted

Investigator 1 (the small local model) also proposed `adManualGc` as the latency-class cause, reading `ad`'s p99
latency spike correctly (`traces_span_metrics_duration_milliseconds_bucket`) - though none of its four ledger
entries in `ai-rca-eval.json` are actually about latency; that finding came from the recorded transcript's own
free text and was carried into the postmortem by hand, not scored as a ledger hypothesis. Investigator 1's two
*wrong* hypotheses (H3, H4 in `ai-rca-eval.json`) were plausible-sounding guesses with no supporting data: a
payment-service cause, and a claim that the error count was "growing steadily" when it had in fact plateaued.
Both were cleanly falsified.

Investigator 2 never proposed a latency cause at all - it stayed entirely inside the errors class and did not
investigate `ad`, `frontend` latency, or anything resembling `adManualGc`. Instead, it found something
Investigator 1 never looked at: `flagd`'s own `EventStream` error count moved twice, once about two minutes before
the product-catalog errors (07:06Z) and again at 07:15Z (+3, not just +1) - both numbers confirmed exactly against
the snapshot. It correctly declined to turn that correlation into a causal claim ("That may mean a feature-flag
change or a flagd disruption. The metrics don't confirm it"), and it also named `productCatalogFailure` by its
real flag name as a guess, while explicitly saying it could not confirm that without flagd logs - a correct
epistemic stance, since no metric in this lab names a seeded flag (INCIDENT-SPEC.md section 2.3).

## Which one the data proved right

On the errors-class cause, the data proved **both** investigators right, independently, which is the more
informative result than either alone: two models with very different capability landed on the same component
from the same snapshot, with no cross-contamination (Investigator 2 was run from a directory containing none of
this repository's files). On breadth, Investigator 2 was more thorough - it found the flagd correlation that
Investigator 1 never looked for - and more disciplined about what it would and would not claim, scoring two
honest `unfalsifiable` entries instead of guessing. Investigator 1 found the latency-class symptom that
Investigator 2 missed entirely, though not as a scored hypothesis. Neither investigator identified the
resources-class flag; the postmortem reports that as unidentified from metrics alone, for the same reason this
comparison's data could not settle `ai-rca-eval-2.json`'s H3 and H4 - some things this incident's own telemetry
simply does not resolve on the recorded path, where no flag state or trace is available to either investigator.
