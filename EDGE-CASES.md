---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 80% - Claude Code drafted the text from the practice log and METRIC-SPEC.md; I reviewed it -->

# Edge cases in the practice event log

The counts above are the ones my service reports for `fixtures/events-practice.jsonl` over the published window.

## E1 - clock skew produces a negative lead time

- What the log contains: three commits are timestamped after the deployment that shipped them: sha-0040 is 834 s after DEP-0012, sha-0094 is 51 s after DEP-0024 and sha-0123 is 780 s after DEP-0031.
- What a default definition would have done: subtract and report the raw negative numbers, or drop the three pairs. Negative values pull the median down, and dropping them silently makes the metric look as if the log were clean.
- Why the rule is defensible: the deployment did happen and the change did ship, so the pair belongs in the sample. A lead time cannot be below zero, so it is clamped to zero, and `negative_lead_time_pairs` counts each clamp so the reader can see how much clock skew is in the data.

## E2 - a revert of a revert

- What the log contains: sha-0071 reverts sha-0070, which itself reverts sha-0069, so there are two commits with a non-null `reverts` and a chain of three commits.
- What a default definition would have done: count each commit as its own change, or give the reverts no change at all. Either way the changes delivered are inflated by the reverts, and the lead time of the original change is measured from the wrong commit.
- Why the rule is defensible: a revert is not new work, it is the same change coming back. Following `reverts` transitively to the original `change_id` makes the chain one change, and `revert_chains_collapsed` reports how many commits were folded in.

## E3 - a hotfix that never touched `main`

- What the log contains: four commits (sha-0019, sha-0077, sha-0108 and sha-0127) live on branches named `hotfix/...` and reached production through deployments without ever being on `main`.
- What a default definition would have done: keep only commits with `branch == "main"`. That removes exactly the urgent fixes from the lead time, which are the changes an on-call reader most wants to see, and the metric then looks faster than the delivery really is.
- Why the rule is defensible: what matters for delivery is whether a commit reached production, not which branch name it carried. Ignoring the branch treats every shipped commit the same, and `commits_never_on_main` still tells the reader how much shipping bypasses the mainline.

## E4 - a deployment with zero linked commits

- What the log contains: four production deployments carry no commits: DEP-0026 and DEP-0032 succeeded, and DEP-0043 and DEP-0044 failed.
- What a default definition would have done: drop them, which understates deployment frequency and change fail rate, or divide by zero when looking for their commits. Dropping the two failures hides real failed deployments.
- Why the rule is defensible: a deployment is an event in production whether or not it carries a change (a config push or a redeploy). It contributes no lead-time pair but it counts in frequency and in both rate denominators, so the instability figures stay honest.

## E5 - a deployment that failed and never recovered

- What the log contains: DEP-0015 failed on 2026-09-07 and its covering incident INC-0004 was opened but never resolved, so it is the only open failure among the eight failed deployments.
- What a default definition would have done: close it at the end of the window, which invents a recovery time, or drop it, which makes the recovery median better than it is and forgets a failure that is still unrepaired.
- Why the rule is defensible: an unknown recovery time should stay unknown. The open failure is left out of the median, reported in `open_failures`, and still counted in the change fail rate, so the reader sees it instead of a made-up number.

## E6 - overlapping incidents

- What the log contains: eleven pairs of incidents have intersecting intervals; for example on 2026-09-07 DEP-0015, DEP-0043, DEP-0044 and DEP-0016 failed within a few hours and INC-0004, INC-0010, INC-0011 and INC-0005 were open at the same time, and INC-0004 is still open at the end of the window.
- What a default definition would have done: merge overlapping incidents into one outage, or add up their durations. Merging makes several failures look like one, and summing counts the same hours of downtime twice.
- Why the rule is defensible: each failed deployment has its own recovery time, measured from its own start to the resolution of its covering incident, so overlap changes nothing in the median. `overlapping_incident_pairs` counts the overlap so that a busy incident period is visible without distorting the metric.

## Gaming demonstration

I improved `deployment_frequency_per_day` by exploiting R-11, which counts every production deployment of any outcome and asks nothing of what it carries (R-10 confirms that a deployment with no commits still counts). The transformed log `gaming/after.jsonl` adds twenty empty "heartbeat" production deployments spread evenly across the window, and it moves every successful production deployment that was in the window three days later. Nothing is deleted, no commit is re-timed and no outcome is changed, so the record is not falsified.

The dashboard number rises from 2.000 to 2.714 deployments per day (+35.7 %), and the two instability metrics also look better because the empty deployments enlarge their denominators (change fail rate 0.190476 to 0.140351, rework rate 0.119048 to 0.087719). Delivery of the work that was already there got worse: measured on the base work alone, the true change lead time goes from 539452 s to 791959 s (146.8 % of the base), and the number of changes delivered in the window falls from 65 to 58 (89.2 %), because the delayed deployments at the end of the window fall out of it.

In a real team the incentive is a target such as "deploy at least three times a day" that is shown on a dashboard and tied to a review. The cheapest way to hit it is to add no-op deployments (a redeploy, a config touch, a version bump) while real releases are batched into a release train, which is exactly the delay used here. The person rewarded is whoever owns the dashboard, the delivery lead or platform team, who sees an "elite" frequency and a lower failure rate, while the customers of the changes that waited three days pay for it.
