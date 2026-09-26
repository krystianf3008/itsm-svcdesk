---
actual_minutes: 2.4667
predicted_minutes: 6
ratio: 0.41
---
<!-- ai-generated: 60% - Claude Code drafted the text from the recorded timestamps; the measurement is as stated below -->

# METR replication (n = 1)

**Feature.** An own test suite for svcdesk behind the compose `tests` profile (`src/tests/`), at least 10 tests, ending
with the `ITSMLAB-TESTS` summary line. **Prediction.** 6 minutes, receipted in `PREDICTION.md` before any file under
`src/tests/` existed. **Actual.** 148 seconds, that is 2.4667 minutes. **Ratio actual / predicted: 0.41**, so the work took
a little over two fifths of the predicted time. The direction (faster than predicted) does not matter for this stretch.

**How it was measured.** The start is the moment the course bot posted the prediction receipt, 14:06:44 local time
(2026-09-26T12:06:44Z), which I noted myself. The assistant began writing about 74 seconds later, when I told it to start.
The end is the moment `docker compose --profile tests run --rm --build tests` finished with exit code 0 and
`ITSMLAB-TESTS: passed=26 failed=0` (2026-09-26T12:09:12Z on the assistant's clock). The interval includes that short wait,
writing 26 tests and the compose service, building the image and running the suite.

**What the figure leaves out, and why the estimate was wrong.** The 148 seconds do not include the time I spend reading
and judging the tests, which I still have to do before I can call them mine. I expected an assistant to help but I priced
in a slow Docker build and some failing runs. Neither happened: the tests were written in one pass against behaviour that
the earlier checker runs had already confirmed, they need only the standard library, and the image layers were cached.
This is one measurement on one task, so it says little about how AI assistance changes my speed in general.
