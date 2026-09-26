---
feature: Own test suite for svcdesk behind the compose `tests` profile (at least 10 tests, ITSMLAB-TESTS summary line)
predicted_minutes: 6
predicted_at: 2026-09-26T12:01:18Z
feature_path: src/tests
---
<!-- ai-generated: 60% - Claude Code drafted the text; the estimate is mine -->

# Prediction

**What is measured.** The wall-clock time from the moment this prediction is receipted until the test suite exists
under `src/tests/`, the `tests` service is defined in `docker-compose.yml`, and one local run of
`docker compose --profile tests run --rm --build tests` exits 0 with a last line
`ITSMLAB-TESTS: passed=<n> failed=0` and n of at least 10.

**How it will be built.** With an AI assistant writing the tests and me reviewing and running them.

**My estimate.** 6 minutes (revised from 3 before the prediction was submitted, because building the image and
running the suite take part of that time). For comparison, without AI and with good knowledge of the libraries I would expect about
20 minutes including checking that the tests run.
