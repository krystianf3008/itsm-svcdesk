---
lab5_triage:
  image: ghcr.io/krystianf3008/itsm-svcdesk@sha256:56a993c19c5a4848d2d598e22c9dd6cb8bad5bc0edcb80cf12d5ce7189e54263
  sarif_receipt: 426
---
<!-- ai-generated: 60% - Claude Code ran the scanners locally, found the real CVE/rule ids and drafted the rows; I reviewed them -->
# Triage

What the gates and the reporting scanners found on my service, and what I did about each (CI-SPEC.md P-11, P-12).
Every row below is a fix made before the first push to `main`, confirmed locally with the same scanner images and
flags the pipeline uses (`docker run aquasec/trivy:0.74.0 image ...`, `semgrep/semgrep:1.178.0 scan --config
p/default .`); none of them appears in the pipeline's SARIF any more, which is the point of fixing rather than
ignoring.

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2026-76844, CVE-2026-85091 (zlib1g) | fix | the unpinned `python:3.13-slim` base carried a zlib build from before these fixes shipped; pinning the base image to a current digest (`sha256:e48f59cd...`) in the Dockerfile pulled a patched zlib1g and removed both |
| trivy | CVE-2026-114613, GHSA-6v7p-g79w-8964 (msgpack, vendored in pip) | fix | pip vendors its own old copy of msgpack under `pip/_vendor`, which Trivy reads from pip's own bill of materials; svcdesk never calls `pip` at run time, so the Dockerfile ends the install layer with `pip uninstall -y pip`, which removes the vendored copy along with the finding |
| trivy | CVE-2025-47273 (setuptools / pkg_resources, vendored in pip) | fix | same mechanism as the msgpack row above: pip's vendored `pkg_resources` carried the vulnerable setuptools code; removing pip after install removes it |
| trivy | CVE-2026-97687, CVE-2026-97689 (urllib3, vendored in pip) | fix | same mechanism again: pip vendors its own urllib3; `pip uninstall -y pip` removes it along with the other three rows above, which is why one Dockerfile change closed four separate CVE ids |
| semgrep | dockerfile.security.missing-user.missing-user | fix | the image ran as root (no `USER` set); added a dedicated, unprivileged `svcdesk` user (uid 10001), with `/app` and `/data` chowned to it, and a `USER svcdesk` line before `CMD` |

No `.trivyignore` entries exist (every fixable finding was fixed, not ignored), so there is nothing P-12's first
half needs a row for, and after the fixes above `deps`, `secrets`, `code` and `image` all report zero findings on
my own code, which is what P-12's second half - a row for every finding outside `lab5-canary/` in the receipted
SARIF - needs: an empty requirement, confirmed empty.

## Bake-off

The canary set holds 10 defects: 5 in code (`app/`, one per class - path-traversal, insecure-transport,
weak-crypto, deserialization, injection), 3 hard-coded credentials and 2 vulnerable dependency pins. Every
detector's recall is bounded by what its class scope can even see, and that ceiling is the first thing the
matrix shows: Grype and OSV-Scanner only read dependency files, so their recall ceiling is 2/10 = 0.2 - both hit
it exactly, with zero false positives (`tp=2, fp=0, fn=8, precision=1.0, recall=0.2`). Gitleaks only finds
secrets, ceiling 3/10 = 0.3, and it also hit its ceiling exactly, at the cost of one false positive
(`tp=3, fp=1, recall=0.3, precision=0.75`) - something in the tree looked enough like a credential to flag
without being one of the three labelled ones. Trivy runs both a dependency and a secret scanner in the `deps`
job, so its scope spans both classes (2 + 3 = 5 possible), and it reached `tp=4, fp=1, recall=0.4, precision=0.8`
- one secret missed, one false positive, matching its combined ceiling closely. Semgrep is the only detector
that can see the five code-level classes at all, and it also landed on `tp=4, fp=1, recall=0.4, precision=0.8`:
the same score as Trivy by coincidence of scope, not because the two tools agree on anything - they found
different defects entirely.

If I had to gate on one number, Trivy and Semgrep tie for the best F1 here (0.5333 each), but for different
reasons a gate should care about separately: Trivy's false positive is cheap to triage (one extra dependency or
secret line), while Semgrep's sits inside application logic and needs more reading to dismiss. Grype and
OSV-Scanner's perfect precision makes them the safest to leave blocking - a report from either is never noise on
this set - while their low recall means neither should be trusted alone to say a dependency is clean. None of
the five found more than 40% of the seeded defects, and this is exactly where Lecture 5's caution matters: a
seeded, decoy-free-by-design set like this one flatters every detector relative to real code, where defects are
rarer, messier and surrounded by far more plausible-looking non-defects than this canary's five `app/` modules
provide. Read every recall above as a ceiling on this lab's own measurement, not as a claim about these tools in
general.
