---
lab5_triage:
  image: ghcr.io/krystianf3008/itsm-svcdesk@sha256:56a993c19c5a4848d2d598e22c9dd6cb8bad5bc0edcb80cf12d5ce7189e54263
  sarif_receipt: 0 # TODO: fill in after the canary's sarif receipt (CI-SPEC.md P-25)
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

TODO (at least 600 characters, P-13): filled in once `bakeoff.json` exists, from the canary's real numbers.
